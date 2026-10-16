# 2026-10-15：RTK EDID 音频与 One-KVM 运动后延迟

RTK UHD HDR 是主机显示的 EDID 名称。本次输入为 3840×2160@60、YUV444、8-bit SDR，
没有验证 HDR 信号。EDID 声明双声道 LPCM，校验有效；板端 HDMI 音频稳定，48kHz、2 声道。
无声原因定位到源 Mac 的默认媒体输出仍为 Mac mini Speakers。切换为 RTK UHD HDR 后，
普通 `afplay` 播放经 One-KVM WebRTC 解码得到非静音音频（峰值约 0.102）。此前定向 HDMI
440Hz 测试音的 ALSA PCM 采样与 WebSocket Opus 解码也通过。未修改 EDID、内核或原有账户数据库。

One-KVM `e5878e6d` 修复 VIM4 视频与音频同属一个 WebRTC 同步组造成的额外视频等待：
使用独立音频 stream ID，保留音频传输；拥塞时不保证严格口型同步。ICE 连接后清空旧音视频队列，
再请求新关键帧；H.265 RTP 时钟改用采集时间戳，音频队列丢包保留缺失的媒体时间。
单独把浏览器 jitterBufferTarget 设为零不能解决同步等待，未纳入修复。

旧 H.264 在运动停止后末 20 秒视频缓冲平均约 124ms，目标缓冲约 134ms、最低缓冲约 41ms；
HID data channel 未积压。正式包在 Chrome 中分别测试 H.264/H.265 各 125 秒，配置 4K60、
60Mbps，含 25 秒全屏运动与快速移动鼠标。两者目标缓冲均不再叠加同步等待，末 20 秒实际
视频缓冲平均分别为 7.45ms、16.16ms；约 60fps，统计丢包与丢帧均为零。
这些数值是浏览器缓冲驻留时间，不是键鼠端到端延迟；未覆盖用户其他浏览器、网络或长期运行。
测试使用独立临时数据库与会话，正式二进制与部署包一致，结束后清理测试实例并恢复正常服务。

原生 ARM64 构建、609 项 Rust 测试、15 项部署助手测试，以及包校验和真实升级/API 重启测试通过。
通过 `board.py deploy` 安装单组件 `2.5.1+vim4.20261016.83`，其余包版本保持不变；
One-KVM 与 manager active、health 正常、dpkg audit/verify 无异常，安装二进制哈希与测试包一致。
版本沿用工作区已有日期前缀并递增，不能据此推断测试日期。本轮没有重建系统镜像。
证据：`logs/rtk-audio-latency/`，含 `final-summary.json`、两种编码逐秒统计、
`final-audio-smoke.log`、`package83.log`、`verify83.log`、`deploy83/`。
