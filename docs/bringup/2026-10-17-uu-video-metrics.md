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

## 部署后实际会话

10:38:40–10:40:31 UTC，4K60、30000kbps 会话产生 22 个发送窗口和 23 份
RR 日志样本。RR 区间及累计丢包均为 0，NACK/PLI/FIR 均为 0；RTT 为
1.05–2.08ms，jitter 为 0.64–3.66ms。4 个 HID 窗口无溢出，最大排队 198µs，
USB 写入无 timeout/error。

首发送窗口为 55.89fps，包含启动等待；之后接近 60fps，sequence_gaps 全部为 0。
10:39:15 的窗口出现短时尖峰：编码后排队最大 39.822ms、发送调用最大 42.176ms、
发送完成帧龄最大 53.401ms。10:40:05–10:40:30 的后续窗口平均排队约 0.28ms，
最大不超过 0.761ms，发送完成帧龄最大 5.288ms。
这些数据未显示持续网络丢包或持续排队积压，但不能排除短时服务端停顿，
也不能证明客户端解码、显示或端到端延迟正常。
证据：`logs/uu-video-metrics/current-session.log`、`session-readable.log`。

## 会话面板部署

随后部署 One-KVM `d1263753`，版本
`2.5.1+vim4.20261016.1022.dev.10.gd126375`，将接收反馈和发送统计接入
「当前会话与链路」。无样本/未知 RTT 显示暂无数据，各类样本独立显示年龄，
超过 10 秒或轮询失败标记过期；断开连接隐藏旧统计，重新订阅清空发送窗口。

622 项 Rust 测试、前端和 ARM64 release 构建、18 项部署助手测试及组件包隔离
验证通过。浏览器以模拟数据验证空样本、未知 RTT、真实零丢包、负累计丢包、
样本过期、轮询失败、断线清除、中英文和手机布局；未使用板子账户执行此测试。

10:52:27 UTC 上板复查：应用 PID 94676，应用与管理器 active、HTTP 200，
USB configured/high-speed，HID 初始化成功，UU host online。
包内和板上二进制 SHA256 均为
`db2d7e8d72028532573c802ba277741bb2f89c133a991aa3f5dd585508f4bdf5`。
实际客户端重新连接后的面板数值尚待观察。
记录位于 `logs/uu-video-metrics/panel-*.log`、`panel-post-deploy.txt`、
`panel-desktop.png` 和 `panel-mobile.png`。
