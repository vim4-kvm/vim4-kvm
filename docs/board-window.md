# 单板 FIFO 与短窗口

本页管板锁、RAM候选链和恢复证明；普通安装只读[占板](#占板时间最短化)和[排队](#排队采样与迁移)。
RAM测试再读[候选链](#候选链与恢复)、[基线](#当前正式基线)、[证据](#基线与证据)；源操作读[MCP](#mcp-与接收)。
当前身份与正式安装分别见[主线基线](kernel-mainline.md#源码与配置)、[升级合同](kernel-mainline.md#正式构建与整包升级)。
命令、参数、路径、阈值以[board-queue](../tools/board-queue)、[board-window](../tools/board-window)的头注释、parser及对应函数为准。
曾通过[uhd5 RAM往返](bringup/2026-10-31-uhd5-main-integration.md)，不覆盖全部故障恢复；当前正式内核RAM往返尚待独占实测。

## 占板时间最短化

- 所有会话必须在同一协调主机共享同一队列；不同主机的临时目录不互通，不得换队列根来清缓存或绕锁。
- 取锁前完成构建、离线验证及无人值守窗口脚本；持锁不读文档、改代码、编译或现场排查。
- 窗口目标15分钟，默认上限30分钟，一个任务累计也按30分钟控制；超过须有协调者明确授权，
  队列显式`--max-min`最多50分钟。本轮[风扇自适应温度对照](fan-thermal-window.md)已获50分钟授权，
  不扩展其他任务。失败立即采证、回收、释放，离线分析再排队；稳定性默认10分钟。
- 只测改动相关门禁，正式候选九类全量只跑一次；当天身份/设置未变复用基线，同批候选链式启动，批末回原基线一次。
- 状态轮询判断就绪；能离线分析的码流、日志与哈希拷回本机。为恢复预留预算，正常恢复不能证明硬锁可恢复。

## 排队、采样与迁移

按[board-queue 的 main/命令帮助](../tools/board-queue)先查状态，再用run包住窗口；直接acquire时必须显式release。板票会传给子命令，run结束或常规信号退出释放。
heavy用于构建等重负载：采样申请先阻止新heavy，等已有heavy退出再独占；heavy彼此共享。不要在heavy中取板锁、在板窗内等待heavy，先释放再排另一类。

keeper兼容旧锁并保管票据；重新申请只能排尾，过期不续期。超时会告警和释放锁，**不会终止原命令或远端动作**；原会话立即收尾，不得启动新操作，后继也不能据此认为硬件空闲。
强杀run后keeper检测父进程消失，keeper死亡由后继/status清理；主机睡眠不保证准时唤醒。
旧会话先按原窗口退出，不嵌套新队列、不删活锁；旧waiter下轮迁移，不享新FIFO资格。临时旧lockf需保留锁文件；未修改旧waiter间不保证FIFO，禁止手工unlink锁文件。

## 候选链与恢复

1. 离线用[display-once.py 的 prepare](../packaging/kernel/display-once.py)生成私有payload；支持的格式、namespace/payload_id及静态PID1根目录合同见其parser/校验函数。普通安装包不能当RAM包。
2. 构建记录提供外部归档SHA；不能以传输后现算哈希代替来源证明。目录含归档时哈希归档，松散payload核manifest及逐文件。改变DT/模块/runtime必须换payload身份，相同ID拒绝覆盖；payload ID不能代替真实GNU build ID。
3. 首候选前采集[基线proof](#当前正式基线)。链式stage比较原proof和持久文件，不要求当前候选身份等于原基线；候选之间也不能覆盖首次挂载点所有权记录。
4. 在同一个run窗口用board-window依次启动、接收、再启动；批末return-baseline。stage沿用安全解包、静态ELF、完整模块、fsync/原子发布校验，不向正式模块树安装候选文件。
5. 串口仅打断autoboot并发送RAM sysboot，不saveenv、不改默认。读取基线MAC，仅在RAM设置，保持DHCP身份；立即收UART，不阻塞等SSH退出。
   大调试 Image 须避开 T7 U-Boot 的低地址映射空洞；prepare/read_trial/启动门禁按 ARM64 头共同核对加载布局，仅在本次环境设置加载地址，见[失败证据](bringup/2026-11-05-vdec-debug-boot.md)。
6. 等新boot ID及预期内核身份、SSH、服务、UDC与应用API；snapshot无观看者时的服务错误不等于采集坏，接收需另验真实解码推进。任何一步失败停止，不自动换候选或重试，先看UART再决定恢复。

只为候选创建空模块bind目标并记录marker；候选模块留私有payload。清理只删本次创建且仍为空、未挂载、未替换的目录；已有正式目录保留，异常报失败，不递归删。
完整proof走stdin，不塞进命令单参，避免Linux单参长度限制；完整inventory保留本机证据，清理只传目录身份。

return-baseline只正常重启一次，不打断autoboot；验证原身份、证明文件、服务、UDC和原应用实际解码推进。
默认启动必须事先指向基线，无proof拒绝恢复。cmdline只允许已审阅的正常/看门狗reason互换，其余token及顺序不变；未知reason只能原样，重复或增删拒绝。
失败保留UART/proof，不反复重启或热重绑网卡。EXIT trap安排恢复并留时间，但finally不能保证硬锁恢复。
租约失效或恢复预算不足时不越权停服务/重启，保留恢复交接文件；本机SSH转发仍清理。

## 当前正式基线

精确release准入来自[来源锁](../packaging/kernel/sources.toml)，运行校验见[board-window 的 identity/ready 与 proof 流程](../tools/board-window)，不凭uname单独判定。
首次proof须在真实基线上，确认默认LINUX/FDT就是所捕获文件；含完整模块、启动/登记文件、运行模块build ID、原应用、稳定DT属性，并与来源锁和manifest逐项比较。用户态覆盖目标也要采集。
候选RAM bind会遮住用户态原文件：链式/返回前只比较持久启动、登记及模块文件；正常重启退出覆盖后才比用户态完整哈希和模块notes/DT/应用状态。缺模块不能当通过。
历史HDR2的持久恢复清单不能包含被bind的程序路径，性能缓存文件清单则必须包括程序/插件，二者用途不同。

同Image的DT候选：先在基线捕获要验证的DT属性，至少一项实际改变，不能只看未变model/compatible；候选Image等于基线、DTB不同、完整模块及依赖数据一致。prepare校候选DT、启动读实时DT并要求新boot ID；不同DT/runtime独立payload身份，SHA覆盖全部内容。
ready要求管理器/HDMI/gadget、唯一活动KVM、UDC，One-KVM另查API。返回必须提供原应用解码推进命令，在sampling锁下运行；失败不报恢复成功。
stage/cleanup携带同一正式来源锁；上传超时不重试。此节是离线合同，实测边界见开头。

## 基线与证据

基线文件按当前部署登记选择，覆盖启动、模块、程序/插件和运行时登记，不能只给uname。缓存身份、参数和失效键见[board-window 的 baseline](../tools/board-window)：当天相同键才复用，变化/跨日重测，失败不缓存；测量后再核身份，缓存须跨worktree共享。
性能对照另提供公开settings，含源/运动程序哈希、编码配置、浏览器及接收机身份，不放凭据；设置变化更新settings。未带设置的旧调用只证明短接收门禁，不能证明性能条件一致。

复用stage先逐文件核原归档、基线、所有权和只读模式，拒绝内部符号链接与内容变化；默认拒绝重复目录。已清理空bind目标重新登记本次inode。
[perf-quick](../tools/perf-quick.py)在每步前留采样/恢复时间，清理错误单列，不覆盖原错误。
只读collect限已审阅状态文件，不触MMIO、HID或采集，不停服务；其他动作需有效板票。证据输出位置/文件名见工具，失败保留原始日志、UART与proof，不删除现场。

## MCP 与接收

先SSH转发One-KVM后端并安全读凭据；密钥不进参数/日志。客户端只在显式调用时创建。
每动作重新initialize及通知，服务重启/会话失效后重建；截图只读调用可重试一次，HID结果不明不自动重放。视觉静止不证明无人操作，截图不证明显示器光度。

HDR操作须有窗口内HID授权。自定义profile必须附现场验证来源、完整apply/restore，不能假定toggle一次即恢复；封装执行顺序为应用→截图→测量→finally恢复→截图。
内置M6序列的坐标、布局、尺寸和等待条件见[board-window 的 MCP 实现](../tools/board-window)；只适用于已验证现场布局，初始EOTF未知、尺寸不符或画面活动立即停止，切换期间未知有界等，不当SDR。恢复依据实际源EOTF，不依赖toggle次数；历史来源见[HDR/MCP记录](bringup/2026-10-31-hdr2-mcp-ice-pq.md)，未重新硬件验收。

接收只创建独立视频页，不加载产品输入脚本、不开音频/数据通道。先SSH确认服务出帧，再等真实解码推进才计时；流更换、计数倒退、停止推进均失败。
采样实际耗时保留，不宣称硬实时；接收/baseline自动sampling。ICE优先literal host，仅测试浏览器关闭mDNS隐藏；确需替换时用接收机LAN地址，不能用板IP或改生产ICE。
Mac本地网络权限可能只拦Node而curl正常，此时转发后端回环；不能转发管理网关当后端，否则offer认证失败。依赖/登录见[公共前提](board-tools.md#浏览器测试的公共前提)。
