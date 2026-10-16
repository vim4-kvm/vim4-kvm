# 2026-10-14：NanoKVM 码率滑块部署

NanoKVM `d639e8f` 增加 1–60 Mbps 快捷档与 0.1 Mbps 步进滑块，
拖动结束提交，刷新从设备设置恢复自定义值。两种前端构建、浏览器模拟 API
回归（拖动只在释放时保存、刷新恢复、保存失败回滚）通过。

干净快照重新构建 NanoKVM 前端，原生二进制复用 `.12` 验证产物，生成
`2.5.1+vim4.20261014.13` 七组件包；隔离包验证与部署检查通过。
实机 Chrome 确认滑块和快捷档存在，刷新后恢复原来的 50 Mbps；未修改用户
视频参数，保持 NanoKVM 为当前应用，HDMI 服务 InvocationID 未变化。
部署后 H.264 WebRTC 3840×2160 采样 10 秒：600 帧、59.97fps，
零解码丢帧、零 RTP 丢包。此为播放冒烟检查，不代表运动场景或端到端延迟。
证据：`logs/nano-slider-{release-build,package,verify,deploy,browser,video}.log`、
`logs/nano-slider-deployed.png`。
