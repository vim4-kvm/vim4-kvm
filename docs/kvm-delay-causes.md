# 不同 KVM 的播放延迟差异调查

本次调查接续 [跨 KVM 实测](bringup-log.md)；源码对应 NanoKVM `1ca2e15`、
JetKVM `390d7e98`、One-KVM `e5878e6d`、kvmd `259d2c7e`、uStreamer `9baf264c`。
分析对象是 Chrome 155 WebRTC 接收路径，不把 Direct、浏览器缓冲和键鼠端到端延迟混为一谈。

## 首要差异：接收端播放策略

| 系统 | 调查基线的发送策略 | 源码证据 |
|---|---|---|
| NanoKVM | 协商后在每帧首包发送 playout-delay min=0/max=0 | [track.go](../NanoKVM/server/service/stream/webrtc/track.go) |
| JetKVM | 拦截器在已协商的 RTP 包上发送 min=0/max=0 | [interceptor.go](../kvm/internal/playoutdelay/interceptor.go) |
| One-KVM | 会话没有注册/发送该扩展，使用浏览器自适应行为 | [universal_session.rs](../One-KVM/src/webrtc/universal_session.rs) |
| PiKVM | GOP 非零时发送 min=0/max=1000（单位 10ms，即上限 10 秒）；只有 GOP=0 才发送 0/0 | [client.c](../ustreamer/janus/src/client.c)、[plugin.c](../ustreamer/janus/src/plugin.c) |

One-KVM 后续提交 `e9de9eeb` 已将下文验证的 0/0 策略加入 VIM4 网页 H.264/H.265：
协商扩展后每帧首包发送，未支持的接收端保持自身策略。保留编码配置、行刷新及音频时钟。
上表和下文默认策略数据描述改动前的基线。

10 秒是允许范围，不是固定等待 10 秒。0/0 是尽快播放意图，也不是网络、解码或显示耗时为零的保证。
[WebRTC 扩展定义](https://webrtc.googlesource.com/src/+/refs/heads/main/docs/native-code/rtp-hdrext/playout-delay/README.md)
说明了这种意图；[当前 WebRTC timing 实现](https://webrtc.googlesource.com/src/+/refs/heads/main/modules/video_coding/timing/timing.cc)
为低延迟播放选择尽快渲染路径。当前上游代码用于解释机制，不冒充本机 Chrome 的精确构建源码。

旧数据里 NanoKVM H.264 的 target/minimum 仍约 35ms，实际驻留却约 1.25ms；
JetKVM 对应约 53ms 与 2.85ms。这并不矛盾：估计目标和实际等候不是同一个量。
不能用 target 很大断言零延迟扩展失效，也不能把 actual 很小解释为采集到显示只有 1ms。

### 实机因果对照

使用 NanoKVM 正式包 `.89`、H.264、3840×2160/60fps、相同 Chrome。每轮新建浏览器会话，
采样 60 秒，第 15–40 秒显示真实 HDMI 全屏运动；音频连接保持相同。
浏览器探针只在 B 组的 createOffer 中移除 playout-delay 扩展，服务端因此不再发送 0/0；
记录的 answer SDP 确认 A 有该扩展、B 无该扩展，实际 codec 均为 H.264。
这项干预不改生产二进制、分辨率、GOP 或解码器。

| 目标码率 / 顺序 | 扩展 | 末 20 秒缓冲 ms | 解码 ms | 全轮统计丢包 |
|---|---|---:|---:|---:|
| 60Mbps A | 0/0 | 0.28 | 3.50 | 3 |
| 60Mbps B | 不协商 | 15.94 | 3.52 | 566 |
| 60Mbps A 复测 | 0/0 | 0.34 | 3.53 | 0 |
| 12Mbps A | 0/0 | 0.26 | 3.53 | 0 |
| 12Mbps B | 不协商 | 19.26 | 3.52 | 0 |

60Mbps B 有丢包干扰，不能用它单独量化播放策略的作用；新增 12Mbps 对照后，两组均零丢包、
零丢帧、零 freeze，解码耗时基本相同，缓冲仍差约 19ms。12Mbps 的 target 也几乎一致
（26.48/26.57ms），说明实际等待差异不能解释为这一对照的网络抖动估计目标升高。
B 组的板端 3 秒 UDP 头部采样确认媒体发往本机有线地址 `192.168.50.239`。
因此“有没有要求尽快播放”已具备实机因果证据；不把约 19ms 当作所有应用/网络的固定收益，
也没有据此证明 PiKVM 全部差距都来自这一项。高码率 B 的丢包来源本轮未进一步定位。

## 接收端耗时拆分

从前轮原始逐秒数据重新计算末 20 秒增量；缓冲除以 emittedCount，解码/处理除以 framesDecoded。
根据 [W3C 统计定义](https://www.w3.org/TR/webrtc-stats/#dom-rtcinboundrtpstreamstats-totalprocessingdelay)，
processing 是接收帧首包到解码完成，包含缓冲与解码，不能再把三列相加。

| 系统 / 编码 | 缓冲驻留 ms | 解码 ms | 接收至解码完成 ms |
|---|---:|---:|---:|
| NanoKVM H.264 | 1.25 | 3.68 | 4.97 |
| NanoKVM H.265 | 0.44 | 3.14 | 3.61 |
| JetKVM H.264 | 2.85 | 3.50 | 6.38 |
| JetKVM H.265 | 1.03 | 2.82 | 3.88 |
| One-KVM H.264 | 7.45 | 4.38 | 11.87 |
| One-KVM H.265 | 16.16 | 3.51 | 19.72 |
| PiKVM H.264 | 30.97 | 4.63 | 35.64 |
| PiKVM H.265 | 14.12 | 3.17 | 17.33 |

One-KVM 来自前一轮 125 秒测试，其余来自 100 秒测试，均配置 4K60/60Mbps，但并非同步或
完全相同负载的编码器对照。表中主要差异落在接收等候，不能归因于 H.265 解码更慢：
这些记录里 H.265 平均解码反而略快。One-KVM 的 8.7ms 差值尤其不能当作 H.265 固有开销。

## 编码配置也不相同

| 系统 | H.264 | H.265 |
|---|---|---|
| NanoKVM | 本板 GOP120 | 本板 GOP120 |
| JetKVM | 固定 GOP120 | 固定 GOP120 |
| One-KVM | 随码率预设；该轮约每秒一个关键帧 | GOP0 + 每帧刷新一行 CTU，订阅/恢复时仍请求关键帧 |
| PiKVM | 默认 GOP30 | 默认 GOP30 |

依据：[NanoKVM 管线](../NanoKVM/server/common/kvm_vision_vim4.go)、
[JetKVM 管线](../kvm/internal/native/vim4_encoder.go)、
[One-KVM 管线](../One-KVM/src/video/pipeline/shared/vim4.rs)、
[PiKVM 默认配置](../kvmd/deploy/vim4/main.yaml)。
原始接收统计支持该差异：100 秒 NanoKVM/JetKVM 各约 51 个关键帧，PiKVM 含预热约 217–219 个；
One-KVM H.265 全轮仅 1 个。关键帧频率改变数据突发与编码预算，但不能仅凭这个相关性
给 PiKVM 的 31ms 指定一个确定的“GOP 贡献值”。

目标码率也不等于实际输出量。例如前轮末 20 秒，NanoKVM H.264/H.265 实收约 34.3/10.1Mbps，
PiKVM 为 43.7/21.4Mbps。因此“都设为 60Mbps”不等于相同帧大小、分包数量或相同画质。
这组吞吐不能直接作为同画质压缩率证据。

## 其余已确认的实现差异与尚未量化部分

- NanoKVM RTP 使用帧 PTS，JetKVM 使用 PTS 差值推进媒体时钟，修复后的 One-KVM H.265
  也使用 PTS。PiKVM [rtpv.c](../ustreamer/janus/src/rtpv.c) 使用打包时刻生成 RTP 时间戳；
  [vim4.c](../ustreamer/src/ustreamer/vim4.c) 把取出编码帧的时刻填入 grab/encode 时间。
  这会改变接收端看到的时间节奏，且其 abs-capture-time 不是 HDMI 真实采集时间；目前未做替换时间戳的因果对照。
- PiKVM 同时运行 JPEG 和 H.26x 分支，经共享内存和 Janus 转发；主循环含最长 5ms 的 bus 等待。
  这些是额外调度点，不等于已经测得每帧固定多 5ms，更不能把它们与浏览器缓冲直接相加。
- NanoKVM 已把 UDP GSO 限到八包，JetKVM/One-KVM/Janus 的发送实现不同。
  之前的大批次丢包已有对照证据；当前各发送器的纯开销量尚未统一测量。
- 音视频同步：旧 One-KVM 的额外等待已有修复前后证据；当前 One-KVM/PiKVM 分离 stream ID，
  NanoKVM 使用独立 PeerConnection。JetKVM 仍同组，但该轮 target 与 minimum 相等，
  没有证据把它目前的几毫秒差异归因于额外同步等待。
- [历史板端编码测试](encoder-experiments.md#wave521-时钟与-4k-编码耗时2026-10-14) 在 666MHz、
  12Mbps 下测得 H.264/H.265 p50 约 11.55/12.96ms。它是编码阶段的另一组条件，
  不能与本次分轮浏览器均值拼成完整端到端结果。

本轮原始数据、浏览器探针和汇总脚本保存在 `logs/kvm-delay-causes/`。
调查不修改生产应用源码或安装包；配置对照结束后恢复原 One-KVM 选择及 NanoKVM 12Mbps。

## One-KVM 低延迟播放策略临时版本对照

基于 `e5878e6d` 的隔离源码副本制作 ARM64 测试二进制，仅在 VIM4 视频协商注册
playout-delay 扩展，并在 H.264/H.265 每帧首包经 `write_rtp_with_extensions` 发送 0/0。
该 API 依据协商结果映射扩展 ID，不向未协商的会话强行发送扩展。
没有改变 GOP、H.265 行刷新、码率、分辨率、音视频 stream ID 或音频发送逻辑。
609 项 Rust 测试与 release 构建通过。测试二进制 SHA-256：
`6c938dbca19d0026a225d42e1b2cbf70c433506fef7cc922fd5418bdfbc0a47d`。

正式 `.83` 和候选分别在独立临时数据目录、账户、18081 端口运行，其他编码应用停止。
先各测两种编码 90 秒；候选 H.265 使用 IPv6，故这四轮只作初步验证，不用它们直接量化策略收益。
RTP 包头采样确认两种编码各在约 3 秒内发送了 181 个值为 `000000` 的已协商扩展。
H.265 的首次包头探针只处理 IPv4，没有捕获到该流；增加 IPv6 解析后才验证成功。

最终对照使用同一个候选二进制，固定本机有线 IPv4 `192.168.50.239` 到板子
`192.168.50.210`。仅在默认策略组移除浏览器 offer 中的 playout-delay 扩展。
每轮新建 Chrome 155 会话、预热 5 秒后采样 60 秒，第 15–40 秒为 HDMI 全屏运动，
保留真实音频轨；配置均为 4K60/60Mbps。SDP、实际 codec 和板端媒体 UDP 目的地址分别核对。
这避免把原版/候选构建、网卡选择或 H.264/H.265 模式错误当作播放策略差异。

H.264 默认/0/0 策略末 20 秒缓冲分别为 32.21/0.50ms，解码为 3.52/3.59ms。
两组零统计丢包、丢帧、freeze，音频正常。但浏览器帧回调间隔 P99 从 33.4ms 变为 50.1ms，
最大间隔约 83ms 基本相同。因此缓冲下降已有证据，不能据此宣称流畅度的每个指标都改善。
帧回调还受浏览器主线程调度影响，不等于屏幕真实扫描间隔；单轮 P99 差异需重复测试才能归因。

H.265 默认/0/0 策略末 20 秒缓冲为 26.31/0.47ms，解码为 3.56/3.57ms；帧回调 P99
均为 33.4ms，最大间隔约 50ms。两组同样零统计丢包、丢帧、freeze，音频正常。
四组实际协商编码、帧尺寸、音频峰值、扩展有无与有线目的地址均通过断言核对。
结果支持继续评估视频 0/0 策略，但尚未覆盖长期、弱网、多观看者、其他浏览器；
缓冲减少约 26–32ms 是这一轮结果，不是承诺固定的端到端收益。

本轮属于策略试验，没有替换正式安装包。日志、协商记录、包头探针、候选补丁与汇总在
`logs/onekvm-playout-ab/`，临时源码在 `build/onekvm-playout-source/`。
