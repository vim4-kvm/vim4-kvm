# 2026-11-06：.36 HEVC inter短流验收计划

本轮只离线构建和准备，**未排板票、未部署**；完成封包后交协调者批准。
申请一张FIFO sampling票，目标15分钟、上限30分钟，只启动一次.36，不重试、不扩输入。
顺序为compliance/DOS=0→H.264三流→MPEG-2四流→HEVC原全I回归→三条inter流。
始终保留420秒恢复正式fd41fb5及2372项proof/视频，不更改默认启动项。

## 来源、构建与身份

独立工作树`/home/deepdream/src/linux-7.3-vdec-integration36`基于主线
`f7b59cb34cd63d6c4b5469bde747a628abdd413f`，no-ff合入HEVC inter尖
`8c0cc0271007af1eb180dc96bcafbbcdd0ddfc70`，无冲突、无内核未提交草稿。
最终源码`943198734a1c803d780af845a49ed04fa2e933d6`，tree
`e79fc53a3418069b8559cc1c54be64c713d199d5`。主线已含AVC/MPEG-2/quiet/HEVC整理版，
不再叠加旧实验分支。增量三提交为MV容量、DPB KUnit和每slice DBLK_CFGB，
依据及未决差异见[inter审查](2026-11-06-hevc-inter.md)。

生产配置与正式kernel.config相同，含CONFIG_DYNAMIC_DEBUG，不加调试片段。
生产O=复用`/home/deepdream/build/vdec-sequence/kernel`，独立QEMU复用
`/home/deepdream/build/hwdecode-parity-kunit`，共享visl未动。生产W=1 Image/DTB/modules
构建同时作为分支尖模块门禁；未改DT binding/DTS，本轮不重复逐提交全系列审查。
本集成尖端已实际运行arm64 QEMU KUnit **33/33、无跳过**，tip.kunit.json/log和
tip.qemu.log保留原始结果；不把协调者此前topic验证冒充本集成验证。

生产W=1 Image/DTB/modules、外部模块及统一/RAM封包实际完成；解码目录零诊断，
全树1168条其他目录warning。规范化工作树路径后与.35完整构建比较，无新增独特
warning文本，不写全树零警告。构建前后cmp确认正式配置不变；原始build36.log和
warnings.json保留。heavy票1471已释放，没有板票或sampling。

| 最终产物 | 身份 |
|---|---|
| release | `7.3.1-vim4-20261106.36` |
| GNU build ID | `355061dc85a2fd695429b501c0c2b87078cf1f89` |
| RAM candidate.tar SHA256 | `ac15a2d07aaa58eb1d1b47d03ac30fb154f696e2aade40a13babea72bcb3fc84` |
| package manifest SHA256 | `47e6faf309e33147f7b789ddce490ca44aa3bc44b431fd27744416ebac50fa1b` |
| config SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA256 | `528165c9954ad8b66d75a8c4e4394b320501d60bb0fb13e5c0c6277afc310f67` |
| 生产未压缩aml-vdec-drv.ko SHA256 | `3c766ae3dec13bde9ef7b09d396aa6c35d298f76a8ba54ca2ae3820660e3b186` |

VM产物位于`/home/deepdream/build/vdec-sequence/bundle36/`，Mac副本位于
`build/hwdecode-parity/integration36/`；copy36.py逐文件核对VM/Mac哈希，
artifact-identity.json保存来源。sources36.toml仅锁本候选，正式sources.toml未修改。
finalize.py实际校验包内容、源码锁/build ID、基线身份及2372项protected_files逐项相等；
默认离线window.py通过，未带--execute。计划暂用r74，已检查无旧运行路径且video.py
实际存在、哈希一致；入场仍须核当时板端身份，不把离线相等当作实板证明。
日志为copy-artifacts.log、offline-validation.log、window-offline.log和plan-path-check.log。
提交前主仓库全套实际607项OK（11项跳过），原始输出为main-tests.log。

## 离线资产与采证

沿用已封存Fluster归档和私有插件，16项工具/插件逐项重核哈希，不改系统库。
三条输入在现有fluster-avc-hevc.tar.gz中，已按[输入CSV](2026-11-06-hevc-inter-vectors.csv)
核字节数/SHA256；30个显示帧MD5按[参考CSV](2026-11-06-hevc-inter-framemd5.csv)
写入本轮validation-plan.json，检查每条索引连续、帧数/尺寸/可见字节数一致。
来源锁仍为vdec-fluster.toml，不下载新流或生成新测试样本。

上板资产解包后、启动候选前，重新读取板端三条完整码流校验SHA256和字节数，保存
hevc-input-checks.json；不以宿主正确代替板端检查。每条解码前再次检查输入身份。
外层与内嵌SSH程序已离线语法检查，不登录板子。原始工具/脚本均在
`build/hwdecode-parity/integration36/`，执行仍须显式--execute/--at-board和板票。

MPEG-2期望值精确选取r73四条驱动输出`name+'.out'`，禁止以`_ref.yuv`作输出身份。
板端先核输出大小/SHA，归档后宿主再实际逐字节比较；原始`.out`完整保留。
r73曾误选参考文件的缺口不再沿用，见[r73记录](2026-11-06-vdec-r73-eos.md)。
已对照主线整理后的实际诊断：before-reset读回已移除，窗口不再要求该旧字符串；
保留有效首AU检查、after-start/timeout读回和实际compliance/像素/EOS判据。
HEVC secure加载日志已降为dev_dbg，HEVC段仅按format选择开启这些日志，
不全开aml_vdec_hw.c的DOS step；收尾关闭，不改变前面DOS=0门禁。

## 单次窗口清单

入场uptime≥300秒、连续UART无复位且前后boot_id相同；核正式proof、视频、空间、
私有浏览器冒烟。候选SSH release/build ID/cmdline/新boot_id逐项匹配，不能只认UART单行。

1. stateless media及带流compliance零失败/零警告；关闭动态调试时DOS step=0，否则停窗。
2. 官方parser下MR3_TANDBERG_B、BA1_FT_C、cabac_mot_picaff0_full均Success；三条ioctl保留，MR3保留像素和队列trace。
3. MPEG-2 sony-ct1/ct2/ct3、mcp10ccett顺序运行；私有修正库路径/ldd/SHA门禁不符整段未运行。要求两队列零ERROR、实际输出等于r73；Sony旧整流像素Fail仍照实登记，不当作新回归。保存逐流kernel.log/ioctl/I420输出。
4. HEVC先跑r73同一全I输入：streaming compliance≥56/56、零失败/零警告，再抓原首AU。首帧98304字节、三个平面与原参考逐字节相同，明确`Captured 1 frames; status 0`且进程退出0。ENUM_FMT须COMPRESSED|DYN_RESOLUTION，初始SOURCE_CHANGE在CAPTURE分配前消费、仅一次CAPTURE STREAMON。DBLK_CFGB改变硬件最终写值，**本步失败即停止HEVC，不跑inter**。
5. 前项全过后依下表逐流解码；完整输入、不截流、不提前EOS。每流外层30秒，capture自身5秒无帧/无EOS仍失败。任何像素/帧数/EOS/ERROR失败即停后续HEVC流，保存已失败和未运行状态，不现场改参数。

| 顺序 | 输入 | SHA256 | 帧数 | 紧凑I420总字节 | 覆盖 |
|---|---|---|---:|---:|---|
| 1 | cip_B_NEC_3 | `786e5bd6ac5418f1e4950fc9c5251826128b15d94eda29679b72a4f79d8a77f7` | 5 | 748800 | I1/P4，reorder=0 |
| 2 | MERGE_E_TI_3 | `e5f1f706176e91b72d13686b8864fe1c8e8be764faa417e3cabbf0df1cf78af0` | 8 | 1198080 | I1/B7，reorder=3 |
| 3 | TMVP_A_MS_3 | `33556aa42355ba43575a6e6f1b579420a9217f576fc0ae07ee57fa2750a38d52` | 17 | 2545920 | I1/B16，TMVP/col读取 |

三条均416×240、每帧149760字节；由既有vdec-capture按可见Y/U/V行紧凑写出，剔除stride
与底部padding，不对DMA容量直接取MD5。逐帧MD5须与CSV显示顺序全同，总MD5须与
发布者一致，并要求`Captured N frames; status 0`、精确字节/帧数、两队列零ERROR、
CAPTURE LAST结束drain。若继续DQBUF，检查EPIPE；只允许初始SOURCE_CHANGE及一次
CAPTURE STREAMON，不错误重建CAPTURE。保存I420、ioctl、GST、内核逐帧POC/slot/refs/
col/status日志及比较JSON；失败也保留已经输出的帧，不仅保存最终MD5。

HEVC仅在剩余≥3+7分钟时开始，整段最多180秒；每次新流前须至少余35秒测试预算。
不足则后续未运行并收尾。入场/上传/启动180秒、stateless90秒、H.264 60秒、MPEG-2
180秒、HEVC180秒、恢复420秒，另留690秒余量，总1800秒；不侵占恢复时间凑完清单。

## 停止、恢复与结论边界

Timeout、ERROR缓冲/结果、WARN/Oops/BUG、AXI/DMA失败、挂死、设备不可用、采证失败
或预算不足均立即收尾；DOS非0也停。普通MPEG-2既有Fluster像素Fail继续收集，但偏离
r73输出停止。HEVC任一步失败只停止后续HEVC并恢复，不抹去前面格式结果。
禁止重试、追加候选启动、换输入或现场改寄存器；未运行、失败、通过逐项分别记录。

请求恢复正式7.3.1-vim4-20261105（fd41fb5、build ID bdbfa439f298e92b5bad092528d11119a974f262）。
若冷复位，最多被动观察两次自然启动，持续失败停下交协调者，不主动reboot循环。
清理前检查/重传helper，只按归属/哈希清本任务固件和RAM候选，正式模块不动。
2372项保护文件逐项一致、视频推进通过后，归档核哈希并删本轮板端上传，释放sampling。
O=对象在封包且窗口结束后清理，封包/日志/共享visl保留。冷复位样本照既有口径计数，
不根据单窗成功判断稳定性。

本轮三条不触发新增MV容量边界，边界由KUnit覆盖，不能冒称已做边界尺寸实板验证。
完整HEVC标准全集、10bit、途中DRC、CRA/RASL、长时多次START/STOP、性能/共存、5.15
有效对照及锁/内存调试均未纳入，不将短清单通过推广为完整5.15 parity。
