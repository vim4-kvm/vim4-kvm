# 2026-10-15：PiKVM H.265 菜单与 Direct 实板部署

用户授权后，将 kvmd `0eb559c7` 构建为 `2.5.1+vim4.20261015.50`，经隔离包校验和
board.py deploy 安装；PiKVM 从 `.41`、配套管理器从 `.49` 升级到 `.50`。管理器使用
当前工作树，保留概览趋势、事件及风扇功能；其他组件版本不变。未重启板子，HDMI 服务
InvocationID 始终为 `3b6f4877c9184fc2b99525504ede4a06`。部署后服务检查、dpkg audit 通过。

Chrome 155 经 localhost SSH 转发访问，依次选择 WebRTC H.265 → Direct H.265 →
Direct H.264 → WebRTC H.264 → WebRTC H.265，每种模式均实际解码 3840×2160，
采样中帧数持续增加；WebRTC getStats 分别确认 `video/H265`、`video/H264`。
Direct H.265 短窗口显示约 59 dyn.fps，刷新后 WebRTC H.265 继续播放。编码切换期间
kvmd PID 41737、监督进程 PID 41687、HDMI InvocationID 均未变，认证接口持续可用。
最终保留 H.265 编码。Direct 需要 HTTPS 或 localhost 安全上下文；普通局域网 HTTP
不因此获得 WebCodecs 能力。本次未测试音频、键鼠实际输入、长时间稳定性和端到端延迟。

安装启动窗口曾出现 8080 未就绪及认证上游 500，服务就绪后部署检查通过。日志中的
`Can't parse streamer features` 在升级前 `.41` 也存在，属于系统信息探测，未在本次修复；
本次四种模式解码验证通过，不将其计为无错误日志验收。
证据：`logs/pikvm/deploy50/`、`logs/pikvm/h265-deploy50-browser.log`、
`logs/pikvm/h265-deploy50.png`；构建与校验产物：`build/packages/2.5.1+vim4.20261015.50/`。
