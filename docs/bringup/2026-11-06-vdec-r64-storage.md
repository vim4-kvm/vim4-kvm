# 2026-11-06：r64 MR3 存储归属实板验证

按[获批计划](2026-11-06-vdec-mr3-storage-plan.md)完成全部10条：
**10 Success、0 Fail、0 Error、0 Timeout、0计划内未运行**。
MR3从r63的53个错误帧、12对ERROR变为300帧逐字节正确、两队列ERROR为0；
MR4/5和7条对照无回退。正式默认已恢复，未部署，不把子集结果当全集或5.15 parity。

## 候选与离线门禁

候选 `7.3.1-vim4-20261106.30`，源码
`d444ab83f7fab8044eea48902b17310763bb7a04`，GNU build ID
`41acb4d49fabc07b272a7f0b137120145796039e`。无未提交HEVC草稿，没有合入其他topic。
生产配置与正式kernel.config逐字节一致，SHA256
`7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`；
Image SHA256 `a535c31594fb49f6126b78ffd65b7389da2b1f36bea2f650eb2a8a8b8755e86f`，
RAM包SHA256 `dd313b78ef9f85e1734ef105e86cd71e8985ad31c8e5621b2065a9bde645091f`。
完整模块/固件哈希保存在package/bundle manifest，封包后复制到Mac再核哈希。
源码尖的模块/内建W=1、有效sparse、27项QEMU KUnit、strict checkpatch证据见
[离线记录](2026-11-06-vdec-mr3-storage.md)；本次完整生产Image/dtbs/modules构建和封包成功。

排票前保护清单门禁实际拦截过一次：复制r63计划时，文本替换误改了模块名
`panel-jdi-fhd-r63452.ko.xz`。从baseline的files重新生成protected_files后，2372项
逐项相等，候选和10条计划离线校验通过。没有放宽门禁，失败发生在占板/上传之前。
私有Playwright/Chromium离线receiver冒烟通过，板窗沿用Chrome156.0.8078.80。

## 窗口与恢复

FIFO1377，一张30分钟sampling票；连续UART覆盖01:45:42.979至01:51:36.479 UTC，
约5分54秒。入场uptime2704.52秒，proof/视频前后boot_id一致，实际连续观察9.31秒，
按方案C不另等5分钟。候选启动1、正常恢复启动1、非请求冷复位0，未追加启动。
就绪轮询曾见manager尚未active的退出码3，随后正常就绪；不是候选或恢复失败。

恢复正式 `7.3.1-vim4-20261105`（fd41fb5，build ID
`bdbfa439f298e92b5bad092528d11119a974f262`），2372项保护文件和proof再次通过。
4K HEVC视频推进297帧、59.364fps，丢包/丢帧/冻结计数均未增加。
重新上传cleanup helper后清理候选挂载点和目录，owned固件按SHA删除，正式模块不动。
688个任务文件归档Mac、逐个核对哈希后删除板端目录；三条保留YUV均为
300×176×144×1.5=11404800字节。生产O目录10723个*.o已删除，保留Image/ko/vmlinux/封包；
共享visl环境未改动。板票已释放。

## 一致性结果

stateless带流v4l2-compliance **60/60、0 warning**；media/Request **8/8、0 warning**。
Fluster固定commit `45d6dca42398305ac3a3ad9a0712028a2d08d97a`，
JVT-AVC_V1与GStreamer-H.264-V4L2SL，输入包、私有v4l2codecs及官方h264parse
与r63相同，逐流保留实际插件身份。未替换系统库。

| 码流 | r64结果 | 逐帧证据 |
|---|---|---|
| MR3_TANDBERG_B | Success | 300帧逐字节等于JM/FFmpeg，MD5 dd1091f75ac15d3ae70485295b0a116e |
| MR4_TANDBERG_C | Success | 300帧逐字节相等，MD5 5f5f14beca549172487bb74c4d3ba8f9 |
| MR5_TANDBERG_C | Success | 300帧逐字节相等，MD5 5f5f14beca549172487bb74c4d3ba8f9 |
| AUD_MW_E、BA1_Sony_D、BA1_FT_C | 全部Success | 逐行/多slice对照 |
| CAMASL3_Sony_B、CVFI1_Sony_D | 全部Success | MBAFF/field、多slice对照 |
| cabac_mot_picaff0_full、cama1_vtc_c | 全部Success | PAFF/MBAFF及负bottom POC偏移对照 |

10条的OUTPUT/CAPTURE DQBUF ERROR分别均为0，trace overrun/dropped events均为0。
计划之外的125条本轮未运行；JPEG、HEVC、MPEG-2、5.15对照未运行。
无BUG/WARN/Oops/KASAN报告，但生产配置不能替代调试锁与内存验收。

## 存储归属的直接证据

六处dynamic debug均实际启用。用kernel-events.jsonl的
`_SOURCE_MONOTONIC_TIMESTAMP`（内核时间，非journal入库时间）与逐流v4l2 trace关联：

- MR3 decode9的OUTPUT QBUF为49.443710秒、timestamp9000ns，随后49.444050至
  49.444086秒的7个DPB条目均为 `ts 0 buffer 1 canvas -2 flags 0x3 gaps 1`。
- decode10 QBUF为49.448500秒、timestamp10000ns，49.448839秒起再次出现同类7项；
  decode9/10最终两队列DQBUF均无ERROR。这补上了r63仅能离线推断的真实查找路径。
- MR3总计104个“buffer命中但无槽”回退、961个“buffer也缺失”回退；MR4/5各380个
  后者，7条对照没有缺失存储日志。总计1825项，全部flags0x3/gaps1，没有gaps0项。
- 三处config_decode_spec失败出口均未触发。列表占位1464项，colocated占位选择0次；
  列表计数不等于宏块实际引用数，宏块引用仍只引用此前JM离线证据。

结果支持按本驱动拥有的picture/canvas槽判断存储归属，不能仅靠仍留timestamp的vb2缓冲。
V4L2 DPB没有non-existing标志，gaps1本身也不能证明任意未来缺失都是合法缺口；诊断仍保留。
S4只有编译/KUnit，L1[0]占位拒绝仍是已知限制。原Khadas环境110/135统计不改写，
两个Sharp的官方parser行为、HOLD+FLUSH及High profile子集仍未验。

## 原始证据

`build/hwdecode-parity/run64/`保存artifact-identity、offline-validation、execution/window日志、
board-upload.tar及逐文件哈希、retained-output-sizes、pixel-comparison、summary.json。
compare.py和summarize.py是build下的一次性证据分析，不是新增仓库测试。
展开的archive/results保存compliance、Fluster原始JSON、逐流ioctl/trace、插件身份、
dynamic-debug和kernel-events.jsonl。后者SHA256为
`5c5e257f95d0f245d0f401ee726a8221d45acfd1afeb488107b13ab677e48353`。
`logs/hwdecode-parity-r64/`保存连续UART/主机时间戳、入场/恢复proof、视频和complete。
构建原始输出为 `build/hwdecode-parity/mr3-storage/build30.log`。
主仓库全套离线检查588项完成、11项跳过，原始输出为 `run64/main-tests.log`。
