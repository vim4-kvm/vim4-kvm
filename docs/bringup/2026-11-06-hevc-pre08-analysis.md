# 2026-11-06：r71 HEVC slice 至 08 前的资源排序

r71证明09逐头IRQ与主机应答可用，故障收敛到首个slice解析至08报告之前。
本轮只离线分析，不改内核，不变更拟用于.34的f21dfc47。协调者已确认该尖端heavy
W=1和QEMU KUnit 25/25通过；[旧记录](2026-11-06-hevc-vendor-port.md)中的
最终门禁阻塞已被这次代跑解除。排序是调查优先级，不是已确定的根因概率。

## 必须更正的厂商路由

先前将`frame_provider/decoder/h265/vh265.c`直接视为amvdec_ports实际实现不准确。
`amvdec_ports/aml_vcodec_adapt.c:209`调用`vdec_init(..., true)`；
`frame_provider/decoder/utils/vdec.c:3063-3083`对T7追加`_v4l`，因此frame-based路径
使用`ammvdec_h265_v4l`，匹配`frame_provider/decoder_v4l/h265/vh265.c:122`。
两个Makefile分别生成amvdec_h265与amvdec_h265_v4l，不能只凭支持is_used_v4l判断入口。

下文厂商file:line除注明utils等共享路径外，均相对
`common_drivers/drivers/media_modules/frame_provider/decoder_v4l/h265/vh265.c`。
旧CSV保留为decoder/h265源码目录，不重生成，不把其349行统计改称V4L实际轨迹。
交叉核对输出：`build/vdec-hevc-port/vendor-v4l-crosscheck.diff`。
parser37字完全相同；workspace T7分支、protocol、mode及run的关键顺序相符。
**decoder_v4l的parser自检是活动代码**，与decoder/h265的#if0不同，见下表第2项。

## 原始证据与可排除范围

只读相邻主仓库`build/hwdecode-parity/run71/archive/results/kernel-journal-0007.jsonl`，
摘录为本工作树`build/vdec-hevc-port/r71-messages.log`，行号保留原JSONL行号。

- `:66-98`：四个09分别读到NAL32/33/34/20，回复01/02/03/04；不能再归因为首个mailbox IRQ不通。header-reply是多次寄存器读取，固件同时前进；首个快照已经显示下一个SPS，status=ff与raw IRQ=1不是上一条01应答失败。
- `:82,90,98`：RPM/INFO从3到7；`:74`为1。`utils`共用scratch1在运行期是DECODE_INFO，低字节被`read_decode_info`用于start_decoding_flag。它不再是RPM地址，不能将1/3/7视为DMA指针遭破坏；也不能凭这些位证明SPS/PPS语义全部正确。
- `:99-104`：timeout PC=a1d/摘要a20，SHIFT=63，RD=b72e0440，WP=b72e576f，LEVEL=532f，parser_core=1，debug G/H=0，LMEM DMA=10110。WP−RD恰为532f；“码流环已经读空”无证据。RD预取与SHIFT语法进度是两个量，不能混算剩余payload。
- `:96`：NAL scratch因config_decode_mode写成80000001。该共享scratch变化与厂商手动09路径的mode重写相符，不是NAL20凭空消失。PC仅定位为观测值，微码源码缺失，不能把a1d翻译成某个具体等待指令。

## 按优先级排序及f21dfc47覆盖范围

| 顺位、CSV阶段 | 08前关联、证据及剩余核对 | f21dfc47覆盖 |
|---|---|---|
| 1 固件身份/swap，06-load | VPS/SPS/PPS已推进，而slice首入口停住，使固件版本/加载格式及可能的overlay依赖优先核对。`:12946-12984`依据包version和submit_count选择swap；`:14654-14698`实际选择hevc_mmu_swap或h265_mmu并保存TEE返回的SCRATCH8，后续恢复。当前只知道SMC返回0，既不证明加载了与厂商相同版本，也不证明存在swap故障。不能凭PC推断swap命中 | **未覆盖**。仍固定HEVC_MMU非swap加载；没有swap地址读回/恢复。应先取得厂商模块名、包version/submit_count、请求的固件名/format、SCRATCH8及实际固件SHA，再决定是否需要改加载路径。不得为试验盲塞swap指针 |
| 2 parser与输入启动先后，08-parser/10-enable/11-action | 这些资源在首个slice之前已活动。r71在CPU reset前已SHIFT=8、RD已预取400，说明旧实现fetch早于CPU启动，并不能单据此判错。实际V4L `:14703-14725`为prot_init→enable_input→ACTION ff→SHIFT0→SIZE；微码头/slice共用parser。对37字和三个skip常量离线逐字核对一致 | **已覆盖主要顺序**（6c8560d、452a8cc），并删除额外IQIT清零。**未覆盖V4L自检**：`:4770-4781`PARSER_VERSION读写自检，`:4794-4817`startcode/emulatecode自检及最终100/300写。f21删除了旧代码的最终两写；与实际V4L不完全同序列。但r71原本具有这两写仍失败，故不能据此认定其为r71根因。本轮不为恢复自检改变.34候选 |
| 3 RPM/LMEM及header DMA，07-workspace/15-irq | 完成slice头必须使参数可供主机读取。`:4710-4712`设置RPM地址，`:4741`设置LMEM地址；`:11844`收到08后才读RPM。r71已有LMEM DMA控制变化、未见debug暂停tag，但没有RPM/LMEM实际内存内容及DMA完成证据。10110本身不能翻译成成功或卡死 | **地址/分配原已存在，f21没有修复DMA协议**。RPM100字节、LMEMa00字节，分别独占4K边界，coherent内存先清零；scratch1启动地址正确、运行值变INFO是预期复用。仍需厂商相同边界的DMA控制和内存内容对齐；不把F当寄存器RPM请求寄存器盲清 |
| 4 参数workspace地址/容量，07-workspace | 08前最直接的是SHORT_TERM_RPS、VPS/SPS/PPS和SCALELUT，厂商分别800/800/800/2000/8000字节，`:4685-4741`显式发布各地址。r71已完成前3类NAL，不足以证明内容正确；但当前没有重叠/容量不足证据。各段通过显式指针传递，不能要求两个分配的绝对差值相同 | **部分覆盖**：f21换成T7 spec[5]的非零IPP/DBLK/VBH/MPRED大小和CFG3=8020；上述参数段大小与旧尖端相同。仍保留额外SAO scratch，RPM/LMEM分开分配，不与厂商布局逐字节相同；仅布局差异不是错误证据。详见下一节 |
| 5 stream剩余字节/WP/END，04-input | 确实是slice解析资源，但当前有532f剩余硬件level、未消费到输入末尾，优先级低于启动/固件/DMA；缺8字节尾部一般应在靠近末尾表现，现停在63。WP不对齐和end−1仍是真实厂商差异，不因本次level大而免修 | **已覆盖**：452a8cc END改exclusive、WP向下8字节对齐、FIFO先于fetch，保留额外一字避免满圈。对当前AU，预期WP从base+576f改为base+5768，END从base+ffff改base+10000；DECODE_SIZE仍176f，不能把padding计为有效payload |
| 6 IPP/DBLK基础初始化，07/08；逐帧MPRED/SAO/canvas，12/13/18–23 | IPP line buffer及IPP reset/enable、DBLK基础workspace/CFG3是08前初始化，仍需与轨迹对齐。**逐图像的MV、参考表、SAO Y/C/压缩头、filter等在厂商08分支之后才配置**：`:11844`处理08，调用头处理，后者`:7470-7490`依次MC/MCRCC/MPRED/SAO，再`:12192-12195`回05+REQ4。因此不能用缺这些逐帧写解释“固件必须先等它们才报第一个08”，除非新轨迹证明厂商首个08之前另有写入 | **基础部分及多项08后差异已覆盖**：f21的IPP/DBLK大小/CFG3；82b68a0的CTRL26/CFGB；8823d08的压缩头顺序。**首次参数探测遍没有picture table/压缩头/帧地址是当前设计**，这些是在08之后获知尺寸才分配。replay已配置时的table初始化不能倒推为首次08前的必需条件 |

同一芯片上厂商与当前驱动的复位默认值、TEE写入等仍可能不同；上述“08后”判断是
主机源码调用顺序的证据，不声称已知微码内部访问时刻。bit20 DV parser默认差异、
debug/SEI开关仍保留在原目录中，但对无DV样本，现无证据把它们排在前面。

## workspace容量复核

f21显式4K carve后的偏移/长度（十六进制，相对于各自基址）：

| 区域 | workspace偏移 / 字节 |
|---|---|
| IPP；SAO_ABV；SAO_VB | 0/8000；8000/30000；38000/30000 |
| SHORT_TERM_RPS；VPS；SPS；PPS | 68000/800；69000/800；6a000/800；6b000/2000 |
| SAO_UP；swap；swap2；SCALELUT | 6d000/2800；70000/800；71000/800；72000/8000 |
| DBLK para/data/data2 | 7a000/40100；bb000/140800；1fc000/100800 |
| MMU VBH；MPRED above | 2fd000/a000；307000/8000 |

末端30f000小于实际分配320000（3200KiB）；没有按本轮尺寸发现越界。side另分配
10000字节：RPM偏移0/100、LMEM1000/a00、map2000/4800、aux7000/6000，
末端d000，互不重叠。MMU map内容、压缩body/header及MV对本次08前停滞优先级低：
它们的当前图像页表/地址在08后才建立。分配容量正确不证明固件写入的内容正确。

## .34判据与本轮交付

.34保留f21尖端及已批准清单，不追加内核小修正；观察从“只收到09”是否推进到
08/RPM/SOURCE_CHANGE。若仍SHIFT63无08，优先拿厂商**实际V4L模块**的固件选择、
parser启动、参数DMA三个边界轨迹；不先补05、不提前分配猜测的图像地址、不重复查mailbox。
若已到08，故障分类即转入host头处理/帧配置，不能继续称08前故障。

本轮新文件及旧记录更正只涉及文档；没有内核变更，因此没有重跑内核门禁。
原始r71摘录和双实现交叉diff保存在build/vdec-hevc-port/。主仓库验证与提交状态见
`~/.local/state/herdr-workers/vdec-hevc-port.result.md`最新补充。
