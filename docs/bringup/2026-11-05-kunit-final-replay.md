# 2026-11-05：全树测试迁移最终组合复验

迁移文件已处理完毕：基线清单 87 个 Python 中，82 个已迁出/删除；保留四个
上游生成器及禁止修改的一个 vdec 测试。vdec、firmware/meson 和本轮风扇源文件
均未修改。所有 V/B/F 仍待实板，删除不等于这些风险通过。

**完整组合 arm64 QEMU：11 套、44/44，通过，0 失败、0 skipped。** 使用最终内核
`514e0f9b81ab7`，表内全部测试在同一次 QEMU 启动中通过，包含上一轮 fixup 后的
全部迁移套件及合入的既有测试。完整运行日志未命中 WARNING、BUG、KASAN、
lockdep 或 panic 错误特征。

初次组合构建在既有 ADLA debugfs fallthrough 上失败，之后按协调要求等待
`278e6837...` 板窗口结束，不新增 heavy 任务。窗口结束后重试仍被既有原型诊断
挡住；按保留既有诊断的方案，在最终运行配置显式设置 WERROR=n，全部编译警告
保留，W=1/sparse 门禁仍记未通过。

| 目录/已有测试 | Python 迁出或删除 | 本任务的 KUnit 项数 |
|---|---|---|
| Wave5 | 13 | 9 |
| HDMI RX | 20 | 9 |
| JPEG | 2 | 2 |
| Meson DRM | 18 | 8 |
| Meson ASoC | 15 | 3 |
| 其余非暂缓驱动（风扇纯逻辑） | 9 | 3 |
| ADLA | 4 | 4 |
| brcmfmac | 1 | 新参数/决策 2，复用 NVRAM 3 |
| PWM | 0（无 Python） | 复用原测试 1 |
| 合计 | 82 | 44（本次迁移 40、原有 4） |

协调解除暂缓后，只执行用户指定的两个合并：内核 `c34249a0729e6` 的第二父为
`0a35577b8de28`，四个原提交保留未改写；主仓库 `2884a56` merge main，README
双方条目均保留。后续内核提交：

| 提交 | 目的 |
|---|---|
| `437a77da87f6e`、`a5310d48b6313` | ADLA 真实 allocator/队列/边界 KUnit，删除四个 mock |
| `11ef9a271b306` | brcmfmac 真实 scan 转换及 capability 决策，删除最后一个 mock |
| `40082674e5ec3` | 清理 30 条失效 MAINTAINERS Python 规则，登记实际音频/显示 KUnit 路径 |
| `514e0f9b81ab7` | ADLA debugfs 标注既有 fallthrough，保持原计算和控制流 |

没有再次修改 PWM/Meson PWM、clk-pwm、PWM regulator 或风扇源码；PWM 的同控制器
ABBA 按[原问题](../pwm-clock-locking.md)保留。上述迁移提交保持原计算和硬件调用
顺序，没有调序重构；合入分支的行为修复沿用已审的
[原记录](2026-11-05-debug-splat-fixes.md)。

VM 工作树 `/home/deepdream/src/linux-7.3-kunit-migration`，通过主仓库 heavy 票
执行，`out=$PWD/.kunit-all-final`。九份现有配置合并、不使用 suite filter，实际命令：

```sh
python3 tools/testing/kunit/kunit.py run --arch arm64 --jobs 8 --timeout 300 \
  --build_dir "$out" \
  --kconfig_add CONFIG_WERROR=n \
  --kunitconfig drivers/media/platform/chips-media/wave5/.kunitconfig \
  --kunitconfig drivers/media/platform/amlogic/t7-hdmirx/.kunitconfig \
  --kunitconfig drivers/media/platform/amlogic/t7-jpeg/.kunitconfig \
  --kunitconfig drivers/gpu/drm/meson/.kunitconfig \
  --kunitconfig sound/soc/meson/.kunitconfig \
  --kunitconfig drivers/thermal/.kunitconfig \
  --kunitconfig drivers/misc/adla/.kunitconfig \
  --kunitconfig drivers/net/wireless/broadcom/brcm80211/brcmfmac/.kunitconfig \
  --kunitconfig drivers/pwm/.kunitconfig \
  --json="$out/result.json"
```

该 WERROR=n 只用于本次组合运行 profile，不修改生产配置或各目录已提交的
`.kunitconfig`，不作为静态门禁通过的证据。完整实际脚本
`build/kunit-migration/all-final-run.sh` 会另查完整 test.log 中的
WARNING/BUG/KASAN/lockdep/panic 输出，不只看 KTAP 汇总。配置包含 generic KASAN
及 PROVE_LOCKING。编译器 GCC 13.3.0、QEMU 8.2.2；有效 sparse 固定
`84ec0658c81db4ccc4aabc420d3dc118c2c6a310`。

失败证据不删除：`build/kunit-migration/all-final-run.log` 保留首次构建的
隐式 fallthrough/WERROR 错误，当次 QEMU 未启动。标注后的普通目标编译见
`adla-fallthrough-compile.log`，DEBUG_FS=y/KUNIT=n 模块见 `adla-debug-module.log`。
完整配置额外 W=1 检查仍因旧的未使用变量被拒绝，见 `adla-fallthrough-build.log`。
标注及 MAINTAINERS 最终 strict checkpatch 输出在 `adla-fallthrough-commit.log`、
`maintainers-final2.log`；后者只本地解析维护者，没有对外发送信息。
`all-final-run2.log` 保留窗口结束后第二次构建的既有 missing-prototypes/WERROR
错误，当次也没有启动 QEMU；最终 WERROR=n 运行输出另记于 `all-final-run3.log`。

最终原始产物同时保存在 VM `.kunit-all-final/` 及主仓库
`build/kunit-migration/`：`all-final-result.json`、`all-final-test.log`、
`all-final.config`，源码与配置核对输出 `all-final-metadata.log`。
内核 tree 为 `d04379581640297230dc0d1624c3457feef14480`。
配置 SHA-256 为 `aae97a541b2c0d83d612072e8f274fe4e973ca609cc7cfa694a4cfc65ca65614`；
Image.gz SHA-256 为 `79ede0237400a4d44944dfb627f988ec88ebc576367e4e9dbcf8329311d26b75`。

范围内建/模块、strict checkpatch、有效 sparse、改动头文件 kernel-doc 均已执行，
逐批实际命令、原始输出及边界见[总清单](2026-11-05-kernel-test-migration.md)的结果链接。
**ADLA 的 W=1/sparse、CRG/TCPM 的 sparse 仍未通过**，保留既有诊断；编译成功或
后续 QEMU 成功都不改写这些结论。准备阶段还有未修改 vDSO 声明诊断，不宣称全树
零诊断。smatch 不可用；没有 binding/DTS 改动。

最终主仓库全测 `python3 -m unittest discover -s tests -p 'test_*.py'`：539 项，
14 skipped，OK，完整输出 `build/kunit-migration/main-tests-all-final.log`。

未做：全部实板标准接口/实流/样本、DMA/复位/恢复、故障注入和模块加载；Wave5
只准备[离线注入方案](2026-11-05-wave5-fault-injection-plan.md)，内部阶段缺口仍保留。
没有访问板子、占板锁、使用子代理、push 或合并到其他分支。
