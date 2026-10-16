# 2026-10-15：UU 输出设置与缩放吞吐检查

参照本地 uu-remote-linux 的 CaptureSetting 协议，补齐合并设置与单独帧率、
尺寸命令、自定义码率同步。原实现收到帧率/尺寸请求会回复成功但不调整输出。
现在等待新编码帧确认设置生效，再回复成功；失败不发送虚假成功响应。
帧率限制 5–60 且不超过输入，尺寸等比例缩小、偶数高度 180–2160、不放大，
码率限制 1000–60000 kbps。自动画质恢复连接开始时的默认码率，不是网络 ABR。
设置作用于共享管线且不持久化；重新建立编码管线不替换媒体订阅和连接。
底层控制和硬件回归测试提交为 One-KVM `3386f73f`；UU 模块仍保留在用户原有
未提交工作树中，本次打包不代表该工作树已成为干净可发布版本。

VIM4 feature 的 593 项 Rust 单测、release 构建通过。普通 Rockchip 目标在当前
Ubuntu 构建器缺少 RKMPP FFmpeg API，未通过，不能当作跨平台验证结果。
独占硬件运行 release 集成测试，4K60 输入，连续八组设置切换均成功产出码流，
记录尺寸与目标码率正确，全部录像用 ffmpeg 软件解码无错误。2 秒窗口输出为：
1080p30/2Mbps 31.30fps、720p15/8Mbps 15.50fps、1600×900@24/12.5Mbps
24.83fps、4K60/20Mbps 59.99fps、1080p60/60Mbps 35.05fps、
1080p60/2Mbps 35.18fps、720p60/8Mbps 39.52fps、4K60/4Mbps 60.08fps。
短窗口包含起始关键帧，低帧率统计略高于设定上限。码率是编码器目标，
没有用静态画面文件大小宣称输出必须等于目标带宽。

缩放 60fps 未通过吞吐验收；调试版与优化版、避开 CPU0 对照均复现，
GE2D 后加独立队列的额外实验仅约 40.7fps，未纳入生产改动。
测试通过只表示设置切换、编码和帧率上限行为正确，不表示缩放达到 60fps。
证据：`logs/uu-remote/settings-hardware-release.log`、`settings-decode.log`、
`settings-scaling-queue.log`；仍需 UU 官方客户端菜单操作与长期观看验收。

单应用开发包 `2.5.1+vim4.20261015.3` 已部署，SHA256 为
`d7da6851aa5a50b6426cc944d95ea9b169b26b9e13c0a3b5b0984dba55c8bb5f`。
沿用其余 `.2` 包组成隔离验证集合，完整 verify.sh 通过，包含真实 dpkg 升级、
配置保留、同版本/降级拒绝及认证更新 API。仅安装新版 One-KVM，保留板上
其他组件版本。重启后 active、首页 HTTP 200、dpkg -V 无差异，UU 主机在线并
保留登录，等待客户端重新连接。未重新刷写全新 Ubuntu 镜像。
包及源树摘要在 `build/packages/2.5.1+vim4.20261015.3/`；部署与校验证据在
`logs/uu-remote/settings-package-verify.log`、`settings-after-deploy.log`。
