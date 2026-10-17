# 2026-10-17：UU 视频诊断统计部署

One-KVM `c679ae3d` 已部署，新增 RTCP 接收反馈和编码输出后的帧龄统计。
测量口径见 [One-KVM 集成](../../One-KVM/VIM4.md#uu-远程)；未修改发送节奏或关键帧恢复策略。

## 版本与验证

仅更新 vim4-onekvm，从 `.1022.dev.8.ga1d33bd` 升级至
`2.5.1+vim4.20261016.1022.dev.9.gc679ae3`。应用源码干净。
单组件构建原版本为 `.1016.dev.2.gc679ae3`，沿用上一部署的重编号流程，
使开发版本高于板上组合包基线；同步更新包版本、内置元数据、更新 feed 和校验和。
过程记录在 `logs/uu-video-metrics/renumber-package.py` 和 `renumber.log`。

- 打包流程通过 621 项 Rust 库测试、18 项部署助手测试、前端和 ARM64 release 构建。
- 重编号后的包通过隔离验证：校验和、动态依赖、sudoers、配置保留、真实升级、
  损坏文件拒绝及认证更新 API 检查。
- 经 `tools/board.py deploy --exclusive` 安装，未挂载虚拟介质。
  首次 HTTP 检查遇到启动窗口，后续复查 One-KVM 8080 和管理器 80 均为 HTTP 200。
- 10:33:50 UTC 复查：One-KVM PID 92850，两个服务 active；dpkg audit 无异常，
  USB configured/high-speed，HID 初始化成功，采集源识别为 3840×2160 NV21 60fps。
- UU signaling connected、host online，设备状态 ready。此时尚未验证新会话的
  RTCP/帧龄统计，也未测量客户端解码、输入手感或端到端延迟。

包内及板上二进制 SHA256 一致：
`e6ed4f75028afde176873d338e92a3e40e77591b54833717bc23411608679a3c`。
日志保存在 `logs/uu-video-metrics/`：`package.log`、`package-verify.log`、
`deploy/`、`pre-deploy.txt`、`post-deploy.txt`、`startup.log`。
