# 2026-10-14：JetKVM 码率控件部署

JetKVM `9faf1c5` 将码率预设、0.1 Mbps 滑块和精确 kbps 输入合并，
采用原生下拉框、滑块轨道和保存按钮。浏览器回归覆盖同步、显式保存、
刷新恢复、保存失败回退、非法边界和保存按钮文字。干净快照前端构建、
ARM64 构建及内部 Go 测试通过，最终 `.16` 七组件包校验与部署通过。

实机 Chrome 将 12 Mbps 改为 17.6 Mbps，保存并刷新确认，再恢复 12 Mbps；
配置文件确认 factor=1。最终版 3840×2160 视频采样 10 秒约 60.06fps，
零解码丢帧、零 RTP 丢包。保留当前 JetKVM 选择，HDMI 服务未重启。
`.15` 截图发现旧控件以 children 传递按钮标签而组件只读取 text，已在
`.16` 修正并补充可见标签检查。未测试长期运动场景或端到端延迟。
证据：`logs/jet-bitrate-final-{build,package,verify,deploy,browser}.log`、
`logs/jet-bitrate-deployed.png`。
