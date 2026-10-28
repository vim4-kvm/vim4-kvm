# 不同 KVM 的播放延迟差异调查

> 摘要：各 KVM 延迟差异的首要原因是接收端 playout-delay 策略；One-KVM、PiKVM
> 已改为 0/0 并复测。后续节依次为接收耗时拆分、编码配置差异、其余实现差异、
> 两个应用的启用与复测，以及 PiKVM 软件端到端基线与候选筛选。按需读取单节。

本次调查接续 [跨 KVM 实测](bringup/2026-10-15-cross-kvm-motion-playout-backlog.md)；源码对应 NanoKVM `1ca2e15`、
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
- [历史板端编码测试](bringup/2026-10-14-wave521-clock-encode-time.md#wave521-时钟与-4k-编码耗时2026-10-14) 在 666MHz、
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

## One-KVM 正式启用与复测

用户确认后，`e9de9eeb` 将相同策略加入正式源码，独立构建并部署
`vim4-onekvm 2.5.1+vim4.20261016.90`。610 项 Rust 测试、15 项部署测试、
49 项工作区测试以及隔离包升级/API 验证通过；新增 SDP 测试覆盖两种编码，
并检查视频扩展不会进入音频协商。此次只更新 One-KVM 应用。

正式安装的二进制在临时账户下复测：Chrome 155、有线 IPv4、4K60、60Mbps，
每组预热 5 秒后采样 100 秒，其中第 15–75 秒为真实 HDMI 全屏运动。
H.264 对照使用同一个正式二进制，仅移除浏览器 offer 中的该扩展。

| 指标 | H.264 默认策略 | H.264 低延迟 | H.265 低延迟 |
|---|---:|---:|---:|
| 连续运动时平均实际缓冲（第 20–70 秒，ms） | 28.58 | 4.55 | 3.55 |
| 结束运动后平均实际缓冲（末 20 秒，ms） | 26.29 | 0.78 | 0.82 |
| 运动期间平均解码耗时（ms） | 3.57 | 4.48 | 1.95 |
| 帧回调间隔 P99（ms） | 50.0 | 50.1 | 33.4 |
| 最大帧回调间隔（ms） | 83.3 | 83.4 | 50.0 |

三组末段帧率均为 60fps，统计丢包、丢帧、freeze 均为 0，解码音频峰值约 0.10。
两种编码的实际 RTP 包头各在 3 秒内捕获 180 个协商 ID=5、值为 `000000` 的扩展。
本轮 H.264 帧回调尾间隔基本相同，缓冲在运动结束后回落，没有观察到持续累积；
仍不能把回调间隔当作屏幕扫描间隔，或把缓冲时间当端到端延迟。
这次没有重测 H.265 默认策略；其因果对照见上一节，也未覆盖弱网、长期和其他浏览器。

结束后恢复正常 One-KVM 服务及原账户配置，清除临时服务、数据和恢复定时器。
`dpkg --audit`、`dpkg -V vim4-onekvm`、board check 通过，HDMI 服务运行实例和 EDID
哈希均保持不变。证据与完整采样：`logs/onekvm-playout-release/`。

## PiKVM 正式启用低缓冲策略与限制

uStreamer `b9f7f04` 将 VIM4 Janus 视频的 playout-delay 改为 0/0，不再根据 GOP
决定是否尽快播放；非 VIM4 构建保留原策略。沿用 Janus 已有的首包扩展发送和协商映射，
不改 GOP30、码率、音频、JPEG 或 Direct 路径。构建并部署
`vim4-pikvm 2.5.1+vim4.20261016.91`，仅更新 PiKVM 应用。
工作区 49 项测试、14 项 PiKVM 部署测试、H.264/H.265 RTP 分包/重组测试、
ARM64 构建、包验证及 Janus 实际挂载/卸载检查通过。

首组前后对照为 `.88` 与 `.91`，Chrome 155、4K60、60Mbps、GOP30，
每轮预热后采样 100 次，约每秒一次，第 15 次采样时启动 60 秒 HDMI 全屏运动。
源端图案和接收浏览器运行在同一台 Mac。固定有线 IPv4，板端包头采样确认媒体发送到
`192.168.50.239`；协商 ID=2，旧版扩展为 `0003e8`、新版为 `000000`，
各约 3 秒捕获 180–181 个扩展。下表运动段取第 20–70 次采样的计数器增量，
静态段取末 20 次；不把采样序号当成严格墙钟，也不把缓冲当作端到端延迟。

| 指标 | H.264 原版 | H.264 0/0 | H.265 原版 | H.265 0/0 |
|---|---:|---:|---:|---:|
| 运动段平均实际缓冲 ms | 64.00 | 5.73 | 31.20 | 4.32 |
| 末段平均实际缓冲 ms | 29.62 | 1.90 | 20.51 | 1.44 |
| 帧回调间隔 P99 ms | 33.4 | 66.7 | 33.4 | 50.1 |
| 最大帧回调间隔 ms | 83.3 | 83.4 | 50.1 | 83.4 |

这四轮末段均为 60fps，零统计丢包、丢帧、freeze，音频峰值约 0.10。
降低缓冲的效果明确，但帧回调尾间隔更大；本次不能声称流畅度全面改善。
帧回调受接收机调度、图案绘制和呈现路径影响，不等于屏幕扫描间隔。

为核对该取舍，另做了临时插件和重复测试，均保留原始日志：

- 0/10ms 临时版本在后半程丢包并停止解码；期间接收机并行编译了另一个候选版本，
  这轮不能用于播放策略的因果比较，也不计为通过。
- 10/20ms 临时版本的运动段缓冲为 5.73ms，P99/最大回调间隔为 83.4/100.1ms，
  零统计丢包、丢帧、freeze。没有观察到更好的折中，未采用。
- 正式 0/0 的一次重复测试出现 120 个统计丢包、128 个丢帧和 4 次 freeze，
  其中采样开始时已包含 34 个丢帧和 1 次 freeze。不能将所有重复轮次写成无停顿。
- 随后每轮重启独立浏览器并关闭后台计时器限速，用 `.88` 原插件与 `.91` 正式插件
  再对照。原插件零丢包但有 77 个丢帧和 2 次 freeze，计数变化集中在运动图案启动附近；
  新插件零统计丢包、丢帧、freeze，运动段/末段缓冲为 5.62/1.50ms，P99 为 66.6ms。
  原插件也出现异常，不能把后续停顿全部归因于新策略；其根因尚未分离验证。

当前 [WebRTC timing 实现](https://webrtc.googlesource.com/src/+/refs/heads/main/modules/video_coding/timing/timing.cc)
在最小等待为零、最大等待不超过 500ms 时仍选择尽快渲染，因此仅把 0/0 改为 0/10ms
并不必然获得平滑播放。该源码只用于解释试验设计，不冒充本机 Chrome 精确源码。

最终保留 `.91` 正式 0/0 策略，撤回全部临时插件。恢复原 One-KVM 选择，以及 PiKVM
H.264、12000kbps、GOP30、60fps、JPEG 质量 80；配置文件与 EDID 哈希、HDMI 服务
运行实例不变。包文件校验、包审计、board check 通过，临时插件备份、浏览器、转发连接
和恢复定时器均已清理。弱网、长期稳定性及剩余帧间隔波动没有在本次解决。
证据：`logs/pikvm-playout-release/`，包括完整逐秒数据、包头探针与所有失败轮次。

## PiKVM 软件端到端基线与候选筛选

2026-10-16 开始按 [统一验收协议](latency.md#优化指标与验收协议) 测量源端绘制到
浏览器合成器提交，不能与前一节的接收缓冲数值混用。初筛使用 `.91` 的正式
编码/Janus 基线、Chrome 155、4K60/H.264、12Mbps、GOP30、音频开启、有线 IPv4。
每轮先启动三带 ID 运动图案并预热，采样 120 或 130 秒；未并行编译。

| 初筛配置 | 样本数 | 端到端 P50 / P95 / P99，ms |
|---|---:|---:|
| 原版 | 996 | 69.72 / 74.75 / 80.86 |
| 编码帧到达即唤醒发布循环 | 1036 | 67.27 / 71.73 / 75.68 |
| 回切原版 | 1086 | 70.86 / 75.47 / 81.11 |
| 仅保留采集 PTS 并用于 RTP 时间戳 | 1026 | 72.45 / 78.39 / 83.73 |
| 仅按需 JPEG 编码，含截图完成通知 | 1012 | 73.78 / 79.90 / 86.42 |

这些轮次均无统计丢包、丢帧、freeze 或不一致标记；第一轮有效样本不足 1000，
其 P99 仅列为诊断值。源端与浏览器 context 每轮重新建立，存在时序相位差异，
不能据此直接宣布几毫秒的因果收益。后两项没有显示出更好的端到端结果，未作为
正式优化采用。时间戳候选在网线上的视频间隔为 1479–1524 RTP tick、中位数
1500；时钟更规整本身不等于浏览器呈现更快。

三带像素回读单次约 27–28ms，会扰动回调。在不回读像素的独立 120 秒运动测试中，
原版、时间戳候选、按需 JPEG 候选的呈现间隔 P99 分别为 32.8、36.2、35.3ms，
最大间隔为 72.0、49.7、50.9ms，均无统计丢包、丢帧或 freeze。
记录 presentedFrames 跳号与观测窗口结束前的无回调时长，避免将回调漏采写成
视频丢帧，或只用卡死前的成功帧计算 FPS。

按需 JPEG 初版在重新连接时因 JPEG 分支未完成 preroll 而阻塞整条管线；
JPEG appsink 设置 async=false 后，MJPEG/WebRTC 切换、参数调整与刷新通过。
硬件 JPEG 中断计数在没有 JPEG 客户端时保持不变，但这只是闲置工作减少的证据，
不是端到端收益。该实验保留在忽略的构建目录，不改变正式采集策略。

另确认一个独立缺陷：VIM4 发布新 JPEG 后没有像普通 JPEG worker 那样减少
snapshot_requested，截图只能等待 HTTP 超时。三次 4K 截图原为
3041.5 / 3031.7 / 3028.0ms；补齐完成通知后为 64.8 / 61.8 / 46.2ms，
均返回有效的 3840×2160 JPEG。这是截图响应改善，不是 WebRTC 视频延迟降低。
PiKVM smoke 已增加截图响应门禁。

全部初筛、失败准备轮次、构建产物与原始日志保留在 `logs/pikvm-e2e/`。

### 保持源端连续的 A/B/A 复核

同一个 HDMI 图案进程连续运行，三轮各测量 130 秒；每轮重新连接并预热，
只切换发布循环，三轮都含相同的截图完成修复。结果如下：

| 轮次 | 有效样本 | 端到端 P50 / P95 / P99，ms |
|---|---:|---:|
| A：固定轮询 | 1003 | 76.27 / 82.03 / 89.21 |
| B：帧到达唤醒 | 1056 | 73.13 / 78.01 / 85.79 |
| A：回切固定轮询 | 1064 | 74.07 / 80.38 / 84.85 |

三轮均零统计丢包、丢帧、freeze，样本数均超过 1000。B 的 P50 比两次 A
的均值低约 2.04ms，小于 A 自身的 2.21ms 波动，也未达到 3ms 门槛；B 的
P99 没有优于回切 A。因此在一组完整 A/B/A 后停止该候选，没有把它提交为
正式优化，也没有声称完成三组配对或 30 分钟同连接耐久验收。

原计划的后续窗口在准备阶段主动取消；`paired3-a1/b1/a2` 是完整测量，
`paired3-b2` 是取消记录。之前 `paired` / `paired2` 未进入有效采样：分别
遇到登录启动竞争和 Node 局域网请求 EHOSTUNREACH。接收工具改为在专用 Chrome
中等待认证后端就绪并登录，短验证与完整 A/B/A 已通过；这些准备失败不混入延迟分布。

当前正式视频策略保持不变，截图修复独立提交。以上数据既未达到端到端 P50
≤60ms 的目标，也不能证明物理延迟极限；进一步优化仍需分离源端绘制/扫描、
采集、编码与呈现各段，以及减少像素回读对接收机的干扰。

## KVM 播放延迟复核（2026-10-15）

以下保留最初的源码审查结论，当时没有切换板上应用或复现其他 KVM 的运动场景。
后续实测、已修复项与限制见 [跨 KVM 运动播放](bringup/2026-10-15-cross-kvm-motion-playout-backlog.md)。
播放策略因果对照见本文前节；本节补充同步、队列与媒体时钟的未决风险。
已上板验证的 One-KVM 修复及测量见 [One-KVM 低延迟播放](bringup/2026-10-15-onekvm-low-latency-playout.md)。
下面区分确定的实现行为与尚未测量的用户可见影响；不能据此宣称其他系统已修复或全部正常。

| 仓库 | 审查提交 | 结论 |
|---|---|---|
| NanoKVM | d009b346 | 音视频独立连接，不具备相同的跨轨同步条件；音频丢包时间未保留 |
| kvm / JetKVM | 390d7e98 | 开启音频时音视频同为 `kvm` stream ID，具备旧 One-KVM 的同步等待条件 |
| kvmd / PiKVM | 3aa6bc21 | Direct 模式解码输入没有显式积压上限 |
| ustreamer / PiKVM | 9baf264c | 插件 SDP 音视频分组独立，但视频使用发送时间、音频队列丢包未保留时间 |

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
