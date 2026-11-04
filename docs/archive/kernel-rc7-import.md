# 主线 rc7 导入与首轮构建

> 归档快照（2026-10-22）：rc7 导入、首轮构建及启动预检，不代表当前状态，现行入口见 [主线内核](../kernel-mainline.md)。

## rc7 导入

下方是最初 Armbian rc7 导入的历史步骤；当前分支已基于 v7.3 重放并合入板级修复，
准确复现应检出 sources.toml 的提交，不重新执行这段导入。固定 Armbian 快照为 7.3 选择 rc7，
不要只凭目录名判断上游版本。源码准备使用独立 Linux 大小写敏感文件系统，
不要切换 Mac 上已有的 `vim4-linux-7.x` 工作树。

重新准备源码时，在新的 Linux 目录执行以下步骤；已有目录不要覆盖。
提交者沿用开发者现有 Git 身份，不修改 Git 配置；`git am` 保留补丁作者。

```sh
git clone --filter=blob:none --no-checkout --single-branch --branch v7.3-rc7 https://github.com/gregkh/linux.git linux-7.3
git -C linux-7.3 switch -c vim4-kvm-7.3 v7.3-rc7
git -C linux-7.3 remote rename origin upstream
git -C linux-7.3 remote add origin https://github.com/vim4-kvm/linux.git
git clone --filter=blob:none --no-checkout https://github.com/armbian/build.git armbian-build-7.3
git -C armbian-build-7.3 checkout --detach ecc676bf89af37788f972db9a7ff3f92844a43eb
git -C linux-7.3 am ../armbian-build-7.3/patch/kernel/archive/meson-s4t7-7.3/*.patch
```

补丁失败时停止审查，不自动跳过或放宽匹配。
`patches.sha256` 记录排序后的补丁校验和，可在 Armbian 补丁目录用
`sha256sum -c /path/to/packaging/kernel/patches.sha256` 核验。
重新 git am 会产生不同提交者时间，HEAD 不一定相同；需对照锁中的 tree 和补丁清单，
审查后更新本地源码锁。已经发布的开发分支则应直接检出固定 revision。

本次还在主仓库不入库的 `build/kernel/vim4-kvm-7.3.bundle` 保存了 164 个提交，
已用 git bundle verify 验证。它需要上游 `v7.3-rc7` 提交，可在已有上游对象的新克隆中
用 `git fetch /path/to/vim4-kvm-7.3.bundle vim4-kvm-7.3:vim4-kvm-7.3` 恢复精确提交。

## 2026-10-19 首轮构建结果

- Linux 提交：`9c8bb58158d810a38ff37dec7c7d18cb131a3b52`，164 个补丁全部 git am 成功。
- GCC：Ubuntu `13.3.0-6ubuntu2~24.04.1`，8 个并行任务。
- 发布名：`7.3.0-rc7-vim4kvm-edge+`；末尾 `+` 表示相对上游标签有额外提交。
- `Image dtbs modules` 成功，Image 53,639,680 字节，生成 2320 个 `.ko`。
  日志没有 `warning:` 或 `error:`；未运行 dtbs_check，未进行启动或功能测试。
- Image SHA-256：`56112d751e3ecadcc4972583c4dbbbed396c353be79f313641fdc001d0875a85`。
- VIM4 DTB SHA-256：`d6d56472c93b2b073fa2e8e80412d4c8d5c0be8eaa391cfc7e4ef07bc8f0d277`。
- 最终配置 SHA-256：`57163bd7de1cd169dc4b4514fce631b1280469d765572994dbce46b557c16c93`。
- 完整输出在 VM 的 `~/build/kernel`；主仓库 `build/kernel/` 保存 Image、
  VIM4 DTB、最终 `.config`、build.json 与 Git bundle。模块留在 VM，未打包安装。
- 主仓库 `logs/kernel/` 保存编译、补丁导入、补丁校验和单元测试日志。
- 主仓库离线测试 83 项通过，4 项跳过；新文档加入索引后又通过 5 项文档检查。
  构建入口在 VM 验证了错误源码、非空输出目录、源码内输出三种拒绝路径。

这些结果仅证明本次源码与配置可编译，不能作为硬件回归通过证据。

## 启动固件预检与模块准备

2026-10-19 检查板子仍运行 `5.15.137-vim4kvm`，`/boot` 剩余约 67 MiB。
Image 已占约 51 MiB，不能假定加入 initramfs 后仍有足够空间。
最终配置中 eMMC、ext4、串口为内建，以太网为模块，试启动需要对应模块。
VM 已执行 modules_install、strip、压缩与 depmod，输出在
`~/build/kernel-stage`（约 31 MiB，2320 个模块）。主仓库
`build/kernel/modules-7.3.0-rc7-vim4kvm-edge.tar.xz` 为约 24 MiB 的模块归档。
这是暂存目录归档，不是可直接向系统根目录解压的安装包；其中含 lib/modules 路径和构建链接。

最初 2026-10-19 上板时的 U-Boot 源码 `b60ff51ece` 启用 CONFIG_CMD_RSVMEM，
`common/bootm.c` 无条件运行 rsvmem check；检查器读取
`/reserved-memory/linux,secmon` 的厂商属性，主线 DTB 没有该节点。
Armbian 使用的 `khadas-vims-v2019.01-mainline` 分支包含三项相关修改：

- `ee17cc6503`：没有 amlogic-dt-id 时跳过厂商 reserved-memory 检查。
- `ee291cdb50`：FUSB302 PD 协商修复。
- `a7b06ca049`：更新 T7 BL31；新旧固件对 SCMI/SMC 的兼容性仍需实机验证。

在 VM `~/src/u-boot-edge` 建立 `vim4-kvm-2019.01-edge` 分支，基于现有安静启动
版本应用这三个提交，保留取消风扇启动测试的修改。版本见 sources.toml。
该目录为依赖 `~/src/u-boot` 对象库的 shared clone，不可单独删除原对象库。
GCC 12 构建 BL33 与 bl33z 成功；厂商代码存在编译警告和 CONFIG_OF_EMBED 提示。
日志在 VM `~/build/u-boot-edge.log`、`~/build/u-boot-edge-stub.log`。

随后扩展 tools/vim4-repack.py，显式 `--update-bl31` 才允许替换 BL31，
默认模式仍拒绝变化。先重建原厂固件验证 round-trip，再验证新 BL31/BL33 与
目标载荷一致，保留早期阶段、BL30/BL40/BL32。新工具与候选源码版本已写入锁文件。
首次上板结果见 [7.3 首次启动](../bringup/2026-10-19-edge-firstboot.md)。
