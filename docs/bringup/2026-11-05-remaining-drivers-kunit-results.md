# 2026-11-05：其余非暂缓驱动测试迁移结果

风险分类先在主仓库 `16b1023` 提交，见清单
[other-1](2026-11-05-kunit-inventory-other-1.md)、
[other-2](2026-11-05-kunit-inventory-other-2.md)、
[other-3](2026-11-05-kunit-inventory-other-3.md)、
[other-4](2026-11-05-kunit-inventory-other-4.md)。本批删除 9 个 Python 文件。
仅离线；V/B 全部待实板。CRG/TCPM 有效 sparse **未通过**；按用户决定保留原始
诊断并完成迁移，不扩大到驱动实现清理。编译成功不表示该静态门禁通过。

| 子系统 | 内核提交 | 替代验证与本次结果 |
|---|---|---|
| Khadas thermal fan | `5eb8482550622` | 删除 1 个 Python；生产温度曲线、故障下限、渐变函数直接 KUnit，arm64 QEMU 3/3；内建/测试模块/生产模块 W=1 与 sparse 无范围诊断 |
| Meson CEC | `399eaac6de011` | 删除 1 个 Python；V/B 待 cec-compliance、真实路由/时钟/IRQ；内建/模块 W=1 与 sparse 无范围诊断 |
| Meson secure genpd | `60d3da1419ffa` | 删除 1 个 Python；B 待真实 SMC/电源域及标准故障注入；内建/模块 W=1 与 sparse 无范围诊断 |
| USB HID/UAC2 function | `3f58f9e78a75f` | 删除 2 个 Python；V/B 待标准 USB/ALSA 与绑定生命周期；内建/模块 W=1 与 sparse 无范围诊断 |
| CRG UDC | `66ebbb5c5719b` | 删除 3 个 Python；V/B 待真实 USB/IRQ/DMA；内建/模块 W=1 编译完成，sparse 未通过 |
| FUSB302/TCPM | `d4eee9d02eede` | 删除 1 个 Python；V/B 待真实 TCPM/PD/regulator；内建/模块 W=1 编译完成，TCPM sparse 未通过，FUSB302 本身无范围诊断 |

另外 `dba6936a6cdd0` 单独修正 CRG 既有 W=1 未使用变量错误：删除未使用常量和
仅计算地址的局部变量，保留调试指针并标 `__maybe_unused`，去掉未使用的返回值
局部变量，但仍调用原中断处理并返回 `IRQ_HANDLED`。无 MMIO、锁、回调或执行
顺序改变。风扇生产代码只改可见性，三个函数体不变；测试不重建 thermal、regmap
或 worker 框架。其余五个目录没有可脱离硬件/框架的 K 风险，未为它们另造 mock
或空 KUnit；QEMU 3 项只证明风扇纯逻辑，不证明其余驱动运行通过。

在 VM `/home/deepdream/src/linux-7.3-kunit-migration` 分支 `kunit-migration`，
通过主仓库 `tools/board-queue run --heavy` 持构建锁，未占板锁。
`out=$PWD/.kunit-other`，实际核心命令如下；配置切换及完整内核构建的原始输出保留。

```sh
python3 tools/testing/kunit/kunit.py run 'khadas-mcu-fan*' --arch arm64 --jobs 8 \
  --timeout 120 --build_dir "$out" --kunitconfig drivers/thermal/.kunitconfig \
  --json="$out/result.json"
for dir in drivers/media/cec/platform/meson drivers/pmdomain/amlogic \
  drivers/thermal drivers/usb/gadget/function drivers/usb/gadget/udc/crg \
  drivers/usb/typec/tcpm; do
  make O="$out" ARCH=arm64 W=1 C=2 \
    CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 "$dir/"
done
make O="$out" ARCH=arm64 -j8
# 模块配置及 KUNIT=n 配置分别完整构建，再对上述目录逐个运行：
make O="$out" ARCH=arm64 M="$dir" clean
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 M="$dir" modules
scripts/kernel-doc -none drivers/thermal/khadas_mcu_fan_kunit.h
git diff --cached | scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

VM `.kunit-other/` 保留 builtin.config、module.config、test.log、result.json。
原模块配置的 TCPM 核心仍为内建，FUSB302 为模块；最终额外将 TYPEC_TCPM 设为
模块并关闭 KUNIT，完整构建后清理、重编该目录，配置保留为
production-tcpm-module.config，命令与诊断见 `tcpm-module-final.log`。
跨配置清理各自目录模块产物，使用对应完整构建生成的符号表，检查有实际 CC/CHECK。
测试模块只编译，未另做加载验证；KUNIT=n 不编测试模块。最终样式修正只折行一个
测试断言，值和逻辑未变，随后再次实际运行 QEMU。新增头文件 kernel-doc 无诊断。
strict checkpatch 各提交最终零 error/warning/check；仅 FILE_PATH_CHANGES 人工核对
MAINTAINERS 通配覆盖后忽略。纯删除提交检查行数为零，不作为替代运行证据。

有效 sparse 使用 `84ec0658c81db4ccc4aabc420d3dc118c2c6a310`。
CRG 既有诊断包括 `__iomem` 地址空间、`__le16/__le32` 端序及未声明全局符号，
触及工具的 `too many warnings` 上限；原输出完整保留，不声称枚举全部诊断。
TCPM `tcpm.c:1706` 的 `vid` 赋值报告 `restricted __le16` 与 `int` 不匹配。
准备阶段另有未修改 vDSO `__kernel_getrandom` 声明诊断，不宣称全树 W=1/零诊断。
未改 binding/DTS；smatch 未安装。

原始输出在主仓库 `build/kunit-migration/`：

- `other-run.log` 保留首次测试局部名 `current` 与内核宏冲突的编译失败；
  `other-run2.log` 和 `other-final-run.log` 为实际 QEMU 3/3。
- `other-gates.log` 保留 CRG 首次 W=1 失败；`other-gates2.log` 为内建/模块/
  生产模块的实际 CC/CHECK 和全部原始诊断，并保留测试断言折行前的 checkpatch 失败。
- `tcpm-module-final.log` 补齐 TCPM 核心的生产模块 W=1/有效 sparse，仍保留类型诊断。
- `other-final-style.log`、`fan-commit-style.log` 为最终风扇/CRG 样式检查；
  `cec-remove-style.log`、`pwrc-remove-style.log`、`gadget-remove-style.log`、
  `crg-remove-style.log`、`fusb-remove-style.log` 为逐提交删除检查。
- 主仓库风险清单全测 `main-tests-other-inventory.log`：534 项，14 skipped，OK。
  最终记录全测 `main-tests-remaining-final.log`：534 项，14 skipped，OK。

未验边界逐子系统留给批量占板：CEC pad/filter/地址与 probe/remove unwind；
secure domain SET/GET 错误、拒绝/未知状态及有限轮询；风扇六传感器失败、sysfs
阈值事务、regmap 失败、worker 与 suspend/resume；HID GET_REPORT request/worker
在反复 configfs bind/unbind 中的引用回收，UAC2 禁用 runtime 和控制传输边界；
CRG EP0/status/ring 逐次分配/IRQ 失败、halt/drain 后回收、超时保留 DMA、挂起成对
通知及 setup/completion 顺序；FUSB302 regulator absent/defer/source/sink 契约及
enable/disable 幂等。使用标准接口、KASAN/lockdep、DMA 调试与适用的标准故障注入，
本轮均未运行。没有将删除 mock、编译或风扇 QEMU 当作这些风险通过。

协调暂缓的 ADLA 四文件与 brcmfmac 一文件保留待确认；Meson PWM/PWM regulator
相关代码未修改，基线 87 个 Python 中没有该目录的文件。vdec 及 firmware/meson
继续由其他分支负责，未修改。

审查后将风扇系统 include 排序、本地 include 移至系统组之后，删除 CRG 的多余
空行；以 `fixup!` 和 `rebase -i --autosquash 2662456a1a636` 折回原提交，
上表提交号已同步。原始记录 `build/kunit-migration/review-fix-autosquash*.log`、
`review-fix-range-diff-final.log` 保留重放及逐提交差异；改动提交的 strict checkpatch
为 `review-fix-checkpatch-final.log`，构建命令/输出为 `review-fix-build.sh`、
`review-fix-build2.log`。没有更改函数体、测试逻辑或硬件顺序。
最终风扇/CRG 内建、启用 KUnit 的模块和 KUNIT=n 生产模块均实际重编完成，
范围 W=1 编译成功；风扇有效 sparse 无范围诊断，CRG 既有地址空间/端序等
诊断仍在，门禁仍未通过。改动提交 strict checkpatch 零 error/warning/check。
主仓库 `main-tests-review-fix.log`：534 项，14 skipped，OK。本次未重跑 QEMU
或访问板子；TCPM 未改，保留此前 sparse 未通过结论。协调暂缓范围继续保留。
