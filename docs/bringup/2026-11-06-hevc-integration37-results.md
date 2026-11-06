# 2026-11-06：.37 HEVC 一致性修复复测

独立132条全部执行：**118 Success /1 Fail /11 Error /2 Timeout，零未运行**；
原102条Success零回退，原30条失败中16条转为通过。来源、身份和门禁见
[.37 计划](2026-11-06-vdec-integration37-plan.md)，对照为
[.36 全集](2026-11-06-hevc-full-results.md)。未部署或合并内核。

## 最终总表与边界

| 阶段 | Success | Fail | Error | Timeout | Not run |
|---|---:|---:|---:|---:|---:|
| .36独立全集 | 102 | 16 | 11 | 3 | 0 |
| .37定向30项 | 16 | 1 | 11 | 2 | 0 |
| .37独立全集132项 | 118 | 1 | 11 | 2 | 0 |

[132条逐流CSV](2026-11-06-hevc-integration37-full.csv)保存原判定、新判定、窗口、
期望/实际帧数、首错或首个缺失索引（从0计）、MD5、LAST/status/ERROR和原始证据路径。
仍有4条超尺寸8bit Known unsupported未执行、11条Main10不在范围；132条中没有
Not available。无5.15有效同流对照，不宣称parity。

原15条像素Fail和DELTAQP_A的Timeout在定向与独立全集中均转为Success；RPS_B仍为
300/300帧、显示索引25首错。剩余11 Error为BUMPING、NoOutPrior_A/B、OPFLAG_B/C、
RAP_B、RPS_D/E、SLIST_B/D、VPSSPSPPS；两Timeout为LTRPSPS_A和WPP_D，均0帧。
定向及全集的14条失败各保存一份原始I420，含空文件；未重试失败求通过。
这些故障尚未证实是固件能力或私有ABI缺失，不新增“不支持”声明，交修复worker继续定位。

## 身份与方法

源码 `3cbab82167a1dc3de870165a5a01fd7c66d48a86`，release
`7.3.1-vim4-20261106.37`，build ID `44eea7201d285aa51eca9c7eae5e259995b06a45`。
只运行无线屏蔽变体 RAM SHA256
`9e21cf7d071dc08735828e1a5f0748411e069405b2f4d15c9c3b165cd7042dc0`。
Image/模块/DTB 不变，仅候选启动参数增加三项无线初始化屏蔽，正式默认与 cmdline 未改。
VBUS 拓扑为 Mac→用户 USB-C 功率计→VIM4，型号未补；本轮未取得新的功率显示读数。

沿用封存的 JCT-VC-HEVC_V1 输入和发布者逐帧 MD5，官方 1.24.2 parser 私有目录；
stateful 解码插件是系统 video4linux2/libgstvideo4linux2.so。每窗核路径、版本、SHA、
固件 secure swap、非零 overlay、节点、DOS step 和板端输入 SHA。失败逐流保留 I420、
GST、ioctl 和内核证据，成功输出取逐帧/整流摘要后删除板端 I420。
定向 30 条和之后的独立 132 条全集分别计数，同阶段不重跑失败求通过。

## 窗口与门禁

| 窗口 | 采样票 | 内容及停止点 | 正式恢复 |
|---|---:|---|---|
| r85 | 1510 | 全 I 和三条短流通过；重复 compliance 3 次均 56/56；定向完成 29 条，LTRPSPS_A 内核 timeout 后停止，余 WPP_D 和六条代表未跑 | 2372 proof、59.554 fps，上传 1238 文件归档核摘要后清理 |
| r86 | 1511 | 非阻断 HEVC compliance 56/56；WPP_D 内核 timeout 后停止，六条代表仍未跑 | 2372 proof、59.754 fps，819 文件归档后清板端 |
| r87 | 1512 | 宿主未及时完成服务清单复核，120秒门禁超时；零上传、零候选启动 | 入场proof/视频通过，正式持续运行，无恢复重启 |
| r88 | 1513 | 候选在 acceptance 前8.555918秒冷复位，未执行解码；按授权不在同票重启候选 | 被动自然恢复正式，2372 proof、59.760 fps，763 文件归档后清板端 |
| r89 | 1514 | 六条代表均Success；全集52条50S/1E/1T，LTRPSPS_A timeout停止，未见旧Success退步 | 正式首次启动复位后自然恢复，2372 proof、59.757 fps，1507 文件归档后清板端 |
| r90 | 1515 | 入场实际uptime不足300秒，门禁拒绝；零上传、零候选启动 | 正式持续运行，无恢复重启 |
| r91 | 1516 | HEVC compliance56/56；补齐80条68S/1F/10E/1T，最后WPP_D timeout后停止，全集收齐 | 正式一次正常恢复，2372 proof、60.169 fps，1783 文件归档后清板端 |

r85 先跑 stateless streaming 60/60、media 8/8、DOS step=0。HEVC 全 I 为56/56，
首帧 98304 字节及三平面逐字节正确、Captured 1 frames; status 0、初始事件先于
CAPTURE 且只一次 STREAMON。cip_B_NEC_3、MERGE_E_TI_3、TMVP_A_MS_3 分别
5/8/17 帧逐帧 MD5、整流、LAST/status 0 通过；之后三轮 select+epoll 都56/56。
这四次通过是当前候选的证据，不宣称已统计证明间歇性 EOS 竞态完全消失。
加上r86/r89/r91，本轮HEVC带流compliance共7次，均56/56；其中指定连续三次
select+epoll观察也全部通过，旧epoll失败本轮未复现。四个实际acceptance窗口的
stateless均60/60、media均8/8、DOS step=0；r88冷复位前这些项未运行。

内核 timeout 先结束当前窗恢复；下一张票只续未运行项。返回的像素/接口失败继续收集。
420 秒恢复预算始终保留，候选每票只启动一次，冷复位后不在同票重启候选。
每次自然恢复后在票外等已知正式启动满300秒，再重新读实际uptime/boot_id做入场门禁。
r87的清单已离线核对与r85相同；替代窗把同一31份配置、radio service定义和全部
ExecStart path/argv比较接在入场快照后，出现变化仍拒绝。真实r87快照回放通过，
额外配置变化、新增gpioset命令两种失败路径均在写复核凭据前拒绝，原始entry-replay.log保留。
r89六条代表通过后，在同一启动和原时限内进入独立全集；后续r90剩余80条中，
把已实测内核timeout的WPP_D放到第8批末尾，E/F在它之前。仅改补跑顺序，输入、
参考与每流timeout不变，避免只为两个尾项额外启动候选。
r90暴露票外等待脚本仅取最后Booting Linux标记的问题：r89最后自然恢复的该行残缺，
虽然Linux version和SSH身份存在，等待锚仍提前了。现从最后已验证的正式运行身份
开始保守等305秒，再以板端实际uptime/boot_id复核，不依赖单一UART行。用r85/r86/
r88/r89实际UART和身份事件回放，新的锚均晚于最后Linux标记；r89多留约34.96秒。
实际门禁拦住了提前入场，未缩短300秒要求；ready-anchor-replay.log保留输出。

## 当前故障证据

定向30项现已完成，16 Success、1 Fail、11 Error、2 Timeout；逐条见
[定向CSV](2026-11-06-hevc-integration37-targeted.csv)，尚不能作为独立全集总数。
DELTAQP_A、CAINIT_G/H、DBLK_A/C/D、DSLICE_A/B/C、RPLM_B、TILES_B 和
WPP_A/B/C/E/F 从旧失败转为通过。RPS_B仍在显示索引25首错；BUMPING、NoOutPrior、
OPFLAG、RAP、RPS_D/E、SLIST_B/D、VPSSPSPPS仍Error，LTRPSPS_A和WPP_D仍timeout。
CAINIT_G逐流日志实测search=00000008，确认采用普通逐slice主机配置路径；未把
多提交同包的收益拆成各提交的独立因果结论。
独立全集重复确认同一失败集合。LTRPSPS_A仍status02，超时采样PC0xda3/0xda6、
SHIFT0x5f；WPP_D仍status05、PC0x6d9、SHIFT0x318。两者都在search=8下失败，
没有把模式修正后仍卡住推断为硬件不支持。普通逐流kernel.log因内核超时守卫抛出
可能为空，原始kernel-journal JSON/error及posthoc-kernel.json保留完整超时读回。

新增拒绝诊断实际拿到：SLIST_B/D均为 invalid RPM，832×480、CTU 0+3、
depth=0x0/chroma=1/dpb=4/reorder=3；VPSSPSPPS报0×0、chroma=0/dpb=0。
RPS_D/E和RAP_B报 invalid reference lists，分别 POC260/type1/refs4/0、
POC253/type0/refs2/2、POC28/type0/refs2/2；完整 RPS 字节保留在逐流 kernel.log。
这些是具体拒绝路径证据，未据此放宽驱动检查或改寄存器。

## 冷复位与恢复边界

r85 的 .37 候选一次启动无冷复位；请求返回正式时，首次正式 Linux 启动后约
7.354690秒回到 T7 ROM，随后被动自然启动成功。没有 panic，也没有第二次候选启动。
恢复成功的 Linux banner 文本残缺，但 Booting Linux 标记与 SSH正式身份可确认启动，
不因 banner 不完整把它记为零启动。三次 Linux 启动分别为候选、正式失败、正式自然恢复。
最后正式2372项文件及视频通过；串口连续原始文件完整保存，字节丢失边界照实记录。
r86候选及正式均无复位。r88候选在Linux起点8.555918秒回ROM，末尾为systemd服务
启动，无panic；尚未acceptance，无解码请求。随后被动启动正式成功；冷复位换票继续，
没有将此启动重复算作一条码流的重跑。r88 UART SHA256为
`80947ca9f1dbe3f1a38829bbac1933e64c6bbaf2a64a868ac7a333a027d43fed`。
r89候选正常，正式首次恢复在Linux起点7.289323秒回ROM，末尾为TEE固件加载及
systemd-hostnamed启动，无panic，随后自然恢复成功；完整UART摘要为
`917197142de4e965d7003be16c1ed0641de8e5756b3a9deede3c85bc76eac273`。
r91候选与正式均正常。合计`.37`无线屏蔽候选5次Linux启动/1次冷复位（仅r88），
本轮正式eMMC恢复7次/2次冷复位（r85、r89），均最终恢复成功；r87/r90零候选启动。
从旧正式≥48/8追加本轮7/2，跨轮正式累计为≥55/10；`.36`原变体6/4、无线屏蔽
变体7/0分别保留，不与`.37`混算。五个候选窗口结束均2372 proof与视频通过，
最后为fd41fb5正式默认。没有新功率读数、RESET/VBUS同步测量或因果归因。

此处正式包复位延续既有板级问题，不能据本轮无线屏蔽或功率计在场推断供电根因。
锁/内存调试内核、5.15对照、性能/共存、10bit、超尺寸和长期稳定性均未由本轮证明。

## 经用户授权的空间清理

初次 .37 离线封包后，Data仅约7.0GiB，执行器在获取板票前拒绝，未操作板子。
协调者经用户同意删除 run≤r78 的38个 board-upload.tar，腾出约15.9G；每个对应的
board-upload-files.json及archive保留，r79起上传包未动，Data恢复到约23GiB。

之后协调者再次经用户同意清理：VM vdec-sequence/bundle28–35、
debug-splat-fixes/board/{retry,debug}；Mac hwdecode-parity/integration31–35中的
candidate.tar、fluster*.tar.gz、tools.tar。bundle36、board/prod、正式deploy-73、
.37目录及全部run目录保留；被删tar的SHA记录在build/cleanup-20261106.txt。
Data恢复约50GiB，r85实测可用52768084KiB。以上均为协调者执行，测试worker没有自行
删除历史证据。后续每窗仍按8GiB门槛检查，新增上传归档核摘要后清板端。

## 原始证据和交付

Mac产物与构建日志：build/hwdecode-parity/integration37/；编排与总表：
build/hwdecode-parity/hevc37/；各窗runNN/archive/results及logs/hwdecode-parity-rNN/。
r85 UART SHA256 `b1b337f57c4c92df0eae5fbb674df54f1641ed7221e265abea002ae1c37559b4`。
独立生产 W=1与QEMU KUnit34/34已在计划中记录。verify-final.py实际审计132唯一项、
118条逐帧/整流MD5与状态、14条失败原始I420摘要、六条代表及零旧Success回归；
五窗正式proof/视频、无线恢复、四窗DOS和无线阻断采证均通过，verification.json/log
保留结果。r88未进入acceptance，无线实际运行快照及DOS明确未覆盖，不计作通过。
最终主仓库全套原始输出为同目录final-main-tests.log。r91 UART SHA256为
`de07730a5b2be7a21bb73e5aec896c9b436958a42e39a63c92a2827cb3936346`。
所有票已释放，本任务上传已逐文件核摘要归档并清理板端，最终Data约45GiB。
未改驱动或固件、未合并、未push、未部署，正式sources.toml仍固定fd41fb5。
