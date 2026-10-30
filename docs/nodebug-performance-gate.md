# nodebug：绑核证据、DDR边界与两启动对门禁

后续[两对实测](bringup/2026-10-30-nodebug-paired-gate.md)已完成：大核memcpy未复现退化，
tmpfs/端到端均值更快但联合区间和条件缺口令门禁不确定。以下保留预登记方案；正式配置/push/pin不变。
[三方记录](bringup/2026-10-30-nodebug-memory-window.md)的tmpfs恢复结论保留；memcpy慢尚未定因。

## 旧记录究竟证明了什么

原始目录本机`build/memory-board-r14/evidence/{A1,B1,N1}/memory`。
旧runner明确`os.sched_setaffinity(0,{2})`后由主线程Popen，C程序没有更改亲和，
Linux子进程继承调用线程亲和。采样线程恢复自己的原CPU集合不改变主线程/子进程。
因此**旧测试已经绑CPU2，不是未绑核**；T7 DTS中的CPU0–3为A73、CPU4–7为A53。
旧C没有sched_getcpu或子进程schedstat，不能冒充逐测项实际运行核的直接测量，
也没有证据支持它跑在小核。state.cpu=2是要求值，affinity_before/restored=0–7是runner恢复记录。

三组均同二进制/libc。每组仅两个约1Hz频率/温度样本，政策min=max且读回policy0=2208000、
policy4=2016000kHz；它们不能给每个8ms memcpy的瞬时实际频率作证明。

| 组 | memcpy 64MiB五次时间ms（全保留） | A73温度采样起→末°C | 64MiB测项开始/结束，开机单调秒 |
|---|---|---|---|
| 5.15 A1 | 55.041 / 8.371 / 8.365 / 8.394 / 8.357 | 57.4→58.8 | 1782.418→1782.563 |
| uhd2 B1 | 15.954 / 8.838 / 8.722 / 8.842 / 8.750 | 56.1→57.0 | 43.353→43.469 |
| nodebug N1 | 15.720 / 10.372 / 10.373 / 10.128 / 9.984 | 60.3→57.5 | 38.001→38.131 |

温度是测量前后稀疏快照，不能线性插值成该测项温度。N1更暖、初始缓存/物理页布局、
DDR/温控状态及启动时长均可能影响比较；固定cpufreq不证明所有这些状态相同。
三个中位数不由首轮异常单独造成，N1的后四次也更慢；不能据此唯一归于温度或调试关闭。
旧数据没有DDR对齐资格，也不足以推翻该启动测到的差距。

## 工具更新：按大/小核分别测，记录实际核与分布

仍用一个C二进制，两内核SHA必须相同。runner原有`--cpu`继续支持：

```sh
python3 tools/memory-bench.py --binary ./memory-bench --cpu 2 --repeats 9 --output NEW_A73
python3 tools/memory-bench.py --binary ./memory-bench --cpu 6 --repeats 9 --output NEW_A53
```

以上是下一窗口示例，本轮未访问板子；VM只能验证绑不同逻辑核，不能模拟A73/A53性能。
先以DT/CPU topology确认编号，不在未知板子照抄2/6。调用者持板/媒体锁、独占CPU内存。
每个调用原150/170/173秒安全边界保留；门禁每boot整个采集预算≤150秒，任一超时即回退，
不能把每项最长时限相加后无限延长窗口。

- C入口要求单CPU亲和，否则拒绝；每段在计时区间外记录sched_getcpu始/末与该CPU的
  `cpuN/cpufreq/scaling_cur_freq`始/末。runner核对两端CPU均等于指定核，缺频率填null而非0。
  频点是框架读回代理，不冒充物理瞬时频率；频率读取在计时外，但会有共同扰动。
- memcpy新增128/256/512KiB、2/8MiB，加原4/64KiB、1MiB、4.8384MB、16/64MiB，
  横跨L2内外；工作集是源+目的，不能按单缓冲尺寸宣称必命中L2。缓存容量仍需记录各核cache/index*/size。
- 每尺寸9次，保留首轮、原序、均值/中位数/P99/max及分布JSON。仅9次时nearest-rank P99=max，
  不称为可靠总体尾分位数。原始首轮不删，门禁另外预先规定冷/暖口径。
- 每CPU共35类尺寸/阶段，输出315行；默认五次仍为175行。频率/温度1Hz采样、
  begin_ns、fault与切换计数仍保留。新增字段不允许将旧记录补填为已测值。
- 工具实际运行、两个逻辑CPU放置、重复分布、nohuge fault边界、亲和恢复与不覆盖结果已在ARM64 VM验证。

## DDR：严格使用可核实的安全接口

允许5.15现有只读`/sys/class/aml_ddr/freq`；允许已审阅DDR/DMC devfreq设备的cur_freq及来源说明。
不写该厂商debug freq覆盖值，不碰PWM/电压，不盲读寄存器/重放地址；遵循LESSONS的audiobus事故教训。
本轮不新增板上debugfs读取：K7 drivers/clk/clk.c:3370–3394的clk_summary会调用
recalc_rate/phase/is_enabled等provider，不能仅因名字含debugfs就视为无硬件访问。
只有已审查相应provider、确认电源/时钟访问合同安全的clk_summary/具名clk_rate才可采；
不为取得DDR数值临时全树dump。K7 t7-peripherals.c:1220的t7_sys_ddr是SYS_PCLK门控，
不是内存PLL频率；r14看到的ddr_pll_osc名称也未证明为实际内存频率。

目前5.15有1008MHz读回，7.3缺已验证的真实DDR读回，不能称“两边都无接口”，也不能称已对齐。
若下一窗仍缺，记录一边缺失；64MiB memcpy及tmpfs读写作**带宽代理**，不能反推GHz，
因为同时含缓存、TLB、CPU拷贝指令、页分配/调度。若将来两边均不可得，同样以代理报告，
纯同DDR条件结论保持不确定。新增DDR只读provider是独立任务，本轮未实现。

## 预登记精简门禁：≤30分钟，至少两对

A=5.15、B=同一nodebug载荷；顺序A1 B1 A2 B2 A-final，四个性能启动独立，末A只恢复。
起始A也重新默认启动，避免再次把30分钟热启动A与刚启动B作配对。

| 时间预算 | 操作 |
|---|---|
| 0–4分钟 | 锁/默认5.15/服务/UDC/备份，二进制/SDK/输入SHA，DDR安全接口能力与CPU拓扑/缓存盘点 |
| 4–22分钟 | 两个不重叠AB对；每boot重新对齐频率/亲和、稳定10秒，A/B按同次序运行；采集部分≤150秒，启动预算≤60秒；条件或超时失败就停止并回退 |
| 22–24分钟 | B2约60秒视频60fps计数回归（测量结束后），保存raw/encoded、错误、丢帧与接收侧计数 |
| 24–28分钟 | 回A、恢复设置/帮助程序，核对哈希/权限、服务/UDC、释放锁；余量2分钟 |

每boot：CPU2和CPU6微基准分别9次，第一对次序2→6，第二对6→2，AB同对相同。
先保存完整重复分布，rep0单列冷态；主要微基准均值/中位数只用预先登记的rep1–8，
不再依据首轮大小决定是否排除。所有尺寸保留，主端点只用64MiB memcpy、4.8384MB fresh pwrite。

NPU固定CPU2、worker CPU1、IRQ CPU0：VGG/DenseNet各3 context×1000去前50，
YOLO各3×101去前10；仅YOLO开启分段，VGG/Dense关闭以免已知>1%时钟插桩。
三模型逐轮完整输出只比已有5.15张量SHA，新的计时分布都在本窗采集，不复用旧计时。
YOLO分别报SDK与e2e+gap。`--timing`<1%资格仍未闭合；先用同boot短开关对照检查，
若无法确认，YOLO e2e结果仅诊断且总体门禁不确定，不靠加同boot轮数强行通过。

每boot先按重复/context层汇总暖均值与暖中位数；两对分别算`d_j=100*(B/A-1)`，
统一以耗时比表示退化（带宽端点也先转同bytes的耗时，避免符号颠倒）。
报告两对原值、等权平均差及双侧95% t CI，df=1、临界值12.706204736；中位数效应同法。
两对不能验证正态/独立或给可靠无分布中位效应区间，预期功效低，不能将数千轮池化成启动CI。

主要8端点：CPU2/6各自memcpy64MiB与tmpfs fresh两项，共4项；NPU SDK三模型共3项；
YOLO e2e+gap共1项。各主要耗时平均退化≤5%且联合单侧上界
`U=mean(d)+t_(1−.05/8,1)*sd(d)/sqrt(2)≤5%`才有整体数值通过证据。
双侧下界>5%为有退化证据，其余跨界为不确定；不能用某项提升抵消另一项退化。
DDR缺失、频率/CPU不匹配、热样本温度boot中位差>3°C、背景消费者不齐、插桩未验证，
均令受影响资格/总体结论不确定，仍报告原数据。对比CPU6用A53温度，CPU2用A73对应传感器。
按begin_ns关联采样；若测项太短而没有足够同期温度样本，就注明不可判定，不插值成逐段实测温度。
停流后须保存两次累计帧/错误计数与消费者状态，若API仍无累计计数则明确缺口，不把fps=0当补齐。
控制外层截止时间，宁可不完成并标不确定；不缩减为一对冒充确认，不发HID/声音，不ptrace视频进程，不pin/push。

## 正式配置最小diff草案（未应用）

[nodebug-formal-draft.patch](../packaging/kernel-edge/nodebug-formal-draft.patch)仅12个配置赋值，
不含LOCALVERSION、不改正式文件；LOCKDEP等隐藏依赖须olddefconfig重算。
已在VM复制配置上应用并olddefconfig，**除LOCALVERSION外与已测nodebug有效配置逐字相同**；
未来正式7.3配置需重新审查依赖，不直接套用行号。`git apply --check`通过，仅为可审阅草案。

| 改为n的选项 | 分类 | 失去的调试能力 |
|---|---|---|
| DEBUG_MISC | 纯调试/无安全影响 | 杂项开发调试选项入口 |
| SLUB_DEBUG | 纯调试/无安全影响 | slab redzone/poison/一致性调试能力；原DEBUG_ON已n |
| DEBUG_RT_MUTEXES | 纯调试/无安全影响 | rtmutex错误使用诊断 |
| DEBUG_SPINLOCK | 纯调试/无安全影响 | spinlock状态/拥有者检查 |
| DEBUG_MUTEXES | 纯调试/无安全影响 | mutex错误使用检查 |
| DEBUG_WW_MUTEX_SLOWPATH | 纯调试/无安全影响 | ww_mutex慢路径验证 |
| DEBUG_RWSEMS | 纯调试/无安全影响 | rwsem状态检查 |
| DEBUG_LOCK_ALLOC | 纯调试/无安全影响 | 活锁对象释放/重初始化、退出时持锁检查 |
| LOCKDEP | 纯调试/无安全影响 | 锁获取释放跟踪与依赖基础；原PROVE_LOCKING已n |
| FUNCTION_TRACER | 纯调试/无安全影响 | function tracer及动态函数入口探测的相关依赖 |
| FUNCTION_GRAPH_TRACER | 纯调试/无安全影响 | function_graph函数调用/返回耗时跟踪 |
| FTRACE_SYSCALLS | 纯调试/无安全影响 | ftrace syscall专用事件；不等于禁止自有进程strace |

保留栈保护、初始化、PAN/MTE/PAC、KASLR/RWX及BTF等原值；SCHED_INFO由KVM选择保留。
需要临时诊断时，最快使用保留的原uhd2调试候选RAM一次性启动并使用其配套完整模块；
定位自己的PID、短时启用相应tracer并恢复，不能ptrace视频进程。
被编译掉的function/syscall tracer、SLUB/锁检查无法在nodebug上靠echo热启用，
须在独立调试配置重新启用本表所需项、olddefconfig和完整构建，以独立release及匹配模块启动。
不在运行的生产kernel混装调试模块，不改变正式默认启动；正式采用草案、pin/push仍待用户批准。

离线验证：ARM64 VM严格编译、两个逻辑核各9次/315行跑通，执行测试通过；
主仓unittest 314项、8跳过，OK；正式配置/锁未变检查、`git diff --check`、草案apply检查通过。
新ARM64二进制`~/build/memory-bench-review/memory-bench-gate` SHA256
`09f8eb10d83ece4f4a68edc95c8fb7e42b79f1d95b3c0534eba71d7724e8ef18`，下窗使用同一文件。
这些不是板上性能结果，也不修改旧三方数据。
