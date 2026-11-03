# 2026-11-03：Wave5 AVC 恢复帧 QP 与编码选择持久化

沿用[单帧 VBV 对照](2026-11-03-wave5-single-frame-vbv.md)的 4K60 密集图、
40 Mbps、1200 字节 RTP、同场景 NV12 参考帧和网页接收器。第四轮五张 IDR
后的首张 P 帧 slice QP 均为 0，达到 2255–2280 包。候选 F 将 P 帧 QP 下限
设为 12，再每帧减 1，到第 13 张 P 帧恢复为 0；I 帧下限 26，使用帧级码控。

在原 uhd7 上按 60 fps 回放录制 raw。输入帧 30–41 交替写入两个单值 P QP
范围 38／18，输出 110 帧中对应 slice 的 QP 逐帧匹配。第 60 帧强制 IDR 为
1,749,786 字节，第 61 帧 P 的 QP 12、1,186,440 字节，第 73 帧 P 的 QP 为 0。

| 密集图，AVC | 现行刷新 45 | F，刷新 0 |
|---|---:|---:|
| 网页稳态分带中位 PSNR | 51.73 dB | 48.66 dB |
| 稳态最大分带相位差 | 2.92 dB | 0.00 dB |
| IDR 至稳态 | 周期起伏 | 1 帧／17 ms |
| 去掉前 3 秒的静态平均码率 | 38.100 Mbps | 0.00676 Mbps |
| 最大 AU 字节／包（独立 RTP） | 2,412,261／2035 | 1,749,783／1477 |
| 新观看者首帧／丢包 1.2 秒后 PLI 至解码 | 756／142 ms | 779／146 ms |
| 静态源端绘制至浏览器呈现 P50／P95 | 68.24／70.92 ms | 66.43／68.82 ms |
| 滚动 P50／P95 | 68.40／77.96 ms | 67.79／79.22 ms |

F 的四次 IDR 后均实测 P slice QP 从 12 逐帧降至 0，首张 P 最大
1,195,084 字节／1008 包。相同网页窗口内，稳态低于基线 3.07 dB，超过
允许的 0.5 dB 差值。生产 AVC 保留刷新 45，HEVC 继续使用 D。

## 各应用的编码选择

- One-KVM 的网页切换成功后将实际采用的 WebRTC 编码写入 SQLite。未含该字段的旧配置
  继续使用 H.264，MJPEG 仍由原有模式字段控制。UU 临时协商不覆盖网页偏好。
- NanoKVM 将协议与编码选择存入当前浏览器的 localStorage，页面重开后重新向板端选择，
  板端的当前编码在内存中。JetKVM 通过 SaveConfig 持久化 video_codec_preference。
- PiKVM 把共享编码写入 `/var/lib/kvmd/video-codec`；各浏览器保存自己的播放方式，
  打开时跟随板端共享编码。JetKVM 此次也为加入已有共享流的观看者请求一次关键帧。

生产更新 One-KVM、JetKVM、Wave5 与 HEVC 源插件。网页接口依次选择 HEVC、AVC、
HEVC，每次均从 SQLite 独立读到对应值。正常重启后首次查询即为 HEVC／40 Mbps。
Chrome 在 3840×2160 下连续 300.003 秒解码 18,004 帧，60.013 fps，零 freeze。
One-KVM、manager、HDMI、gadget 服务 active，HID 节点正常、UDC configured、
taint 保持 4096，无新增内核告警。实际持板 691.859 秒，含探测、安装、重启与冒烟。

## 登记 issue

NanoKVM 旧接口 `POST /vm/screen` 的 `value` 是非指针整数。缺失时与显式 0
无法区分，例如只传 `type=type` 会选择 MJPEG。评分 3，登记在此，未改接口。
