# 2026-10-16：共享数据盘管理与四套 KVM 目录部署

- 管理器新增 `#/disks`：FAT32 多数据盘、文件上传下载与目录操作、卷标、检查、快照恢复、
  原始镜像下载及安全扩容。已连接的盘禁止管理端写入；扩容和恢复先生成完整临时镜像，
  再在共享锁内原子替换。当前支持 FAT32，不含 exFAT。
- 四套 KVM 使用板级共享目录与统一介质锁，能列出其他应用镜像和数据盘；
  他处挂载的介质保留所有权保护。平台包提供 `vim4-media-api-1`，应用显式依赖此接口。
- 干净源码构建部署七组件 `2.5.1+vim4.20261016.110` 和 PiKVM 应用 `.111`。
  源码：主仓库 `cdf5352`，管理器 `9390ea5`、NanoKVM `d58501d`、JetKVM `c8c5390`、
  One-KVM `a8f245b`、PiKVM `89e5a5c`。部署使用主仓库 `7688cef` 的安装脚本，
  只允许内容仍符合旧包 Conffiles 校验和的 sudoers 随新版升级。
- 包隔离验证通过；完整构建中 One-KVM 612 个 Rust 测试通过，管理器助手 55 个测试通过。
  板上 `dpkg --verify` 八组件无差异，`dpkg --audit` 无输出；One-KVM 与管理器服务正常，
  8080 HTTP 返回 200。安装后第一次即时探测曾遇到应用尚未监听，随后复核恢复正常。
- 实机创建临时 64 MiB 盘，四个应用助手均列出该盘；上传含中文文件名的 2 MiB 二进制文件，
  扩容至 96 MiB、再恢复快照至 64 MiB，两次下载均逐字节一致，文件系统检查通过。
  测试盘和快照已删除。网页桌面与 390px 移动视口可用，无水平溢出。
- 部署前后均为 One-KVM，原有可写 `disk.img` 路径、512 MiB 大小、inode `45826:130812`
  和 LUN 属性不变，USB 为 configured；boot ID 保持
  `9ac9de0a-1b7f-44fe-934e-c9d8e40ed5d0`。应用部署有服务重启，未重启系统。
  为保留现有可写盘，未切换四套应用逐一验证网页挂载，也未做被控电脑文件系统读写测试。
- 证据：`logs/datadisk/package110.log`、`package111.log`、`verify110.log`、`verify111.log`、
  `deploy110/`、`deploy111/`、`board-roundtrip.log`、`post-deploy.log` 和 `ui/live-*.png`
  （均在 `logs/datadisk/` 下）。
