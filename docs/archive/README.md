# 归档快照索引

这里保存固定版本的调查与交付证据。当前架构和约束请从[子系统入口](../subsystems/)按需读取。

- [主线 rc7 导入与首轮构建](kernel-rc7-import.md)：2026-10-22 快照；现行入口见[主线基线](../kernel-mainline.md)。
- [Chrome/完整帧/LAN 分包实验](latency-20261013.md)：2026-10-13 快照；现行方法见[延迟测量](../latency.md)。
- [KVM 播放策略逐轮对照](kvm-playout-20261016.md)：2026-10-16 快照；现行约束见[播放差异](../kvm-delay-causes.md)。

- [ADLA npu2 离线修复](npu-adla-npu2.md)：2026-10-30 快照；现行合同见 [NPU](../npu-adla.md)。
- [ADLA npu3 离线修复](npu-adla-npu3.md)：2026-10-30 快照；现行合同见 [NPU](../npu-adla.md)。
- [ADLA npu4 离线取证](npu-adla-npu4.md)：2026-10-30 快照；现行合同见 [NPU](../npu-adla.md)。
- [NPU 六段集成草案](npu-adla-integration.md)：2026-10-30 快照；现行合同见 [NPU](../npu-adla.md)。
- [nodebug 配置候选](uhd2-nodebug.md)：2026-11-03 最后实质清理；原实验为 10-30，现行合同见 [内存与拷贝](../memory-copy-audit.md)。
- [HDR2a1 统一候选](hdr2-unified-candidate.md)：2026-10-30 快照；现行合同见 [HDR2 DMA](../hdr2-dma-contract.md)。
- [HDR2a3 离线修复](hdr2a3-offline.md)：2026-10-30 快照；inode 关联及池上限已被后续修正，见 [HDR2 DMA](../hdr2-dma-contract.md)。
- [kbase r3 离线修复](gpu-kbase-repair.md)：2026-10-30 快照；现行合同见 [kbase](../gpu-kbase-7x.md)。
- [uhd5 kbase 构建](gpu-kbase-uhd5.md)：2026-10-31 快照；现行合同见 [kbase](../gpu-kbase-7x.md)。
- [uhd5 kbase 集成清单](gpu-kbase-uhd5-integration.md)：2026-10-31 快照；现行合同见 [kbase](../gpu-kbase-7x.md)。
- [NanoKVM-Pro 的 VIM4 功能状态](feature-status.md)：2026-10-17 快照；现行来源为[应用](../subsystems/application.md)。
- [NanoKVM 功能差异评估](nanokvm-feature-review.md)：2026-10-13 快照；现行来源为[应用](../subsystems/application.md)。
- [NanoKVM 基线切换](nanokvm-migration.md)：2026-10-15 快照；现行来源为[应用](../subsystems/application.md)。
- [One-KVM VIM4 功能复核（2026-10-14）](one-kvm-audit.md)：2026-10-14 快照；现行来源为[应用](../subsystems/application.md)。
- [HDMI 恢复路径对照](hdmi-recovery-review.md)：2026-10-14 快照；现行来源为[音视频](../subsystems/video.md)。
- [7.3 USB 与音视频适配拆解](kernel-edge-porting.md)：2026-10-20 快照；现行来源为[新内核基线](../kernel-mainline.md)。
- [7.3 补丁清单与主线跟进](kernel-patch-inventory.md)：2026-10-24 快照；现行来源为[补丁维护方法](../kernel-mainline.md#补丁维护方法)。
- [T7 音频全路由离线审计与基础驱动系列](audio-routes-offline.md)：2026-10-23 快照；现行来源为[音频能力](../parity/audio.md)。
- [T7 音频处理、TDMD 与完整构建（仅离线）](audio-processing-offline.md)：2026-10-23 快照；现行来源为[音频能力](../parity/audio.md)。
- [T7 GPU 电压、CPU DVFS 与系统 PM 离线候选](platform-pm-offline.md)：2026-10-24 快照；现行来源为[平台能力](../parity/platform.md)。

[内核审计附件](kernel-audit/)随补丁快照保存，其中包含整理前的 host-tests-initial.json。
音频结果 JSON 和验证日志由对应音频快照链接。

- [1080p120 完整链路审查](1080p120-audit.md)：2026-11-03 快照；现行入口见[维护合同](../video-modes.md)。
- [厂商编码库 fast packing 审计（2026-10-25）](encoder-fast-packing-audit.md)：2026-10-28 快照；现行入口见[维护合同](../performance-baseline.md)。
- [7.3 GPU HDR→SDR／缩放规格与第一阶段原型](gpu-hdr-pipeline.md)：2026-10-30 快照；现行入口见[维护合同](../hdr.md)。
- [保留循环的Mesa候选与冷恢复boost](gpu-loop-candidates.md)：2026-11-03 快照；现行入口见[维护合同](../gpu-maintenance.md)。
- [Bifrost循环代码生成与展开语料代价](gpu-loop-codegen.md)：2026-10-30 快照；现行入口见[维护合同](../gpu-maintenance.md)。
- [Bifrost同块回跳修复与GPU上电轮询候选](gpu-loop-repair.md)：2026-11-03 快照；现行入口见[维护合同](../gpu-maintenance.md)。
- [VIM4 GPU 离线候选与验收方案](gpu-parity-plan.md)：2026-11-03 快照；现行入口见[维护合同](../gpu-maintenance.md)。
- [G52 编译与短负载调频：离线候选](gpu-performance-candidates.md)：2026-11-03 快照；现行入口见[维护合同](../gpu-maintenance.md)。
- [GPU 性能差距：离线测量复核与下一窗口](gpu-performance-diagnosis.md)：2026-10-30 快照；现行入口见[维护合同](../gpu-maintenance.md)。
- [7.3 VDIN HDR2硬件映射：可行性与实现计划](hdr2-hardware-plan.md)：2026-11-03 快照；现行入口见[维护合同](../hdr.md)。
- [T7 HDR2普通HLG离线候选](hdr2-hlg.md)：2026-11-03 快照；现行入口见[维护合同](../hdr.md)。
- [nodebug：绑核证据、DDR边界与两启动对门禁](nodebug-performance-gate.md)：2026-11-03 快照；现行入口见[维护合同](../performance-baseline.md)。
- [NPU 端到端分段：离线分析与下一窗口](npu-e2e-timing.md)：2026-10-30 快照；现行入口见[维护合同](../npu-adla.md)。
- [NPU性能：历史波动分析与多启动门禁](npu-performance-gate.md)：2026-10-30 快照；现行入口见[维护合同](../performance-baseline.md)。
- [RTP 逐包发送优化审查](rtp-send-optimization-audit.md)：2026-10-28 快照；现行入口见[维护合同](../performance-baseline.md)。
- [UU 经 KVM 的滚轮速度对照](uu-scroll.md)：2026-10-15 快照；现行入口见[维护合同](../input-latency.md)。
- [本地 VRR／帧锁定透传审查](vrr-passthrough-audit.md)：2026-10-26 快照；现行入口见[维护合同](../vrr-preparation.md)。
- [对照依据与复核方法](parity-sources.md)：2026-11-03 快照；现行入口见[维护合同](../parity/README.md)。
