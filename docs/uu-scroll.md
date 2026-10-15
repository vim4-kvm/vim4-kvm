# UU 经 KVM 的滚轮速度对照

2026-10-15，用户报告同一个鼠标通过 UU 连接 KVM 时，滚动慢于 UU 直接连接
被控 Mac。板端 one-kvm.service 为 active，软件包 2.5.1+vim4.20261015.14；
只读配置确认 UU 身份为 macos、reverse_scroll=true。

## 已确认的单位差异

One-KVM `src/uu_remote/input.rs` 的 MouseScroll 分支统一累积 delta_y，
每 120 单位发送一份 wheel=±1 的 HID 报告。未满 120 的部分保留到后续事件，
连接释放时清零；因此不是每个小增量都直接丢弃，但有输出阈值。
此处没有按 UU 广播的目标系统区分单位。

官方 UU 4.42.0 UURemoteServer ARM64 的路径如下（静态反编译）：

- `0x100095764` 的 MouseScrollAction 分支调用 `0x100096874`。
- `0x100096874` 从 JSON 读取 delta_x/delta_y，`0x1006288EC` 通过
  integerValue 取整数，没有除以 120。
- `0x100095FBC` 将动作传给 `0x100182060`，两轴增量原样复制到事件。
- `0x1000F8AE8` 的 kind=2 分支调用 `0x1000FB8C8`。
- `0x1000FB8C8` 使用 CGEventCreateScrollWheelEvent2，单位为
  kCGScrollEventUnitPixel，垂直增量原样作为 wheel1，水平增量取反作为 wheel2。

分析二进制 SHA256：
`283146ff9bbc6762021f45e950503e90e230d96962e6a0667413cb4497b5a23a`。
上述路径没有显示“120 协议单位等于一个物理滚轮刻度”的依据。
但 USB HID 的一格仍会经过被控 Mac 的滚轮速度/加速处理，不能由此直接推导
固定的 120 倍补偿，也不能保证一个固定比例在所有应用、滚动节奏下完全等同。

## 接收端测量

`tools/uu-scroll-probe.swift` 只接收自身窗口的滚轮事件，不注入输入、
不安装全局事件监听器。记录普通/精确 delta、CG 行/点 delta、方向及滚动阶段。
15 分钟后自动退出，也可直接关闭窗口。

```sh
mkdir -p logs/uu-scroll
swiftc tools/uu-scroll-probe.swift -o logs/uu-scroll/probe
logs/uu-scroll/probe > logs/uu-scroll/events.jsonl
```

分别通过 UU 直连 Mac 和 UU 连接 KVM，在同一窗口选择对应按钮，
以同一鼠标向下滚动 10 格、每格约隔半秒。按钮会开始新一轮，
不能把事件数量直接当作物理滚轮格数；比较应同时考虑 delta 单位和事件节奏。
此测量并不直接记录 CONTROL 数据通道的原始报文。

网页对照可选择第三个按钮“KVM 网页”。每个连接方式分别做慢速和快速两轮，
每轮开始重新点击对应按钮；程序的 begin 记录用于划分轮次。窗口汇总统一使用
CG pointDeltaY，避免混合 NSEvent 的行与点单位。

## 本轮用户对照结果

用户完成两轮后确认“完成”。两轮各收到 10 个事件：

| 路径 | 精确滚动 | pointDeltaY | 总点增量 | 首末事件间隔 |
|---|---|---|---|---|
| UU 直连 Mac | true | 每次 -120 | -1200 | 2.474 秒 |
| UU 连接 KVM | false | -1, -6, -57, -43, -124, -64, -159, -1, -1, -1 | -457 | 2.885 秒 |

KVM 首轮前段连续快速滚动、后段明显放慢，直连轮节奏也未严格保持每格半秒。
因此总位移比约 2.63 仅是这两段操作的结果，不能用作通用速度系数。
KVM 后三个间隔较长的事件都只有 -1 point，直连所有事件稳定为 -120 points。
这确认两条路径的速度响应不同，并与普通 HID 经系统加速、官方 UU 注入精确
像素事件的静态分析相符。不能把非精确事件的 scrollingDeltaY（行）直接和
精确事件的 scrollingDeltaY（点）相加比较，本表使用 CG pointDeltaY。

原始证据位于 `logs/uu-scroll/events.jsonl`。测试窗口已关闭、临时 LaunchAgent
已卸载，未修改被控机滚轮速度、HID 描述符或板端软件。

修复方向是为 UU 的像素增量设计显式的 HID 转换和速度校准，保留小增量余数，
并限制快速输入时的输出突发。现有普通鼠标描述符不能直接承诺精确像素语义，
应单独验证慢速单格与快速连续滚动，而不能仅调整一个常数后声称与直连一致。
当前尚未修改输入换算或部署修复。

## 增加 One-KVM 网页对照

用户要求进一步比较绕过 UU、直接打开 One-KVM 网页的滚轮行为。
`web/src/views/ConsoleView.vue` 的 handleWheel 对每个 WheelEvent 只保留
deltaY 的正负，发送 scroll=±1；不保留幅度或 deltaMode。
`src/hid/datachannel.rs` 把该值直接交给同一个 HID 后端。
因此网页与 UU 的转换入口不同，但都落到普通 USB 鼠标滚轮报告。

Mac IORegistry 的 One-KVM USB Device 事件服务显示 HIDScrollResolution=589824、
HIDScrollAccelerationType=HIDMouseScrollAcceleration；其 HIDEventServiceProperties
中 HIDMouseScrollAcceleration=20480。此处仅记录只读属性，不据此判断描述符错误。
网页初步样本也为 precise=false，间隔较长时约 1 point、连续输入时明显增大。
首段包含 51 个事件和双向操作，不能当作严格的 10 格标定。

用户进一步澄清：网页没有 UU 那种突然变得很快的感觉。因此共同的系统加速
只能解释共有行为，不能解释 UU 独有的突增；不能据此将两条输入链路等同。
代码中 UU 将一条累计出 N 格的 CONTROL 事件拆成 N 份 wheel=±1 报告，而网页
每个事件只发一份报告。这是需要隔离的额外突发来源。

后续网页轮 29 个原生事件、总点增量 +1167；UU 轮 27 个原生事件、总点增量
-7374。两轮节奏、方向及事件数量不同，不用这个比值计算补偿系数。
USB 抓取第一轮只覆盖网页，捕获 31 份非零滚轮报告；超时发生在 UU 轮之前。
测试期间另有更新把板端版本从 .14 升到 .43 并重启服务，导致补抓的旧 PID
失效；再次附加新 PID 时用户滚动已结束，未取得足以验证 UU 突发的 USB 样本。

对 One-KVM 进程使用 strace（即使仅输出鼠标 fd 的 write）造成明显卡顿，
UU 发送约 23–34fps。用户报告卡顿后立即发送 SIGINT 解除跟踪，确认
TracerPid=0、服务保持 active；发送恢复约 60fps、mean_send_us 约 767–798，
sequence_gaps=0，用户确认恢复。测试窗口和临时 LaunchAgent 已关闭。
后续不能继续用 ptrace 跟踪实时视频进程来判断输入或视频性能。

离线候选修正仅消除人工拆包：保留累计值、方向和余数，将同一 CONTROL
事件换算得到的 N 格作为一个 wheel=N 报告发送（现有输入限幅保证 |N|≤100，
可由有符号 8 位 HID 字段承载）。这不等于已解决 Mac 像素与 HID 单位的标定，
也尚未经过实机手感对照。

候选验证：修改文件 rustfmt 检查通过；ARM64 Ubuntu 环境中 605 项 Rust 库测试、
release 构建和 15 项 VIM4 Python 助手测试通过。全仓 cargo fmt --check 还报告
既有的 update/web 等文件格式差异，未为本任务修改这些无关文件。
测试和构建日志在 `logs/uu-scroll/offline-tests-final.log`、`offline-build.log`。
测试仅验证总刻度、余数、方向、断线重置及有界输出等软件行为，不替代实机手感验收。

## 候选部署

用户授权后通过 `tools/board.py deploy --exclusive` 将 One-KVM 从
`2.5.1+vim4.20261015.43` 升至 `.44`，源码 `dac8693c`。
包使用现有 Ubuntu 打包配方，仅生成 One-KVM 组件；sources.json 分别记录
二进制构建镜像与完整打包镜像。其他组件版本保持不变。
部署校验和、APT 模拟与安装通过，One-KVM 和管理器 active，网页 HTTP 200；
部署后立即探测 8080 曾遇启动窗口拒绝连接，随后重查成功。
板端二进制 SHA256 与本地 release 一致，HDMI 服务 InvocationID 未变，
新进程识别输入为 3840×2160 NV21 60fps。尚未取得新进程的 UU 发送统计，
不能引用旧进程的 60fps 作为升级后视频验收；慢速、快速滚轮手感仍待用户确认。
部署日志：`logs/uu-scroll/deploy-44/`。本轮没有再次使用 ptrace。
