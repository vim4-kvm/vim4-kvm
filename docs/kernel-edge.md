# VIM4 新内核基线

当前开发分支已接通 HDMI 输入、VDIN 直接 DMA、Wave5 H.264/H.265、硬件 JPEG 与音频，
并部署完整 manager 和四种 KVM 的双内核运行时；5.15 可保留启动，共用同一应用的数据。
当前包、匹配内核、安装/回退与实际验收范围见
[双内核完整系统集成](bringup/2026-10-21-dual-kernel-integration.md)。
本页保留 Armbian 编译基线与专项历史记录；通用 edge.config 不等于已验收的整板配置。
当前板上保留 v7.3 正式版 `e0346697f2503`，release `7.3.0-vim4kvm-uhd1+`、
build ID `3ed254bfa838ab50732fdce1c5134400a1663fd5`；uhd1.config 同次完整 Image/DTB/
2335 模块，含 HDMI 输入模式、诊断、动态 LPCM、GPU 纯调频和模块化 IR。
One-KVM 为 `382efb70e7ebb`，manager 为 `7a69cedb6d526`。第三轮抽样、编解码往返、
4K60、USB、GPU 与管理页已执行；44.1kHz 单次音频跳变和扫描时 MMC 警告仍记录为遗留，
不能宣称零警告或长期稳定性通过。哈希、备份、完整结果见
[正式版保留记录](bringup/2026-10-22-edge-7-3-final-retained.md)。
第二轮 19 模式通过后即时 EDID 检查触发的回退见
[历史尝试](bringup/2026-10-22-edge-7-3-final-deploy.md)，脚本入口见
[部署准备](bringup/2026-10-22-deploy-7-3-final-prep.md)。
其他会话的临时音频测试可能占用板子；本页的部署基线不代表其测试窗口中的瞬时版本。

CRG USB 设备端早期已完成真实键鼠和
只读虚拟盘三轮组合测试，仍需扩大 USB 验收，范围见
[CRG 组合实测](bringup/2026-10-19-crg-composite.md)。
HDMI RX 已通过 EDID/DDC 源端读回，并在固定 148.5 MHz 实验路径中取得真实的
1920×1080 RGB24 视频快照，三处帧号一致且重复采集推进，见
[取帧实测](bringup/2026-10-19-hdmirx-frames.md)。V4L2 MMAP 已通过私有 cached DMA 环
实现稳定段约 60fps，5400 帧运动校验通过，见
[1080p60 实测](bringup/2026-10-19-hdmirx-dma-ring.md)。后续 DMA-buf 导出也通过 5400 帧检查，
并完成 180 帧软件 H.264 编解码校验，见
[DMA-buf 实测](bringup/2026-10-19-hdmirx-dmabuf.md)。固定 RGB8 4K60 输入与
H.264/H.265 硬编码已取得实验结果，见
[Wave521 与 4K60](bringup/2026-10-19-wave521-uhd.md)。独立 One-KVM 已在网页播放
两种格式的 4K60；重复重配的 DMA 回收修复见
[应用接入记录](bringup/2026-10-20-onekvm-wave5.md)。直接 DMA 的固定 4K60 实验已将
整机 CPU 降到约 4.2–4.3%，见 [本地基准与直接 DMA](bringup/2026-10-20-direct-dma-benchmark.md)；
长期稳定性验收尚未完成。
当前已部署包含 VDIN/Wave5 修复与安静风扇的完整匹配 Image/模块，见
[启动风扇与 HDMI 恢复](bringup/2026-10-20-edge-recovery.md)；首次安静曲线的性能短测见
[安静风扇与整包验证](bringup/2026-10-20-edge-quiet-fan.md)，旧 Image 加 VDIN 覆盖的
同连接 30 分钟结果见 [持续延迟](bringup/2026-10-20-edge-status-latency.md#同连接-30-分钟)。
现有 5.15 内核工作树和发布版本保留；workspace.toml 的用户态仓库锁随双内核适配更新。
受支持的 RGB8 1080p60/4K60 自动重配与应用缓冲回收见
[动态模式记录](bringup/2026-10-20-edge-dynamic-modes.md)。
有限的 [HDR10 4K60 采集与 HDR→SDR](bringup/2026-10-20-edge-hdr-capture.md) 已接通，
独立 edge 服务使用专用 EDID 和显式选项；HLG、其他 HDR 格式与长期验收仍未完成。

## 源码与配置

- Linux 工作树：OrbStack `vim4-build` 的 `/home/deepdream/src/linux-7.3`。
- 开发分支：[vim4-kvm-7.3](https://github.com/vim4-kvm/linux/tree/vim4-kvm-7.3)，固定版本见源码锁。
- 上游：`https://github.com/gregkh/linux.git`，`v7.3`，完整历史的过滤克隆。
- Armbian：`https://github.com/armbian/build.git`，固定提交
  `ecc676bf89af37788f972db9a7ff3f92844a43eb`，VM 中为 `~/src/armbian-build-7.3`。
- 补丁：`patch/kernel/archive/meson-s4t7-7.3/*.patch`，按文件名排序，共 164 个。
  这是 S4/T7 共用集合，保留原作者；逐项应用不等于完成硬件正确性审查。
- 构建配置与源码锁：[packaging/kernel-edge](../packaging/kernel-edge/)。
  与现有 `packaging/kernel` 完全独立，不交给 5.15 的打包脚本。

`edge.config` 取自固定 Armbian 提交的 `config/kernel/linux-meson-s4t7-edge.config`，
增加 `CONFIG_LOCALVERSION="-vim4kvm-edge"` 及 KVM 所需的 configfs gadget 功能
（HID、NCM、ECM、RNDIS、mass storage、UAC2），并启用实验 CRG UDC 模块。
通用基线中 CRG 由 udc-test DTB 接入，普通 VIM4 DTB 保持 USB host 行为；
当前完整运行时使用 tested_build 记录的匹配专用 DTB，不能直接用通用产物覆盖。
脚本执行 olddefconfig，最终配置写入
外部构建目录并记录校验和；并非复现 Armbian 镜像构建的所有配置钩子。

完整运行时的准确配置为 `packaging/kernel-edge/uhd1.config`，Linux ARM64 上可用
`bash packaging/kernel-edge/build.sh SOURCE NEW_OUTPUT packaging/kernel-edge/uhd1.config`
重建匹配 release；不传第三参数仍构建通用 edge 基线。该命令不安装、不重启，
DTB/固件和完整模块的安装与登记按双内核记录执行，保留当前板子的 DTB/MAC 配置。

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
`sha256sum -c /path/to/packaging/kernel-edge/patches.sha256` 核验。
重新 git am 会产生不同提交者时间，HEAD 不一定相同；需对照锁中的 tree 和补丁清单，
审查后更新本地源码锁。已经发布的开发分支则应直接检出固定 revision。

本次还在主仓库不入库的 `build/kernel-edge/vim4-kvm-7.3.bundle` 保存了 164 个提交，
已用 git bundle verify 验证。它需要上游 `v7.3-rc7` 提交，可在已有上游对象的新克隆中
用 `git fetch /path/to/vim4-kvm-7.3.bundle vim4-kvm-7.3:vim4-kvm-7.3` 恢复精确提交。

## 构建

在 Linux ARM64、GCC 13 环境中运行；需要 make、flex、bison、bc、OpenSSL/ELF
开发库和 pahole。准备阶段不安装到开发机或板子。

```sh
bash packaging/kernel-edge/build.sh /home/deepdream/src/linux-7.3 /home/deepdream/build/kernel-edge
```

脚本要求源码 HEAD 与锁一致、工作树干净、输出目录为空且位于源码之外。
编译 `Image dtbs modules`，成功后生成 `build.json`，记录源码、编译器和产物校验和。
构建失败时保留日志和输出用于诊断；手工继续 make 或另选新的空目录，不自动清理。
此入口不生成 deb、不安装模块、不连接板子、不修改启动项。

## 2026-10-19 首轮构建结果

- Linux 提交：`9c8bb58158d810a38ff37dec7c7d18cb131a3b52`，164 个补丁全部 git am 成功。
- GCC：Ubuntu `13.3.0-6ubuntu2~24.04.1`，8 个并行任务。
- 发布名：`7.3.0-rc7-vim4kvm-edge+`；末尾 `+` 表示相对上游标签有额外提交。
- `Image dtbs modules` 成功，Image 53,639,680 字节，生成 2320 个 `.ko`。
  日志没有 `warning:` 或 `error:`；未运行 dtbs_check，未进行启动或功能测试。
- Image SHA-256：`56112d751e3ecadcc4972583c4dbbbed396c353be79f313641fdc001d0875a85`。
- VIM4 DTB SHA-256：`d6d56472c93b2b073fa2e8e80412d4c8d5c0be8eaa391cfc7e4ef07bc8f0d277`。
- 最终配置 SHA-256：`57163bd7de1cd169dc4b4514fce631b1280469d765572994dbce46b557c16c93`。
- 完整输出在 VM 的 `~/build/kernel-edge`；主仓库 `build/kernel-edge/` 保存 Image、
  VIM4 DTB、最终 `.config`、build.json 与 Git bundle。模块留在 VM，未打包安装。
- 主仓库 `logs/kernel-edge/` 保存编译、补丁导入、补丁校验和单元测试日志。
- 主仓库离线测试 83 项通过，4 项跳过；新文档加入索引后又通过 5 项文档检查。
  构建入口在 VM 验证了错误源码、非空输出目录、源码内输出三种拒绝路径。

这些结果仅证明本次源码与配置可编译，不能作为硬件回归通过证据。

## 启动固件预检与模块准备

2026-10-19 检查板子仍运行 `5.15.137-vim4kvm`，`/boot` 剩余约 67 MiB。
Image 已占约 51 MiB，不能假定加入 initramfs 后仍有足够空间。
最终配置中 eMMC、ext4、串口为内建，以太网为模块，试启动需要对应模块。
VM 已执行 modules_install、strip、压缩与 depmod，输出在
`~/build/kernel-edge-stage`（约 31 MiB，2320 个模块）。主仓库
`build/kernel-edge/modules-7.3.0-rc7-vim4kvm-edge.tar.xz` 为约 24 MiB 的模块归档。
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
首次上板结果见 [7.3 首次启动](bringup/2026-10-19-edge-firstboot.md)。

## 审查边界与后续验证

原始 164 个 Armbian 补丁涉及 108 个文件，未修改 HDMI RX、VDIN、Wave5 或 USB gadget 路径。
后续本地 CRG 实验驱动及验证范围见 [适配记录](kernel-edge-porting.md#crg-实验驱动2026-10-19)。
GPU 纯调频已完成[专项验证](bringup/2026-10-21-edge-gpu-devfreq.md)及上述合并部署；
音频输出和显示输出仍需上板验证，不能用编译成功替代。

- `0097`：GPU 800 MHz、IO coherent；需验证 Panfrost、内存压力和持续负载。
- `0100/0101/0111`：音频控制器与 HDMI 输出声卡，不代表 HDMI 输入音频采集。
- `0106`：HDMI TX 驱动声明 TMDS ≤600 MHz、RGB 8-bit、双声道 I²S、无 HDCP；不是完整 HDMI 2.1 能力。
- `0088`：PCIe DMA 依赖固件 SMC 保护窗口；需验证板上固件兼容性。
- `0103/0146`：保持显示及 USB/SDIO/eMMC 电源域，涉及功耗与恢复行为，需测试挂起恢复。
- `0073–0080`：USB Host 接入，不是 HID/虚拟介质需要的 CRG UDC。

基础启动结果见上述首次启动记录；下一阶段依赖与验收见
[USB 与音视频适配拆解](kernel-edge-porting.md)。
新板 `kvim4n` 的硬件差异和启动固件要求也必须核对，不能直接复用厂商 DTB。
