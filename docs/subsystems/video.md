# 音视频

视频链路：HDMI RX port 1 → vdin0 → VFM tvpath → vfm_cap DMA-buf →
vfmcapsrc → amlvenc → NanoKVM WebRTC。板级 HDMI 服务打开输入并配置采集，
应用负责推流。video71 是输出回写。

## HDMI 显示器行为

默认把 VIM4 当作一直连接的显示器：HDMI 接收服务与浏览器会话独立，
没有观看者时仍保留所选 EDID 和显示器连接。HPD 表示接收端存在，
不能保证发送端持续输出画面，也不能强制主机退出休眠或虚拟显示器模式。

| 事件 | 预期行为 |
|---|---|
| 网页刷新、连接或断开最后一个观看者 | 只管理推流会话；不改 EDID、不脉冲 HPD、不重启 HDMI 接收服务 |
| 更换编码格式、码率或采集缩放尺寸 | 只调整采集/编码；不改变主机看到的显示器能力 |
| 应用重启，接收端仍加载相同 EDID | 保持显示器连接；恢复操作应幂等 |
| 用户更换 EDID | 写入新能力并重新协商；允许短暂黑屏和主机重新排列显示器 |
| 用户明确要求重新连接显示器 | 允许热插拔脉冲；不把该操作绑定到普通网页刷新 |
| 主机停止输出、休眠或切换虚拟显示器 | 保留显示器连接，区分无信号与采集故障；不周期性重写 EDID |

JetKVM 的“空闲时隐藏显示器”是用户主动选择的例外，默认保持关闭。
切换应用时若两者保存的 EDID 不同，可能需要一次重新协商；这不等同于
网页会话变化，不能把应用切换的 EDID 恢复放进每次连接路径。

静止画面不能作为故障判据。持续收到或解码 60 fps 也不能证明画面内容在更新。
若需要自动恢复，先分辨 HDMI 信号锁定、采集帧推进和浏览器解码各自的状态，
优先恢复故障环节；不能根据像素不变自动热插拔。

验收时分别记录 HDMI 服务运行实例、EDID/HPD 变更日志、输入锁定和浏览器解码状态：
覆盖无观看者、连续刷新、重新连接、应用重启和主机休眠恢复。
使用物理 HDMI 桌面上的运动标记验证内容更新，不能用虚拟桌面上的标记代替。
虚拟显示器退出后的恢复还需单独复测；切换 EDID 后恢复只说明重新协商有效，
不能据此确定故障在主机还是 VIM4。上述内容是行为约束，不代表所有场景已通过硬件验收。

## HDR 输入

EDID 预设声明 HDR10/HLG，主机开启 HDR 时发送 PQ/HLG 10bit 信号。采集为 8bit，
未处理时画面发白。T7 的 vdin0 有独立 HDR2 核，内核在 HDMI 输入为
HDR10/HDR10+/HLG 时将其映射到 SDR，SDR 输入直通（`dmesg` 中
`vdin_set_hdr vdin0 fmt:N`，0=SDR、1=HDR10）。切换由驱动的信号变化处理完成，
不重启服务。vframe 的 signal_type 仍描述源信号；将来 HDMI 环出需要原样输出 HDR 时，
在 vdin0 上设置 `vdin1_bypass_hdr 1` 关闭入口映射，网页另走 vdin1 回写。
Dolby Vision 未支持，EDID 也不声明。

映射表由 `vim4-hdr-curve`（tools/hdr-curve.sh）生成：增益曲线 `oo_y_lut_hdr_sdr`
和 SDR 编码曲线 `oe_y_lut_sdr`。厂商增益曲线相当于 400 尼特映射为 SDR 白，
厂商编码为 gamma 2.2，macOS HDR 桌面会整体偏暗、暗部偏亮。
参数 `HDR_SDR_WHITE`（主机 SDR 白，默认 203 尼特，即 BT.2408 参考白；macOS HDR
灰阶实测 199）和 `HDR_SDR_PEAK`（高光保留到的亮度，默认 1000）保存在
`/etc/default/vim4-kvm-hdr`，与 NanoKVM 改写的 `/etc/default/vim4-kvm-hdmi` 分开。
SDR 白以下 95% 线性，其上用扩展 Reinhard 曲线压入顶部 5%；编码为 sRGB。
增益寄存器为 12 位（上限 4095），SDR 白低于 157 尼特会溢出反而变暗，故下限 160。

hdmi-setup.sh 在打开输入前写入；运行中由 vdin0 attr 的 `reload_hdr` 请求采集中断在帧边界重载，
不重启采集。vim4-manager 的“HDR 转 SDR”滑动条拖动时实时预览，松开后保存。
`oe_y_lut_sdr` 与 VPP/OSD 的 HDR→SDR 共用，将来接 HDMI 输出时同样生效。
HLG 输入仍用厂商 HLG 曲线。

HDMI 启动脚本默认使用完整帧低延迟模式（VDIN mask 0x3）；
HDMI_LOW_LATENCY=0 恢复厂商自动策略。模式含义、对照结果及帧一致性检查见测量文档。

按改动范围先读：

- [采集插件](../../gst-plugin-vfmcap/README.md)：格式和 DMA-buf 生命周期。
- [编码插件](../../gst-plugin-venc/VIM4.md)：帧率预算、安装和测试。
- [应用与音频](../../NanoKVM/VIM4.md)：功能覆盖和构建。
- [视频配置](../../NanoKVM/deploy/vim4/VIDEO.md)：RTP、码率、GOP。
- [端到端测量](../latency.md)：软件端点定义和观测开销。
- [KVM 播放延迟复核](../kvm-playout-review.md)：各应用同步组、队列与媒体时钟风险及验证边界。
- [编码实验记录](../encoder-experiments.md)：旧插件降级、帧率重建、QP 与行刷新验证。
- [HDMI 恢复路径对照](../hdmi-recovery-review.md)、[UU 虚拟屏恢复](../hdmi-uu-recovery.md)：显示器恢复故障的源码审查与现场取证。

编码器测试不能与应用或其他任务并发占用硬件。
验证区分静止/运动、分辨率/帧率切换、热插拔、重连和丢包恢复。
记录版本、配置、负载；帧率、吞吐量和端到端延迟分别报告。
