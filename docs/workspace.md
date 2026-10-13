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
| vim4-manager | main | 管理面板：选择 KVM 界面、查看板子状态 |

## 初始化入口

需要 Python 3.11+、Git 和相应私有仓库访问权限：

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

all 顺序构建 capture、encoder、server、frontend、jetkvm、manager，不包含独立的内核构建。
支持分别选择上述目标，服务端先运行 VIM4 Go 测试，再输出 build/NanoKVM-Server；
前端输出 NanoKVM/web/dist，插件输出各自构建目录。build/ 不入库。
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

部署仍显式使用 board/install.sh、tools/kernel-install.sh 或 NanoKVM 的安装工具，
分别遵循对应文档。完成构建不意味着硬件回归或整机镜像验证通过。

## 文档维护

CLAUDE.md 仅引用 AGENTS.md 和 LESSONS.md；AGENTS.md 只做路由。
当前架构归子系统文档，历史证据归上板记录，错题本记录原因与验证入口。
子仓库独立克隆时可从 [公共文档](https://github.com/vim4-kvm/vim4-kvm/tree/main)
读取；完整工作区中的相对链接按本布局解析。
