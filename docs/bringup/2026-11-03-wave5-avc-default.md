# 2026-11-03：Wave5 AVC 默认按需 IDR

用户接受密集静态图稳态 48.66 dB，选择关闭 AVC 循环刷新。此前同图刷新周期 45
时稳态为 51.73 dB，带间最大相位差为 2.92 dB；关闭后相位差为 0.00 dB。数据来自
[第六轮同窗对照](2026-11-03-wave5-avc-recovery-qp.md)。

uhd7 上，One-KVM 直接创建私有 V4L2 编码器，UU 订阅它的编码输出。
NanoKVM、JetKVM、PiKVM 的 ustreamer 使用 `vim4wave5enc`，其 AVC 子元素
为同一个 `v4l2h264enc`。GOP 0 时，设备使用帧级码控和 I 帧 QP 下限 26。
私有插件在启动和每次请求 IDR 时重新开始计数，在提交输入前设置 P 帧下限；
首张 P 为 12，第 13 张 P 为 0。HEVC 继续使用原有 D 配置。

## 登记 issue

- One-KVM 从 MJPEG 跨模式切入 WebRTC 时可能先保存编码偏好，随后模式转换失败。评分 3。
- One-KVM 网页用请求编码比对就绪事件，硬件因几何限制选用安全编码时，两者会不一致。评分 4。
