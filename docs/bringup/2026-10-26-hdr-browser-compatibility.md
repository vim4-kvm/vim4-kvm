# 2026-10-26：Chrome 与 Safari 的远程 HDR 兼容性复核

当前 One-KVM H.265 原生 HDR 输出包含真实 Main10、PQ 和 BT.2020，Chrome 156
解码后仍保留这些颜色信息；Safari 27.0.1 虽能收到并解码同类码流，当前 WebRTC
播放帧却是八位 BT.709/sRGB，不能算 Safari 远程 HDR 已通过。普通 MP4 播放的
正对照可以保留 PQ，因此不能从 Safari 能播 HDR 文件推断 WebRTC 也支持 HDR。

## 现场与方法

接续[全局 HDR 默认](2026-10-26-hdr-global.md)。One-KVM `2e670914`，内核
`5.15.137-vim4kvm-hdrdual6`；源为 Mac mini 的实体 HDMI 4K60，RX 报告
`HDR10-GAMMA_ST2084`，全局 `HDR_SDR_ENABLED=0`，曲线203/1000。
检查时保存的编码为 H.264；该路径仍输出 SDR，关闭 HDR 转 SDR 不会自动换成 H.265。

测试临时切到 H.265。Chrome 156 使用独立无头实例，Safari 27.0.1 使用普通原生窗口，
均通过现有 One-KVM `/api/webrtc/offer` 接收视频，用原生 `<video>` 播放。
仅在本机回环端口代理认证与信令，不修改 Safari 安全设置或生产应用。
接收端 encoded transform 原样传递数据，并另存首个关键帧；板上 ffprobe 软件解码
这份已接收码流，核对 SPS/VUI 和像素格式。没有额外占用硬件编码器。
浏览器用 `VideoFrame(video)` 读取当前播放帧，Chrome 另取克隆视频轨道的处理器输出。
帧率为八秒 `framesDecoded` 差分；未运行运动一致性夹具，不作为画质或端到端延迟验收。

## 实测结果

| 检查 | Chrome 156 | Safari 27.0.1 |
|---|---|---|
| H.265 SDP | 显式声明并选中 `profile-id=2` | 只有 H.265，没有显式 Main10 声明 |
| 接收到的关键帧 | Main 10、`yuv420p10le`、PQ、BT.2020、limited | 同为 Main 10、`yuv420p10le`、PQ、BT.2020、limited |
| 视频元素当前帧 | PQ / BT.2020 / BT.2020-ncl / limited | NV12八位、sRGB / BT.709 / BT.709 / full |
| 克隆轨道的当前帧 | 同样保留 PQ / BT.2020 | 页面未提供轨道处理器，未测 |
| 解码帧率 | 59.865fps，零报告丢帧 | 59.978fps，零报告丢帧 |

Chrome 返回不透明硬件帧，`format=null`，不能用这个值证明像素位深；十位结论来自
接收码流的软件解码。两边均协商 RTP color-space 扩展，但协商成功也不能证明接收后
保留 HDR。当前发送的四字节扩展与码流 VUI 都带 PQ/BT.2020；本次关键帧未见
mastering-display 或 MaxCLL/MaxFALL side data，未将静态母版元数据完整透传算作通过。

Safari 的关键帧也是 Main10：不能把视频元素的 SDR 标签解释成服务端已经回退 SDR。
网页路径目前还存在接收能力与发送 profile 一致性缺口，不能按 UU 的八位兼容处理
推断网页也有同样降级。本次只确认行为，没有修改协商或生产播放路径。

## Safari 正对照与源码交叉检查

把 Chrome 收到的同一个关键帧用 ffmpeg `-c copy -tag:v hvc1` 封装成 MP4，
没有重新编码、没有另补 HDR 静态元数据。Safari 播放后 `VideoFrame(video)` 返回
PQ / BT.2020 / BT.2020-ncl（fullRange=true，未作为范围保真验收），与 WebRTC
的八位 BT.709 结果不同。同一取帧 API 能读出 PQ，排除了“此 API 总会抹掉 HDR”的解释。
同一关键帧的 WebCodecs 单帧控制亦能解码，但 Annex B 与 hvcC 配置两种路径均返回
NV12 / BT.709 / sRGB，不能把简单改用 VideoDecoder 当作已验证的修复。

WebKit 上游的 [H.265 WebRTC 解码实现](https://github.com/WebKit/WebKit/blob/main/Source/ThirdParty/libwebrtc/Source/webrtc/webkit_sdk/objc/components/video_codec/RTCVideoDecoderH265.mm)
请求八位 full-range NV12，并覆盖为 BT.709/sRGB；这一实现与现场结果吻合，但上游
main 不是本机 Safari 的精确构建源码，不能据此断言全部版本和解码后端相同。
[VideoFrame 的 video 构造路径](https://github.com/WebKit/WebKit/blob/main/Source/WebCore/Modules/webcodecs/WebCodecsVideoFrame.cpp)
读取播放器当前帧；[MediaStream 播放器](https://github.com/WebKit/WebKit/blob/main/Source/WebCore/platform/graphics/avfoundation/objc/MediaPlayerPrivateMediaStreamAVFObjC.mm)
的取帧函数直接返回当前视频帧，与显示层使用相同帧对象。
上述实测与源码交叉证据足以将本机问题定位到 Safari 当前媒体接收/解码链路，
但没有测量屏幕光度，也未证明所有 Safari 版本均不支持 WebRTC HDR。

## 交付边界与恢复

Chrome 的码流和解码颜色识别已通过，用户另一台 MacBook 的浏览器版本、屏幕 HDR
能力及最终光度尚未验证。无头 Chrome 的动态范围查询为 false，不能代替用户屏幕检测；
本机 Safari 的 `dynamic-range: high` 为 true，同样不能覆盖视频解码结果。
要在现有支持路径观看 HDR，需源端实际 HDR、管理器关闭 HDR 转 SDR、One-KVM
选择 H.265，以及接收端保留 Main10/PQ；H.264 不满足这一条件。

Safari 若要真 HDR，需要独立验证可保留十位 PQ 的播放后端，不能只加 HDR 标签、
强改 SDP 或按浏览器名称宣称支持。MP4 正对照仅证明本机文件播放路径可行，
尚未实现低延迟连续播放、音画同步与断线恢复，不作为可用替代方案交付。

测试后恢复原保存的 H.264，保留原全局关闭转换及203/1000参数；无重启、无二进制部署。
One-KVM PID151299、重启计数0，boot ID保持
`5c6b0cb6-2523-43fe-a4a4-c2cbdb0850f5`。
原始 JSON、关键帧及临时探针位于忽略目录 `build/hdr-gpu/`：
`chrome-hdr-native.json`、`chrome-hdr-bitstream.json`、`safari-hdr-native.json`、
`safari-hdr-bitstream.json`、`safari-hdr-control.json`、`*-hdr-keyframe.h265`。
关键帧含真实桌面，不纳入版本库。
