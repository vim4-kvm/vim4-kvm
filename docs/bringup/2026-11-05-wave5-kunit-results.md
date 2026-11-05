# 2026-11-05：Wave5 KUnit 迁移结果

Wave5 目录的 13 个 Python 文件全部迁出或删除，两套 KUnit 共 9 项在
arm64 QEMU 实际通过。生产函数只增加 KUnit 条件可见性与导出，未提取函数体，
未改变调用点、执行顺序或硬件访问时序。测试使用真实驱动类型，没有重建
vb2/V4L2 或寄存器框架。本轮无板端访问；删除硬件 mock 不等于实板验证通过。

原风险与替代路径见清单 [1](2026-11-05-kunit-inventory-wave5-1.md)、
[2](2026-11-05-kunit-inventory-wave5-2.md)、[3](2026-11-05-kunit-inventory-wave5-3.md)。
全树其余子系统尚未迁移，其待确认项保留，见[总清单](2026-11-05-kernel-test-migration.md)。

## 提交与覆盖

内核工作树：VM `vim4-build` 的 `/home/deepdream/src/linux-7.3-kunit-migration`，
分支 `kunit-migration`，基线 `2662456a1a636f668454ab04a1c63f567206a592`。
以下内核路径相对 `drivers/media/platform/chips-media/wave5/`。

| 提交 | 实际变更 |
|---|---|
| `d357c8011be41` | `wave5_vui_kunit.c` 3 项：默认色彩、709/sRGB/PQ/full 位序与长度、非法输入不写输出；新增 `.kunitconfig` 和独立测试模块；删除 `test_vui.py` |
| `1bb4eee1fb3c1` | `wave5_params_kunit.c` 6 项：可见裁剪/旋转、刷新预算、VBV 单位与错误边界、层次 B 引用、普通多 B/层次 P 引用、legacy profile/P010 endian；删除四个参数 Python 测试 |
| `555dcc06f70b4` | 删除六个硬件/框架 mock，并移除已迁出的板端工具及其测试；本提交无生产 C 改动 |

主仓库 `b819265` 将工具迁至 [wave5-reproduce-hang.py](../../tools/wave5-reproduce-hang.py)，
三项工具回归迁至 [test_wave5_hang_observer.py](../../tests/test_wave5_hang_observer.py)。
仅更新测试的导入路径，保留工具默认只输出计划及执行时的独占约束。
`9a20901` 移除 buffer benchmark 对旧内核 mock 的调用；内核参数只记录源码身份。
规则扩展为主仓库 `1940e77`，最初的 87 文件清单先于内核改动提交于 `95569ba`。

## 实际验证

所有构建通过主仓库 `tools/board-queue run --heavy` 持共享 heavy 锁运行；不取板锁。
实际命令在 VM 内以内核树为 cwd，关键命令如下；完整输出见下表。
`out` 为该工作树下 `.kunit-wave5`；内建及模块配置分别另存
`builtin.config`、`module.config`。切换为模块时先启用 `MODULES`，将驱动和测试设为
模块，运行 `olddefconfig` 和完整构建生成匹配的符号表，再作目录 W=1/sparse。

```sh
python3 tools/testing/kunit/kunit.py run 'wave5-*' --arch arm64 --jobs 8 \
  --timeout 120 --build_dir "$out" \
  --kunitconfig drivers/media/platform/chips-media/wave5/.kunitconfig \
  --json="$out/result.json"
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  drivers/media/platform/chips-media/wave5/
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  M=drivers/media/platform/chips-media/wave5 modules
scripts/kernel-doc -none drivers/media/platform/chips-media/wave5/wave5-params-kunit.h
git diff --cached | scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

最终 QEMU 对应 `1bb4eee1fb3c1` 的 C 实现，9/9 通过；随后仅删除 Python。
内建、模块 W=1 和有效 sparse 均运行，Wave5 范围无诊断；另外以 `KUNIT=n`
构建生产模块，确认条件导出关闭后可编译。测试模块已编译，未在 QEMU 单独加载。
sparse 为 `84ec0658c81db4ccc4aabc420d3dc118c2c6a310`，版本
`v0.6.5-rc1-21-g84ec0658`，日志有实际 CHECK 行。
准备阶段存在未修改的 arm64 vDSO `__kernel_getrandom` sparse 诊断，
不宣称全树零警告或全树 W=1 通过。

strict checkpatch 最终零 error/warning/check。新增/删除文件仅忽略
FILE_PATH_CHANGES，人工核对现有 MAINTAINERS 的 Wave5 目录通配覆盖新测试。
新增头文件 kernel-doc 无诊断；未修改 binding/DTS。smatch 未安装，未运行。
主仓库完整离线检查 534 项通过（14 skipped），工具 `--help`、默认计划模式通过；
未运行工具的板端执行模式。

后续故障注入配置复验发现跨配置 M= 复用旧对象，已清理自身模块目录产物后
重新确认生产 CC/CHECK、无 KUnit 导出和无注入 whitelist，最终证据为
`build/kunit-migration/production-clean-rebuild.log`；见[方案](2026-11-05-wave5-fault-injection-plan.md)。

原始输出保存在主仓库 `build/kunit-migration/`（不入库）：

| 阶段 | 文件 |
|---|---|
| VUI 首轮与最终 | `wave5-vui-run.log`、`wave5-vui-gates.log`、`wave5-vui-module.log`、`wave5-vui-final.log` |
| 参数与最终 9 项 | `wave5-params-run.log`、`wave5-params-run2.log`、`wave5-params-final.log`、`wave5-params-final2.log`、`wave5-gop-final.log` |
| 生产无 KUnit 模块 | `wave5-production-module.log` |
| 最终原始 QEMU/JSON/配置 | `wave5-final-qemu.log`、`wave5-final-result.json`、`wave5-builtin.config`、`wave5-module.config` |
| 样式/删除检查 | `wave5-params-style.log`、`wave5-params-commit-style.log`、`wave5-remove-style.log`、`wave5-final-status.log` |
| 主仓库/工具 | `main-tests-final.log`、`main-tests-results-final.log`、`wave5-tool-help.log`、`wave5-tool-plan.log` |

保留失败记录：早期模块配置未启用 MODULES；缺少 MODULE_DESCRIPTION；
KUnit 断言直接使用 bit-field 导致 typeof 编译错误；新增 AVC 旋转断言只减一侧
裁剪而失败。均已修正并复验。未因此修改生产行为。

## 待实板

带流 compliance、码流/像素与 QP/IDR/LTR 分析、P010 DMA 和固件 HDR 元数据、
多实例、drain/LAST、在线控制更新、IRQ/close/streamoff 并发、PM/复位/隔离和
分配失败后的 DMA 所有权全部待实板。标准故障注入限调试内核；QEMU 纯逻辑
不能证明总线 idle、DMA 停止或真实帧输出。软件 HDR10 SEI 构造器未接固件的
历史 CPU SPS 比对不能当作硬件证据，本轮未为其增加生产功能。
