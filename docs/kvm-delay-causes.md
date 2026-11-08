# 不同 KVM 的播放延迟差异调查

本页定位播放延迟；缓冲下降不等于端到端或流畅度改善。
One-KVM读[策略](#首要差异接收端播放策略)、[配置](#编码配置也不相同)；同步/卡顿读[风险](#kvm-播放延迟复核2026-10-15)。
导航：[统计](#接收端耗时拆分) · [验收](#验收边界) · [历史](#相关记录)；测量见[协议](latency.md#优化指标与验收协议)。

## 首要差异：接收端播放策略

各应用当前协商/发送规则见[NanoKVM](../NanoKVM/server/service/stream/webrtc/track.go)、[JetKVM](../kvm/internal/playoutdelay/interceptor.go)、[One-KVM](../One-KVM/src/webrtc/universal_session.rs)、[PiKVM](../ustreamer/janus/src/client.c)。
尽快播放意图不表示网络/解码/显示耗时为零；未协商接收端保持自身策略，WebRTC改动不证明Direct/JPEG收益。
One-KVM正式复测未持续积压，但H.264回调尾部未改善；PiKVM缓冲下降伴尾部退步，重复轮有丢包/冻结，旧插件也有异常，根因未分离。弱网、长期、多观看者/其他浏览器未覆盖，不能推广固定收益。

## 接收端耗时拆分

统计计算见[接收器](../tools/one-kvm-smoke.mjs)。processing含缓冲/解码，不能相加；target/minimum是估计目标，actual是驻留，均不是端到端。
旧统计非同步同负载，不能据均值差认定H.265固有开销。

## 编码配置也不相同

当前设置见[One-KVM集成](../One-KVM/VIM4.md)与实际管线；不沿用历史厂商配置到Wave5。
同目标码率不等于同画质/帧大小/分包数，不能由相关性指定GOP贡献。发送时钟/调度开销未统一量化，最长等待不是每帧固定开销，分轮均值不能拼端到端。

## One-KVM 低延迟播放策略临时版本对照

临时对照含IPv6初测限制与固定IPv4协商干预。

## One-KVM 正式启用与复测

正式启用后按运动/静态分段并核对RTP包头。

## PiKVM 正式启用低缓冲策略与限制

正式启用与失败复测：0/10、10/20未采用，0/0仍有尾部退步，不能宣称全轮无停顿。

## PiKVM 软件端到端基线与候选筛选

软件端点初筛及连续源A/B/A未证实发布唤醒/采集PTS/按需JPEG达到收益门槛。
按需JPEG初版因preroll阻塞，async=false后功能恢复；截图完成通知修复改善HTTP响应，不能称WebRTC延迟降低。

## KVM 播放延迟复核（2026-10-15）

[跨KVM运动实测](bringup/2026-10-15-cross-kvm-motion-playout-backlog.md)与[旧One-KVM修复](bringup/2026-10-15-onekvm-low-latency-playout.md)提供历史证据；以下是仍需验证的同步/队列边界，不代表已修复。

## 优先复测：JetKVM 音视频同步

[webrtc.go](../kvm/webrtc.go) 的 attachAudioTrack 与视频轨创建均使用 stream ID `kvm`。
前提是 effectiveAudioEnabled 返回真且协商出支持的音频编码；只传视频时没有此同步条件。
因此它具有与旧 One-KVM 相同的浏览器同步等待触发条件，但尚未实测其缓冲增长幅度。

视频经 [backend_vim4.go](../kvm/internal/native/backend_vim4.go) 和
[timing.go](../kvm/internal/gstcapture/timing.go) 使用采集 PTS 差值计算 duration，
并非旧 One-KVM H.265 的固定帧间隔实现。不要不加区分地复制全部 One-KVM 修改。
[native.go](../kvm/native.go) 同步 WriteSample，未发现该层有无界应用帧队列。

下一步应在音频开/关、相同运动负载下比较 jitterBufferTargetDelay 与
jitterBufferMinimumDelay 的增量，并对独立 stream ID 做 A/B。
不能用静音按钮替代移除音频轨，也不能把帧率正常当作延迟正常。

## NanoKVM：音频丢包后媒体时钟压缩

[audio_vim4.go](../NanoKVM/server/service/stream/webrtc/audio_vim4.go) 创建独立的
音频 PeerConnection，音频 `pion-audio` 与视频 `pion-video` 分离，且只在 ICE
connected/completed 后加入音频广播。未发现 One-KVM 同组同步等待的相同路径。

但每个音频观看者的队列最多 4 包，满时直接丢弃新包；队列项只有字节数据，没有时间戳或序号。
write 始终以 20ms WriteSample，未设置 PrevDroppedPackets。
例如两次实际发送之间丢了 4 个 20ms 包，下一包媒体时钟仍只前进一个包，而非保留 100ms 间隔。
这是确定的时间信息丢失；可能表现为音频恢复抖动，不足以证明会拖慢独立的视频连接。
此外 [common/audio_vim4.go](../NanoKVM/server/common/audio_vim4.go) 的 ReadAudio 仅返回 Data，
若修复需考虑采集层丢包，不能只给观看者队列补一个计数器就声称全链路时钟正确。

视频 [manager.go](../NanoKVM/server/service/stream/webrtc/manager.go) 在 HasPTS 时直接写入
90kHz RTP 时间戳，writer 队列容量 1；不属于固定时间步长的同一问题。

## PiKVM：分别检查 WebRTC 与 Direct

WebRTC 插件 [sdp.c](../ustreamer/janus/src/sdp.c) 已声明 `msid:video v` 与 `msid:audio a`，
不具有源码层面相同的 stream ID；最终浏览器接收的 SDP 仍需上板核对。

另有三处独立风险：

- [rtpv.c](../ustreamer/janus/src/rtpv.c) 用 packetize 时的单调时钟产生视频 RTP 时间戳，
  而不是采集 PTS。[vim4.c](../ustreamer/src/ustreamer/vim4.c) 也把取出已编码样本的时间
  填入 grab_begin_ts。编码/队列抖动可能混入媒体时钟，不能把 abs-capture-time 当作真实采集时间。
- [acap.c](../ustreamer/janus/src/acap.c) 在编码输出队列满时跳过 PCM，但只在成功编码后推进 pts，
  缺失媒体时间会被压缩；后面的逐客户端 RTP 队列丢包保留已有包时间戳，是不同情况。
- Direct [stream_media.js](../kvmd/web/share/js/kvm/stream_media.js) 持续调用 decode，
  没有根据 decodeQueueSize 或帧龄限制解码输入。`await decode()` 不等待帧解码完成，
  因为该方法返回 undefined；慢解码器可能持续积压。
  [WebCodecs 方法定义](https://www.w3.org/TR/webcodecs/#dom-videodecoder-decode)。
  渲染端仅保留最新已解码帧，不能消除解码前积压。

Direct 服务端 [server.py](../kvmd/kvmd/apps/media/server.py) 已有 32 帧队列溢出清空与请求关键帧，
不能说整条链路完全没有限流；60fps 下 32 帧约为 0.53 秒的帧数，但不是实测延迟。
WebRTC [client.c](../ustreamer/janus/src/client.c) 也有有限 RTP 队列，满时丢新包，
没有按帧龄追赶。不能简单丢任意 H.264/H.265 包来缩短缓冲，恢复需要关键帧边界。

## 共用的无声排查

源主机没有向 HDMI 输出音频，会影响所有 KVM。更换 EDID 后应重新确认主机输出设备，
再验证非零 PCM、应用解码与网页播放；HDMI RX 显示音频稳定不能证明不是静音。
本轮没有逐个 KVM 重测声音，只有上一轮 One-KVM 的 PCM/Opus/WebRTC 实测证据。

## 验收边界

后续优先顺序：JetKVM 同步组 A/B → PiKVM Direct 慢解码恢复 → 音频队列丢包时钟。
使用相同浏览器、4K60 与运动负载，分别记录音频开关、RTP 时间间隔、队列深度/帧龄、
缓冲增量、丢包及 freeze，运动停止后持续观察恢复。
WebRTC 缓冲统计的含义见 [W3C 定义](https://www.w3.org/TR/webrtc-stats/#dom-rtcinboundrtpstreamstats-jitterbufferminimumdelay)；
它不是端到端键鼠延迟。本轮未修改这些应用的实现或部署新版本。

## 相关记录

- [KVM 播放延迟复核](#kvm-播放延迟复核2026-10-15)：各应用同步组、队列与媒体时钟风险及验证边界。
- [KVM 延迟差异调查](#首要差异接收端播放策略)：播放策略对照、接收耗时拆分、GOP 与时间戳差异。
