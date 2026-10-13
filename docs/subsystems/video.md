# 音视频

视频链路：HDMI RX port 1 → vdin0 → VFM tvpath → vfm_cap DMA-buf →
vfmcapsrc → amlvenc → NanoKVM WebRTC。板级 HDMI 服务打开输入并配置采集，
应用负责推流。video71 是输出回写。

HDMI 启动脚本默认使用完整帧低延迟模式（VDIN mask 0x3）；
HDMI_LOW_LATENCY=0 恢复厂商自动策略。模式含义、对照结果及帧一致性检查见测量文档。

按改动范围先读：

- [采集插件](../../gst-plugin-vfmcap/README.md)：格式和 DMA-buf 生命周期。
- [编码插件](../../gst-plugin-venc/VIM4.md)：帧率预算、安装和测试。
- [应用与音频](../../NanoKVM/VIM4.md)：功能覆盖和构建。
- [视频配置](../../NanoKVM/deploy/vim4/VIDEO.md)：RTP、码率、GOP。
- [端到端测量](../latency.md)：软件端点定义和观测开销。
- [编码实验记录](../encoder-experiments.md)：旧插件降级、帧率重建、QP 与行刷新验证。

编码器测试不能与应用或其他任务并发占用硬件。
验证区分静止/运动、分辨率/帧率切换、热插拔、重连和丢包恢复。
记录版本、配置、负载；帧率、吞吐量和端到端延迟分别报告。
