# 2026-10-15：UU 连接初期体感延迟诊断

用户报告连接初期延迟偏高、随后下降，截图为连接第 6 秒、UDP P2P、60fps、
56 ms frm.、0% loss；frm. 的确切统计口径尚未确认，不能视作网络 RTT。
当前连接为 3840×2160、60fps、20Mbps，握手约 46ms；单次 UDP 发送队列采样
为空、温度 54°C，不据此排除瞬时积压或客户端缓冲。UU 使用发送时刻预测 RTP
间隔，网页 H.264 使用帧 PTS，列为待测差异，尚未修改时间戳或队列策略。

One-KVM `9c251763` 增加 STREAMER 客户端回报的数值白名单解析（含压缩 JSON），
仅记录帧率、延迟和计数；限制负载大小、解压大小、递归与节点数，不记录原始
负载、凭据或键鼠内容。发送端每 5 秒记录 FPS、发送耗时、帧间隔、序号缺口和
相对首帧 PTS 的积压变化；后者不是绝对采集延迟。

600 项 Rust 测试、ARM64 release 与完整包验证通过。诊断包
`2.5.1+vim4.20261015.7` 已部署，服务 active、HTTP 200、dpkg -V 无差异，
UU host online；等待客户端重连采样，尚未证明延迟根因或修复效果。
deb SHA256：`8e1effe270f0c22cd50510fc62e28d460281e78208752b41e813240e3a3520b5`。
证据：`logs/uu-remote/latency-{tests,release,package-verify,deploy,after-deploy}.log`。

03:07–03:08 UTC 用户反馈暂未复现。03:07:53 的 4K60/20Mbps 会话，板端
连续 5 秒窗口约 60fps，平均发送耗时约 0.35–2.01ms，窗口最大发送耗时可达
41.6ms，启动一次序号缺口后未继续缺帧。PTS 相对偏移约 -561ms 后稳定，
不能把这个负值当作负延迟或绝对采集耗时。客户端 30 秒回报 current delay
10ms、target delay 12ms、jitter buffer 2ms、decode 2ms、render 59fps；这些
不是完整操作到显示延迟，也不能证明启动前几秒从未偏高。
此前会话发送曾为 34–41fps 后回到 60fps，不能只保留恢复后的数据宣称始终稳定。
诊断版未修改视频发送策略，因此本次未复现不作为修复结论。证据：
`logs/uu-remote/latency-session.log`。
