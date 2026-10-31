# 2026-10-30：nodebug 消除 tmpfs 写入差距，视频回归通过

完成[候选审计与完整构建](../uhd2-nodebug.md)及5.15/uhd2/nodebug三方各一次启动测量。
**nodebug的tmpfs fresh write、YOLO fwrite与端到端均快于本窗5.15；用户态memcpy仍较慢。**
建议批准正式配置采用同组纯调试关闭项；不据单启动诊断宣布全栈性能追平或执行pin。
本轮未修改正式uhd1/uhd2配置、源码pin、GPU文件，未push；保页例外仍为用户已于 2026-10-30 接受。

## 版本、构建与现场

原7.3源码f71b5c6289cb保持不变；独立`~/build/uhd2-nodebug`完整Image/dtbs/modules通过，
release `7.3.0-vim4kvm-uhd2-nodebug+`、ID `af60b9bcb3cb6b84a62d6f4f664e9db53dfde202`。
原uhd2 ID `b5f919294867c4a1853406d10bf1f8997bf135de`，5.15 ID
`4a9b69d62ba7b3a5adeb41b213f7f3e573006165`。新旧7.3模块集合相等，均2338个，
网口/Wi-Fi/ADLA/Wave5/HDMI/JPEG/CRG UDC/IR/Panfrost匹配模块均通过打包检查。
nodebug代码源树无改动；运行时仅增加精确release路由和一次性工具白名单，沿用相同CMA/HDMI参数。

14:09:57–约14:21 PDT持板锁/重负载锁，各测量持两个媒体锁，约12分钟，低于30分钟。
先确认GPU暂停、5.15/四服务/UDC正常及锁空闲；完成备份、新候选stage、原uhd2私有载荷2355文件复核。
顺序A=5.15、B=uhd2、N=nodebug，最后回A；两个7.3均U-Boot RAM一次性启动，默认5.15不变。
原uhd2用原匹配帮助程序，nodebug切入前换为配套帮助程序，最后恢复本窗原始备份。
没有测量与编译重叠、刷U-Boot、写PWM/电压、HID、声音或ptrace视频进程。

微基准二进制三边同SHA `7d944e982f3e999c4d111b683a74d55857f97ab730f40dada52b3ba10add0fa7`，
libc同SHA `0e92a693bf489f4250855529681829c1cce831b2a7034c8b70ca8c6b8aa5c39c`；
同probe `d721833446b3525f84263d8a1daf123367dafa56a1ded2ea07e79c90a73e5bd3`及旧5.15 SDK/模型/输入。
CPU2、performance，两簇min=max为2208/2016MHz，CPU频率读回保持该值；worker CPU1、IRQ请求CPU0。
每kernel先YOLO三个101轮context，再微基准五重复，micro与NPU均有外层超时。
YOLO去前10轮，全部2727份输出SHA与已有5.15参考一致；微基准30类阶段/尺寸共150行/kernel。

## 三方微基准

下表五次重复的中位数，未删点；[全尺寸汇总及五次原ns](../data/nodebug-microbench-20261030.csv)。
数据是各一启动的诊断，不是启动层统计门禁。

| 测项 | 5.15 | uhd2 | nodebug |
|---|---:|---:|---:|
| libc memcpy 1MiB，MiB/s | 8516.8 | 8147.0 | 6653.2 |
| libc memcpy 64MiB，MiB/s | 7645.6 | 7241.6 | 6170.3 |
| tmpfs fresh pwrite 4.8384MB，ms | 3.632 | 6.675 | **2.559** |
| tmpfs rewrite，同尺寸，ms | 2.400 | 2.887 | **1.754** |
| tmpfs pread/copy-to-user，同尺寸，ms | 1.816 | 2.315 | 1.994 |
| tmpfs fwrite+close fresh，同尺寸，ms | 3.681 | 6.779 | **2.593** |
| 64MiB默认匿名首次触碰，ms | 56.987 | 6.985 | 7.533 |
| 64MiB nohuge首次触碰，ms | 57.451 | 122.411 | **48.990** |
| 默认/nohuge首次minor faults | 16384/16384 | 32/16384 | 32/16384 |

tmpfs write与4K匿名fault路径的明显回升，支持原调试组带来实际分配/锁路径成本；
不能唯一归因于LOCKDEP，因为候选还关闭SLUB调试、函数/syscall tracer，函数对齐有依赖变化。
同页数nohuge比较避免把THP少fault误作一般页分配快；默认匿名触碰的跨内核差主要受THP策略影响。
pread仍慢于5.15约9.8%，64MiB用户态memcpy慢约19.3%，1MiB慢约21.9%；
因此没有证明“通用内存全部恢复”。这些读/用户态拷贝不随fresh write一起改善，
后续应独立排查DDR、物理页/THP布局、缓存与跨启动波动，不能为追数据关闭安全加固。

## YOLO 分段

三个context暖均值等权平均，单位ms/轮；原SDK区间保持，计时工具扰动<1%资格未在本窗重验。

| 阶段 | 5.15 | uhd2 | nodebug |
|---|---:|---:|---:|
| SDK | 30.434875 | 30.561057 | 29.321092 |
| fwrite | 3.500196 | 6.913376 | **2.617888** |
| float扫描 | 1.948525 | 1.912407 | 1.918323 |
| e2e（SDK至扫描结束，不含gap） | 36.328421 | 39.953407 | **34.262997** |
| gap | .003024 | .002873 | .002272 |

nodebug fwrite相对本窗5.15 **−25.21%**，e2e **−5.69%**；本次已消除原约3.5ms的写入差距。
这里只能证明同窗口这些端点恢复；未做四个独立启动对、不更新旧性能资格为通过，
也不能把张量落tmpfs的测试循环等同不保存输出的应用工作负载。

## 视频与KVM基本回归

nodebug以仅视频recvonly的受控页面接收One-KVM，没有加载HID处理代码或建立输入通道。
约40秒WebRTC观察，40个采样点：2356帧推进/39.162秒（接收侧约60.16fps，含解码批次节奏）；
One-KVM自身raw/encoded从296/296推进至2398/2398，35.034764秒，**59.99755fps**。
接收侧丢帧、丢包、freezeCount均0；pipeline Playing，raw与encoded累计一致。
已加载wave5/t7_vdin_test/t7_hdmirx/adla_core/crg_udc及网络模块，最终候选taint=0，
未见Wave5编码错误、NPU创建失败/恢复错误、内核WARNING/Oops。
WebRTC主动关闭时有SRTP/ICE已关闭提示，发生于测试停止阶段，不计作编码失败。

manager登录、主页面、JS资源、/api/status与/api/kernel均200，运行release读回nodebug；
One-KVM页面与JS资源均200。仅为本次约40秒60fps冒烟，不替代十分钟长稳、GPU、音频或HID回归。

## 条件缺口、恢复与建议

A的DDR freq为1008MHz，B/N无真实DDR provider，未以时钟名称或虚构值补齐；
固定CPU频点不证明同DDR条件。A73采样范围A 54.4–59.1、B 52.2–58.0、N 50.9–60.3°C，
温度/启动差异仍可能影响单启动memcpy结论，不选择性删除较慢nodebug组。
本窗未另立“停流累计计数静止”资格，独立测量先调用stop、无视频接收者；视频计数证明只覆盖nodebug开启流的回归。

建议批准把[纯调试关闭集合](../uhd2-nodebug.md#审计与取舍)同步到正式7.3配置，保留独立调试构建；
安全基线不变。正式配置、release部署及pin仍待用户批准，本轮未执行。
下一步单独复查memcpy/pread；若要声明7.x全局性能追平，仍须可靠启动配对及默认策略复验。

最终回默认5.15.137-vim4kvm-hdrdual6，12份文件SHA、uid/gid/mode与入场全相同，
One-KVM/manager/HDMI/gadget四服务active，UDC configured；CPU/亲和恢复，各锁及串口释放。
板上证据`/var/tmp/vim4-memory-board-r14/`，本机`build/memory-board-r14/evidence/`，
归档SHA256 `ccb860afcbce8e75684e17c10f9de7f570ca8a90637d39f3436a3b66efc17309`；
本机另保留UART、视频计数、HTTP结果、原始/最终证明与构建输出日志。模型/张量二进制不入库。
主仓unittest 314项、8跳过，OK；`git diff --check`及正式uhd1/uhd2/sources未变检查通过。
候选准备提交f413437；内核源仍f71b5c6289cb，无新驱动源码提交。完整构建/打包日志位于VM候选输出目录。
