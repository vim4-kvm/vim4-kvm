# 2026-11-05：内核树 Python 测试迁移

清单先于代码提交。内核基线 `2662456a1a636f668454ab04a1c63f567206a592`，
工作树为 VM `/home/deepdream/src/linux-7.3-kunit-migration`。仅离线，不占板锁。

排除 comedi 和 DRM CI 后共 87 个 Python 文件；其中 4 个是源码生成器，
1 个是禁止修改的 vdec 测试，另有 Wave5 板端工具。不能将 87 全部视为待删测试。
下列分表逐文件登记；未能确认的风险明确标待确认并保留。
当前为初始审计，尚未完成所有断言风险确认，不声称迁移完成。

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
