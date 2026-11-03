# 2026-11-03：Wave5 AVC 默认按需 IDR

用户接受密集静态图稳态 48.66 dB，选择关闭 AVC 循环刷新。此前同图刷新周期 45
时稳态为 51.73 dB，带间最大相位差为 2.92 dB；关闭后相位差为 0.00 dB。数据来自
[第六轮同窗对照](2026-11-03-wave5-avc-recovery-qp.md)。

uhd7 上，One-KVM 直接创建私有 V4L2 编码器，UU 订阅它的编码输出。
NanoKVM、JetKVM、PiKVM 的 ustreamer 使用 `vim4wave5enc`，其 AVC 子元素
为同一个 `v4l2h264enc`。GOP 0 时，设备使用帧级码控和 I 帧 QP 下限 26。
私有插件在启动和每次请求 IDR 时重新开始计数，在提交输入前设置 P 帧下限；
首张 P 为 12，第 13 张 P 为 0。HEVC 继续使用原有 D 配置。

生产安装后，HDMI 经 `vim4wave5enc` 编码时读回刷新 0、RC `0x3e8fc021`、
I/PB QP 寄存器 `0xacda/0xcc0ccc`。随后读回 PB 寄存器低六位从 11 降至 0。
正常重启后 One-KVM 首次查询即为保存的 HEVC／40 Mbps。切到 AVC 后，网页
的首帧为 708 ms，4K60 短窗解码 59.78 fps、零 freeze。对第二个观看者丢包
1.2 秒，丢弃 74 个 SRTP 包，PLI 计数增加 2，显式 PLI 后 113 ms 解出关键帧。
起播及恢复 IDR 的 slice QP 均为 26，随后完整的 P 帧序列为 12、11…0。

切回 HEVC 后，刷新为 0，RC 为 `0x3e8fc021`，I/PB 为 `0xacda/0xcc0cc0`，
未触发 AVC 的逐帧写入。Chrome 在 3840×2160 连续 300.005 秒解码 18,004 帧，
60.012 fps，零 freeze。进程映射的两个插件与运行中的 One-KVM 可执行文件均已核对
SHA-256。四个服务 active，UDC configured，HID 节点正常，taint 保持 4096，
无新增内核告警。一次持板 394.104 秒，板上保留 HEVC／40 Mbps。

## 登记 issue

- One-KVM 从 MJPEG 跨模式切入 WebRTC 时可能先保存编码偏好，随后模式转换失败。评分 3。
- One-KVM 网页用请求编码比对就绪事件，硬件因几何限制选用安全编码时，两者会不一致。评分 4。
