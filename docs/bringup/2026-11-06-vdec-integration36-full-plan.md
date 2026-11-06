# 2026-11-06：integration36 HEVC Main 8bit全集计划

**仅离线准备，未申请板票，未运行全集，未部署。** 继续使用r77验证的同一.36封包，
计划覆盖JCT-VC-HEVC_V1的全部Main/Main Still Picture 8bit输入。目标136条：132条
安排实际解码，4条超当前驱动尺寸上限记Known unsupported；11条Main 10在本轮范围外。
现有封存包147条输入全部重新核验，Not available=0。132条拆成8个FIFO sampling窗口，
每窗目标20分钟、上限30分钟，420秒恢复绝对保留。本文交协调者审批，不据计划自行排票。

## 输入清单、参考与候选身份

完整147行[清单CSV](2026-11-06-hevc-full-vectors.csv)列出套件索引、名称、profile、
输入路径/字节数/SHA、可用性、执行/排除原因、窗口、帧数/尺寸、超时、发布者MD5及
逐帧参考文件SHA。不按文件名猜profile，使用锁定套件字段并核解码格式/尺寸。
Main共135条、Main Still Picture共1条（IPRED_B_Nokia_3），合计8297个参考显示帧。
四条超尺寸共40帧，可执行132条共8257帧。不隐藏不支持项以提高通过率。

Fluster锁为`45d6dca42398305ac3a3ad9a0712028a2d08d97a`（0.6.0），套件JSON SHA256
`778c3cf8724b7f3a9f9ad59d4633531f110e3d660d27f47721b96e148224d04f`，沿用
[vdec-fluster.toml](../../packaging/kernel/vdec-fluster.toml)的真实套件/解码器名。
这里使用标准套件输入和结果，执行器是vdec-capture/v4l2h265dec，报告应称“Fluster套件
经vdec-capture执行”，不能冒称Fluster原生runner结果。保留其原始索引和发布者摘要。

现有VM缓存`/home/deepdream/build/hwdecode-parity-fluster-avc-hevc-complete-v2`与Mac
`build/hwdecode-parity/integration36/fluster-avc-hevc.tar.gz`逐项相符，归档SHA256
`6b00986ed4ddba213f413c83c01a7bd6d4e392d01ee028416cd657eda9cabed4`。
147个输入从归档实际读取，SHA与manifest及本次盘点逐项相等。此包曾在r74–r77等
窗口上传到板并按流程清理，**不是当前板端常驻缓存**；后续批准窗口需重新暂存并核SHA。
本次不访问板子，不联网下载任何新码流。若将来本地/板端缺项，单列Not available，
不临时下载或换输入；哈希不符则停在入场门禁，不能按缺项忽略损坏。

| .36不可变身份 | 值 |
|---|---|
| source | `943198734a1c803d780af845a49ed04fa2e933d6` |
| release | `7.3.1-vim4-20261106.36` |
| build ID | `355061dc85a2fd695429b501c0c2b87078cf1f89` |
| RAM SHA256 | `ac15a2d07aaa58eb1d1b47d03ac30fb154f696e2aade40a13babea72bcb3fc84` |
| manifest SHA256 | `47e6faf309e33147f7b789ddce490ca44aa3bc44b431fd27744416ebac50fa1b` |

即使内容相同的HEVC系列随后合入主线，也不重贴旧包源码身份、不重建本轮候选。
正式恢复身份仍为fd41fb5，不随内核Git主线移动而改变。

逐帧参考已按发布者整流MD5核验136/136：133条FFmpeg、3条HM；其中裁剪和参数集
切换必须使用正确参考路径，见[核验记录及SHA](2026-11-06-hevc-full-reference.md)。
VPSSPSPPS_A_MainConcept_1实际为6帧、6种尺寸，不采用FFmpeg漏帧后的2帧结果。

## 窗口划分与时间、空间预算

逐条归属以CSV的window列及full-plan.json为准，按套件顺序执行，只有参数集/DRC流
移到最后。已知超尺寸项只登记，不故意提交给固件触发超时。窗口编号是计划分组，
不是已批准板票或未来固定r编号；因停窗未完成的尾部另列Not run，续窗仍须协调者批准。

| 窗口 | 流数 | 帧数 | 解码估计秒 | 全部流外层超时之和+每流5秒采证 | 所有流均保留I420的上限MiB |
|---:|---:|---:|---:|---:|---:|
| 1 | 18 | 916 | 121 | 630 | 1369 |
| 2 | 18 | 543 | 109 | 630 | 1011 |
| 3 | 17 | 809 | 112 | 625 | 207 |
| 4 | 16 | 1232 | 122 | 620 | 428 |
| 5 | 18 | 1563 | 143 | 630 | 341 |
| 6 | 17 | 546 | 104 | 595 | 138 |
| 7 | 11 | 1424 | 103 | 445 | 1336 |
| 8 | 17 | 1224 | 126 | 595 | 776 |

估计按每流5秒启动/采证+30fps计算，只用于排窗，**不是T7性能实测结论**。
r77三条inter共30帧及全I门禁在候选约70.5秒内完成，整个UART约205.6秒，但不能
把这个短流速度外推到高分辨率长流。每窗按20分钟目标、30分钟硬上限申请；
8窗名义占板160分钟、最坏批准上限240分钟，不含排队，早停/复位续窗不自动授权。

预算分项：入场/传输/暂存180秒，候选启动120秒，stateless compliance90秒，HEVC
全I门禁60秒，批次最多630秒，恢复420秒，共1500秒，余300秒缓冲。逐流采证实际
超过预估时消耗缓冲；下一流前重新核完整外层超时、采证和420秒恢复预算，不能借用恢复。
后续实施沿用现有vdec-window/watchdog/manifest路径，离线默认、--execute/--at-board
显式执行；先离线验证新的“像素失败继续/超时停止”、拆行解析、变尺寸分帧和恢复门禁，
再进入已批准窗口。本文不宣称全集编排器已经实板运行。

除以下5条均30秒外层超时；500帧长流按至少10fps+10秒收尾留60秒（估算，不是保证）：

| 长流 | 帧数 | 窗口 | 外层超时 |
|---|---:|---:|---:|
| LTRPSPS_A_Qualcomm_1 | 500 | 3 | 60秒 |
| MVDL1ZERO_A_docomo_4 | 500 | 4 | 60秒 |
| OPFLAG_A_Qualcomm_1 | 500 | 4 | 60秒 |
| SAODBLK_A_MainConcept_4 | 500 | 7 | 60秒 |
| SAODBLK_B_MainConcept_4 | 500 | 7 | 60秒 |

vdec-capture已有5秒无帧/EOS等待限制仍保留；无帧超时即使外层尚未到时也停窗。
后续需放宽必须另有证据和授权，不现场反复尝试。每窗入场保留现有6GB可用空间门禁，
流执行前核剩余空间足以保存其最大I420及至少2GB余量。CSV参考总字节可算保存上限，
单条最大579120000字节；成功流可在逐帧/整流校验后删I420，只保摘要；失败流I420全部
保留到宿主归档核验。无空间则尾部Not run并恢复，不为腾空间删除应用或他人文件。

## 入场、执行与逐流证据

1. FIFO sampling入场；uptime≥300秒、连续UART无新复位，正式2372 proof/视频/空间通过。
   重核包、工具/插件和本窗每条输入SHA；运行身份以SSH release/build ID/cmdline/boot_id核对。
2. stateless media/video compliance及DOS=0，再做r77相同HEVC全I门禁（56/56、原首帧
   98304字节逐字节、status0、COMPRESSED|DYN_RESOLUTION、初始事件先于CAPTURE）。
   固定门禁失败停窗；H.264/MPEG-2不重复回归，引用r75同包证据。
3. 目标流使用私有官方1.24.2 h265parse和既有v4l2h265dec/vdec-capture；gst-inspect路径、
   ldd、库SHA与r77 tools-manifest逐项核对。不得回落到Khadas parser或软件解码器。
   管线为filesrc→h265parse→v4l2h265dec→videoconvert→I420 appsink，不限定固定宽高，
   不缩放/截断，不改系统插件。每条完整输入、等待EOS，并以参考帧数核对结束。
4. 输出按可见Y/U/V行紧凑保存；固定尺寸按frame_bytes分帧，DRC按HM确认的6个布局
   分帧，并核逐帧caps/GST/ioctl顺序，不能用第一次尺寸解释整文件。每条校验总字节、
   帧数、全部帧MD5、发布者整流MD5、status0、ERROR/LAST/EOS和事件顺序。
   普通流要求仅初始SOURCE_CHANGE且不意外重建CAPTURE；DRC流允许真实分辨率变更
   对应的重新配置，不能机械套用“一次STREAMON”，也不能把未支持DRC当像素通过。
5. 每条新进程和独立输出目录；结束关闭管线、释放队列，核节点可查询及无硬件故障后
   才继续。禁止自动重跑失败码流。动态调试仅HEVC必要日志，DOS诊断仍关闭。

逐流保留kernel.log（journal cursor增量，不反复全量dump）、GST日志、ioctl原始trace
和摘要：OUTPUT/CAPTURE QBUF/DQBUF计数、ERROR/LAST、SOURCE_CHANGE、STREAMON/OFF、
DECODER_CMD、进程退出/超时、帧数/尺寸、逐帧MD5与首错帧。沿用按线程合并ioctl拆行
的修复；采证失败单列，不用缺证据推断通过。失败I420保留；Success的哈希和布局足以
重建对比口径。输出机器可读JSON及摘要，每条只能落一个主状态，不把Error记成像素Fail。

## 不支持项与判停

| 目标内Known unsupported（预判、未实际解码） | 可见尺寸 | 依据 |
|---|---|---|
| PICSIZE_A_Bossen_1 | 1056×8440 | 超高 |
| PICSIZE_B_Bossen_1 | 8440×1056 | 超宽 |
| PICSIZE_C_Bossen_1 | 528×4216 | 超高 |
| PICSIZE_D_Bossen_1 | 4216×528 | 超宽 |

.36的hevc_priv.h将宽/高上限定为4096/2304，hevc.c:h265_validate_params实际拒绝；
Main10还由P_BIT_DEPTH检查拒绝，本轮11条Main10列Out of scope，不混入136分母。
其余特性不能仅靠名字预判失败；若运行明确报告unsupported，记录返回值/特性证据后
继续下一条。普通像素Fail、缺帧但正常EOS、非超时的单流解码错误记Fail/Error并保留输出，
只在关闭成功、节点仍可用且无下列故障时继续，不用一条像素失败吞掉后续样本。

**停整窗：** 外层或无帧/EOS超时、挂死、BUG/WARN/Oops/KASAN、DMA/AXI错误、
设备不可用、管线无法关闭、恢复异常、关键采证无法完成或恢复预算不足。超时不是
Unsupported；即使已知某特性也不掩盖挂死。未启动尾部逐项Not run，失败流不现场重试。
最终分母分别报告目标136的Success/Fail/Error/Timeout/Known unsupported/Not available/
Not run；11条Main10独立列范围外。输入可用数不等于硬解通过数。

## 早期冷复位一次重试与正式恢复

沿用r77授权语义：仅candidate attempt 1在acceptance前（任何解码执行前）冷复位可考虑
attempt 2；进入acceptance后或解码中复位/挂死直接恢复，不再启动候选。本窗最多两次
候选，分别写attempt、Linux/ROM主机单调时戳、SSH身份与acceptance-start；不重置计数。
第一次冷复位先被动等待正式默认，核baseline成功后才允许第二次；自然恢复再次异常
直接收尾。预算必须覆盖剩余整批，而不是只够一条：预留自然恢复120秒、重新暂存120秒、
候选启动120秒、compliance90秒、全I60秒、剩余批次外层超时+采证、恢复420秒及30秒余量。
例如630秒批次需要剩余≥1590秒；恢复/暂存之后再次核预算，不足则本窗全部Not run，
不会为用完第二次额度侵占420秒。早期重试条件尚未在r77触发，不称其已实板验证。

最终恢复正式7.3.1-vim4-20261105、fd41fb5、build ID
`bdbfa439f298e92b5bad092528d11119a974f262`，2372项proof逐项相等、视频推进通过。
冷复位后只被动等待自然默认、最多两次自然启动，持续失败停止交协调者，不主动循环。
清理helper先检查/重传，owned固件副本逐项核哈希后删除，正式模块不动；本窗上传/失败
I420归档到Mac核验后删板端，释放sampling。密码只stdin，不改默认项，不现场部署。
USB-C供电/HID连接Mac背景只记未测量，不据成功/复位次数归因供电上限。

## 离线证据与审批交付

原始证据目录见[参考核验](2026-11-06-hevc-full-reference.md)，软件参考仅用heavy票，
没有板票。全套检查输出为build/hwdecode-parity/hevc-full/main-tests.log。
提交前实际607项OK（11项跳过）；初次单篇超过12KB的文档门禁失败已拆分修复并保留日志。
批准前不生成执行中的板票或修改正式包。
