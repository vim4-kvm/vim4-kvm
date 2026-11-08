# 2026-11-02：uhd7 固定高刷与原生 YUV444 窗口

4K60 网页回归、1080p120 AVC/HEVC 和 1440p120 HEVC 吞吐通过，1440p 生产 AVC 限 60 生效。
三份高刷码流和 4K60 原生 444 均未丢采集帧，图样帧号的不连续强推断由信号源呈现造成。
444 的分量、横纵单像素色度和帧内一致性通过。QHD HEVC 实际 SPS 低报 level。Gaming VRR 未测。已恢复已安装的 FullKvm/kbase uhd7。

## 身份与临时加载

主仓输入 `621531066c94`，内核 `13e4a364967c`，gst-plugin-venc `87c70529`，
One-KVM `1e477daf`，vfmcap `6fe6eac`。heavy 票 633 在登记的 VM 输出树只重编三个模块。
uhd7 配置、vermagic、模块依赖匹配，均保留 BTF。CONFIG_MODVERSIONS 关闭；按正式导出符号核验全部导入。

| 模块 | SHA-256 | 导入/未解析 |
|---|---|---|
| t7-hdmirx | `26ecd71ae1e448279b27b338e948a34d03c499e59530f797b355434e3e013a6a` | 57/0 |
| t7-vdin-test | `cec04ebaa243d539ab7b7af319185c8a921ea4bccf4c31c371dbd0b6c0bef8be` | 168/0 |
| wave5 | `6c487345288e8a9e3eb5ab64ee9d80e4a9ad643261bfcc27ab5c4ce0b8e40c8a` | 207/0 |

用户态二进制沿用上轮逐项验证的 SHA。板上比对实际模块 notes 与候选 ELF，从服务 cgroup 验证运行中 One-KVM，
核对 r14e 私有目录的插件，确认 `vim4ptsrate` 可发现。RTK-CONTROL 保存表、安装表与 RX 的 384 字节读回一致，
SHA-256 为 `ec7f330a18d36bed31f4de4ce104fa4e8844f1ef9d6dbdd89a2ab8f955792f92`。
只经 One-KVM MCP 控制 HDMI 信源 M6；首个 HID 前检查接收 Mac 的 USB 树，源端再确认芯片和单一 RTK 屏。
未向 M4 发 HID。采样使用 board-queue sampling，网页接收走本机 18081 至板上 8081 的 SSH 隧道，无音频测试。

## 固定模式

主测票 645。三档均为逐行 SDR、YCbCr444 8bit，Gaming VRR 控件为 0。
RX 的 G_PARM 分别为 4K **59.999**、1080p **119.998**、1440p **119.899 Hz**。
M6 回读原生 1080p/1440p 的 120 Hz 模式 ID 86/119；未单独验到 1080p119.88。

| 网页测量 | 编码 | 时长 | 新增解码帧 | fps |
|---|---|---:|---:|---:|
| 原 4K60 | H.264 | 10.004 s | 603 | 60.276 |
| 候选 4K60 | H.264 | 10.003 s | 598 | 59.783 |
| 候选 1080p120 | H.264 | 12.002 s | 1438 | 119.814 |
| 候选 1440p120 | H.265 | 12.001 s | 1438 | 119.826 |
| 候选 1440p120，AVC 生产限额 | H.264 | 10.001 s | 600 | 59.992 |
| 恢复原 4K60 | H.264 | 6.003 s | 358 | 59.636 |

各行 framesDropped、packetsLost、freezeCount、pliCount 增量均为 0。网页数据取实际解码，
未测光学延迟或物理显示次数。固定 4K60 候选较同窗基线低 0.493 fps，通过预定的 2 fps 门限。

| 独占 bench | PTS / 墙钟 fps | 板外解码、帧号和实际 SPS |
|---|---|---|
| 1080p raw | 119.996 / 119.997 | NV12；未读取 raw 内容标记 |
| 1080p AVC | 119.996 / 119.992 | 660 帧，重复 1、缺 1，High 5.1 |
| 1080p HEVC | 119.996 / 119.992 | 660 帧，重复 3、缺 3，Main 5.0 |
| 1440p raw | 119.897 / 119.898 | NV12；未读取 raw 内容标记 |
| 1440p HEVC | 119.897 / 119.890 | 660 帧，重复 7、缺 7，Main 5.0 |

每项预热 60 帧，计时 600 帧。三份码流均为 yuv420p，完整解码逐帧检查黑白标记、三处帧号与校验和，
各 660 帧均可读且三处一致。三份编码 bench 各有 raw_frames=output_frames=660，计时段 capture_irqs/vpu_irqs 均为 600/601。
1080p AVC、1080p HEVC、1440p HEVC 的最大采集 PTS 间隔分别是 8.337、8.337、8.350 ms（1080p raw 为 8.339 ms）。
444 最大交付间隔为 17.484 ms。均未出现丢一个 HDMI 帧应有的约 16.7 ms（120 Hz）或 33.3 ms（60 Hz）间隔。
三份码流中相邻帧号的重复和跳号成对，有时先跳后重，无旧帧倒序或帧内撕裂。444 实际计数见下节。

**接收端无丢帧。严格帧号连续性的失败由信号源呈现造成（强推断，缺呈现回执故未证明）。**
高刷源 `latency-source --display-link` 在三份码流覆盖的帧号区间内，逐次 vsync 回调未见重复或缺失 target。
1080p 启动时 ID 6→7 的 target 间隔为 16.667 ms，在 bench 取样之前。帧号记在 AppKit NSView.draw。
若绘制错过合成器锁存，屏幕会多显示一遍上一帧，随后跳到新帧号。444 的 capture-pattern 用 1/60 秒 NSTimer，
也未与 vsync 同步。5.15 同一图样曾出现过一次重复、一次跳号。5.15 全帧记录

**登记 issue：测试源呈现回执。** 测试源需使用 CAMetalLayer 并在 presentedHandler 中逐帧记录 presentedTime，
与实际采集的图样帧号对照后，才能把严格连续性作为采集/编码门禁。本轮保留原测试源。

**QHD HEVC 的 level 信令失败。** bench 的编码 caps 为 5.1，实际 SPS 的 level_idc 为 150（5.0）。
2560×1440 按实测速率约需 4.42 亿亮度样本/秒，超过 5.0 的 267,386,880 上限。该结论来自保存的 bench 码流；
同为 5.0 的 1080p120 约需 2.49 亿样本/秒，符合该上限。QHD 网页 H.265 实际解码 119.826 fps。[FFmpeg 的 HEVC level 表](https://github.com/FFmpeg/FFmpeg/blob/n7.1/libavcodec/h265_profile_level.c#L19-L36)

**登记 issue：QHD HEVC SPS 低报。** wave5 将 HEVC_LEVEL 控件的 5.1 映射到 153 并写入寄存器。
尚未区分是 GStreamer 实际设置的控件值还是固件夹取导致 SPS 为 150。频率 2 × 严重度 2 = 4，低于处理阈值 5，本轮只登记。

## YUV444 和未验项

M6 回 3840×2160、1920×1080 HiDPI，运行 capture-pattern。v308 appsink 实收 **3600 帧 / 59.985392 秒**，
按首末帧计算 **59.998 fps**，最大交付间隔 **17.484 ms**。invalid=0、torn=0、color_bad=0；
横纵单像素红/青交替保留。末帧红块 Y/Cb/Cr 为 62/102/239，青块为 187/153/16。
末帧 24,883,200 字节，SHA-256 `fcdfc60afb2287f4a598d025b2dd5a10c78923274b34fed896912415fca1a4d3`。

**严格连续性失败。** 重复 4 次，累计缺 3 个 ID，重复 ID 为 850、945、1128、2206。工具按合同返回 1。
此时结束新增用例并恢复。7 帧池、25 MiB CREATE_BUFS 拒绝、关采集后的导出 fd、显式回 NV12 均未执行；
本次确实收到 YCbCr444，RGB 回退分支未触发。1080p/4K Variable、基准未知、限流慢转快、
专门 EDID 撤回失锁与重新协商均跳过。固定模式切换时的短暂失锁不计作专门失锁测试。

## VRR 补测

**M6 不提供 Variable，VRR 未测。** 通过已安装 One-KVM 的 MCP，在 M6 系统设置中展开 RTK UHD HDR 的刷新率菜单。
两张截图均显示完整菜单，显示模式由源端独立读回。

| M6 物理模式 | 模式 ID | 菜单勾选 | 菜单全部可选刷新率（Hz） |
|---|---:|---:|---|
| 1920×1080 原生 | 86 | 120 | 120、100、60、50、30、25、24 |
| 3840×2160（逻辑 1920×1080） | 88 | 60 | 60、50、30、25、24 |

未申请板票、装载候选或重启。补测持板 **0 秒**，累计 **1355.600 秒（22 分 35.600 秒）**。
M6 已切回原 mode 88 并读回物理 3840×2160、60 Hz。两档 Variable 变速、Gaming VTEM、VRR 控件与固定回零、
PTS/Vtotal、source-change、网页解码及未知基准的本地 60 fps 预算均无本轮实测数据。
菜单截图、OCR 和源端回执在 `logs/hfr-yuv-vrr-followup/` 的 `1080-menu.jpg`、`4k-menu.jpg` 及配套文件。

## VRR 补测 2

本次以板上安装的 RTK-CONTROL 为基线，从 hfr120 工作树运行 `tools/vrr-edid.py`，
参数为 `--protocol hdmi-forum --mode remote --receiver 48 120 --request 48 120`。
安装表已含 HDMI Forum 48–120 Hz，HF-VSDB 载荷为 `d8 5d c4 01 78 88 01 00 30 78`。
生成表与安装表 **384 字节完全一致**，见上文 SHA-256。三个 128 字节块的校验和均为 0（模 256），
1080p120/4K60 时序和音频块逐字节相同。AMD FreeSync 40–61 Hz 来自历史 256 字节物理表
（SHA-256 前缀 `32c6a608`）。当前预设与历史表的对应关系见 [EDID 文件说明](../../board/edid/README.md)。

**HDMI Forum VRR EDID 下 M6 仍不提供 Variable。** 票 648 经 manager 的 `edid-select RTK-CONTROL`
重新发布，核对生成表、安装预设、保存表及 RX 读回的全部 384 字节。经 One-KVM MCP 切至原生 1080p、
回读 mode 86，RTK 菜单勾选 120 Hz，另有 100、60、50、30、25、24 Hz。截图为
`logs/hfr-yuv-vrr2/1080-menu.jpg`。此票止于源端准入，未加载候选，未测 VRR 变频或 4K。

随即由 manager 写回 RTK-CONTROL，再次逐字节读回通过。M6 确认恢复 mode 88、物理 4K60。
原 uhd7 身份及保护文件前后一致，boot ID 未变，四个服务逐个 active，UDC configured。
票 648 持板 **87.216 秒**（含恢复），全部 13 张票累计 **1442.816 秒（24 分 2.816 秒）**。
离线比对、发布与恢复读回、M6 回执、前后身份及队列时间在 `logs/hfr-yuv-vrr2/`。

## 板时与恢复

首轮共享队列 634–645 共 **12 张板票，1355.600 秒（22 分 35.600 秒）**，含所有失败尝试及恢复；最长 340.312 秒。
未按原设想一次完成。每次重排扣除已用秒数，并为恢复保留 5 分钟。

| 票号 | 实际秒数（按票号顺序） | 发生的事 |
|---|---|---|
| 634–636 | 2.284 / 44.853 / 36.455 | 默认项读取需 sudo；MainPID 是 Python GPU 启动器，实际 ELF 在服务 cgroup；接收 Mac 的 ioreg 返回字典 |
| 637–638 | 63.864 / 67.285 | simple-card 持有 RX 引用，临时解绑并重新绑定后模块加载成功；One-KVM 启动后加入 8081 就绪等待 |
| 639–643 | 101.914 / 132.675 / 137.621 / 133.878 / 137.061 | 4K60 已可接收；M6 Terminal 定位、中文输入组合、旧窗口 OCR 和 zsh 回执 URL 转义分别修正 |
| 644 | 157.399 | M6 确认原 mode 88；进程级显示模式在工具退出时还原，1080p 回读失败 |
| 645 | 340.312 | M6 使用会话级模式设置并回读；完成表中测量，444 帧号门禁失败后正常恢复 |

634 未装载候选、未重启。635–645 每票各有一次正常恢复启动，共 11 次。最终 boot ID
`5fa86ad6-7aaa-4418-bcc6-6d2105a5b97c`，release `7.3.0-vim4kvm-uhd7+`，
GNU ID `d6f9c685802759c85cba6bd92bce90396d1cf6ec`。原 cmdline 和启动文件、运行登记、三个模块 notes、
应用/插件、EDID 身份通过比较；原 One-KVM 进程 SHA 为 `b2bdf8a7ca5425f37f52c81246327c874a2802701c3af54aa800c051f1719130`。
One-KVM、HDMI、manager、gadget 分别 active，UDC configured，taint 前后均 4096。
M6 确认恢复 mode 88，物理 4K60/逻辑 1080p。收尾发出了切回原输入法的 MCP 操作，未独立核验最终前台应用和输入法。

候选期 dmesg 差分无新增内核 WARN、Oops、BUG、SError 或 panic。票 645 三次换模式各有一次
`link readiness revoked: reason=5v-or-align error=-67` 后重新锁定；票 644 另有一次。
GStreamer 扫描器报告两个系统插件的可选依赖缺失及一个 GLib 属性注册告警，三项 1080p bench 均出流。

证据在忽略目录 `logs/hfr-yuv-1793679362/`（主测原始状态、M6 回执、接收 JSON、码流、逐帧分析和末帧）
及 `logs/hfr-yuv-deploy/`（构建、各票据、原/恢复身份和全帧统计）。已安装内核、应用和默认启动项均保持原身份。

### 5.15 行为有误之处

本次没有新发现。此次实测内核为 7.3。
