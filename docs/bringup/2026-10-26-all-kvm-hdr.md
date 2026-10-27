# 2026-10-26：四套 KVM 的远程 HDR 接入

NanoKVM、JetKVM、PiKVM 接入 5.15 公共硬件 Main10 管线，与已有 One-KVM
使用同一管理器「视频输入 → HDR 转 SDR」默认值。输入为 PQ 且关闭转换时保留
十位 HDR10；H.264、JPEG、截图和开启转换的 H.265 保留 SDR。
Chrome 156 的网页帧已核实 PQ/BT.2020，未把另一台 MacBook 的物理屏幕亮度视作已验收。

## 实现与边界

- 编码插件新增 `vim4h265src`：检查原生采集 ABI，编码器优先预留 200 MiB，
  PQ 经 Mali AMLY→P010 和硬件 Main10；SDR 经独立 VDIN1 与原八位编码器。
  全局偏好或输入 EOTF 变化后完整释放旧管线再重开。缺失偏好沿用安全 SDR 默认。
- NanoKVM、JetKVM 从编码 caps 提取每帧色彩信息，通过已协商的 RTP 扩展发送，
  不根据全局开关猜测。WebRTC 预留 Main10，Main1-only 浏览器回退 H.264 SDR。
  PiKVM Janus 声明 Main10，接收端不支持时明确提示改选 H.264。
- NanoKVM、PiKVM Direct 从 SPS 选择 profile/level。普通 Canvas 会损失 HDR，
  Chrome 改用 `MediaStreamTrackGenerator` 写入原生 HTML video；SDR 保留 Canvas。
  NanoKVM 保持稳定的鼠标目标，像素选择器从当前可见媒体读取画面。
- NanoKVM HDR 截图独立读取硬件映射的 SDR 帧，避免把 PQ 简单截成八位 JPEG。
  PiKVM JPEG 与 Main10 编码分支分开。公共启动器为所有 5.15 应用选择私有 Mali。
- 7.x、HLG、HDR10 静态 mastering/MaxCLL 透传及物理屏幕亮度未验收。
  Safari 27.0.1 的远程 HDR 限制见[浏览器复核](2026-10-26-hdr-browser-compatibility.md)，
  不能因为收到 Main10 或使用 Direct 就声称 Safari 真 HDR 已支持。

## 实板条件与首轮结果

5.15.137-vim4kvm-hdrdual6，boot ID `5c6b0cb6-2523-43fe-a4a4-c2cbdb0850f5`。
Mac mini HDMI 输入 3840×2160 60 Hz PQ；RTK UHD HDR 不变，HDMI OUT 未连接。
接收端为本机 Chrome 156，SSH loopback 网关；各应用独占采集编码，逐套运行。
以下为六秒网页呈现计数采样，不是光学显示、运动画质或端到端延迟测量。

| 应用与路径 | 网页色彩 | 呈现 fps |
|---|---|---:|
| NanoKVM WebRTC | PQ / BT.2020 | 59.96 |
| NanoKVM Direct | PQ / BT.2020 | 60.13 |
| JetKVM WebRTC | PQ / BT.2020 | 59.92 |
| PiKVM Janus WebRTC | PQ / BT.2020 | 59.95 |
| PiKVM Direct | PQ / BT.2020 | 59.97 |

首轮均无页面异常；JetKVM/PiKVM WebRTC 启动期各有一帧丢弃，不能概括成全程零丢帧。
原始日志与 JSON 在不入库的 `build/all-kvm-hdr/`。

## 切换、兼容与交付

五条路径各完成 `保留 HDR → SDR → HDR → SDR → HDR`，每段稳定采样四秒。
全局开关改变后约 2–4 秒恢复，稳定阶段约 60 fps；三个 WebRTC 路径的视频
PeerConnection 始终为一个。Direct 的实际解码帧在 PQ/BT.2020 与 BT.709 间切换，
HDR 使用原生 video，SDR 使用 Canvas。NanoKVM 每条路径的三个 HDR 阶段均能另取 SDR JPEG。

PiKVM 首轮切回 SDR 暴露两个 VDIN1 打开者竞争，现已修复：仅原生 HDR 将 JPEG
与 Main10 分开，SDR 的 JPEG/HEVC 共用一个采集源。修复后 WebRTC 和 Direct
各完成两轮往返。公共源也补充启动部分失败时的子管线 NULL 清理回归，确保归还设备。

模拟只支持 Main1 的 Chrome 能力及合法 SDP 协商后，NanoKVM、JetKVM 回退到
H.264/BT.709；PiKVM 显示明确的 Main10 不兼容提示。此模拟不代替其他浏览器实测。
NanoKVM 的稳定 Direct 容器通过失焦释放、旋转、裁剪、区域外松键、触摸取消及键盘回归。
NanoKVM、PiKVM 的 H.264 及 JetKVM 回退后的 H.264 均验证为 BT.709、约 60 fps。
最终共享插件安装后，原有 One-KVM 的 H.264、H.265 也通过独立浏览器解码回归。
PiKVM HDR Direct 的 90° 旋转操作确认保留 PQ，显示目标尺寸为 2160×3840。

已通过 ARM64 构建、NanoKVM/JetKVM 两种构建目标的 Go 测试及每帧色彩回归，
管理器 Go 测试/ARM64 构建、两个前端构建、PiKVM 21 项应用测试、五项 SPS 测试，
以及编码插件 DMA 生命周期与六项公共源测试。
正式打包尝试遇到旧缓存环境缺 SDK；重建环境又被固定 Ubuntu snapshot HTTP 502 阻断。
本轮使用已有 ARM64 构建容器和固定 SDK 编译、校验哈希后安装候选文件，
不将此记录视为全新镜像或完整组件包构建通过。

源码提交：NanoKVM `9beae9f`，JetKVM `6c1e02a`，kvmd `410f89e3`，
uStreamer `d2867f1`，编码插件 `29eccd1`，管理器 `b9e703a`；主仓库固定对应 revision。
最终共享插件 SHA-256：
`54681bd298585454f7095ea77a4a2da80f4a11c7f9eec8496f4466d8d77e3f1d`。
板上原文件与设置备份为 `/var/backups/vim4-all-hdr-20261026/`；未重启、未改内核或 EDID。
结束时恢复 One-KVM H.264、关闭全局 HDR 转 SDR；NanoKVM/JetKVM 视频设置、
PiKVM 原 H.264 偏好及全局曲线文件均与测试前备份逐字节一致。
