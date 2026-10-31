# ADLA npu4：缓存复用、取消唤醒与分阶段延迟取证

本轮仅离线，未访问板子；GPU分支及工具不改、不混入提交。
保页例外仍为**用户已于 2026-10-30 接受**。
依据[npu3实测](bringup/2026-10-30-npu3-acceptance.md)，修复已证实的ABI与通知缺陷；
约104ms延迟没有足够现场分阶段数据，不能登记为已根治。

## 缓存fixup合同

厂商`common_drivers/drivers/adla/kmd/drv/common/adlak_submit.c:891–925`
仅在INVOKE的addr_fixups_num非零时替换模型缓存及数量，零count保留此前缓存。
其执行器使用模型缓存，零count不表示“本次任务禁止地址fixup”。
npu3取证为383个非压缩task，第一段带两个fixup，第三段count=0，
task 380/381仍各引用一个缓存条目；被误判`0+1 exceeds 0`，返回EINVAL。

npu4检查有效模型缓存的addr_fixups_num，仍检查offset/count、loc、shift、unit及命令长度。
无缓存却引用非空区间、超过缓存尾端或非法目标仍拒绝。
另修复分配/复制/校验失败后缓存释放但count残留：清零count，分配失败返回ENOMEM。
宿主测试执行真实校验块，覆盖零count复用、无缓存、真正越界、格式长度及unit=0。
同类审查覆盖注册dep/reg fixup、压缩命令范围与两种执行器；这些以注册模型数量为界，
没有另一处以本次零count替代缓存长度的执行边界检查。
内核`drivers/misc/adla/drv/common/adlak_submit.c:994–1017`为有效缓存检查，
`:964`/`:1038`为失败后count清零；注册命令范围检查在`:719`起，执行器在`:1975`附近取缓存。

## cancel：通知与等待类型匹配

npu3的adlak_uninvoke_request用wait_event_timeout等待invoke_cnt=0或recovery_error，
完成通知adlak_to_umd_sinal_give却只用wake_up_interruptible。
工作已排空时非可中断等待者未被唤醒，直到5秒deadline重新检查条件，实测约5.19秒。
通知改wake_up_all，同时唤醒WAIT及CANCEL；保留排空等待的非可中断性质，
避免信号打断DMA停止确认。宿主执行真实通知函数，模拟两类等待者，旧通知会失败。
证据入口：`drv/common/adlak_submit.c:1569`等待，
`drv/port/os/linux/adlak_os.c:605–614`通知，路径均相对内核drivers/misc/adla。

正常短模型cancel目标≤250ms，超限即失败；这是新的验收目标，非厂商5.15实测保证。
依据：10ms worker轮询在HZ=250向上取整约12ms，软复位内存停止轮询上限约30ms，
再留调度、第二次reset及通知余量。5秒保护上限保留，超限明确报错，绝不提前释放页。
真实硬件、系统调度及复位耗时仍须上板；部分提交等待硬件的其他路径不能靠该目标证明。

取消时没有完成IRQ也会返回SUBMIT_WAIT；npu3先调用正常IRQ bottom-half，再检查cancel，
因此记录status=0并进入profiling停止/错误解析。现在先分流cancel到软复位、退役、通知，
不把取消轮询返回当硬件完成。正常提交器错误也不再被worker忽略，失败进入复位路径。
上述状态分流在`drv/common/adlak_inference.c:373–385`、`:413–429`，
trace定义为内核`include/trace/events/adla.h`。

## 约104ms：证据、修复边界与可区分测量

正确对照是DenseNet约1.92ms→104ms；约30ms是YOLO，不是这个故障后的DenseNet基线。
npu3首先有取消/超时、idle轮询警告及status=0，其后profiling已有207.78ms异常轮，
再开始视频并行；关闭视频请求后仍104.20ms。视频并发不是延迟异常发生的必要条件。
IOVA/CMA前后稳定、无分配失败日志，不支持“持续分配泄漏”；不排除瞬时竞争。
候选无多频devfreq策略，正常CCF目标固定800MHz；故障期间未采实际频率，不能排除失配。
YOLO拒绝先于入队，后续DenseNet是新进程/新模型缓存，不是复用YOLO的错误输出路径。

本轮修复上述取消误入完成解析和提交失败忽略；不凭猜测改电压、频率或CMA。
尚不能证明这两处就是持续104ms的全部根因。新增标准tracepoint `adla:adla_phase`：
submit、irq_wait、complete、reset各报elapsed_ns/result/clk_hz，默认禁用，无逐任务printk。
submit包含命令补丁/缓存同步/MMU/parser，complete包含profiling及完成状态解析。
下一窗口用tracefs独立instance收集并在结束删除实例，不改全局其他会话tracer：

```sh
# 持独占锁后；由外层timeout限制整个阶段，结束关闭事件并保存trace。
mkdir /sys/kernel/tracing/instances/npu4
echo 1 > /sys/kernel/tracing/instances/npu4/events/adla/adla_phase/enable
cat /sys/kernel/tracing/instances/npu4/trace > phase-before.txt
```

每阶段前后记时、QUERYCAP iova_free、CmaFree、ADLA那一行/proc/interrupts、
clk_core、runtime_status、线程/proc/PID/schedstat与上下文切换计数；不读危险MMIO、不ptrace。
先做无故障DenseNet100轮，再逐一cancel→100轮、WAIT超时→100轮、kill→100轮，
最后profiling→100轮；每项独立目录，不能把几种故障串完后只测一个总结果。
若某项使延迟持续异常，保存该项前后计数，剩余并行性能项记受干扰，禁止重试挑样本。

| 观测 | 可区分原因 |
|---|---|
| submit长、irq_wait短，CMA/IOVA波动或分配失败 | 同步/命令生成/MMU及内存路径，非计算时间；另用进程create时间区分初始化 |
| irq_wait长、IRQ增量少；reset增加或错误 | IRQ/worker/恢复状态，结合标准sched_switch筛选ADLA线程及schedstat区分离CPU |
| complete长，仅profiling后出现 | profiling停止/状态解析路径 |
| phase报实际频率异常或PM状态矛盾 | CCF/runtime PM失配，先取证不强制写频率/电压 |
| 内核阶段短而用户耗时长 | SDK、CPU调度或用户缓存/拷贝；不能归为硬件计算慢 |

trace是诊断开销，普通101轮性能关闭事件，诊断另跑短组；IRQ计数只归属于ADLA。
视频帧/编码计数与NPU阶段时间统一时钟对齐；保留每组失败及未完成样本。

## 产物与离线验证

独立release `7.3.0-vim4kvm-npu4+`，内核仍在VM `~/src/linux-7.3-npu`，
输出`~/build/npu-adla4`、载荷`~/build/npu4-candidate`，旧候选均保留。
完整Image/dtbs/modules与静态PID1同release；五个助手增加显式npu4分派，5.15默认不变。
正式源码/部署锁不变。最终bundle须下一窗口新现场证明，离线不stage、不伪造证明。

| 验证 | 结果 |
|---|---|
| 内核提交 | `vim4-npu-adla@34f345566a1b9`，原版权/作者/许可证保留 |
| 主仓运行时 | `1fed075`，五个匹配助手显式分派npu4 |
| build ID | `57e1dd72a4287f3982518d1b2e66ed6544ab99d3` |
| Image SHA256 | `369fe504be34eeecb5adb70e5181207d020946449dd20e8102c5848dafd8173e` |
| 完整构建 | Image/dtbs/modules，独立release，2338模块 |
| strict checkpatch | 完整提交含说明与Signed-off-by，0 errors / 0 warnings / 0 checks |
| 宿主 | 四个Python harness及bounds/ABI C通过；含实际校验块和完成通知回归 |
| schema/DT | ADLA binding及匹配DT检查通过 |
| W=1/sparse | 实际24个CHECK；106条诊断，无本轮新增行命中，保留厂商存量清单 |
| 主仓unittest | 308项、7跳过，OK；未混入GPU工具改动 |

存量包括旧式inline、原型、未使用变量、kernel-doc、格式符以及sparse类型/地址空间等，
包括原有adlak_submit_wait声明提示；不宣称全驱动零告警、不做机械格式化。
VM日志为上述输出目录的final-build.log、verified-build.log、host-tests.log、
checkpatch-final.log、w1-sparse.log、schema.log、dtbs-check.log、package.log及build.json。
这些日志本轮重新生成；复制的npu3输出只是构建缓存，不能作通过依据。
本机副本`build/npu-r9/candidate/`；独立复核16个载荷文件SHA、归档2338模块的release、
静态PID1 ELF/release及内核提交一致。runtime清单固定主仓1fed075，未包含GPU工作树改动。
签署说明前的npu4草稿单独保留，不用于上板；只使用上述build ID与最终manifest。

## 下一窗口≤30分钟

| 分钟 | 操作与停止条件 |
|---|---|
| 0–5 | 等GPU释放，确认5.15/服务/UDC和锁，备份并临时安装匹配助手，刷新证明，RAM一次性启动npu4 |
| 5–8 | 512MiB CMA、ADLA/HDMI正常；先NPU关闭视频基线，帧推进/无编码错误，失败停本项 |
| 8–13 | 视频停流请求后，三模型101轮完整字节比较，task create必须0；均值/P50/P99/max及≤5%门槛；YOLO失败取参数后继续后续独立项 |
| 13–21 | 按上述顺序每种故障前后短组取phase/IRQ/频率/PM/资源，取消≤250ms；同context继续、close和kill回收，无释放失败；profiling放最后 |
| 21–25 | 若无持续异常，同视频会话NPU关/开各有界运行；完整DenseNet组101轮，帧推进/编码错误/丢帧与延迟；有异常则保存证据标受干扰 |
| 25–30 | 回5.15，按本窗口备份恢复助手，核对12文件哈希/权限、四服务、UDC，保存并释放所有锁/串口 |

复用既有5.15基线；SDK、probe、模型/输入SHA不变时不重采。单项≤10分钟且带timeout，
不发HID（被控机Mac mini M6）、不测声音、不ptrace视频进程、不写PWM/电压，不push。
真实复位失败保页、物理电压和全部DMA页回收仍不能离线证明；失联无法恢复则停止报告。
