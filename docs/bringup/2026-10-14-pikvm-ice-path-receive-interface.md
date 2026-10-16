# 2026-10-14：PiKVM 卡顿：ICE 选路与实际收包接口

继续定位时使用临时逐帧日志，比对 uStreamer 发布和 Janus 读取的时间戳。
有效连接窗口没有漏读；按 SSRC 抓取板端 RTP，7998 帧全部发出、序号无缺口，
最大帧发送间隔约 67ms。临时日志代码已移除，没有进入正式包。

Mac 的有线 en0 只有 IPv4，Wi-Fi en1 同时有 IPv4/IPv6。网页使用有线 IPv4，
浏览器 selected candidate pair 也报告远端 `192.168.50.210`，但对应 SSRC 的实际
视频几乎全从 en1 的 IPv6 收到；en0 只有少量探测包。该轮五次超过 100ms 的
画面间隔分别对应 139–213ms 的网卡收包空窗，画面恢复落后收包恢复约 12–23ms。
因此仅看网页 URL、ICE 统计或板端平均帧率，会漏掉这条无线媒体路径。

先临时关闭 Janus IPv6 做对照：视频走 en0，120 秒解码 7197 帧，零丢帧、零丢包、
零 freeze，最大画面回调间隔 50.1ms。随后恢复 IPv6，改用 `ice_nomination = "regular"`：
视频仍走 en0，120 秒解码 7200 帧，零丢帧、零丢包、零 freeze，最大间隔 33.5ms。
最终保留双栈，不修改电脑的网络配置。该观察说明本机双网卡场景下 aggressive
nomination 的媒体路径选择导致了剩余停顿，不代表无线网络自身的抖动已被修复。

kvmd `464a3558` 增加 VIM4 Janus 配置，主仓库 `7f53d27` 打包该配置并让隔离验证
启动实际安装的 Janus 配置；`.40` 构建、隔离 verify、board.py deploy 通过，
验证日志确认 regular nomination 生效。浏览器 soak 同时记录慢帧时间和 ICE 路径。
修正不需要额外 Janus fork；原 `.39` 镜像不含本次选路修正，应使用更新候选包。

证据：`logs/pikvm/h264-publish.tsv`、`h264-consume.tsv`、`h264-wire-trace.json`、
`h264-client-wire.log`、`h264-mac-en0.pcap`、`h264-mac-en1.pcap`、
`freeze-correlation.json`、`h264-ipv4-soak.log`、`h264-regular-soak.log`（同目录）；
`build/pikvm-package-40.log`、`build/pikvm-verify-40.log`、`logs/pikvm/deploy-40/`。

`.40` 正式包最终长测（3840×2160、60fps、12000kbps、GOP30，Mac 同时开启有线与
Wi-Fi，使用无缓存 Chrome 上下文）：H.264/H.265 各观察 300 秒，各解码 17998 帧，
两者 framesDropped、packetsLost、freezeCount、totalFreezesDuration 增量均为 0。
最大画面回调间隔分别为 33.5ms/50ms，P99 均约 33.4ms；H.264 窗口期间宿主还在
组装和压缩镜像。两种编码的独立运动检查各取得 8 个不同图像哈希；长测窗口本身
是桌面场景，不是持续高运动或 WAN 性能保证。H.265 额外复测音频峰值 0.16226、
键鼠、ISO 主机读取/eject、4K MJPEG 切换、设置保存与刷新，全部通过。
`dpkg -V vim4-pikvm` 无差异，临时诊断程序已被正式包替换；最终保持 PiKVM
active/enabled、H.265 开启、虚拟介质未挂载。整机 check 通过。
证据：`logs/pikvm/h264-final-40.log`、`hevc-final-40.log`、
`stability-summary-40.json`、`hevc-final40-route.pcap`（同目录）、
`logs/pikvm/final-state-40/`。

同步导出包含修正的 `build/images/vim4-kvm-ubuntu-pikvm40/`，配方 `7f53d27`，
默认 PiKVM/H.264。只读离线验证、压缩包/原始镜像校验和 flash dry-run 通过；
尚未擦除 eMMC 或进行新镜像首次启动。用户要求优先解决画面卡顿，当前完成的是
现有系统正式包上板回归与新镜像准备，不能将其表述为已通过刷机验收。
