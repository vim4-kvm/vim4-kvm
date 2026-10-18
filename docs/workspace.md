# 工作区

当前目录就是 vim4-kvm/vim4-kvm 主仓库。其他仓库克隆到其直接子目录，
由根 .gitignore 精确忽略；各自保留 .git 和提交历史，不使用 submodule。
AGENTS.md、CLAUDE.md、LESSONS.md 直接随主仓库版本管理，不再生成外层入口。

| 目录 | 分支 | 归属 |
|---|---|---|
| . | main | 公共文档、板级服务与部署工具 |
| NanoKVM | vim4 | 当前应用，官方 Sipeed NanoKVM fork |
| gst-plugin-venc | vim4 | 官方 Khadas 编码插件 fork |
| gst-plugin-vfmcap | main | DMA-buf 采集插件 |
| common_drivers | vim4-kvm-5.15 | 官方 Khadas 驱动与设备树 fork |
| kvm | vim4 | JetKVM 应用，可在管理面板中选择 |
| One-KVM | vim4 | One-KVM 应用，可在管理面板中选择 |
| kvmd | vim4 | 官方 PiKVM fork，VIM4 HID、虚拟介质与 Ubuntu 服务集成 |
| ustreamer | vim4 | 官方视频服务及 Janus 插件 fork，VIM4 DMA 采集和硬件编码 |
| vim4-manager | main | 管理面板：选择 KVM 界面、查看板子状态、EDID/HDR/风扇曲线调节、Wi-Fi 连接与热点 |

## 初始化入口

需要 Python 3.11+ 和 Git；源码仓库均可公开克隆：
完整配置迁移测试另需 ruamel.yaml（构建镜像已包含）；浏览器登录集成测试使用
PLAYWRIGHT_MODULE 指定 Playwright，没有浏览器依赖时只运行纯离线单元部分。

```sh
git clone https://github.com/vim4-kvm/vim4-kvm.git
cd vim4-kvm
python3 tools/workspace.py bootstrap
python3 tools/workspace.py status
```

bootstrap 从 workspace.toml 的开发分支克隆缺失仓库，已有仓库不拉取、不切分支、
不重置。非独立 Git 工作树或符号链接会报冲突。status 显示提交、分支、脏状态和
固定版本偏差；不自动连接 VM 或板子，也不声称远端已同步。

`bootstrap --locked` 将新克隆检出到清单固定提交；已有仓库必须版本吻合且干净，
否则报错并保留原状。清单更新和子仓库提交应一起审查；分享固定清单前须先推送
其引用的子仓库提交。它固定源码，不固定系统包和编译器，尚不是完整镜像构建锁。

## 构建

```sh
python3 tools/workspace.py build frontend
python3 tools/workspace.py build all --dry-run
python3 tools/workspace.py build all       # 在具备依赖的 Linux ARM64 上
python3 tools/workspace.py build kernel    # Mac 上使用 OrbStack vim4-build
```

all 顺序构建 capture、encoder、server、frontend、jetkvm、onekvm、manager，不包含独立的内核构建。
支持分别选择上述目标，服务端先运行 VIM4 Go 测试，再输出 build/NanoKVM-Server；
前端输出 NanoKVM/web/dist，插件输出各自构建目录。manager 同时输出
`build/vim4-manager` 和 NAS 文件夹 U 盘守护进程 `build/vim4-nasdisk`。build/ 不入库。
构建使用现有工作树（含开发改动），正式打包前先执行 locked 检查。

前端需要 pnpm/Node；Linux 后端需要 Go、Meson、GCC、GStreamer 开发库，
编码插件还需要 libamvenc、GE2D、DRM allocator/bufferpool 厂商开发库。
具体依赖见子仓库 VIM4.md/README。脚本不自动安装系统包，不 SSH 到板子，
不部署、不安装插件、不停启服务。缺失依赖会报错；dry-run 仅打印构建命令。

主内核不能检出到大小写不敏感的 Mac 文件系统。单独在 Linux/OrbStack 中按
[kernel.md](kernel.md) 准备 ~/src/linux、其中的 common_drivers 和内核 .config。
workspace.toml 的 kernel 表记录来源、分支、固定提交和 VM 名，bootstrap 不创建
这个外部工作树。build kernel 使用已有 Linux 工作树，--kernel-dir 可指定其路径；
Mac 上该参数指 VM 内路径。此目标不检查外部工作树版本，应单独核对清单。
MCU 风扇代码属于主内核。内核构建不会同步或覆盖 VM 中的现有源码。

U-Boot fork 为 [vim4-kvm/u-boot](https://github.com/vim4-kvm/u-boot/tree/vim4-kvm-2019.01)，
VM 工作树为 `~/src/u-boot`，版本记在 workspace.toml 的 `uboot` 表。
按该仓库 VIM4.md 手工构建与重打包；workspace.py 和镜像组装尚未自动集成。
启动风扇测试的修改与实板结果见 [上板记录](bringup/2026-10-17-uboot-quiet-fan.md)。

部署仍显式使用 board/install.sh、tools/kernel-install.sh 或 NanoKVM 的安装工具，
分别遵循对应文档。完成构建不意味着硬件回归或整机镜像验证通过。

## 文档维护

按需加载，控制每次会话的固定上下文：

- 自动加载：CLAUDE.md 只引用 AGENTS.md 与 LESSONS.md。AGENTS.md 只做路由；
  LESSONS.md 只收跨子系统教训。tests/test_docs.py 限制两者体积。
- 子系统文档（docs/subsystems/）描述当前架构，末尾「错题」收该子系统的教训。
- 上板记录每条一个文件（docs/bringup/），新条目同时在索引登记一行；单条超出
  测试上限时拆分，或把结论提炼进子系统文档。
- 长篇调查文档开头写结论摘要，读者按章节读取。
- 新增、删除或改变 tools/ 脚本的影响时同步 [工具目录](tools.md)；测试检查目录完整性
  和本地链接、锚点。

子仓库独立克隆时可从 [公共文档](https://github.com/vim4-kvm/vim4-kvm/tree/main)
读取；完整工作区中的相对链接按本布局解析。
