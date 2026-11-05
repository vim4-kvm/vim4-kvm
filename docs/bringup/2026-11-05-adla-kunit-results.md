# 2026-11-05：ADLA 测试迁移结果

协调暂缓解除后，先合入内核 `debug-splat-fixes`：merge `c34249a0729e6` 的第二
父提交为 `0a35577b8de28`，原四个修复提交未改写。主仓库 merge `2884a56` 保留
双方 README 条目，并修正新文档指向已更名规则章节的锚点。主仓库风险清单先于
代码提交 `7c39e36`，见 [other-1](2026-11-05-kunit-inventory-other-1.md)、
[other-2](2026-11-05-kunit-inventory-other-2.md)。本批四个 Python 全部删除。

| 内核提交 | 变更 |
|---|---|
| `437a77da87f6e` | `adlak_kunit.c` 四项、Kconfig/Makefile/`.kunitconfig` 和私有声明头；真实 allocator/取消/OS mutex 条件导出；删除含 K 风险的三个 Python |
| `a5310d48b6313` | 删除 DMA、复位、真实等待者/worker 生命周期 mock，无生产改动 |
| `514e0f9b81ab7` | 以标准 fallthrough 标注利用率 switch 原先进入下一 case 的路径，解除完整 QEMU 配置的默认编译错误，不改变计算或控制流 |

arm64 QEMU 实际 4/4：

- bitmap 池直接初始化并调用生产分配/释放，覆盖零长、对齐溢出、截到池尾的
  排除区、非整页分配、耗尽不占用、释放复用和计数；使用真实 INVALID_ADDR，
  旧 mock 自定义的哨兵值与生产值不同，不保留假常量。
- 取消直接调用原函数，使用真实 ADLA 结构、内核 list 与生产 OS mutex；验证
  net/invoke ID 隔离、非活动项引用/计数减少、活动项只标取消而不移出/回收。
- 直接测试生产 `adlak_range_valid()` 和 `adlak_fixup_valid()` 的负数、尾边界、
  溢出安全、字对齐、shift/unit 约束。未重建 ioctl、DMA、时钟或等待队列。

生产改动增加 KUnit 可见性/条件导出、声明和上述编译标注；取消函数参数使用
等价的 Linux 固定宽度类型。原计算、调用位置、锁范围、MMIO 和 DMA 时序未变。合入分支已有
SG 上限修复继续保留，见[启动 splat 记录](2026-11-05-debug-splat-fixes.md)。

在 VM `/home/deepdream/src/linux-7.3-kunit-migration`，持主仓库 heavy 构建票，
`out=$PWD/.kunit-adla`，实际核心命令：

```sh
python3 tools/testing/kunit/kunit.py run 'amlogic-adla*' --arch arm64 --jobs 8 \
  --timeout 120 --build_dir "$out" --kunitconfig drivers/misc/adla/.kunitconfig \
  --json="$out/result.json"
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 drivers/misc/adla/
# MODULES=y，驱动/测试均 m；再以 KUNIT=n 各完整构建匹配符号表：
make O="$out" ARCH=arm64 -j8
make O="$out" ARCH=arm64 M="$PWD/drivers/misc/adla" clean
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse \
  -j8 M="$PWD/drivers/misc/adla" modules
scripts/kernel-doc -none drivers/misc/adla/drv/common/adlak_kunit.h
git diff --cached -- drivers/misc/adla | \
  scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

内建、独立测试模块和 KUNIT=n 模块均编译完成，实际有 CC/CHECK；跨配置先清理
自身模块产物。KUNIT=n 的 `adla_core.ko` 经 nm 确认没有新 KUnit 导出。VM 输出
保存 builtin.config、module.config、production.config、test.log、result.json。
测试模块未另做加载验证。首次 QEMU 后只修正缩进/空行，逻辑和数值未变；最终
全套重跑另见总清单，不将后续模块构建当作 QEMU 运行。

**W=1 与有效 sparse 静态门禁未通过。** 既有 vendor 未使用变量、缺少原型、
格式及 kernel-doc、gfp_t/整数 NULL、地址空间等诊断仍在，与已审合入记录的
保留边界一致；未扩大硬件实现清理。新增测试和私有头没有范围诊断。准备阶段
另有未修改 vDSO 声明诊断，不宣称全树零诊断。sparse 为
`84ec0658c81db4ccc4aabc420d3dc118c2c6a310`。strict checkpatch 最终两提交均零
error/warning/check，仅 FILE_PATH_CHANGES 人工核对既有 MAINTAINERS 范围后忽略。
私有头 kernel-doc 无诊断；未改 binding/DTS；smatch 不可用。

主仓库 `build/kunit-migration/` 保存原始输出：`adla-run.log`、`adla-gates.log`、
`adla-gates-resume.log`、`adla-commit.log`、`deferred-style-initial.log`、
`deferred-style-final.log`；实际命令在 `adla-gates*.sh`。第一次模块门禁使用相对
M 路径触发旧 Makefile 的 include 路径错误，已改用绝对 M 路径真实重编，失败
输出完整保留。主仓库合并全测 `main-tests-merge-splat-final.log` 和清单全测
`main-tests-deferred-inventory.log` 均为 539 项、14 skipped、OK；锚点修复前的失败
保留在 `main-tests-merge-splat.log`。
本记录全测 `main-tests-adla-results.log` 同为 539 项、14 skipped、OK。

九配置组合的首次整套构建在 `all-final-run.log` 保留：COMPILE_TEST 使 WERROR
开启，既有 debugfs 隐式 fallthrough 被拒绝，QEMU 未启动。标注后普通目标编译
及 C=2 完成（`adla-fallthrough-compile.log`），DEBUG_FS=y/KUNIT=n 模块 W=1/C=2
实际重编完成（`adla-debug-module.log`、配置 production-debugfs.config）。标准标注
不增加指令或改变原落入下一 case 的行为。完整配置的额外 W=1 目标仍被既有
do_resume/do_suspend 未使用变量错误阻断（`adla-fallthrough-build.log`），门禁继续
记未通过；该次目标检查没有关闭 WERROR 或屏蔽该诊断。标注提交 strict checkpatch 零诊断，
见 `adla-fallthrough-commit.log`；最终全套运行结果另记，不用普通目标编译代替。
第二次全套构建仍被已有 missing-prototypes 阻断，失败见 `all-final-run2.log`。
最终组合运行 profile 显式 WERROR=n，以保留全部 vendor 警告并执行运行测试；
原 W=1/sparse 失败结论不变，未改生产配置或提交的各目录 `.kunitconfig`。

全部 V/B 待实板：同步 CANCEL/WAIT 的成功、超时、信号和硬件错误；reset 停 DMA
后才能发布/释放，失败必须隔离；close 超时后的 context/模块 pin 与迟到完成；
两类真实等待者均唤醒、有限 IRQ 轮询和可取消性；PM/clock/regulator/probe defer
逐阶段 unwind；真实 model v1/v2 配置选择、零计数 INVOKE 复用旧 fixup 数组与
命令 emitter 一致；SG/DMA 段长。沿用实际下游 SDK/ioctl，配合 KASAN/lockdep、
DMA 调试及标准故障注入，不伪称已有标准 accelerator ABI。本轮没有故障注入、
真实任务或板访问，删除不等于这些风险通过。
