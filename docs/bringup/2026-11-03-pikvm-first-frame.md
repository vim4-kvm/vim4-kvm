# 2026-11-03：PiKVM 首帧拆段与冷启动口径

原 8169 ms 包含 6316 ms 的 HTTP 启动等待，HTTP 200 后 1853 ms 已解码。
三轮复测冷切换为 8166–8243 ms，已启动服务的新页面为 639–703 ms。
关键帧探针确认首个编码帧为 key，按需请求有效。本轮未复现需要修改产品代码的
首帧回归，保留现有持久安装。最终恢复 One-KVM、H.265、Custom 40000 kbps 并验证网页解码推进。

## 历史证据校正

原始 `logs/mainline-merge/jetfirst-verified/pikvm-first.json` 的 started 为
1793704699662，firstMs 为 8169。对应 navigation 记录先出现 3 次 502、20 次 500，
到 1793704705978 才完成成功导航。6316 ms 占总计约 77.3%，余下 1853 ms 包含
Janus 协商、接收和解码。历史事件没有逐项时间戳，无法进一步追溯精确拆段。

该脚本先调用 loginManager，再开始计时，因此 8169 ms 排除了登录请求与
`/api/select` 请求本身，却包含 select 返回后剩余的服务启动时间。
nginx 日志显示 500 源于 `/auth_check` 连接尚不存在的 `/run/kvmd/kvmd.sock`，
此时 nginx 已启动，kvmd 后端还在初始化。HTTP 200 也不代表编码管线已准备好。

旧记录的 codecId 和 SDP 为 H.265/Main10，不能直接归因近期 AVC GOP 默认值变化。
10 月 18 日的 3.3–6.2 s 属于 One-KVM/NanoKVM/JetKVM 切换测试，PiKVM 只记录了
H.265 4K60 成功，没有给出首帧秒数，不能作为 PiKVM 的历史回归基线。
见[原验收](2026-11-03-mainline-modules.md)与[统一登录记录](2026-10-18-unified-auth-gateway.md)。

## 环境与方法

主仓起点 `2b7f39d`，文档工作树从 origin/main 创建，分支 pikvm-first-frame。
源码工作区为 kvmd `3c2687fac215`、uStreamer `4cc24074`、gst-plugin-venc `f6a23c5dd9ac`。
运行内核 `7.3.0-vim4kvm-uhd7+`，沿用前次模块部署，未更换内核或用户态程序。
板上日志明确使用 `/opt/vim4-kvm/hdr10-r14e/ustreamer`，参数 desired-fps=60、
h264-bitrate=12000、h264-gop=0，持久 codec 文件为 h265。
实际 uStreamer SHA256 为 `9d9a568dfe65d0378791a7272b188a9953ba3fe9dba347049032a64a53f25e34`，
Janus 插件为 `0865af4948dc1e2d1b7b3ec393b858a7db9e67db150d7e10199208af7395e99d`。
未重新验证全部已部署插件与源码提交的对应关系。两次附加哈希读取使用了不存在的
默认 uStreamer/config/plugin 路径，原始错误保留，随后从运行日志确认并读取实际 uStreamer 路径。

同一台 Mac 的独立 Headless Chrome 156.0.8078.80，经 SSH 转发访问管理器 80 和网关 8080，
RTP 使用浏览器协商路径。Janus 沿用 regular nomination 与 IPv4/IPv6。
每次新建浏览器 context，登录后加载真实产品网页。测试 Chrome 使用既有接收工具的
禁用 mDNS 隐藏参数，未修改生产网络。三轮均 One-KVM→PiKVM 冷切换，随后立即新开
PiKVM 页面测服务已启动状态，再恢复 One-KVM。六轮同一持久编码配置。
冷/暖差异用于解释计时口径，并非产品修复前后的收益比较。

HTTP 非 200 每 250 ms 重试，完成成功导航记 ready。这个边界包含成功页面加载，
是后端可用时间的上界。WebSocket 记录 Janus create/watch/offer/start/key_required，
浏览器记录 ICE/peer 状态和首个视频呈现回调。getStats 目标每 20 ms 轮询，实际
浏览器统计更新与调度使首次观测有数十毫秒误差。first 表示首次观察 framesDecoded>0，
不能当作精确解码完成时刻。登录独立记录，未计入导航首帧列。

## 三轮原页面结果

以下均为 ms。Janus offer 一列是 watch 发出至收到携带 offer 的 event。

| 轮次 | 登录请求 | 导航→HTTP ready | watch→offer | ICE checking→connected | ready→首次解码观测 | 导航→首次解码观测 |
|---|---:|---:|---:|---:|---:|---:|
| 冷 1 | 285 | 6270 | 1483 | 50.3 | 1973.2 | 8243.2 |
| 冷 2 | 352 | 6386 | 1471 | 61.1 | 1846.9 | 8232.9 |
| 冷 3 | 331 | 6157 | 1596 | 58.7 | 2008.6 | 8165.6 |
| 暖 1 | 297 | 58 | 5 | 64.4 | 580.9 | 638.9 |
| 暖 2 | 271 | 120 | 5 | 53.8 | 583.3 | 703.3 |
| 暖 3 | 286 | 99 | 5 | 63.3 | 574.4 | 673.4 |

ready 后约 93–139 ms 发出 Janus create，create→success 约 1–3 ms。
冷启动额外等待集中在 HTTP 可用前，以及 watch→offer。后者未加服务端内部计时，
尚不能把整段归因某一个 Janus/GStreamer 初始化函数。

六轮首个解码统计均有一个关键帧，三秒观察新增 180/180/181/181/181/182 帧，
尺寸均为 3840×2160，framesDropped、packetsLost、freezeCount 增量为零。
暖 2 在首帧时 pliCount=1，其余为零，后续均无新增 PLI。
GOP 0 下仍可快速接入，现有数据不支持等待周期 GOP 或关键帧请求失效这一原因。

## 接收、关键帧与呈现探针

另一个窗口为浏览器 RTCPeerConnection 开启 encodedInsertableStreams，
接收 TransformStream 只记录首次帧及首次 type=key 的时间并原样传递。
这一窗口用于定位，不混入上表六轮无编码帧探针结果。下表相对导航开始计时。

| 边界 | 冷启动 ms | 服务已启动 ms |
|---|---:|---:|
| HTTP ready | 5963 | 56 |
| Janus create | 6076 | 147 |
| Janus watch | 6089 | 155 |
| ICE checking | 7732.8 | 166.1 |
| ICE connected | 7796.6 | 216.7 |
| Peer connected | 7801.1 | 287.1 |
| 网页发送 key_required | 7803 | 290 |
| 首次观测 RTP packetsReceived>0 | 7881.2 | 631.1 |
| 首个编码帧，type=key | 7888.5 | 637.2 |
| 首次呈现回调 | 7945.7 | 689.3 |
| 首次观测 framesDecoded>0 | 7947.3 | 696.9 |

两轮首个编码帧即关键帧。请求→关键帧分别约 85.5/347.2 ms，
关键帧→首次呈现约 57.2/52.1 ms。RTP 首次统计是收包的上界，无法由 getStats
恢复第一个 UDP 包的精确到达时间。首次呈现早于统计首次更新属不同观测边界，
不能把两者相减当作解码延迟。本轮没有采用 ptrace/strace。

## 恢复、预算与交付

所有窗口经 tools/board-queue，性能窗口开启 sampling，阻止 heavy 构建重叠。
FIFO 719 票据 `95fb4ddc19074d169ef47c8d81fa065d` 持板 101.317 秒，
FIFO 724 票据 `3ebab5ba6d674187bfb4c379748bd79c` 持板 45.595 秒。
FIFO 727 只读身份窗口持板 0.568 秒，累计 147.480 秒，含每轮恢复，低于 30 分钟。
板票、sampling 和本次 SSH 转发均释放。

最终管理器 active=onekvm，`/api/stream/mode` 为 h265，
`/api/config/stream` 为 Custom 40000。最后网页三秒新增 180 个解码帧，3840×2160，
四项服务 one-kvm/manager/HDMI/gadget 为 active，UDC configured，采集的内核日志
无 WARN/Oops/BUG/Call trace。源端沿用现有低运动桌面，未发送 HID，未改 M6 或 M4。
本轮验证解码推进，没有独立运动图样的内容更新验证，也未测音频、光学端到端延迟或长期稳定性。

无需产品修复，因此没有子仓改动、候选部署或产品修复前后 A/B。本轮只提交调查记录、
索引及原 issue 的结论链接。后续若优化冷启动，应先在 kvmd 后端初始化和 Janus
watch→offer 两段做独立计时，现有证据不足以选择具体产品改动。

原始证据在主工作区忽略目录 `logs/pikvm-first-frame/`，包括 measure.mjs、两个窗口脚本、
cold/warm/restore 的 JSON 与 PNG、probe 子目录、服务日志及最终配置。
主仓离线 `python3 -m unittest discover -s tests -p 'test_*.py'` 通过，
489 项、15 项跳过，24.850 秒；文档专项 8 项通过，git diff --check 通过。
交付结果文件为 `/tmp/herdr-workers/pikvm-first-frame.result.md`。
