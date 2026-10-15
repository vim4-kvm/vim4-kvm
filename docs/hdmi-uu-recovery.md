# UU 虚拟屏退出后 HDMI 桌面不恢复

2026-10-15，macOS 27.0.1（26A434）、UU 4.42.0、VIM4 RTK-CONTROL EDID。
本轮只读调查，未重发 EDID、修改显示配置、停止 UU 或重启采集。

## 已确认的故障位置

用户先重发 EDID 恢复，随后再次用真实 UU 客户端连接，确认复现。
复现后板端仍为 3840×2160、约 60Hz、YUV444 8bit，fmt_valid=1、sm_state=5，
frames_received 从 127858 推进到 134428，frames_delivered 从 126392 推进到 132962。
这排除了本轮现场的 HDMI 失锁、采集帧完全停滞；未检验像素内容是否正确。

Mac 的 CGGetOnlineDisplayList 仅返回 ID 44，vendor=0x756e6b6e（unkn）、
model=0x76697274（virt），1920×1080。原物理显示器 ID 2 的模式、身份查询
均不可用，不能把返回的 -1 当成普通布尔状态。桌面处于系统兜底显示器，
并未恢复到 RTK 物理输出。板端“有信号”不代表 Mac 正在向它呈现桌面。

## 同一轮日志顺序

以下为 Mac 日志原始时间，板子 UTC 时间相差 8 小时：

1. 15:13:47：此前 Screen Sharing 退出后，物理 display 2 有 setEnabled:1，
   UURemoteServer 报它 active；保留了同一环境下恢复成功的对照。
2. 15:14:28.478：WindowServer 创建“UU远程 1”，vendor=0x5544、product=0x5201、
   serial=0x750001，ID 43。UURemoteServer 的 VirtualDisplay RPC 日志确认调用方。
   此虚拟屏不是此前 UUDisplay 辅助程序使用的 0x5555 身份，UUDisplay 进程未运行。
3. 15:14:28.895：UURemoteServer 仍能看到物理 ID 2，但标记为 inactive。
4. 15:14:28.905：UURemoteServer 调用 CDVirtualDisplayDestroy，返回 SUCCESS。
   虚拟屏从创建到销毁约 0.43 秒；不能仅凭日志断言是用户退出还是内部错误清理。
5. 15:14:28.911：WindowServer 创建兜底 ID 44。
6. 15:14:28.916 起：UU 查询显示信息报 error requesting display info dictionary
   (0x3e9)。调查末尾在线列表仍只有 ID 44。

## UU ARM64 恢复代码的局限

分析对象为安装中的 UURemoteServer，提取的 ARM64 slice SHA256：
`283146ff9bbc6762021f45e950503e90e230d96962e6a0667413cb4497b5a23a`。
IDA 数据库中的命名和注释为本轮分析添加，没有改动正在运行的应用。

- `0x10006C0F0`，由日志字符串定位的 `restorePhysicalModes(_:)`：
  调用 `0x100044EEC` 获取当前在线显示器，排除管理中的虚拟屏，按 UUID 查找保存的
  物理屏模式，再调用模式设置函数。没有在此路径重新探测或启用离线物理屏。
- `0x100044EEC`：两次调用 CGGetOnlineDisplayList，分别获取数量和 ID 列表。
  因此本次 ID 2 已不在线的状态，不会被上述恢复循环处理。
- `0x1000031F4`：CGBeginDisplayConfiguration 后调用 CGSConfigureDisplayMode，
  忽略该调用的返回值，再调用 CGCompleteDisplayConfiguration；返回/报错只基于
  begin 和 complete。这可能遗漏单步设置错误，但本轮没有该函数的运行时返回值，
  不能认定它就是此次直接触发点。

静态代码证明的是一条恢复路径的盲区，不是证明 UU 完全没有其他恢复逻辑。
x86_64 清理路径还观察到 CGRestorePermanentDisplayConfiguration 调用，
不能写成“UU 根本不尝试恢复”。

## 为什么有物理屏还创建虚拟屏：发现异常历史配置

用户指出预期连接时直接使用现有物理屏。因此必须区分“UU 创建过虚拟屏”与
“UU 在物理屏正常时主动替换它”。前者有日志证明，后者未证明。此前物理屏
active 的记录在 15:13:47，不能当作 15:14:28 创建前一瞬的状态。

ARM64 `0x1000F283C` 的 AppData 路径调用
`restorePersistedVirtualDisplaysIfNeeded(deviceId:isAssistance:completion:)`。
经任务队列进入 `0x1000702F8`：检查会话 epoch、非空设备 ID 和非 assistance，
加载设备保存的虚拟屏列表。列表非空时继续恢复，并把 NSScreen 数量传给
`0x10006FE28`；后者有槽位和显示器总数限制，并不要求物理屏数量为零。
这证明“恢复历史虚拟屏”是有物理屏时也可能创建的独立路径。

用户不确定以前是否创建过虚拟屏。最初字符串扫描未找到记录，随后确认
每个控制端的设置保存在加密 MMKV 中；只读解析后，三个控制端配置中有一个
保存了如下 `virtualDisplays`，另外两个没有该字段：

```json
[{"slot":1,"name":"UU远程 1","width":1,"height":1,"refreshRate":60,"hiDPI":false}]
```

该记录创建时间为 2026-08-17 04:14:27 UTC，更新时间为同日 06:07:21 UTC。
所在配置文件被当前 UURemoteServer 打开，修改时间与本轮连接相符。
解析检查了密文 CRC、字段边界及读取前后文件未变化；仅输出显示相关字段，
没有把密钥或其他账户配置写入调查记录。诊断脚本及输出位于本地忽略目录
`logs/uu-display-recovery/read-display-settings.py` 和 `display-settings.jsonl`。

运行时日志进一步吻合：ID 43 最初使用 mode 56（1920×1080 逻辑尺寸），
15:14:28.905 UU 请求切到 mode 86，对应 1×1、60Hz，模式表标为 unsupported。
随后同一毫秒销毁虚拟屏。WindowServer 记录仍为 modeset 56，并报
`No valid display config commands detected`，因此不能说 1×1 模式成功生效。

异常历史配置是当前最强的触发候选，但尚未取得分支运行时调用跟踪或清除记录后
的对照结果，也未确定这条 1×1 记录最初如何生成。当前未清除 UU 配置、
未修改其程序或自动创建设置。

## 结论边界与下一步

目前定位在 UU 虚拟屏生命周期与 macOS 显示配置恢复的交互。
RTK EDID 不足以解决本轮问题；重发 EDID/热插拔可作为重新枚举的恢复手段，
但不是 EDID 内容错误的证据。

下一轮优先隔离已发现的异常历史记录：备份对应配置，仅移除其 slot 1 虚拟屏，
恢复物理 HDMI 后用同一控制端重连，记录是否还创建虚拟屏及物理输出能否保留。
优先使用 UU 自身的删除功能；若需离线修改 MMKV，须停止写入进程，并校验其他
字段未变，不能直接覆盖正在使用的映射文件或清空整个账户配置。
这次对照完成前，物理屏掉出在线列表的具体机制仍未确认。
不把周期性 HPD 当作根因修复。

本轮证据位于 `logs/uu-display-recovery/`：窗口服务器与 UU 显示事件、CG 探针、
板端状态、ARM64 反编译片段及 IDA 数据库。它们未包含正式修复或恢复验收。

## 用户授权后的配置对照准备

用户明确要求不备份、直接删除异常记录。停止 UU 用户代理与应用、确认
UURemoteServer 退出且目标 MMKV 数据/元数据文件无人打开后，仅把该控制端
`virtualDisplays` 中唯一的 1×1 条目移除，结果为空数组。保留字段编码长度，
验证其他记录逐字节未变，重新加密并同步 CRC、序列和已确认元数据。
未创建备份，未改 UU 应用二进制，未重发 EDID。

重新启动 UU 用户代理及应用后，只读检查确认 CRC/字段编码有效、
`virtualDisplays=[]`，83 条 `displayInfos` 保留。此处完成的是配置清理，
仍需恢复 HDMI 后用同一控制端重新连接，验证是否还创建虚拟屏及恢复是否正常。
