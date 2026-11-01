# 2026-10-31：原生 HDR 第二阶段窗口补审修复

补审03cf31e..ad4f04b后，C1–C4均确认为实际缺陷。本轮只修这四项、追加历史探针核查、
封存r14c并做离线测试；**没有上板、M6操作或新增硬件验收结论**。仍等main登记uhd6后再排窗口。

## 提交与回归

| 项目 | 提交 | 修复及新增测试 |
|---|---|---|
| C1 control ID错位 | `3ce328e6bb8fd6cc6fcf721a96865536ef83afe6` | 按UAPI基类定义CLL=0xa50900、mastering=0xa50901；模拟ioctl核验ID、4/24字节大小、control/query结构大小与非零返回布局；Linux C直接编译系统UAPI作交叉校验 |
| C2 JPEG插件被目录bind遮蔽 | `8c8dbf81d7e26fee6061c2110d89bb9be24f9b5a` | 纳入已验JPEG插件及固定哈希；组装时实际gst-inspect全部公开/通用factory并核对私有库路径；缺JPEG和系统同名副本掩盖缺项均离线拒绝 |
| C3故障后configure重启负载 | `ac270dff27af7a2283610432ab5193fe859b15e3` | 工作入口统一检查故障、截止时间和有效租约/恢复余量；取消先锁存，进行中的configure与stop共用锁排序；不清除故障锁存。受限收证/恢复入口独立，不允许configure/boot混入 |
| C4未取得责任却恢复源端 | `10be5726aa215af4dd25ffdc97fbed8d54410992` | HDR关、空闲及原Chrome前台资格通过后保存源状态；首次HID发出前标记责任，涵盖结果未知；只恢复保存的状态。拒绝路径不关原HDR或原Settings |

C3的确定性并发测试先阻塞已开始的configure，再触发故障、观察取消锁存，最后放行configure；
实际顺序为configure完成→stop，之后再configure不会产生SSH。另测故障、截止、过期/余量不足时
所有工作入口均不发远端请求，监控读失败也停载，恢复入口不能重新放行工作。
C4覆盖初始HDR开、非空闲、首次HID前保存失败、预先打开Settings，以及首次HID结果未知的恢复责任。
真实r13 OCR的Chrome左边缘为41.8像素，资格与打开菜单共用该已观察的菜单栏范围，避免两处资格矛盾。

## r13核查结论

r13实际探针使用**正确ID**；不存在因本次C1而撤销原r13结论的依据。
执行日志先在r12中把错误ID改正，再复制为r13；实际保留脚本也为正确ID且ioctl错误不被吞掉。
内核dc220366的t7-vdin-test实际注册标准CLL/mastering controls，布局同UAPI。
原始脚本、执行链与metadata文件SHA及追加说明见[r13记录](2026-10-31-hdr10-native-final.md#2026-10-31-追加metadata-探针-id-复核)，
历史原始文件未改写。错误ID是在新phase2探针中重新引入，已在C1修正。

**下一次窗口必须重新验证真实metadata一致性**：从这两个正确的V4L2控件取得新鲜数据，与实际
接收的137/144 SEI逐字节比对；任何读取失败都失败退出，不能用历史零值兜底。r13的零值证明
仍只适用于原样本；非零源、HLG/动态metadata没有因软件夹具而变成已验。

## r14c及组装检查

JPEG封存件来自本地 `build/hdr-gpu/libgstvim4jpegenc.so`，SHA与r13基线受保护插件一致，也与
sources.toml中已验JPEG插件相同，无需读取板子。新包只比r14b增加该插件，原有二进制逐个核对SHA不变。
当前[用户态清单](../../packaging/hdr10/phase2-sources.json)已指向r14c，r14a/r14b不再用于后续候选。

| 制品 | SHA256 |
|---|---|
| hdr10-p0-5-userspace-r14c.tar.gz | `57f2730a2eaefaaa767adabf578d19224a2efcb79449b3549a600517bca69ac8` |
| libgstvim4jpegenc.so | `bc21e64cdaf932d7eb25712bcd9e41bd476ad7858de1bbe9e72a202cab5c730b` |
| Panfrost r14c uhd5 RAM干跑 | `18e893fad157df3a7cae797907fc2580e90381e6b752066957279125cc1d2aa8` |
| kbase r14c uhd5 RAM干跑 | `d181f79350ae17b8afe21293ac83165062ba34bc8d7c36a730e2b30f08ae4fdf` |

两份实际干跑各含2341个匹配模块、静态ARM64 PID1及完整清单。归档、清单和检查日志均在
HDR worktree `build/p0-5/`；两包明确 `dry_run=true, hardware_validated=false`，不能上板。
`check-phase2-plugins.py`在组装后的独立目录真正加载8个私有factory、12个通用factory，拒绝
从系统目录意外补齐私有factory。依赖真实设备枚举的v4l2h264enc/v4l2h265enc在离线证明中明确
列为未验，窗口会在配置应用前用 `--device-factories` 补验；不伪造这些factory使离线检查通过。
NULL态插件加载不等于实际HDMI/GPU/编码工作通过。

## 验证与剩余范围

- 主仓全量401项、15跳过、其余通过；新增Linux UAPI编译项在Mac跳过，在ARM64 Linux实际运行通过。
- ARM64 Linux专项26项全部通过，含UAPI布局、缺插件、M6责任及故障排序，不发送实际HID或ioctl。
- 两栈RAM真实组装/静态PID1编译/模块和逐文件清单复验通过；只编译PID1，没有重编内核或未变的应用。
- 日志：`c3-root-tests.log`、`c3-c4-linux-tests.log`、`c2-linux-dry.log`、`r14c-seal.log`，均在`build/p0-5/`。

所有重负载通过共享board-queue heavy排队，无板票据；临时容器已停止。main仍锁uhd5，未改默认5.15、
未合入正式、未发Release。真实UU解码、三应用HDR/缩放/切换、原生期间SDR截图、两GPU栈硬件门禁及
真实metadata一致性仍待统一uhd6窗口，不能把本次离线结果记为实板通过。
