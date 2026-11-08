# 2026-11-06：.32 integration 离线封包与板窗计划

本轮仅离线准备，**未排板票、未部署**。计划提交协调者批准后，才使用一张FIFO
sampling票，目标约15分钟、上限30分钟、只启动一次候选。正式恢复目标仍为
7.3.1-vim4-20261105（fd41fb5），不改变默认启动项。

## 源码与封包

独立工作树`/home/deepdream/src/linux-7.3-vdec-integration32`，从主线
5dd4f646bcd8af7b9749bf1396c2a9a2ebf04e5f依次no-ff合并：

1. HEVC `f065c6712f7e034918d5473fdd6778e4e636eef3`：ACTION/reset基础上WAIT_FLAG=0、输入诊断。
2. quiet-power `efe8d3689a77ec36a3d02556bb6601cb9a22acef`：常规DOS/电源诊断降为dev_dbg。
3. MPEG-2 `aaec5091f3dc411daba42eb3cb24d3fc254d1937`：允许合法单向参考B，保留真实丢参考错误。

三次均无冲突，最终头`6dd53c32b88975e6f962c65b785581d34e5c223e`，tree
`490dacd43d87bc50e50478a0d1e4aebf01ef2b11`。没有未提交的内核草稿。
生产O=复用`/home/deepdream/build/vdec-sequence/kernel`，配置与正式kernel.config
逐字节相同，其中已启用CONFIG_DYNAMIC_DEBUG=y，不加调试配置片段。
原始构建、合并、资产和计划位于`build/hwdecode-parity/integration32/`。

最终头的W=1完整modules目标实际编译并链接通过，从O=下取到的aml-vdec-drv.ko
SHA256为`4a2a0f0b5b8bba4762a0ddf48075ef422a3be8bb21ba9d26db427c4681db6d8f`；
这只是分支尖验证产物，不用于混装候选。该次全树有59条其他警告，解码目录零诊断，
不能写成全树零警告。arm64 QEMU KUnit为28/28通过，原始输出为tip.module.log、
tip.module.sha256、tip.kunit.log/json和tip.qemu.log。
等待MPEG-2时中止的旧集成头检查及初次生产构建分别保留在pre-mpeg2/和
build32-interrupted.log，不计入最终通过结果。本集成未改binding或DTS，未另跑schema检查。

生产W=1 Image/DTB/modules、外部模块和统一包均完成；构建前后cmp确认正式配置不变。
VM包位于`/home/deepdream/build/vdec-sequence/bundle32/`，Mac核验副本位于上述integration32目录。

| 产物身份 | 值 |
|---|---|
| release | `7.3.1-vim4-20261106.32` |
| GNU build ID | `e1a0cd5f0c6d1d166f3c877b52812ccc9ec6fe6a` |
| RAM candidate.tar SHA256 | `a7bc25de56d21e0847982f081efc749f6545f09069fa60440833aa4364cd011c` |
| package manifest SHA256 | `a44c8c47bdfc8b007d6ecf9b27ef1bab498477d7a096b97180326243879ac433` |
| config SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA256 | `e5c98784350d69077573ff8038b23ac4938e360b317687d17b170518fd781964` |

`artifact-identity.json`记录复制源与实际哈希；`sources32.toml`仅为候选锁，正式sources.toml未改。
`finalize.py`已校验完整封包、源提交、baseline身份与候选baseline_files，并从当前baseline.json
生成validation-plan.protected_files，2372项逐项相等。工具逐文件哈希及Fluster归档与r69
身份核对通过，计划无旧run目录。执行草稿remote.py保持--execute/--at-board门禁，
没有执行板端路径；原始核验输出见copy-artifacts.log、offline-validation.log及build32.log。
主仓库提交前全套595项检查通过、11项跳过，原始输出为main-tests.log。

## 窗口顺序与预算

顺序固定：入场 → stateless compliance → H.264十条 → MPEG-2六条 → HEVC短清单 → 恢复。
软预算为入场上传/启动180秒、compliance90秒、H.264120秒、MPEG-2180秒、HEVC180秒；
恢复/归档/视频420秒绝对保留，其余630秒可借用。HEVC仅在剩余≥3+7分钟时开始，
不满足则整段记未运行。单条Fluster30秒，HEVC捕获30秒；现有进程树watchdog不变。

入场要求uptime≥300秒、连续UART无复位、采证前后boot_id一致，正式proof和全部
保护文件一致，私有浏览器离线冒烟、视频和空间门禁通过。采用r69实测的SSH启动身份
门禁：release、GNU build ID、封包APPEND及新的boot_id逐项核验，就绪后再复核；
连续UART只负责启动/复位计数及证据，丢banner的已知边界沿r67记录。

普通像素Fail保存后继续；Timeout、BUG/WARN/Oops、设备/DMA/停机异常、采证失败或
恢复预算不足立即收尾。冷复位不重试候选，最多观察两次自然恢复。HEVC失败只停止
HEVC并恢复，不改变前面格式的结果，不换流重试。

## stateless 降噪回归与 H.264

关闭aml_vdec.c、aml_vdec_hw.c、h264.c和hevc.c的dynamic debug并保存实际设置。
stateless media/video带流compliance必须通过；从增量journal统计DOS step行数，
预期0，非0保存现场并停止后续回归交审。WARN/ERROR原文不被降噪过滤。
这只验证此次降噪范围和队列回归，不替代调试内核锁/内存检查。

使用r69锁定的官方parser/插件，跑MR3_TANDBERG_B、MR4_TANDBERG_C、MR5_TANDBERG_C，
加AUD_MW_E、BA1_Sony_D、BA1_FT_C、CAMASL3_Sony_B、CVFI1_Sony_D、
cabac_mot_picaff0_full、cama1_vtc_c七条对照。保留MR三条输出与trace，按原参考比较；
全部是此前通过流，出现Fail即记录回归，不扩大采样、不现场修改。

## MPEG-2 六条

按[worker清单](2026-11-06-mpeg2-r69-analysis.md#下一窗清单仅-6-条)：先sony-ct1/ct2，
再mcp10ccett、sony-ct3、bits_conf_lep_11、Tek-5.2_conf4。只使用r69 fixed组私有
parser/v4l2codecs/codecs，路径、ldd解析与SHA身份门禁全部通过后才运行；不符跳过
该段，不影响其他格式。系统库不替换，不夹带未受本修复影响的漂移流。

保留I420、ISO输出、完整ioctl、QBUF/DQBUF及内核日志。两条Sony分别应有60/24显示帧；
单列timestamp1/2的CAPTURE ERROR、显示0/1是否仍全零及这两帧ISO误差；后续帧
与r69 fixed逐帧比较，相异先解释。全流仍按原ISO容差，不因消除零帧改判Success。
四条对照必须保持通过。像素分析只作一次性证据，不新增像素生成/比对测试。

## HEVC 有效输入与首帧

按HEVC短清单，只启用hevc.c +p。
固件/电源预检、IRQ起点采证后，compliance显式送r69同一hevc-intra.vhdr（16 AU）。
核对首AU5999字节（0x176f）、前缀`0000000140010c01ffff040800000300`、skip=0及
启动前WAIT_FLAG=0；保存ACTION/reset三时点、IRQ差值、SOURCE_CHANGE和停机日志。
compliance失败即停；没有有效输入证据的超时单列，不能算有效码流回归。

compliance和输入证据通过后仅捕获一帧。输入从该Vhdr原样提取首AU，5999字节，
不重新编码；VM FFmpeg已实际解码得到唯一256×256 I420帧、98304字节，与原16帧
参考的首帧逐字节相等。首AU SHA256为
`b1156fde7a491f62a774491c9be2a3fdd7cf57761f4e5b7338bb59729739574e`，参考整帧SHA256为
`45f7799c139bd16f32def71d02a08ec07ee7d248ef8181ac3d1803664f7d3307`。
三平面哈希、完整输入和参考输出由hevc-first.json、first-reference.log锁定。

保存可见I420和stride，比较尺寸/整帧/三平面哈希；不等时仅在宿主离线量化误差，
不提高容差。本次只证明开启诊断时的单AU首帧；P/B、诊断关闭复验和全集均不运行。

## 恢复与证据交付

HEVC失败保存input、三阶段/timeout快照、IRQ和AXI停机日志。正式恢复按r60/r69流程，
清理前确认helper存在，不在则从仓库重传。核对全部baseline保护文件后，按归属和
哈希清理本任务固件/候选；正式模块及应用数据不动。验证视频推进与丢帧/冻结/丢包，
归档逐项校验后立即删除板端本轮目录。

输出逐流原始JSON/摘要、compliance、增量journal游标与原文、UART及主机时间戳、
模块/插件身份、输出与reference哈希、恢复proof和视频。通过、Fail、Timeout和未运行
分别列出，不因一个codec失败抹去其他codec结果。计划当前只供审核，不授权排票。
