# 2026-10-14：PiKVM 切入检查补漏

用户从已恢复虚拟磁盘的 NanoKVM 切入 PiKVM，prepare 因 LUN 非空拒绝启动；
旧管理器只检查 PiKVM 自己挂载的介质，已经停止并禁用了 NanoKVM。
管理器 `de596ac` 在 select/restart PiKVM 前检查任何现有 LUN，提前给出安全弹出
提示，保留原应用和开机选择。16 项助手测试通过；板上带原磁盘切换被拒绝，
NanoKVM 仍 active/enabled。macOS 安全 eject 后可正常切入 PiKVM。
修复以干净源码构建为 `.35`，隔离 verify 与 board.py deploy 通过。浏览器复测
3840×2160 WebRTC 持续出帧、JPEG 快照通过，最后保留 PiKVM active/enabled。
证据：`logs/pikvm/deploy-35/`、`logs/pikvm/entry-fix-smoke-35.log`。
