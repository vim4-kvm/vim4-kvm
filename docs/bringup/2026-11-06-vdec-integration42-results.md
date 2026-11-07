# 2026-11-06：integration42 的 K10 共存补证与 K9 采证停止

**K10 自然共存通过：Wave5、JPEG encoder、decoder 均绑定，DOS 区域仅由 JPEG encoder 登记。**
r110 随后因 K9 采证脚本要求一个没有调用点的 trace 事件而停止；不能解释成编码器无活动。
第一段实际有600次 Wave5 CAPTURE DQ、约60fps、零ERROR；busy-open、编码器卸载/重载及解码均未运行。
正式恢复期间连续3次冷复位，达到本任务硬停阈值；最终自然恢复，2372 proof及被动4K视频通过。
接口/格式/HEVC132条全 **Not run**。未部署、合并、push、改默认或saveenv；不再排票。

## 候选与离线门禁

沿用已批准的 integration41 计划及工具 `e2ff0eb`，只更新源码和按UTC规则产生的release；
另按协调者要求加入只读 `/proc/iomem` K10证据。仍用无线屏蔽RAM变体，一窗只启动候选一次。

| 项 | 实际身份 |
|---|---|
| 内核 | `3facfaa37284f7193508c2a16fbf5162c6242616` |
| tree | `d29cfb893ae401d53a5a569c5d5f0fb085b3188b` |
| K10 | `5f9a4be44b1d9a92bbdb4707d0aefecef292a975`，仅T7不再申请独占DOS region |
| release | `7.3.1-vim4-20261107.2` |
| GNU build ID | `fa5a9fa53dc3f84802722702f18623730ab81d83` |
| 生产config SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| 普通RAM SHA256 | `3a99942f4cacef21b4254a55cfb8afbe3b71a5b31acb86d2207a3adfdf3f9e3a` |
| 无线屏蔽RAM SHA256 | `5be8eca765f2fda0ea2d7008cb0a9dbad959196dfdd9527d3fd4edcfedce7843` |
| manifest SHA256 | `02ebff518a53a75d6beac98a109996dad10192e23f57df1fd7682772ad2e294b` |
| 统一组件包 SHA256 | `8fb7c55fce771a1ef076a4aa0014b35c5c76c596b78b09067632965f38842fa8` |

按要求复用 `/home/deepdream/src/linux-7.3-vdec-integration40` 和
`/home/deepdream/build/vdec-integration40/kernel`；路径名字含40，实际HEAD是上述3facfaa。
旧f41a9bfd保存为 `vdec-integration40-before42`。先封存O=元数据及两个旧bundle的全清单，
make clean卸除O=端旧硬链接再重编，避免改写旧bundle/debug。
构建后 **.40/.41各3083项文件/链接摘要逐项不变**，两个bundle均保留。

本轮实际跑过生产 W=1 Image/dtbs/modules：1168条既有告警，与.41按文件/文本归一化的集合
零新增、VDEC零；15份驱动真实编译命令含额外告警参数。config与生成auto.conf逐项一致，
DEBUG_FS/DYNAMIC_DEBUG启用，没有KASAN混入。arm64 QEMU KUnit **67/67**，无跳过/崩溃。
统一封包核模块/BTF/vermagic/build ID/depmod/native来源；无线变体只改extlinux.conf/trial.json，
其余2357文件不变。未改DT/binding，不声称重跑无关schema检查。
作者的逐提交W=1/QEMU、strict、DEBUG_FS及sparse门禁只引用其 `build/vdec-fixes/k10` 原证据。

离线检查覆盖：实际上传脚本/资产逐项SHA、2372保护清单一致、旧计划拒绝、缺helper拒绝、
r72/r73/r75拆行ioctl及r107 genpd回放、120条旧Success像素回退拒绝、10个目标改善允许。
K9辅助检查覆盖EBUSY/错误errno/成功open、loaded但未绑定、错误minor/OUTPUT过滤、零活动/ERROR/
过短突发，以及正式无信号与无关失败的区分。新增iomem缺失、decoder/外来部分占用拒绝，
并回放r109实际region错误。它们不证明尚未运行的busy-open/解码通过。
私有Playwright import冒烟及主仓 **610项全套测试通过、17项跳过**，最终输出见 `final-tests.log`。

离线证据根为本工作树 `build/hwdecode-parity/integration42/`：`build42.log`、
`offline-production.json`、`tip.kunit.json`/`tip.qemu.log`、`retained/`、
`retained-bundles-unchanged.log`、`artifact-identity.json`、`identity.json`、
`check110.log`、`k9-offline.log`、`vb2-trace-source.log`。heavy票先结束，未与sampling重叠。

## r110：K10通过，K9在第一段统计停止

FIFO **1626**，sampling、30分钟票。入场正式uptime2532.95→2542.91秒、boot_id不变，
2372 proof和被动3840×2160 **59.96fps**通过。排空UART后开始连续观测；无新增独立无线服务。
输入/EDID未变，未向Mac发HID。候选无线变体仅启动一次，SSH核release/build ID/cmdline/boot_id
与封包一致。候选未发生冷复位。

| 模块 | 实际平台绑定 |
|---|---|
| wave5 | `platform:vdec` → `fe310000.video-codec` |
| t7_jpeg | `platform:t7-jpeg` → `fe320000.jpeg-encoder` |
| aml_vdec_drv | `platform:aml-vdec-drv` → `fe320000.video-codec` |

三个解码节点均存在；`/proc/iomem` 的唯一DOS reservation为：

```text
fe320000-fe32ffff : fe320000.jpeg-encoder jpeg-encoder@fe320000
```

没有decoder region reservation或r109的region申请错误，K10自然共存条件通过。
随后K9 measure9000原始统计：600次CAPTURE DQ、**59.9986fps**、零ERROR、零trace丢失，
One-KVM同一PID853、3840×2160、单客户端，应用统计59.99–60.00fps。
但脚本同时要求 `vb2_v4l2_buf_done>0`，实际为0，故按既定门禁停止，未执行busy-open。

离线源码核对发现采证假设不成立：当前 `include/trace/events/v4l2.h:245` 定义该事件，
`drivers/media/v4l2-core/v4l2-trace.c:9` 导出，但media实现无该事件的调用点。
真实完成路径 `drivers/media/common/videobuf2/videobuf2-core.c:1219` 调用
`trace_vb2_buf_done(q, vb)`，属于另一套 `vb2` 事件。实际2400条trace只有1200 QBUF和1200 DQBUF。
因此这是**采证门禁错误**，不能归因K9租约/编码器无活动，也不能将已收DQ补算成整项通过。
未现场放宽判据、改脚本或补跑。consumer的“page closed”日志发生在门禁异常后的受控终止阶段，
不能代替或推翻板端600次完成证据。后续修采证须保留当前失败记录，另行批准板窗。

原始证据位于 `run110/archive/results/k9/before/` 的bindings、iomem、kernel.log、
measure-9000、vector-9000 trace/stats；主机 `run110/before.log` 保存实际异常。
busy-open、PM/解码前后比较、编码器卸载重载与恢复推流门禁均 **Not run**，不宣称K9整体通过。

## 冷复位、恢复与停止边界

K9门禁失败后正常请求一次正式默认恢复，随后只被动等待，未发额外reboot或再启动候选。
恢复第1–3次Linux均冷复位，第4次自然启动成功：

| 本窗启动 | 观察到的身份 | Linux起点→ROM | 复位前末条内核日志 |
|---|---|---:|---|
| 1：候选 | .42无线屏蔽，SSH确认 | 无复位 | 不适用 |
| 2：请求正式恢复 | banner残缺；正式cmdline及Nov5构建时间，无SSH | 7.543737s | 5.016489，brcmfmac固件加载 |
| 3：自然恢复 | 正式20261105，完整release banner | 8.794253s | 5.968884，brcmfmac固件加载 |
| 4：自然恢复 | 正式20261105，完整release banner | 7.662153s | 6.206355，fusb302 “Initiating hard-reset…” |
| 5：自然恢复 | 正式20261105，banner及最终proof确认 | 无复位 | 正常恢复 |

时间来自连续UART接收块的主机monotonic时戳，非硬件触发器精确时间；缺损banner不补造release。
第4次启动的PD hard-reset行只是复位前时序证据，未测RESET/VBUS/PD，不能据此断定根因。
本任务 **5次Linux启动/3次冷复位**：候选1/0，正式恢复请求/自动恢复4/3，达到累计3次硬停。
按默认启动项归类，正式eMMC累计由≥76/14增为 **≥80/17**；其中本窗首个恢复runtime身份不完整，
严格banner/SSH确认口径为 **≥79/16，另1/1请求正式但未确认release**，两种口径并列保留。

从恢复开始到正式自然就绪 **84.49秒**，在420秒预算内；2372保护文件逐项通过，
被动3840×2160 **59.35fps**、帧12→309通过，无线状态、One-KVM及UDC恢复。
清理前重传helper，仅按marker/归属/哈希清理本任务固件副本、RAM候选和上传目录；
790个归档文件逐项核SHA后才删除板端上传，未触碰其他任务数据。连续UART SHA256：
`19d8f1242a1dec8467fdc8dcf8ecc13900683f15b4ec317547e04eb9f361a661`。
Mac→USB-C功率计→板子拓扑不变，无新功率读数；不将黑名单等同物理断电或据小样本归因。

[132行总表](data/2026-11-06-vdec-integration42-full.csv)全部Not run，Success/Fail/Error/Timeout均0，
原120条Success覆盖0，不作不回退或像素修复结论。CSV SHA256
`802d87305e6b1f60aaa0120437d2c98f77b96b8a995b1d9991c1edd2c2c73b35`。
[完整摘要](data/2026-11-06-vdec-integration42-summary.json)保留逐启动身份及限制、K9实际统计和恢复。
板停在正式 `7.3.1-vim4-20261105` / build ID `bdbfa439f298e92b5bad092528d11119a974f262`；
票已释放。冷复位阈值与采证失败均已报告协调者，不再续跑integration42。
