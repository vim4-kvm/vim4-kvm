# 2026-11-05：内核树 Python 测试迁移

清单先于代码提交。内核基线 `2662456a1a636f668454ab04a1c63f567206a592`，
工作树为 VM `/home/deepdream/src/linux-7.3-kunit-migration`。仅离线，不占板锁。

排除 comedi 和 DRM CI 后共 87 个 Python 文件；其中 4 个是源码生成器，
1 个是禁止修改的 vdec 测试，另有 Wave5 板端工具。不能将 87 全部视为待删测试。
下列分表逐文件登记；未能确认的风险明确标待确认并保留。
全部授权范围已完成风险确认及文件迁移，共 82 个 Python 文件迁出/删除。
逐批 arm64 QEMU 的实际结果如下；九份配置合并后的完整重跑为 **11 套、44/44**，
包含全部 fixup 后的代码。最终提交、实际命令、完整输出及失败证据见
[组合复验](2026-11-05-kunit-final-replay.md)。

| 已执行批次 | Python 文件数 | 实际 QEMU KUnit | 结果记录 |
|---|---|---|---|
| Wave5 | 13 | 9/9 | [结果](2026-11-05-wave5-kunit-results.md)及[仅离线准备的故障注入方案](2026-11-05-wave5-fault-injection-plan.md) |
| HDMI RX | 20 | 9/9 | [结果](2026-11-05-hdmirx-kunit-results.md) |
| JPEG | 2 | 2/2 | [结果](2026-11-05-jpeg-kunit-results.md) |
| Meson DRM | 18 | 8/8 | [结果](2026-11-05-drm-kunit-results.md) |
| Meson ASoC | 15 | 3/3 | [结果](2026-11-05-asoc-kunit-results.md) |
| 其余非暂缓驱动 | 9 | 风扇 3/3，其余为 V/B | [逐子系统结果](2026-11-05-remaining-drivers-kunit-results.md) |
| ADLA（暂缓解除后） | 4 | 4/4 | [结果](2026-11-05-adla-kunit-results.md) |
| brcmfmac（暂缓解除后） | 1 | 新 2/2，复用 NVRAM 3/3 | [结果](2026-11-05-brcmfmac-kunit-results.md) |
| PWM/PWM regulator（无 Python） | 0 | 复用原测试 1/1 | [结果](2026-11-05-pwm-kunit-results.md) |

构建和检查已执行；CRG/TCPM 的有效 sparse、ADLA 的 W=1/sparse 保留既有诊断，
明确记为静态门禁未通过，其余各批的检查范围及限制见结果。组合运行 profile
显式 WERROR=n 保留编译警告，不作为静态门禁通过证据。所有 V/B/F 均待实板，删除
不等于验证通过。Wave5 内部阶段故障注入仍有缺口，不能声称已覆盖。

剩余 5 文件：4 个上游生成器继续保留；1 个 vdec 测试禁止修改，保留其待确认风险。
ADLA/brcmfmac/PWM 的暂缓已按协调解除，先执行指定的内核 debug-splat-fixes 和
主仓库 main 合并，原四个修复提交未改写，随后完成风险清单及迁移/复验。
PWM 原本没有 Python，复用现有 KUnit；同控制器 ABBA 未解决，见结果边界。
本轮风扇源码只读。所有提交仍只在两个 `kunit-migration` 分支，未 push、合并到
其他分支、对外发送或访问板子。

| 分表 | 文件数 |
|---|---|
| [2026-11-05-kunit-inventory-drm-1.md](2026-11-05-kunit-inventory-drm-1.md) | 6 |
| [2026-11-05-kunit-inventory-drm-2.md](2026-11-05-kunit-inventory-drm-2.md) | 6 |
| [2026-11-05-kunit-inventory-drm-3.md](2026-11-05-kunit-inventory-drm-3.md) | 6 |
| [2026-11-05-kunit-inventory-other-1.md](2026-11-05-kunit-inventory-other-1.md) | 6 |
| [2026-11-05-kunit-inventory-other-2.md](2026-11-05-kunit-inventory-other-2.md) | 6 |
| [2026-11-05-kunit-inventory-other-3.md](2026-11-05-kunit-inventory-other-3.md) | 6 |
| [2026-11-05-kunit-inventory-other-4.md](2026-11-05-kunit-inventory-other-4.md) | 1 |
| [2026-11-05-kunit-inventory-hdmirx-1.md](2026-11-05-kunit-inventory-hdmirx-1.md) | 6 |
| [2026-11-05-kunit-inventory-hdmirx-2.md](2026-11-05-kunit-inventory-hdmirx-2.md) | 6 |
| [2026-11-05-kunit-inventory-hdmirx-3.md](2026-11-05-kunit-inventory-hdmirx-3.md) | 6 |
| [2026-11-05-kunit-inventory-hdmirx-4.md](2026-11-05-kunit-inventory-hdmirx-4.md) | 2 |
| [2026-11-05-kunit-inventory-jpeg-1.md](2026-11-05-kunit-inventory-jpeg-1.md) | 2 |
| [2026-11-05-kunit-inventory-wave5-1.md](2026-11-05-kunit-inventory-wave5-1.md) | 6 |
| [2026-11-05-kunit-inventory-wave5-2.md](2026-11-05-kunit-inventory-wave5-2.md) | 6 |
| [2026-11-05-kunit-inventory-wave5-3.md](2026-11-05-kunit-inventory-wave5-3.md) | 1 |
| [2026-11-05-kunit-inventory-audio-1.md](2026-11-05-kunit-inventory-audio-1.md) | 6 |
| [2026-11-05-kunit-inventory-audio-2.md](2026-11-05-kunit-inventory-audio-2.md) | 6 |
| [2026-11-05-kunit-inventory-audio-3.md](2026-11-05-kunit-inventory-audio-3.md) | 3 |

顺序：Wave5 → HDMI RX → JPEG → Meson DRM → Meson ASoC → 其余。
每批先确认原断言风险，再直接测试生产函数；不得重建媒体/DRM/ASoC 框架。
删除前将分表中的待确认项改成有依据的 K/V/B/F/T，未确认项保留。
实板替代验证均记待实板；删除、QEMU 和编译均不证明硬件通过。
每批结果另记提交、实际命令、原始输出位置及未验边界。
