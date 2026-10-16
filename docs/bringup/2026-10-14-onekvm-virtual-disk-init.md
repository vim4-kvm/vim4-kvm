# 2026-10-14：One-KVM 虚拟盘初始化修复

创建 256 MiB 虚拟盘失败的原因是 Ubuntu 包未包含 Ventoy 引导资源；服务启动时
报告 `boot.img not found`，创建时报 `Resources not initialized`。普通 ISO 挂载
不会覆盖此路径，之前的虚拟盘单元测试又因错误的资源目录直接跳过，未能发现缺项。

One-KVM `5b3df497` 从 `/usr/share/vim4-onekvm/ventoy` 加载 VIM4 包内资源；
主仓库 `a2f6b76` 将仓库自带 boot.img、core.img.xz、ventoy.disk.img.xz 解压打包，
安装及验证检查拒绝缺失资源。用户盘位于独立的数据目录，升级不覆盖。
修复测试资源路径，在临时目录解压，缺失或损坏时测试失败，不再静默跳过。

仅升级 `vim4-onekvm` 到 `2.5.1+vim4.20261014.6`。557 项 Rust 测试（包括实际
创建、目录、文件读写和流式读取）、42 项工作区测试、4 项助手测试及 release 构建通过；
七组件包校验通过。`dpkg --audit`、`dpkg --verify vim4-onekvm` 均无输出。

服务 05:35:04 UTC 成功加载资源，用户随后于 05:35:22 创建 268435456 字节虚拟盘，
05:35:25 挂载到 LUN 0。macOS 识别 USB ExFAT 卷 `/Volumes/ONE-KVM`，只读验证
完整读取盘内 8343098 字节文件。保留用户正在使用的虚拟盘及连接，没有重建或卸载。
HDMI InvocationID 仍为 `5adb6d1c9b494584996befd0f64d2877`，One-KVM 和管理器均 active。

新增端到端脚本 `tools/one-kvm-drive-check.mjs`；首次执行因读取状态响应层级错误
在修改介质前退出，已修正为 `status.state` 并通过语法检查。因用户已开始使用虚拟盘，
没有完整重跑自动上传/下载/卸载流程，也未验证 Ventoy 启动操作系统。
日志位于 `logs/one-kvm/ventoy-*.log`。
