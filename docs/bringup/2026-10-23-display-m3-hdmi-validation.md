# 2026-10-23：M3 HDMI 离线验证与一次性启动清单

对应 [实现与 HDR2 门禁](2026-10-23-display-m3-hdmi-color.md)，
[M2 第三窗口](2026-10-23-display-m2-window3.md) 的物理证据不能替代本批 M3 验证。

## 构建证据

本阶段按用户指令停止开发，保存点如下；没有正式部署或合入正式内核分支：

| 远端分支 | 收尾提交 | 检查范围 |
|---|---|---|
| `vim4-display-m3` | `c916015a6dbb4` | 完整 Image/DTB/2334 个模块、host 回归、厂商参数对照、DT schema、strict checkpatch 通过；未上板复验该修复 |
| `wip/display-m3-hdr2` | `ca1ff12502e76` | 保存 `9137809a908cc` 分配高度修复与 `ca1ff12502e76` 颜色配置不保持时静音保护；host 测试和 strict checkpatch 通过，完整构建未完成、未上板 |

`f0c60b6dd4540` 已修复 binding 的旧 maxItems=22 限制。逐提交完整构建也已覆盖
`cf5dacb442ced`（标准 HDMI atomic 属性）、`be1ea339651db`（跳行缩放）、
`d76e5ce8acd41`（HDR2/BT2020 门禁）及窗口候选 `4e7f9da265482`。
`c916015a6dbb4` 完整构建 build ID 为 `7585ee0aa4b3986364e9f103ebae650371dc33fe`，
Image SHA256 为 `1757fa33d4cc211a0d31f4bfdde23234ae796ad02fb308a1567d69ff27c724ba`。
收尾时终止了后续 WIP 构建，没有继续补实现或启动新构建。

本地证据保留在 `logs/display/m3/window-4/` 的 build-checkpoints.log、各提交 build
日志、checkpatch-postwindow-commits.log 和 host 测试日志。已核对远端旧 M3 独有
提交均有 patch-equivalent 新历史，再以预期旧 HEAD 的 force-with-lease 更新自己的
实验分支；未改正式分支。WIP 已独立推送，后续不能把它视为通过完整检查的候选。

VM `~/build/kernel-display-m3`（约7.2GiB）及本窗口静态 init、测试工具已删除；
Mac `build/display-m3/` 产物也已清空删除，脚本和 manifest 留在日志归档。
未删除共享依赖、其他任务构建目录或板上他人的备份。

收尾只读核对：实际 build ID 仍为 `eeddb005df059a850853876d52ef603aa1af192b`，
one-kvm / vim4-manager / vim4-wave5-monitor 均 active，UDC configured，isolated=0、
taint=0。本任务窗口及构建锁持有进程均已退出；之后出现的 RX 任务锁属于另一窗口。
本次未重启、未播放测试音、未做新的上板测试。
收尾主仓全量离线测试：`python3 -m unittest discover -s tests -p 'test_*.py'`，
236项通过、跳过10项；包含一次性启动和恢复测试。

## 4K 窗口收尾结论与下一阶段

用户收尾结论为 1080p、1440p、4K30、4K60 均出画，4K60 SCDC config/status
读回 `0x03/0x0f`，显示器扬声器实际出声、拔插后画面恢复。逐模式独立反馈不完整，
仍保留[窗口记录](2026-10-23-display-m3-window4.md)中的时序限制，不将其记为颜色通过。
AVI 声明 RGB，而 CSC=0、OSD HDR2 留下 YCbCr 路径，导致 YCbCr 数据按 RGB 显示；
颜色明显错误。CSC 写入为何不保持尚未查清。HDR 没有物理测试。

下一阶段先解决有效 CSC/HDR2 路由与所有权、验证 WIP 两项修复，再一次性启动复验
各模式颜色、4K GPU PRIME scanout、60Hz flip、NV12 与采集共存；补带时间戳的
HPD/ELD 恢复、10-bit/有效 420 EDID 及 HDR→SDR。P010/AFBC 仍先补硬件与排空证据。
以下是后续窗口清单，不表示本阶段继续开发或执行。

## M2 + M3 一次性启动批量上板清单

先按部署文档 rebase 当时正式 HEAD，重建同次 Image/DTB/完整模块。备份及默认项
保持当时正式部署，只用已验证的一次性启动；复位 / watchdog 后回默认项。每组持
board + heavy 双锁，按短窗口释放。M3-video 首先只读核对 boot routing / fetch-off
合同，匹配后才让 probe 领取 15 个 SRAM domain；不匹配应安全拒绝。

无需用户在场、但仍须获得板子测试窗口的项目：

1. HPD 电平、EDID 原文与模式/420-only/deep-color/HDR 能力；只测 sink 声明支持的
   模式。读回 PLL、VENC、GCP/P2T、formatter、实际 TMDS / SCDC，8↔10、444↔420 往返。
2. 当前 HDR / BT.2020 应返回 `-EOPNOTSUPP`；错误 EOTF/type、混合色域、RGB limited、
   无 SCDC 的高 TMDS 应拒绝。取得 HDR2 所有权后才验 HDR→SDR 与 blob 更新。
3. OSD 1080p60 60 flips/s、Panfrost renderer 与 linear PRIME 直接 scanout；
   cursor / overlay、zpos、alpha、缩放、RMFB/disable。不能用 llvmpipe 代替 GPU。
4. VD1/VD2 单/双对象 NV12、VDIN/Wave5/vdec 布局、延迟 IN_FENCE、同几何 modeset、
   4K→1080p30/60 和双层混合；producer 不得提前 QBUF。记录跳行细节损失和安全退休。
5. 模式切换期间 4K60 HDMI-IN 编码 / 音频连续性、tmds-invalid、HID/UDC、oops/taint；
   电源所有权改动按部署门禁执行九类全量回归。

需用户在场 / 合适显示设备的项目：

1. M2 SMPTE 同卡 M0 相对对照已通过，仍需 GPU 颜色及有效矩阵 / AVI bank 读回。
   USB 卡有 MJPEG/YUV422 和自身转换，按用户反馈不用绝对 RGB 容差判 HDMI 精度；
   记录同图参考与候选的色块差、是否通道错位/压黑/范围压扁。
2. M2 已有一轮物理 997Hz 录音；新路径再次验证出声与 HDMI-IN 音频共存。
   使用普通系统 Chrome 选择采集卡，不能用 ALSA write 成功替代录音。
3. M2 用户拔插状态已通过；M3 验无显示器启动和重连的 EDID / ELD、声卡、画面恢复。
4. 支持 1440p / 4K60 / 420 / HDR10 / 10-bit 的 sink 上验证模式、HDR 状态与渐变；
   当前 HDMI TO USB EDID 无 1440p/4K60/SCDC，不能据它验收这些能力。

取得 T7 HDR2 所有权之前先补只读证据：每个 OSD 的 HDR2 CTRL / MATRIXI / MATRIXO、
EOTF/OETF/ogain/cgain enable、Mali/Dolby bypass、VPP blend 路由、有效 SRAM/clock。
依厂商 `set_hdr_matrix()`、`hdr_func()`、`fix_vpu_clk2_default_regs()` 建立
disable→排空→矩阵/LUT 初始化→路由→enable 合同，确认不访问 VDIN HDR 核；
不能用通用 0x3910 系数相同来替代此合同。

每组结束重启回默认正式基线，确认实际 build ID、KVM/manager/隔离监控 active、
isolated=0、taint=0、画面、一路编码、UDC configured 和 HID，再清理临时文件、释放锁。
失败项保留证据，实验分支不正式部署。
