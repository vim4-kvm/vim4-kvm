# 2026-10-14：MJPEG 单帧耗时与 NanoKVM 分辨率菜单

在 `.20` 的编码路径上增加临时计时探针（只从 /tmp 加载，不安装探针插件），
保持 4K60 输入、Q80、666MHz 默认编码时钟和全屏运动网格。连续输入 300 帧，
队列允许丢弃积压帧，去掉起始 10 个输出后统计 238 个编码输出，平均耗时如下：
DMA 导入 0.016ms、命令提交 0.163ms、poll 等待完成 18.792ms、输出 ioctl
0.206ms、输出复制 0.803ms、释放导入 0.013ms。证据：
logs/mjpeg-hardware/profile-split.log、profile-motion-split.jsonl。

poll 包含硬件运行与中断/调度等待，不是纯硅片时延；但远大于 DMA/提交开销，
不能把每帧约 19ms 的等待归因于网页限帧。当前路径即使忽略其他开销也仅约 53fps，
尚未证明能稳定 4K60。驱动 jpeg_enc_clk_enable 对 T7 固定设置 666666666Hz，
其 clock_level 参数不改变这个分支；没有超频或修改内核。测试结束恢复 NanoKVM。

NanoKVM e3dbe78 删除采集分辨率菜单遗留的 MJPEG 10fps 显示上限，按配置 FPS
显示（自动时为 60），保留原样式及实际帧率说明，并修正流设置 API 文档。
前端需显式使用 VITE_PLATFORM=vim4；首次 `.21` 漏带参数，实机检查发现通用菜单，
随后重新构建 `.22`。通用构建检查不能替代 VIM4 菜单实机验证。
`.22` 组件校验和部署通过，Chrome 实机打开采集分辨率菜单及刷新后，三个选项均
显示“最高 60 FPS”，保存设置仍为 4K、60fps、Q80、30000kbps。证据：
logs/mjpeg-hardware/nano-resolution-ui.log、nano-resolution.png、
verify-resolution-final.log、deploy-resolution-final.log。保留当前 NanoKVM 选择、
disk.img 挂载和 HDMI 服务运行实例。
