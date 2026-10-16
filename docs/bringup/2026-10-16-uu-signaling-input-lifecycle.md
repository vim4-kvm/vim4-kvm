# 2026-10-16：UU 信令与输入生命周期更新部署

- One-KVM `e41303d1` 以干净源码构建单组件包
  `2.5.1+vim4.20261016.112`，通过 board.py deploy 安装，替换原 `.110`。
  主仓库构建来源 `c5590bb`；沿用正式构建配方并复用 Cargo 缓存。
  改动包括 Engine.IO 心跳超时重连、输入发送与关闭释放串行化、拒绝旧会话迟到输入，
  以及只声明当前协商编码的 CodecNegotiation 初始化消息。
- 构建通过 615 个 Rust 测试、65 个主仓库测试、18 个 Linux 部署助手测试、
  网页和 ARM64 release 构建。包隔离验证通过，包含配置保留、升级 API、安装与重启。
- 板上 One-KVM 与管理器 active，8080 HTTP 200，UU 信令重连后首次续期
  `success=true`；服务 `NRestarts=0`，`dpkg --verify vim4-onekvm` 和 `dpkg --audit`
  无输出，board.py check 通过。安装后的即时探测曾早于 8080 监听，随后复核正常。
- 其他组件保持原版本；boot ID 仍为 `9ac9de0a-1b7f-44fe-934e-c9d8e40ed5d0`，
  USB 为 configured。本次未重新绑定 UU 账号，未重启系统；部署前 LUN 为空。
  更新后尚未完成官方客户端画面、音频、HID 和真实断网恢复验收；部署前的连接日志
  不作为新版功能通过证据，输入竞态及编码能力约束目前由离线测试覆盖。
- 证据：`logs/one-kvm/uu-deploy-package.log`、`uu-deploy-verify.log`、`uu-deploy112/`、
  `uu-postcheck112/` 和 `uu-current-service112.log`（均在 `logs/one-kvm/` 下）。
