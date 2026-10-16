# 2026-10-15：部署 One-KVM UU 远程开发版本

按用户要求部署其已增加 UU 远程支持的工作树。复用
`2.5.1+vim4.20261015.2` 开发包：重新计算 One-KVM 全部已跟踪和未跟踪源码
摘要，与 sources.json 中 `b775d90fbc26713861bb7799a1c96d23fd711edb312cc260dc98244e76fcd794`
一致，全部制品校验和通过。已有构建记录包括 589 项 Rust 测试、release 构建、
隔离包验证和真实单应用升级测试通过；源码尚未提交，不能表述为干净发布包。

整组件安装会触发现有管理器 `.41` 到 `.2` 的降级限制，因此改用已安装的
`vim4-onekvm-update` 限定助手，仅安装 One-KVM deb。助手验证 SHA256、包元数据、
升级版本和 APT 计划，完成后核验安装文件。保留 manager 与 PiKVM `.41`，
通过 `vim4-manager-helper select onekvm` 切换当前及开机默认应用。
One-KVM active/enabled，PiKVM inactive，首页 HTTP 200，未认证 UU 状态接口
HTTP 401，sudo dpkg -V 与 board.py check 通过。现有账户和数据保留，
尚待网页登录、视频和 UU 官方客户端扫码绑定后的端到端验证。

切换前停止 PiKVM 两端采样，保存到 `logs/pikvm/overnight/board-until-onekvm.jsonl`
及原 browser JSONL。实际浏览器只记录约 10 分钟，板端约 17 分钟；本轮未完成
12 小时观察，不能按日志文件存在或墙钟间隔算作隔夜通过。
部署证据：`logs/uu-remote/install-single-20261015.2.log`、`select-onekvm.log`、
`board-check.log`；复用构建证据为同目录 `test.log`、`release.log`、
`package-2.5.1+vim4.20261015.2.log`。
