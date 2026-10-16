# 2026-10-15：UU H.265 出画面与周期性发送阻塞

用户逆向定位官方客户端 H.265 tracker 的 AP 起始偏移错误：从第二个头字节
开始读长度，丢弃包含 VPS/SPS/PPS 的 AP，关键帧因此无法进入解码。
`3873af30` 将参数集改为独立单 NAL 包，保留 CRA 分片及 marker 回归；605 项
Rust 测试、ARM64 发布构建及完整安装包验证通过。`.11` 上板后用户确认出画面，
官方 UU 4.39.1 的 H.265 会话回报 decode/render 59fps、decode 2ms；板端约
60fps。此前离线解包器和 VideoToolbox 检查没有经过 tracker，不能替代真实链路。
制品：`build/packages/2.5.1+vim4.20261015.11/`，deb SHA256：
`d2d8b19233f66cce61d2ee1f943b598c2cfdede84e53d294e2a56fb9e06e4345`。
证据：`logs/uu-remote/hevc-single-nal-{tests,release,package-verify,deploy,session}.log`。

用户随后确认每秒周期性停顿。相同会话为 3840×2160、60fps、20Mbps H.265，
本地千兆有线 IPv6。只解析板端出站 RTP 包头的 15 秒采样得到 901 个时间戳、
零序号缺口；每秒一次的大帧约 927KB、820–821 包，发送跨度 36.36–41.88ms，
超过 60fps 的 16.7ms 帧间隔。温度约 53℃，不能用平均 60fps 判断连续流畅。
证据：`logs/uu-remote/srtp-before-packets.log`。

当前 SRTP 包的 10 字节认证尾部与 AES-CM/SHA1-80 一致。锁定的 aes 0.8.4
和 polyval 0.6.2 默认未启用 ARM 硬件后端。在同板 core 7 上，对 817 个
1100 字节有效载荷包进行 Context 加密基准，软件 AES-CM 约 20.3ms，开启
aes_armv8 后约 6.1ms，首尾包解密校验通过。该基准隔离加密成本，不能代替
完整发送或端到端延迟。证据：`logs/uu-remote/srtp-probe{,-crypto}-board.log`。

`e0ff58c0` 启用 RustCrypto 的运行时 ARM AES/PMULL 后端，605 项测试、发布构建
和完整包验证通过，`.12` 于 05:18 UTC 上板。但实际抓包仍为 35–40ms，未修复
停顿。随后核对 Cargo feature 发现正式程序的 SRTP 启用了 vendored-openssl，
最初的独立基准未复现此配置；不能把该基准归因为正式程序的瓶颈。补齐 feature
后 AES-CM 的 817 包加密在 core 7/0 上分别约 6.0/4.6ms，解密校验通过。
大核组及单核 affinity 对照均未改善，全部线程已恢复 CPU 0–7；单核抓包还出现
4 次序号不连续，不能作为正常配置数据。8 秒 strace 会显著扰动时序，仅用于
系统调用分布，不能当作延迟验收。perf 工具仅解包至 /tmp，未安装系统包。
证据：`logs/uu-remote/srtp-{crypto-build,crypto-package-verify,crypto-deploy,
after-packets,probe-openssl-board,big-core-packets,single-core-packets,perf-stat}.log`。

用户提供的 uu-remote-linux issue #8 是 libx264 的 VBV 太小导致周期灰帧，
与本次硬件 H.265 路径不同，未套用其增大 VBV 的修复。
独占编码对照使用相同 HDMI 桌面、20Mbps、GOP60、60fps，每档 240 帧，只记录
大小、不保存画面；结束自动恢复 One-KVM。默认 I 帧从 260KB 增至 596KB；
QP 下限 20/24/28 时周期 I 帧分别稳定至约 471/361/275KB。短时独占实验
不能证明长期画质、运动场景和接收端连续流畅。证据：
`logs/uu-remote/hevc-qp-probe.log`。

`64d0931a` 在 VIM4 H.265 管线设置 `i-qp-min=28`，限制静态桌面的周期 I 帧
质量继续升级；保留现有 GOP、P 帧码控、帧率和分辨率。该限制可能影响 I 帧细节，
尚需用户检查文字画质。605 项 Rust 测试、ARM64 发布构建、完整安装包验证
（含实际升级、配置保留和认证更新 API）通过。`.13` 于 05:35 UTC 上板，
service active、HTTP 200、dpkg -V 无差异、UU host online，保留 H.265 配置。
制品：`build/packages/2.5.1+vim4.20261015.13/`，deb SHA256：
`bdc9c396f0dc815d470668b4921dfd3bee1b7762e0f585fa7e28d43e566e7be0`。
证据：`logs/uu-remote/hevc-keyframe-{build,package-verify,deploy,health}.log`。

`.13` 用户反馈仍有周期停顿，因此未通过验收。抓包显示周期帧已缩至约 284KB、
发送跨度 10.8–12.8ms，但起始间隔仍约 23ms，完整帧完成间隔达 33.8–35.8ms；
只把发送耗时降到 16.7ms 以下不足以保证 60fps 连续呈现。客户端平均 decode/render
仍为 59fps，不能否定用户观察。证据：`logs/uu-remote/hevc-keyframe-frame-gaps.log`。

进一步独占对照，每组 480 帧，在第 240 帧主动请求 IDR：H.265 的 GOP 0/-1
均只在启动和主动请求处产生完整关键帧。GOP 0 加 `intra-refresh-rows=1` 时约
60.03fps、帧间隔 p99 17.19ms，主动 IDR 期间最大 23.51ms，实际约 19.84Mbps
（目标 20Mbps）；无行刷新时同一桌面约 10Mbps。保留厂商 QP 范围，避免用
降低关键帧画质继续压缩突发。独立录制的 480 帧经 ffmpeg `-xerror` 全部解码，
退出码 0；临时码流验证后删除。行刷新不替代接收端丢包恢复验证。
证据：`logs/uu-remote/hevc-refresh-{probe,decode}.log`。

`a8aa1869` 改为 VIM4 H.265 `gop=0 intra-refresh-rows=1`，撤掉 `.13` 的 QP
限制。605 项 Rust 测试、发布构建及完整包验证通过，`.14` 于 05:45 UTC 上板，
service active、HTTP 200、dpkg -V 无差异、UU host online。官方客户端重新连接
H.265 4K60/20Mbps，稳定窗口发送约 60fps，客户端 decode/render 59fps、decode
2ms、current/target delay 12–13ms。多个稳定窗口最大发送约 3.3–3.6ms，原先
每秒一次的大帧突发不再持续出现；但长采样仍发现偶发约 752KB 的大帧，发送
29ms、完整帧完成间隔约 59ms，不能宣称完全无顿挫或长期验收通过。短时 GStreamer
force-key-unit uprobe 记录了主动关键帧事件，尚未逐一关联请求来源；探针已移除。

05:50 UTC 的恢复实验只针对探测到的媒体 UDP 流，以 OUTPUT DROP 持续约
359ms，实际拦截 5 包，但本机返回 EPERM，导致该 UU 会话音视频发送任务退出。
这不是有效的网络丢包模拟，**丢包恢复验证未通过，不能记录为自动恢复成功**。
规则已删除，CPU affinity 已恢复，要求客户端重连；不把受干扰的 39fps 回报
当作正常运行指标。用户随后表示“应该差不多了，先提交”，本轮停止进一步实验。
未进行隔夜运行、其他客户端、完整端到端延迟或全新 Ubuntu 镜像刷机验收。

制品：`build/packages/2.5.1+vim4.20261015.14/`，deb SHA256：
`66da64e28df1d7ac6030622ee1a8140e55b1429e16ad1f75e6dd0fa359abf6b0`。
证据：`logs/uu-remote/hevc-refresh-{build,package-verify,deploy,health,session,
packets,steady-packets,key-requests,loss,recovery-packets}.log`。
