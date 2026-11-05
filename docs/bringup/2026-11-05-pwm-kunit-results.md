# 2026-11-05：PWM 既有 KUnit 复验

> 本页保留原验证时的 SHA。修订后的对应、完整提交检查与当前利用率修复边界见
> [审查返工记录](2026-11-05-kunit-review-rework.md)。

PWM/Meson PWM、clk-pwm 和 PWM regulator 在基线 87 个 Python 文件中没有条目，
合入后再次核对这些目录也没有 Python。直接复用已审 `0a35577b8de28` 的
`drivers/pwm/core_kunit.c`，没有重复写测试，没有更改这些目录或 `include/linux/pwm.h`。
该提交及同分支另外三提交作为 `c34249a0729e6` 的第二父系原样合入，未 rebase。

arm64 QEMU 的 `pwm-clock-locking` 实际 1/1，`PROVE_LOCKING` 开启。原用例经受控
线程竞争实际建立 PWM → CCF，再从 CCF 回调进入另一个控制器；回调确实执行且
lockdep 保持开启。它只证明不同控制器的建模回归，不证明同控制器锁顺序安全。
同控制器真实 ABBA 继续按 [PWM 锁分析](../pwm-clock-locking.md)登记，未在本任务修复。

在 VM `/home/deepdream/src/linux-7.3-kunit-migration`，持主仓库 heavy 构建票，
`out=$PWD/.kunit-pwm`，实际核心命令：

```sh
python3 tools/testing/kunit/kunit.py run 'pwm-clock-locking*' --arch arm64 --jobs 8 \
  --timeout 180 --build_dir "$out" --kunitconfig drivers/pwm/.kunitconfig \
  --json="$out/result.json"
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse \
  -j8 drivers/pwm/ drivers/clk/clk-pwm.o drivers/regulator/pwm-regulator.o
# 对模块配置与 KUNIT=n 对照分别完整构建匹配符号表，再逐目录清理/重编：
make O="$out" ARCH=arm64 -j8
for dir in drivers/pwm drivers/clk drivers/regulator; do
  make O="$out" ARCH=arm64 M="$PWD/$dir" clean
  make O="$out" ARCH=arm64 W=1 C=2 \
    CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse \
    -j8 M="$PWD/$dir" modules
done
scripts/kernel-doc -none include/linux/pwm.h
git diff 0a35577b8de28^ 0a35577b8de28 | \
  scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

内建及原本支持的模块构建完成，PWM core 始终内建；Meson、clk-pwm、regulator
实际生成模块，测试也实际生成 `core_kunit.ko`。另编译 KUNIT=n 对照，测试模块
不参与；模块只编译，未另做加载验证。配置切换后清理自身模块产物，日志有实际
CC/CHECK，范围 W=1/有效 sparse 无诊断。strict checkpatch 对原完整提交重新检查
零 error/warning/check；仅 FILE_PATH_CHANGES 人工核对原 PWM MAINTAINERS 通配后
忽略。include/linux/pwm.h kernel-doc 无诊断。准备阶段既有 vDSO 声明诊断保留，
不宣称全树零诊断；smatch 不可用，未改 binding/DTS。

主仓库 `build/kunit-migration/pwm-gates.log` 保存 QEMU、三种配置编译、静态检查和
kernel-doc 的原始输出；完整实际脚本 `pwm-gates.sh`。VM `.kunit-pwm/` 保存
builtin.config、module.config、production.config、test.log、result.json。
完成迁移后的全部套件重跑另见总清单。
主仓库记录全测 `main-tests-pwm-results.log`：539 项、14 skipped、OK。

未验：真实 Meson 控制器时钟/占空比、电压 regulator、Wi-Fi clock 消费者、
同控制器 debugfs/request/CCF 并发及真实启动 splat。以上全部待实板；不同控制器
测试通过不等于同控制器 ABBA 已修复，也不等于整机零 lockdep 告警。
