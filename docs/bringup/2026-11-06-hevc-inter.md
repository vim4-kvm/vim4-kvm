# 2026-11-06：HEVC P/B 逐帧路径离线审查

基于已合主线且经 heavy 的 `f7b59cb34cd63d6c4b5469bde747a628abdd413f`，
VM 自有 worktree `/home/deepdream/src/linux-7.3-vdec-hevc-port` 新分支 `vdec-hevc-inter`。
本轮只修两个有明确依据的差异，另补实际生产函数的 DPB KUnit；未碰板、排票、push 或合并。
原系列及 r73 单帧证据边界见 [主线整理](2026-11-06-hevc-mainline-series.md)。

## 三个提交

| SHA | 改动及依据 |
|---|---|
| `c54ad969164a9349f4c969abf39ecfbc44e01e6e` | hevc.c:233、246；MV 池容量按64×64 CTU取整。厂商 get_mv_buf 的实际CTU尺寸算法见 vh265.c:3369–3381，MPRED单位与读端上界见:5191–5205 |
| `b0191218b175c243402313eca04e338f2f1cac94` | RPS、free-slot、输出排序三个既有函数仅加 KUnit visibility；测试 unused-but-retained reference、待输出帧防复用、耗尽、IDR/BLA清引用、B重排跨epoch顺序 |
| `8c0cc0271007af1eb180dc96bcafbbcdd0ddfc70` | hevc.c:941；SAO_CTRL1读写之间补每slice的 DBLK_CFGB=0x5700，宽≥1280加bit4。厂商实际V4L路径:5544–5556；此前只有新图像:5483–5500的0xff00 |

本文厂商路径均相对只读 `common_drivers/drivers/media_modules/frame_provider/`，
目标是 `decoder_v4l/h265/vh265.c`，并非早期参照的 `decoder/h265/vh265.c`。

MV旧注释“最小LCU能容纳所有LCU”在边缘CTU不成立：720×720按16×16分配65536字节，
64×64实际需73728；832×608分别65536和66560。新容量分别131072，覆盖16/32/64三种CTU，
读端END仍使用同一池容量。厂商默认按分辨率档分配较大的固定池，动态分支按实际CTU；
本驱动继续保留独立固定池，只修容量下界，不引入厂商分配器。

DBLK第二次写不是冗余同值写：新图像先0xff00，配置SAO输出时再0x5700；每slice都执行后者。
此次新增写会改变重建期间的最终寄存器值，必须先复验原全I像素，再验P/B。
不以r73在旧值下出过一帧来证明新序列已验证。

## 步骤表增量与未决项

[增量CSV](2026-11-06-hevc-inter-steps.csv) 共131项，按08参数→POC/RPS→图像/MMU→
tile scratch→MC→MCRCC→MPRED→SAO→05/REQ4→0a→输出/回收/EOS排序。
MPRED 16对POC写展开成32项，保留L0→L1顺序。
基线统计：相同111、不同14、缺失5、待证1；新尖端：相同112、不同14、缺失4、待证1。
“相同”仅指静态算法/寄存器表达式一致，不表示已有P/B硬件轨迹或像素证据。
条件分支和循环模板保留在行中，不能将131行不分条件顺次重放；v变量计算参见对应源码函数。
DOS地址为word，字节偏移=word×4；DMA地址须按当前slot、col slot、workspace、CAPTURE角色归一化。

已存在且此次未重写的关键路径：

- RPS解码正负delta、used/LT位；保留used=0但仍在RPS的旧图；列表按负/正/LT及modification建立。
  MC将slot索引写入L0 canvas0、L1 canvas16，ANC2AXI指向各slot压缩头。
- col按当前列表与collocated_ref_idx选图；LDC检查未来POC。MPRED写当前MV、col MV、row jump、
  CTU/tile、引用使能/LT/POC对及读写指针。LongTerm_Curr/Col在厂商和本驱动都为0。
- 每图MMU map指向当前body，旧图header/body/MV一直保留到RPS和待输出所有权都释放；
  每AU复位后重写picture table。CAPTURE线性输出和压缩参考池独立，交付CAPTURE不释放参考body。
- 输出按epoch、POC排序；pending大于SPS reorder数才交付；STOP将尾部pending排序冲刷，
  最后一个有效输出或空CAPTURE带LAST。已有r73仅覆盖单帧，不能证明多帧尾部已闭环。

表中仍不同/缺失的处理决定：

1. **旧压缩图的实际解压读取待证**：静态header/map/table路径存在，I帧不读取旧参考。
   第一条P流逐帧MD5是最直接判据；若首P失败，对齐canvas索引→header→body、col MV和MPRED读端。
2. **完成状态与错误标记**：厂商:11258–11319把frame输入的部分耗尽状态送pic_done；
   当前在有活动图时把0e/20/22/24/50视为错误，保留该保守规则，不能把耗尽当重建完成。
   厂商:6550–6574、11481–11497另查PARSER_LCU_START/错误标记，当前缺该检查。
   如出现异常0a/无ERROR的像素错，最少增加0a时DOS word0x3124低24位与lcu_total的读回，
   以及SHIFT_STATUS的over-decode位；先确认正常流值，再决定如何套用厂商阈值。
3. **三条未消费的MPRED读**：vendor读CURR_LCU、CTRL0、CTRL1后，值未参与最终写值计算；
   当前省略。它们列缺失但没有证据是必需握手，不凭空补延时。
4. **内存和输出策略差异**：厂商scatter/tail回收、V4L图槽绑定与本驱动固定压缩池不同；
   当前保留完整容量，未缺必需回收寄存器。SAO长度采用本驱动64KiB量化的实际CAPTURE容量，
   厂商末尾覆写为V4L luma/chroma size；不改有效stride。
5. **重排/随机访问差异**：厂商默认fast-first-I，本驱动按SPS保留；prevTid0过滤已用KUnit覆盖，
   厂商代码更宽松。CRA/RASL策略、每图SPS reorder变化、长时多次START/STOP不由本次短清单验收。

## 三条最小短清单

取现有封存的JCT-VC HEVC_V1 Main/yuv420p输入，未下载新流。
只读来源为主仓库 `build/hwdecode-parity/run72/archive/avc-hevc/`；
r73计划登记板上bundle `/var/tmp/hwdecode-standard-r73/avc-hevc`。
本轮未登录板，t3k须按 [输入清单](2026-11-06-hevc-inter-vectors.csv) 重核实际输入SHA256，
不能把历史路径当作当前存在性证明。锁定Fluster 45d6dca4与套件摘要见
[来源锁](../../packaging/kernel/vdec-fluster.toml)。

| 顺序 | 流 | 字节 | 416×240帧数/类型 | 覆盖 |
|---|---|---:|---|---|
| 1 | cip_B_NEC_3 | 13228 | 5：I1/P4，reorder=0 | 最小的已扫描简单P，多次参考与slot复用 |
| 2 | MERGE_E_TI_3 | 15971 | 8：I1/B7，reorder=3 | 最小B重排组，col来自L0/L1，尾部冲刷 |
| 3 | TMVP_A_MS_3 | 17238 | 17：I1/B16，reorder=3 | TMVP/col MV跨图读取及持续复用 |

按现有Main流输入大小先扫描最小35条；其中前五条ipcm只有I，不符合目标。
FFprobe实际解码确认上述类型/尺寸/8bit格式，两个B流在显示顺序的packet位置中出现回退。
FFmpeg 6.1.1-3ubuntu5 的trace_headers确认CTU64、DPB字段及reorder，MERGE包含两种col来源。
三条软件解码总MD5均与套件发布者一致：依次为
`1315714c7b3f3237b469259f66d9b7aa`、`6e74dbd450123246c22bf01b389bbe11`、
`168f8096e56b8a8c1aa03fa5fffdfd23`。
[逐帧参考CSV](2026-11-06-hevc-inter-framemd5.csv) 保存显示顺序的30个MD5。
参考按可见I420平面紧凑串接，每帧149760字节，剔除stride/底部padding；不得对DMA容量直接取MD5。
这三条不触发新MV容量边界，容量回归由新增KUnit覆盖，不能冒称已用它们测过边界尺寸。

## 给integration候选的单次清单

1. 先跑r73同流HEVC compliance，至少56/56；原全I首AU逐字节一致且 `Captured 1 frames; status 0`。
2. 同一启动按上述顺序逐流运行既有 `vdec-capture`：
   `filesrc location=输入 ! h265parse ! v4l2h265dec ! videoconvert ! video/x-raw,format=I420,width=416,height=240 ! appsink name=capture`，
   期望帧数依次5/8/17。不截码流、不只抓首帧、不人为提前EOS；沿用官方parser/插件环境。
   每流外层30秒上限，capture自身5秒无帧/无EOS即失败。raw大小应为748800/1198080/2545920字节。
3. 每帧按149760字节切块，以CSV显示序号比较MD5，再比总MD5；必须每项相同、帧数精确、
   输出/CAPTURE DQBUF均零ERROR，`Captured N frames; status 0`，最终LAST结束drain；若继续DQBUF应为EPIPE，不能错误重建CAPTURE。
   保存ioctl、GStreamer、内核逐帧POC/type/slot/refs/col/status及原始I420；同尺寸流只允许初始SOURCE_CHANGE。
4. 任一像素/帧数/EOS/ERROR失败即停后续，保留原始输出，禁现场改寄存器或扩流；
   timeout、DMA停机失败或内核splat沿既有窗口恢复规则处理。本worker不执行板窗。

## 离线验证与门禁

三提交完整format-patch逐个strict checkpatch均0/0/0；git diff --check通过。
新增四项KUnit直接调用生产函数，未抽取源码、模拟MMIO/vb2或增加宿主mock。
协调者已代跑尖端8c0cc027 heavy：EOS fixture PASS、QEMU KUnit 33/33、W=1无新增诊断（仅既有KUnit模块缺MODULE_DESCRIPTION），模块SHA256 `7b736425a25e103f30a23b48be219a486e01fb3792e584c9f12717bdafe1871f`。
VM `/home/deepdream/build/vdec-hevc-port/validate.sh` 已固定尖端8c0cc027，先跑既有EOS fixture，
再跑arm64 QEMU amlogic-*和W=1模块；复用自有kunit/module O=。
Mac副本 `build/vdec-hevc-port/validate.sh`，报告写构建根inter/，语法检查通过。
patch/strict日志、probe、headers、framemd5、输入与发布者摘要核验原始输出保存在
`build/vdec-hevc-port/inter/`；重组前系列heavy已由协调者报告通过，本轮P/B硬件尚未运行。
