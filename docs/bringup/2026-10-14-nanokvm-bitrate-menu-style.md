# 2026-10-14：NanoKVM 码率菜单样式修正

NanoKVM `a0c9574` 清除新增档位按钮的浏览器默认背景、边框与字体，
继承原菜单样式，滑块区域缩至 180px。VIM4 前端构建和码率浏览器回归通过。
完整 `.14` 包校验及部署通过；Chrome 实机检查确认透明按钮背景、无边框、
继承菜单文字颜色和字体，深色主题截图符合原菜单风格，视频正常播放。
当前设备码率为用户设置的 30 Mbps，刷新后恢复；测试未写入码率。
证据：`logs/nano-style-{release-build,package,verify,deploy,browser}.log`、
`logs/nano-style-deployed.png`。
