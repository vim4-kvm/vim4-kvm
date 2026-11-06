# 2026-11-06：r71 .33 手动头IRQ与MPEG-2拒绝证据

**HEVC收到4次09 IRQ，VPS/SPS/PPS/首slice逐头应答完成，但没有08，仍超时。**
本次证明mailbox到Linux及主机头应答通路实际工作，不能再把此轮归为“首个头IRQ未到”。
stateless compliance通过、DOS step=0、H.264三条Success。MPEG-2 sony-ct1仍Fail，
原始日志已给出微码完成错误；执行草稿误读日志目录而提前停段，另外三条未运行。
正式恢复、视频、归档和清理完成，无非请求冷复位，未部署、未追加候选启动。

## 身份与入场

按[.33计划](2026-11-06-vdec-integration33-plan.md)，FIFO1443，单张30分钟sampling票。
源码effc7d77e51fdf8cc303bb02a301d343be56f7c3，release 7.3.1-vim4-20261106.33，
build ID 0055df24ab8980d7e8f1adb8ce056f5fd1a94326，封包哈希与获批计划一致。
入场uptime4468.30→4477.24秒，boot_id一致，正式proof/视频通过；候选SSH身份逐项匹配。
内核模块由包manifest核SHA后加载，私有用户态身份门禁通过，没有混装模块或替换系统库。

排票前修正执行草稿残留的归档参数70和cleanup-r70为71，并离线断言目标；
实际归档901项，删除的目录是本轮`/var/tmp/hwdecode-standard-r71`。
浏览器首次冒烟未在import前传PLAYWRIGHT_BROWSERS_PATH而失败，未碰板；按既有私有
路径从进程环境传入后通过。失败及成功日志均保留，未安装全局依赖。

## compliance与H.264

stateless media 8项、video带流60项，均零失败/零警告。关闭诊断时DOS step=0。
MR3_TANDBERG_B、BA1_FT_C、cabac_mot_picaff0_full均Success。
MR3为300帧、11404800字节，与宿主参考逐字节相等，MD5
`dd1091f75ac15d3ae70485295b0a116e`。保存的MR3和Sony trace丢事件均为0。
本次不是全集，仍保留r65+r69的129S/1F/5KU历史口径。

## MPEG-2：微码完成错误已捕获，采证门禁误停

只有sony-ct1运行，Fluster Fail；sony-ct2、sony-ct3、mcp10ccett均未运行。
mpeg12.c和aml_vdec.c的动态调试确已开启，三个诊断点均显示`=p`。
原始逐流kernel.log及根目录journal JSON同时保存了如下证据：

| 请求timestamp（ns） | type/structure | forward/backward | 微码完成 | 返回路径 |
|---:|---|---|---|---|
| 1000 | 3/2，B bottom | U64_MAX/0 | out=2、info=0、errors=226 | microcode completion ret=-5；公共worker stage=codec run |
| 2000 | 3/3，B frame | U64_MAX/0 | out=2、info=0、errors=10 | microcode completion ret=-5；公共worker stage=codec run |

因此本轮这两次错误不是主机参考查找或canvas拒绝，已进入微码完成路径；具体固件
失败机制仍交MPEG-2 topic分析，不据此改参考策略。ioctl两队列仍在tv_usec=1/2标ERROR。

输出60帧、7096320字节；显示帧0非全零、帧1全零，对ISO最大差232/226，差值>2
字节数118252/118254。显示帧2起与r70逐字节相同，对ISO差值>2的位置仍7个。
整文件MD5为`d5fcb1a20d56d133bc0735da4e42d656`；错误缓冲内容不作为有效像素证据。

误停根因是执行草稿从`results/kernel.log`截取增量，但run_fluster的
require_clean_kernel_log(output)把文本写入本条码流的目录；共享KernelJournal只把
cursor和原始JSON写到根目录。自动rejection-evidence.json因此错误地记诊断集合为空，
安全停止MPEG-2，不能把它当“内核未打印”的证据。
执行过的run71/remote.py不改写；下一窗草稿改读新建的逐流kernel.log。宿主用本轮真实
ioctl/两份日志重放，旧路径复现缺失1000/2000、新路径完整匹配，输出在
diagnostics-path-check.log；未补跑板子。这次离线检查补上了此前只测解析函数而未覆盖
实际日志落点的缺口。

## HEVC：09与第一条header-reply

有效首AU5999字节、skip=0、前缀匹配原fixture。首次search=0x200001，WAIT初始0。
Linux HEVC IRQ从0增至4；日志逐条为09/32→01、09/33→02、09/34→03、09/20→04。
四次IRQ的PC均为0x7da，SHIFT分别0x0c/0x28/0x56/0x60。

第一条header-reply（回复VPS命令01后）原始读回：

| 字段 | 值 |
|---|---|
| reset/MPSR/CPSR/PC | 0 / 5 / 0 / 0x7a3 |
| status / saved irq / mailbox mask | 0xff / 0x09 / 1 |
| stream RD / WR / control / FIFO | 0xb72e0400 / 0xb72e576f / 0x0eb10071 / 0x20790007 |
| WAIT / SIZE / SHIFT / SHIFT_STATUS | 1 / 0x176f / 0x28 / 0x31008013 |
| mode_or_nal / search | 0x21 / 0x200001 |
| mailbox_irq / FIQ_SEL / MCPU group / mask / request | 1 / 0 / 0 / 0xfff9 / 0 |
| parser status / core / IRQ control | 0 / 1 / 0x69400091 |
| debug G / H / RPM-or-info | 0 / 0 / 1 |
| LMEM command / DMA / stream level | 0xb72d1000 / 0x1031c / 0x536f |

回复首slice命令04后search切0x200002，SHIFT=0x62；最后timeout快照SHIFT=0x63、
status=0、PC=0xa1d，紧接摘要再次读PC为0xa20，两个读数保留。MCPU mask=0xfffe，
mailbox_irq=0，RPM-or-info=0，debug G/H仍0。没有08、SOURCE_CHANGE或有效帧；
首帧捕获未运行。读回是跨时间多次寄存器读取，不解释为原子状态快照。

compliance streaming失败，终检捕获timeout，按计划停止HEVC并正常重启恢复。
后续诊断转向逐头应答后的slice/RPM/LMEM路径；此次IRQ通路证据不证明像素正确或
所有模式均工作，也不把自动NAL模式要求成必须出现09。

## 恢复、统计与原始证据

连续UART时间线242.374秒。本窗两次Linux启动：`.33`一次，113.041577292秒后为请求
恢复的ROM；正式默认一次成功，无非请求冷复位。正式eMMC覆盖下界从≥30/6更新为
≥31次/6复位；`.33`1/0，`.32`1/0，`.31`5/1，`.28`9/2、正式RAM2/1不变，不作稳定性推断。

最终2372项保护文件一致；视频推进299帧、59.765fps，丢帧/冻结/丢包无新增。
helper重传，按归属/哈希清候选和固件，正式模块未动，complete.restored=true。
901项归档核验后删板端目录并释放票；本任务三个O=的对象文件已清理，封包和日志
保留，未动共享visl。清理明细在object-cleanup.json。

原始证据：`logs/hwdecode-parity-r71/`的UART/chunks、身份、proof及视频；
`build/hwdecode-parity/run71/`的board-upload.tar/文件清单、archive/results、
summary.json、codec-messages.log和一次性summarize.py。UART SHA256为
`d6940fe0c35eb28e5403acac7dbc06e643a040d970a2a1579d26ac475960eb90`。
提交前主仓库全套实际运行607项，OK（11项跳过），原始输出为run71/main-tests.log。
