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
