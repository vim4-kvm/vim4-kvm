# 2026-11-06：T7 HEVC 厂商序列移植候选

交付七个内核提交及[寄存器目录](2026-11-06-hevc-vendor-registers.csv)。未上板，未出帧；
尖端f21dfc47由协调者经heavy代跑：W=1、KUnit 25/25通过，模块`58bf25309444`。
接续启动证据与[r70 结果](2026-11-06-vdec-r70-integration32.md)。

**路由更正**：amvdec_ports实际选decoder_v4l/h265；本文及CSV的decoder/h265是对照源，
并非V4L实际入口。parser自检差异及r71排序见[08前定位](2026-11-06-hevc-pre08-analysis.md)。

## 身份与分支选择

厂商根为相邻主仓库只读 `common_drivers/drivers/media_modules/`，其 Git HEAD 为
`31619c527655514b4c89516ef609b6db1dd47db6`；本轮读取的 vh265.c、utils 和
vdec_hevc_if.c 没有未提交修改。以下 file:line 都相对此根，不沿用旧记录的厂商 SHA。
内核源为 VM `/home/deepdream/src/linux-7.3-vdec-hevc-port`，分支
`experiment/hevc-vendor-port`，起点 `857b5a2e2442f8d17cb024869b4e1aba035c84aa`。
唯一 O= 根为 `/home/deepdream/build/vdec-hevc-port`，其中 module、kunit 分开。

| 判定 | 源码依据及本轮选择 |
|---|---|
| 芯片 | `common/chips/decoder_cpu_ver_info.h:66` T7=0x36；`.c:237-254`：前后时钟不合并、无外部硬件 parser、有 canvas、有 AXI 控制、无第二后端、无 RDMA/vcpu 特性。后两项未初始化，零初始化为 false |
| 多实例入口 | `amvdec_ports/aml_vcodec_adapt.c:264-279` 默认 FRAME_BLOCK，stream_mode 才切 STREAM_PARSER；`h265/vh265.c:14818` m_ins_flag=1，`:14798-14805` 安装 run/IRQ 回调。本轮一个 V4L2 会话仍对照此多实例实现，不开发调度多实例 |
| DW/MMU | `amvdec_ports/decoder/vdec_hevc_if.c:152-164,199-203` V4L2 默认 DW=1、线性 memory mode；不是 vh265.c:266 的裸模块 DW=0。`vh265.c:15087-15110` T7 且 DW 无 bit4，MMU=1；DW 无 bit5，dw_mmu=0 |
| NAL | `vh265.c:434,2654` nal_skip_policy=2 → PB_skip_mode=2；`:12335-12362` 默认自动8，debug 才手动1。`:531,12262-12306` performance=1，bit21、framebase1、MBX0；本候选恢复自动头解析 |
| SEI/DV 搜索位 | `vh265.c:513-514` 全局 SEI 初始0、DV parser初始1；`:14407-14408` 的 SEI=7属于单实例 probe，不能套到多实例。厂商默认仍会 OR bit20。本轮按不扩展 DV 的限制保留 bit20=0，记录为差异，不能称完全同值 |
| buf_alloc | `vh265.c:398-402,15408` 默认宽/高/size为0；V4L2字符串给4096×2304。workspace另由`:7776-7801`按芯片能力选 spec[5]，不是按256×256样本选老 spec[1]；spec[5]定义在`:1319-1348`，对应 CFG3=8020（`:5043-5048`） |
| secure加载 | `common/firmware/firmware_drv.c:100-106` T7返回 tee_enabled()，并非 vdec_secure()。`utils/amvdec.c:972-987`选择TEE或本地；TEE固件加载不等于播放secure视频。本轮沿用现有SMC HEVC_MMU加载，不增加secure视频 |
| swap未决 | `vh265.c:12484-12522,14217-14256`由固件包version/submit count、enable_swap、取固件成功与否决定。`utils/amvdec.c:577-584` h265_mmu与hevc_mmu_swap是不同格式；静态T7 ID不能决定实际固件名。必须由金标准轨迹/包身份确认，未替换现有非swap固件 |
| 线性/压缩 | MMU压缩参考帧＋DW线性输出同时存在；不是纯线性参考。`vh265.c:4015-4065,4097-4170`建压缩头/ANC2AXI表；`:5635-5975` SAO同时写DW和压缩头。I slice不需要MC参考表，但仍需要MPRED写端、SAO/DBLK/IPP |

## 执行顺序与对齐方法

CSV 是逐个源码寄存器操作的目录，包含读、写、RMW、原始表达式、DOS word 地址、
条件说明、厂商 file:line、857b5a2e 和移植后的定位。byte offset=word address×4；
不要把 DOS word 地址直接当 CPU 物理地址。指针按角色归一化（workspace子区、RPM、
LMEM、page map、picture header/body、MV、DW Y/C），不能比较两次分配的绝对地址。
expression_context保留附近计算和条件；运行值不能凭同名判同值。

目录共349条源码操作：相同113、不同40、缺失2、待证194，比较对象是**起点**。
相同不代表硬件已执行。缺失两项为CTRL26的不同条件写入位置。表保留互斥条件和禁用测试分支，**不能将每行
顺次重放**；不是已筛完全部条件的动态金标准。诸如LUT循环、parser helper和回调要按
下面的调用顺序插入，循环按次数展开后匹配。目录行数不是总线访问次数。
仍需将194个待证项筛选为当前路径或排除；此项未完成，不能称完整闭环对齐。

1. `utils/vdec_power_ctrl.c:151-180,268-282`：先HEVCF/HEVCB gate及clock，再runtime PM域；T7的dos_local_config直接返回（`:196-205`），不要套后代芯片的MEM_PD全复位。
2. `utils/vdec.c:5244-5353`：hevc_arb_ctrl(false,false)隔离两端；STREAM_CONTROL=0；MMU_RESET bit0置1；RESET3复位parser/DBLK/CPU/DDR/IQIT/IPP/MPRED/SAO/FIFO/MMU，再0；等WRRSP低12位清；MMU_RESET清1；arb使能。T7不走RESET7等其他芯片分支。当前对应aml_vdec_hw.c:1295-1325；停机已有更严格的读写双确认，不削弱。
3. `utils/vdec.c:1984-1998`：START、exclusive END、RD、向下8字节对齐的padded WP、endian。`vh265.c:14152` fresh WAIT=0。非swap固件加载经`:14237-14238`，TEE内部写入不可见。当前prepare_hw的加载在地址准备之前，保留并列为顺序差异。
4. `vh265.c:12318-12320`：workspace先行，再decoder init。work区写IPP、RPM、RPS、VPS/SPS/PPS、SAO_UP、MMU map、SCALELUT、CFG3/4/5/E、LMEM；MMU map base在G12A以后用ASSIST_MMU_MAP_ADDR。
5. `vh265.c:5108-5208`：IQIT bit14脉冲；关CABAC/parser；parser中断控制RMW；SHIFT_STATUS低2位；SHIFT_CONTROL=e5；CABAC/parser开启；status0；LUT地址0和1024个零；decode_size0；CMD_WRITE=10000；调用parser_cmd_write（37字，`:5072-5084`）；三个CMD_SKIP；IF_CONTROL=25；IPP reset1→enable2。STARTCODE/EMULATECODE写在#if0，不参与当前路径。
6. `vh265.c:12325-12365`：mailbox clear1/mask1、PSCALE0、debug0、NAL自动8及默认parser位、STOP_POS0；再调用config_decode_mode；再config_aux_buf。当前bit20、固件swap恢复和buffer布局差异尚需轨迹裁定。
7. `utils/vdec.c:2329-2333`：endian→FIFO bit29→fetch bit0；`vh265.c:14268-14291`：ACTION ff→SHIFT0→SIZE（有效payload加前缀偏移，当前偏移0）→已配置时picture table。
8. `vh265.c:4097-4170`：ANC2AXI conf6、逐有效slot写header>>5、conf1、canvas access1和32个零；随后init_decode_head_hw：DECOMP_CTL1=10、CTL2=0、body length/offset、header length、VH0/VH1、CTRL9 bit0、CTRL5 bit10。当前仍把无效slot补零，厂商在首个无效slot即break，此为额外写差异。8bit MMU body=3200×ceil(w/64)×ceil(h/32)，header=32×ceil(w/128)×ceil(h/64)（`:2310-2348`）。
9. `utils/amvdec.c:1056-1080`：RESET3三读→bits11/12→0→三读→MPSR1。现有只读启动诊断保留；它们是额外读操作，轨迹应按地址和值过滤，不按相邻行强配。
10. IRQ `vh265.c:11746-11765`先清mailbox再读status；首个自动slice事件是08，不要求09。RPM按每4个u16倒序读（`:11346-11358`）。现有V4L2先报SOURCE_CHANGE并停机，CAPTURE准备后同AU重投；这是接口桥接产生的额外一遍，需将探测遍和解码遍分段对齐。
11. 首个图像分配header、body pages、MV和DW Y/C；coherent map填入每页PFN；tile scratch（`:5389-5397,7357-7381`）。config_mc_buffer→mcrcc→mpred→sao（`:7550-7566`）。I slice MC无引用；MCRCC CTL1=2→0；MPRED仍写当前MV起点/row jump、CTRL0/1、尺寸/tile、reference数量/enable/POC、16对L0/L1 POC、ABV/WPTR/RPTR/end。SAO按new_pic写无效Y、T7 CTRL26=0、CTRL5、Y/body/header/length、C/length、WPTR、T7 CFGB、CFG2/1/debug、CTRL1、IPP AXI、filter控制。最后才`:11650-11653`回复status05和MCPU_REQ4。
12. 0a解码完成后固件停止/AXI排空，再交付CAPTURE；不能用08、source event、IRQ次数或非零缓冲替代正确I420像素。

## 状态处理边界

| status | 厂商行为/本候选 |
|---|---|
| 00、01–07 | IDLE、主机解析/数据命令、运行状态；不是任意IRQ都应回复ff。当前未知状态终止并保留日志 |
| 08 | RPM及头处理；建立图像/参考/MPRED/SAO；成功回05+REQ4；参数探测第一遍按既有SOURCE_CHANGE停机 |
| 09 | 手动NAL搜索才逐头回01/02/03/04或f0，再REQ4（`:11306-11308`）；默认自动模式无需这些IRQ |
| 0a | 完成图像、安排输出（`:10800`起）；本候选等待停机后交缓冲 |
| 0b | 错误图像，不交有效帧 |
| 0c/0d | SEI数据/应答；`:11100-11108`直接回0d，无REQ；本轮补齐 |
| 0e/22 | 输入边界，厂商根据frame模式走pic_done（`:10760-10791`）；当前只在无活动图像时完成，不能当0a，仍有行为差异 |
| 0f | 厂商over_decode记标志并调度DONE（`:11091-11096`）；本候选无专门分支，走错误，不伪报有效帧 |
| 12、30、80 | 定义有DATA_REQUEST/DUMP_LMEM/不支持码率状态，默认首帧路径未找到有效处理需求；本候选未知状态报错，待轨迹证明 |
| 20/24 | frame输入耗尽；当前报错，不推断图像完成 |
| 21/23/25 | timeout/oversize/参数错；参数错厂商`:10792-10799`停机，本轮补齐25，不发ff |
| 50/51 | 下一图像/下一DV层；只保留已有50无活动图像边界处理，51不扩展 |
| f0/fd/fe/ff | 主机discard/continue/error/done命令；不得把它们当需统一ack的事件 |

## 提交与验证

| SHA | 改动 |
|---|---|
| d9c85c7e364be | hevc.c:401，恢复默认自动NAL |
| 452a8cc80fd8d | hevc.c:421，exclusive end、WP对齐、FIFO先于fetch |
| 82b68a0204739 | hevc.c:883、hevc_regs.h:7，T7 CTRL26/CFGB顺序 |
| 8823d08b9bb94 | hevc.c:287，picture table后压缩头；删除无厂商对应的SAO_MMU_DMA_CTRL写 |
| 6c8560dae2ff4 | hevc.c:1557，整体启动顺序；去额外IQIT清零 |
| aadc70fb57248 | hevc.c:1408，SEI0d应答、25错误、未知状态不再盲回ff |
| f21dfc47ecf5e | hevc.c:37、323，T7 workspace及CFG3；去禁用块的startcode写 |

`aadc70fb57248`经heavy队列全新O=：arm64 QEMU 25/25通过；W=1模块编译链接通过，
五个既有KUnit模块missing MODULE_DESCRIPTION警告，HEVC修改无编译诊断。
最终f21dfc47ecf5e的checkpatch为0 errors/0 warnings；本worker的heavy受权限阻挡，
后由协调者代跑W=1、KUnit 25/25通过。
Mac原始输出在build/vdec-hevc-port/validation-aadc.tar、checkpatch.log和
logs/vdec-hevc-port/heavy*.log；脚本为build/vdec-hevc-port/validate.sh。

## t48/t3k 单次上板清单

1. 最终尖端已由协调者审diff并完成heavy；由t3k按integration身份/uptime/UART门禁执行，不混装最小配置模块。记录内核SHA、release/build ID、模块/固件/fixture SHA、IRQ、5999字节payload及前缀，保留hevc.c dynamic debug。
2. 只运行原同一hevc-intra.vhdr的带流compliance。预期首次search=0x200008，允许无09，期望08/RPM、SOURCE_CHANGE；重投后05→0a及CAPTURE完成。若firmware启用默认其他parser位，先与表的已知差异对照，不在板窗临时改寄存器。
3. compliance通过后只捕获同一256×256八位全I码流首帧，保存可见I420（98304字节），逐平面哈希/最大误差对比同fixture软件参考。不扩P/B、10bit、DV、其他流，不新增假设重试。
4. 任一timeout、WARN/Oops、非请求复位、ERROR缓冲、错误像素或AXI停机失败立即停止HEVC；保存三阶段/IRQ/RPM/header-reply/timeout、UART和停机证据。由t3k按现有流程隔离/恢复；本worker不触板、不申请板票。

未完成：实际厂商固件名/swap与TEE内部轨迹；逐条条件筛选和运行值验证；全默认参数同值
（bit20、endian、workspace布局、有效slot数）；首帧硬件验收。
