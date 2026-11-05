# 2026-11-05：KUnit 提交说明与利用率分支审查返工

此前只对 diff 跑 strict checkpatch，漏掉提交正文和 Signed-off-by，原“通过”
不足以代表完整提交检查。本次先合入主仓库 main 的新规则（merge `9e82115`，
包含 `f57be2f`），再逐提交补实际变更、原因和 bringup 中已经完成的验证结果。
正文按约 72 列换行，Signed-off-by 使用 debug-splat-fixes 本地提交的同一身份。
没有把未完成的硬件或静态检查写成通过。

## 只改提交信息的独立证明

通过 `git rebase -i -r --no-update-refs 2662456a1a636` 保留合并结构。
四个 debug-splat-fixes 提交在 todo 中直接 reset 到原提交，不重建其对象；
只改本分支提交说明及一个以 sparse 工具命名的 DRM 标题。

消息阶段完成后的 HEAD 为 `c3bbaea0d70da`。实际命令及输出：

```text
$ git diff --exit-code 514e0f9b81ab7a293a678546d336c4f8f6ec63ec c3bbaea0d70daf989cc9b0412fa4af5e09d91245
exit status: 0; diff output: empty
$ git rev-parse OLD^{tree} NEW^{tree}
d04379581640297230dc0d1624c3457feef14480
d04379581640297230dc0d1624c3457feef14480
```

原始输出在主仓库 `build/kunit-migration/history-review/metadata-tree-proof2.log`。
原 `c34249a0729e6` 合并重建为 `e7e7c8f061f77`，仍有两个父提交，
第二父仍为 `0a35577b8de28`。以下四个 SHA 原样保留并验证为最终 HEAD 的祖先：

- `17d29954473b6`
- `496597ebdf195`
- `4c4126df2f8aa`
- `0a35577b8de28`

该空 diff 只证明消息修订阶段；下述按审查要求单独处理的行为修复另有文件差异，
没有将其混作“只改消息”。

## 撤销 fallthrough，恢复厂商旧分支的 break

原 `514e0f9b81ab7` 添加 fallthrough 的判断不成立：旧分支的
`2048 * cur_freq` 随即被 S6 值覆盖，不能仅为消除告警声明它是有意的。
消息阶段后撤掉其临时版本 `c3bbaea0d70da`，该提交不在最终分支历史中。

只读核对厂商 5.15 common_drivers，文件为
`drivers/adla/kmd/drv/port/platform/linux/adlak_debugfs.c`。其
`1089974722fff`（adla: update drivers）新增 S6 信息和 `0x301` case，
将新 case 插在原来的 break 前；父版本明确是：

```c
case 0x00000100:
case 0x00000200:
case 0x00000300:
        dev_macc_count = 2048 * cur_freq;
        break;
```

由父版本与新增分支差异可确定：旧版本本来在当前时钟公式后退出。
`7e35e3bcc51a2` 单独补回 break，使旧硬件版本不再落入 S6 的固定最大频率公式；
S6、调度、clock、DMA 和 MMIO 路径没有改动。

**需实板回归：只影响利用率显示。** 该属性由 adlak_debugfs.c 中的
utilization show 路径提供，本轮未测实际利用率值。没有凭编译或 KUnit 将显示
行为改动记为实板通过。相对审查前 HEAD 只有这一处文件变化；忽略缩进的语句差异：

```diff
-fallthrough;
+break;
```

原始证据：`vendor-s6-change.patch`、`vendor-before-s6.c`、
`drop-fallthrough.log`、`break-commit.log`、`final-tree-diff.log`，均在上述
`history-review/`。厂商工作树未写入任何改动。

## 每提交完整检查与离线验证

实际对每个非合并提交执行：

```sh
git format-patch -1 --stdout "$commit" |
  scripts/checkpatch.pl --strict --ignore FILE_PATH_CHANGES -
```

消息阶段及最终分支各 **29/29** 通过（本分支 25 个、原修复 4 个），
均零 error/warning/check。最终 25 个本分支提交包含独立 break 修复，
不再包含原 fallthrough 提交。仅按要求忽略 FILE_PATH_CHANGES，未忽略提交信息检查。
第一次完整检查发现 DRM 标题以工具命名，该失败原样保留；改为实际变更后复验通过。

主仓库 `build/kunit-migration/history-review/` 保存：

- `rebase-messages.log`、`rebase-messages2.log`：保留合并结构的重写输出。
- `checkpatch-metadata-summary.log`：第一轮标题警告；`checkpatch-metadata2-summary.log`
  为消息阶段 29/29；`checkpatch-final-summary.log` 为最终 29/29。
- `checkpatch-metadata2/<完整SHA>.patch/.log` 与
  `checkpatch-final/<完整SHA>.patch/.log`：逐提交原始 format-patch 和检查输出。
- `break-builds.log`、`break-builds2.log`：DEBUG_FS=y 的 arm64 内建对象、KUNIT=n
  ADLA 模块 W=1/C=2 实际重编；日志有 CC/CHECK。既有 vendor 未使用变量、原型、
  格式和 sparse 诊断保留，**W=1/sparse 门禁仍未通过**。
- `break-diff-style.log` 保留首次缩进警告；修正 tabstop 后差异检查通过，
  最终完整提交检查也通过。
- `main-tests-message-rule-merge.log`：主仓库合并新规则后全测 540 项，
  14 skipped，OK。最终结果文档全测另附。
  本次全部记录更新后的完整主仓库测试为 540 项、14 skipped、OK，原始输出
  `history-review/main-tests-final.log`。

原始数据也在 VM 本工作树的 `.kunit-history-review/`。只改消息不重做内核编译，
以空 diff 和相同 tree 保留已有代码验证；单独 break 修复重新编译并作运行回归。

新提交 `7e35e3bcc51a2` 的完整 arm64 QEMU **11 套、44/44，通过，0 skipped**。
使用九份原配置与既有运行 profile WERROR=n，generic KASAN/PROVE_LOCKING；
完整运行日志未命中 WARNING/BUG/KASAN/lockdep/panic 错误特征。WERROR=n 保留编译警告，
不改变 ADLA、CRG/TCPM 静态门禁未通过的结论。全部 V/B/F、实际利用率显示、
Wave5 故障注入和 PWM 同控制器 ABBA 的边界继续保留。

运行实际命令复用 `build/kunit-migration/all-final-run.sh`，即组合复验记录中的
九配置无 suite filter 命令。新的完整输出为 `history-review/final-kunit.log`，
原始 KTAP/JSON/配置分别为 `final-test.log`、`final-result.json`、`final.config`；
源码与配置身份见 `final-metadata.log`。新内核 tree 为
`d8a6d3ec7b67bbb8318f98caff544554a107d610`；配置 SHA-256 为
`aae97a541b2c0d83d612072e8f274fe4e973ca609cc7cfa694a4cfc65ca65614`，Image.gz
SHA-256 为 `4f4d4a68c2d798385cfc374f9d9243300898c7734e46ecdc3472cf9f447a71ee`。
这些文件都在主仓库 `build/kunit-migration/` 下，旧运行原始输出保留未覆盖。

## 新旧 SHA 对照

历史 bringup 和原始日志保留实际验证时的旧 SHA；当前分支按下表对应，
除另列 break 修复外仅变更提交信息。

| 审查前 | 最终分支 |
|---|---|
| `d357c8011be41` | `17e860ed364b1` |
| `1bb4eee1fb3c1` | `2fe18556e9be4` |
| `555dcc06f70b4` | `5b42bb43f0eb1` |
| `8d3530f41a4db` | `bbfcec123c1a7` |
| `3e974b369efca` | `97060bbb5792a` |
| `610d4b7218873` | `cc98d5834487e` |
| `e05cc33e80edf` | `32908a2b9918c` |
| `bebd278ea650c` | `655fe4fb4620b` |
| `3f8048acd1eda` | `e629ca750b803` |
| `cc7e380b3d8dc` | `c7325ce0a8117` |
| `97c02ec109ecd` | `d1eb93b4348a3` |
| `8ae2f94521141` | `3f2b06bb7c603` |
| `6c262d98e42db` | `37761d3e1e4fc` |
| `dba6936a6cdd0` | `4d241db853a27` |
| `5eb8482550622` | `2440538e5860a` |
| `399eaac6de011` | `a520165f2fabe` |
| `60d3da1419ffa` | `1258768645d85` |
| `3f58f9e78a75f` | `e1306cc8fef06` |
| `66ebbb5c5719b` | `58058fc64ccfa` |
| `d4eee9d02eede` | `5671f99b59b06` |
| `437a77da87f6e` | `fb081104cf14b` |
| `a5310d48b6313` | `82d4d12207f29` |
| `11ef9a271b306` | `7e8afb2e6b024` |
| `40082674e5ec3` | `7ce6e3435ed85` |
| `514e0f9b81ab7` | 撤销；临时消息版本 `c3bbaea0d70da` |
| `c34249a0729e6`（合并） | `e7e7c8f061f77`（保留双父结构） |
| 新增行为修复 | `7e35e3bcc51a2`，需实板回归 |

未访问板子、未占板锁、未 push、未使用子代理。仅改授权两个工作树；
本轮风扇、PWM/clk-pwm/regulator 源码保持不变，原四个修复 SHA 未改写。
