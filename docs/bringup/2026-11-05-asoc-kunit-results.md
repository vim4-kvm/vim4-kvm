# 2026-11-05：Meson ASoC KUnit 迁移结果

`sound/soc/meson/` 的 15 个 Python 文件全部删除。风险分类先在主仓库
`5ae16d5` 提交，见清单 [1](2026-11-05-kunit-inventory-audio-1.md)、
[2](2026-11-05-kunit-inventory-audio-2.md)、[3](2026-11-05-kunit-inventory-audio-3.md)。
本轮无板端访问、无实流音频测试，V/B/F 全部待实板。

| 内核提交 | 实际变更 |
|---|---|
| `8ae2f94521141` | `t7_audio_kunit.c` 三项、Kconfig/Makefile/`.kunitconfig`；真实生产 EQ/DRC 验证及 card 参数函数按 visibility 条件导出；私有 TDM link 参数类型原样移至头文件；删除两个含 K 风险的 Python |
| `6c262d98e42db` | 删除其余 13 个寄存器/DAPM/PCM mock，无生产改动 |

arm64 QEMU 3/3：biquad Q23 稳定性/位宽边界，full/multiband DRC 成对系数与
增益约束，以及真实 ASoC card/runtime/hw_params 对象的 FE/BE 转换。
无转换保留原参数，转换两侧允许不同 rate/channels，FE merged 标志对应更新。
没有重建 ASoC、regmap、clock、DAPM 或 PCM；生产函数体、执行顺序和 MMIO 均未改。
头文件保留原私有结构字段和布局，未增加用户 ABI。

在 VM `/home/deepdream/src/linux-7.3-kunit-migration` 的 `kunit-migration` 分支，
持主仓库 heavy 锁；`out=$PWD/.kunit-audio`，实际核心命令：

```sh
python3 tools/testing/kunit/kunit.py run 'meson-t7-audio*' --arch arm64 --jobs 8 \
  --timeout 120 --build_dir "$out" --kunitconfig sound/soc/meson/.kunitconfig \
  --json="$out/result.json"
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 sound/soc/meson/
make O="$out" ARCH=arm64 M=sound/soc/meson clean
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 M=sound/soc/meson modules
scripts/kernel-doc -none sound/soc/meson/axg-card-params.h sound/soc/meson/t7-audio-kunit.h
git diff --cached | scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

内建、独立测试模块、生产 KUNIT=n 模块的 W=1 与有效 sparse 完成，范围无诊断。
配置切换后完整构建匹配符号表，清理自身模块产物再编译。VM `.kunit-audio/`
保留 builtin.config、module.config、test.log、result.json。
QEMU 通过后仅拆开测试初始化中的连等赋值以符合 checkpatch，并实际重编测试模块；
没有更改初始化值或测试逻辑。测试模块未另做加载验证。

sparse 为 `84ec0658c81db4ccc4aabc420d3dc118c2c6a310`；准备阶段有未修改 vDSO
`__kernel_getrandom` 声明诊断，不宣称全树 W=1/零诊断。strict checkpatch 最终
零 error/warning/check；仅忽略 FILE_PATH_CHANGES，现有 MAINTAINERS 通配覆盖新文件。
新增头文件 kernel-doc 无诊断。未改 binding/DTS；smatch 未安装。

原始输出在主仓库 `build/kunit-migration/`：`audio-run.log`、`audio-gates.log`、
`audio-final.log`、`audio-commit-style.log`、`audio-remove-style.log`。
保留初次连等赋值的样式检查失败。主仓库风险清单全测
`main-tests-audio-inventory.log`：534 项，14 skipped，OK。

未验：真实 ALSA/DAPM 路由、ASRC 转换和系数、AED/VAD SRAM、FIFO/TDM/SPDIF
通道/位宽/selector、MMIO bank 隔离、reset/cache/clock/电源失败与逐写回收、
多 formatter rollback、重复启停和实际样本。假想外部端点的图可达性不能证明
VIM4 接线或真实音频通路；生产 DT 资源及路由后续用标准 schema/DTB/ALSA 验证。

审查后以 `fixup!` 和 `rebase -i --autosquash 2662456a1a636` 折回头文件排序修正，
上表为重写后的提交。`t7-aed.c` 的 KUnit include 移至系统头文件组首，`axg-card.c`
的本地 include 排序；保持 `sound/soc.h` 先于依赖它的 `sound/soc-dai.h`。
原始重放与逐提交差异见 `build/kunit-migration/review-fix-autosquash2.log`、
`review-fix-range-diff-final.log`，strict checkpatch 见 `review-fix-checkpatch-final.log`。
`review-fix-build.log` 保留第一次额外交换 sound 头文件后出现的类型编译错误，
已恢复依赖顺序；最终对应构建命令保留在 `review-fix-build.sh`，输出
`review-fix-build2.log`。此次只改 include 顺序，未改生产函数或测试逻辑。
最终内建、独立测试模块及 KUNIT=n 生产模块的范围 W=1/有效 sparse 重跑完成，
有实际 CC/CHECK，范围无诊断；strict checkpatch 零 error/warning/check。
主仓库 `main-tests-review-fix.log`：534 项，14 skipped，OK。本次未重跑 QEMU，
此前 3/3 的原始证据保留；未访问板子。
