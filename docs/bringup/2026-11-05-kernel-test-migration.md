# 2026-11-05：内核树 Python 测试迁移

清单先于代码提交。内核基线 `2662456a1a636f668454ab04a1c63f567206a592`，
工作树为 VM `/home/deepdream/src/linux-7.3-kunit-migration`。仅离线，不占板锁。

排除 comedi 和 DRM CI 后共 87 个 Python 文件；其中 4 个是源码生成器，
1 个是禁止修改的 vdec 测试，另有 Wave5 板端工具。不能将 87 全部视为待删测试。
下列分表逐文件登记；未能确认的风险明确标待确认并保留。
非暂缓范围已完成风险确认及迁移，共 77 个 Python 文件迁出/删除，arm64 QEMU
直接测试生产函数累计 34/34；各批结果、实际命令和未验边界如下。

| 已执行批次 | Python 文件数 | 实际 QEMU KUnit | 结果记录 |
|---|---|---|---|
| Wave5 | 13 | 9/9 | [结果](2026-11-05-wave5-kunit-results.md)及[仅离线准备的故障注入方案](2026-11-05-wave5-fault-injection-plan.md) |
| HDMI RX | 20 | 9/9 | [结果](2026-11-05-hdmirx-kunit-results.md) |
| JPEG | 2 | 2/2 | [结果](2026-11-05-jpeg-kunit-results.md) |
| Meson DRM | 18 | 8/8 | [结果](2026-11-05-drm-kunit-results.md) |
| Meson ASoC | 15 | 3/3 | [结果](2026-11-05-asoc-kunit-results.md) |
| 其余非暂缓驱动 | 9 | 风扇 3/3，其余为 V/B | [逐子系统结果](2026-11-05-remaining-drivers-kunit-results.md) |

构建和检查已执行；CRG/TCPM 的既有有效 sparse 诊断按用户决定保留，明确记为
静态门禁未通过，其余各批的检查范围及限制见结果。所有 V/B/F 均待实板，删除
不等于验证通过。Wave5 内部阶段故障注入仍有缺口，不能声称已覆盖。

剩余 10 文件：4 个上游生成器继续保留；1 个 vdec 测试禁止修改；ADLA 四文件、
brcmfmac 一文件按协调要求暂缓，待 t48 确认后再确认风险和迁移。Meson PWM/PWM
regulator 相关代码同样暂缓，基线清单中没有该目录 Python。保留的待确认项未删除，
整个任务仍有协调暂缓范围未完成。两个工作树均只在 `kunit-migration` 提交，未
push、合并、对外发送或访问板子。

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
