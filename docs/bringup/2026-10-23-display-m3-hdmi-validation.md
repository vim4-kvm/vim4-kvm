# 2026-10-23：M3 HDMI 离线验证与一次性启动清单

对应 [实现与 HDR2 门禁](2026-10-23-display-m3-hdmi-color.md)，
[M2 第三窗口](2026-10-23-display-m2-window3.md) 的物理证据不能替代本批 M3 验证。

## 构建证据

完整逐提交构建和最终清理结果在本批检查结束后登记。中间 merge 的 Image/DTB/模块
编译完成，但 schema 检查发现 M3 新增窗口后仍受旧 maxItems=22 限制；
`f0c60b6dd4540` 修正此约束，并已通过完整构建、host 回归和 DT schema。
其他提交尚未完成构建时不推送。

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
