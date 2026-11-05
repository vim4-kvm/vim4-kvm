# 2026-11-05：Meson DRM KUnit 迁移结果

Meson DRM 的 18 个 Python 全部删除，arm64 QEMU KUnit 8/8。
风险先在主仓库 `ed1a0ad` 提交，见清单
[1](2026-11-05-kunit-inventory-drm-1.md)、[2](2026-11-05-kunit-inventory-drm-2.md)、
[3](2026-11-05-kunit-inventory-drm-3.md)。本轮无板端访问，V/B/F 全部待实板。

| 内核提交 | 实现 |
|---|---|
| `3f8048acd1eda` | 独立 `meson_t7_kunit.c`、Kconfig/Makefile/`.kunitconfig`；生产纯函数仅条件导出，OSD static 函数按 visibility 接口暴露；删除十个含 K 类风险的文件 |
| `cc7e380b3d8dc` | 删除其余八个硬件/atomic/fence mock，无生产改动 |
| `97c02ec109ecd` | 单独消除实际 sparse 诊断：仅本文件使用的 vclk 参数表改 static；MMIO map 错误返回改 IOMEM_ERR_PTR，不改错误值或硬件顺序 |

8 项直接测试生产 framebuffer/GEM DMA 边界、VCO/OD/TMDS 单位与范围、
firmware/native mode 准入、NV12/NV21 MIF 的 crop/stride/容量与失败不发布半状态、
PPS phase 和容量、三层 OSD 有界描述符/地址快路径回退、alpha/reflection。
使用真实 DRM 类型及 helper，未重建 DRM、fence、引用计数或寄存器框架。
生产计算函数体未改，未移动 MMIO、DMA、IRQ、锁或发布顺序。

在 VM `/home/deepdream/src/linux-7.3-kunit-migration` 的 `kunit-migration` 分支，
持主仓库 heavy 锁；`out=$PWD/.kunit-drm`，实际核心命令：

```sh
python3 tools/testing/kunit/kunit.py run 'meson-t7*' --arch arm64 --jobs 8 \
  --timeout 120 --build_dir "$out" --kunitconfig drivers/gpu/drm/meson/.kunitconfig \
  --json="$out/result.json"
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 drivers/gpu/drm/meson/
make O="$out" ARCH=arm64 M=drivers/gpu/drm/meson clean
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  M=drivers/gpu/drm/meson modules
scripts/kernel-doc -none drivers/gpu/drm/meson/meson_t7_kunit.h
git diff --cached | scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

最终 KUnit 8/8；随后只作 sparse 的链接/类型修正和 Python 删除。
内建 W=1/有效 sparse、独立 KUnit 模块、KUNIT=n 的生产内建和原支持模块的
Meson DRM/TX 模块构建完成。**T7 handoff 原 Kconfig 仅内建，未改为支持模块**；
不能声称构建了不存在的 handoff 模块。模块仅编译，未加载。
切换配置后完整构建匹配符号表并清理自身模块目录产物；配置保留于 VM 的
`.kunit-drm/`，包括 builtin.config、module.config、production-builtin.config、
production-module.config。

sparse 固定 `84ec0658c81db4ccc4aabc420d3dc118c2c6a310`，最终驱动范围零诊断。
准备阶段未修改 vDSO 的 `__kernel_getrandom` 声明诊断保留；不宣称全树 W=1 或零诊断。
strict checkpatch 最终零 error/warning/check，仅忽略 FILE_PATH_CHANGES，
MAINTAINERS 的 Meson 目录通配覆盖新文件。新增头文件 kernel-doc 无诊断。
未改 binding/DTS；smatch 未安装。

原始输出在主仓库 `build/kunit-migration/`：

| 阶段 | 文件 |
|---|---|
| KUnit 与范围检查 | `drm-run.log`、`drm-gates.log`、`drm-final-kunit.log` |
| 生产/静态修正 | `drm-production.log`、`drm-module-final.log` |
| 样式/删除 | `drm-style.log`、`drm-commit-style.log`、`drm-remove-style.log` |
| 主仓库清单全测 | `main-tests-drm-inventory.log`：534 项、14 skipped、OK |

保留失败：长行/续行对齐已修正；模块配置最初保留内建 display connector，
其引用模块 KMS helper 导致链接失败，改为匹配模块后通过。一次对 bool
DRM_BRIDGE_CONNECTOR 写 m 被 olddefconfig 提示并纠正，最终配置按 Kconfig 生效；
不为这些配置问题修改驱动行为。

未验：标准 IGT/modetest/CEC/HDMI ALSA、HPD/DDC/SCDC、EDID 色彩组合、
实际 PLL/VENC/PHY、boot AFBC 拒绝接管、SRAM/genpd、scanout/reader/fence 引用、
vsync/RDMA 两序与丢失、RMFB、多 plane、超时 DMA 隔离、VDIN 资源共存及标准图样。
描述符和数值 KUnit 不证明硬件取数、颜色或迟到 IRQ 安全。
