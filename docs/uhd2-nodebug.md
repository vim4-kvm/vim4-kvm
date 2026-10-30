# uhd2-nodebug：调试配置对照候选

最新[三方上板结果](bringup/2026-10-30-nodebug-memory-window.md)：tmpfs/YOLO端到端恢复、视频约60fps；memcpy仍慢。默认5.15与正式配置不变。
后续[绑核证据与两对门禁](nodebug-performance-gate.md)含正式配置最小diff草案，尚未应用。
最新[两对实测](bringup/2026-10-30-nodebug-paired-gate.md)输出/60fps通过，性能资格仍不确定，大核memcpy未复现退化。

用户授权本轮关闭纯调试开销，不需要额外批准；正式配置/pin/push仍需批准。
**uhd1同样开启锁调试，历史7.3视频/GPU/NPU数据均包含该层成本。** 不是NPU补丁新增。
候选独立配置`packaging/kernel-edge/uhd2-nodebug.config`，源码仍为
`integration/npu-uhd2@f71b5c6289cb3254690e57292327e73514f0715f`，
release `7.3.0-vim4kvm-uhd2-nodebug+`。不修改uhd1/uhd2.config或正式sources锁。

## 审计与取舍

[逐项CSV](data/uhd2-nodebug-config.csv)对照厂商5.15、uhd2与候选；absent表示配置无该项，不能等同硬件缺功能。
实际有效差异由olddefconfig生成；源Kconfig依据及既有内存性能证据见[内存审查](memory-copy-audit.md)。

| 分类 | uhd2 → 候选 | 理由 |
|---|---|---|
| 锁调试 | DEBUG_LOCK_ALLOC/LOCKDEP、DEBUG_RT_MUTEXES/SPINLOCK/MUTEXES/WW_MUTEX_SLOWPATH/RWSEMS y→n | 纯调试；厂商均关闭。减少锁生命周期、获取释放检查；不是降低内存访问隔离 |
| slab/misc | SLUB_DEBUG、DEBUG_MISC y→n | SLUB_DEBUG_ON原本n，仍去掉编译进来的调试分支；不是关闭分配安全清零 |
| 函数/syscall跟踪 | FUNCTION_TRACER、FUNCTION_GRAPH_TRACER、FTRACE_SYSCALLS y→n；动态ftrace能力与TASKS_RUDE_RCU等依赖随之退出 | 运行时未开启时动态ftrace主要是NOP，不能称原先每函数都记录；候选消除入口插桩布局与相关能力。函数对齐8→4是依赖变化，归因仅能到整组nodebug，不能唯一归为LOCKDEP |
| DEBUG_LIST/SG/NOTIFIERS、DEBUG_PREEMPT、DEBUG_VM*、PAGEALLOC、PAGE_OWNER、DEBUG_OBJECTS | 原已关闭，继续关闭 | 不是本轮新增优化；不把编译支持HAVE/ARCH_HAS项误作运行时开启 |
| SCHED_DEBUG/SCHEDSTATS | SCHEDSTATS原n，SCHED_DEBUG未见该有效选项 | 不新增调度统计；SCHED_INFO仍y，因为arch/arm64/kvm/Kconfig:37强制选择，保留KVM功能，不为删它去禁用KVM |
| 符号/观测基础 | DEBUG_INFO/DWARF/BTF、DEBUG_FS、FTRACE的基础事件/tracepoint、STACKTRACE保留 | 符号不逐调用执行；保留匹配BTF/模块、已有设备状态与事件诊断。DEBUG_KERNEL/BUGVERBOSE自身不是开启全部检查 |
| 安全加固 | STACKPROTECTOR_STRONG/PER_TASK、INIT_STACK_ALL_ZERO、PAN/MTE/EPAN、内核PAC、KASLR、STRICT_KERNEL/MODULE_RWX等原值保持 | 属于安全基线，不作为纯调试删除；HARDENED_USERCOPY/FORTIFY_SOURCE原n，保持现状，不在本次引入安全策略变化 |
| 分配/THP/交换 | INIT_ON_ALLOC/FREE、THP/mTHP、memcg、NUMA、zswap及迁移策略原值保持 | 避免同时改变分配/交换行为掩盖调试组效应，保留后续独立实验条件 |

纯调试关闭按本轮授权执行；关闭不是安全取舍，但会减少故障诊断能力，调试构建仍应保留。
正式配置的采用与pin另待用户批准。候选仅增加release白名单，不扩大到任意7.x。
五个共用rootfs帮助程序按相同release分派；启动器核对CMA/首次HDMI参数与完整匹配模块。

## 构建与上板

VM独立输出`~/build/uhd2-nodebug`，完整Image/dtbs/modules；原uhd2输出与源码树不修改。
完整构建已通过，build ID `af60b9bcb3cb6b84a62d6f4f664e9db53dfde202`；有效配置SHA
`eced177a5c69ec9c44fdd2656e870618684046f749253755c9f6f6889728e919`。
完整模块清单与uhd2的2338模块集合相等，打包核对网口、Wi-Fi、ADLA、Wave5、HDMI、JPEG、
CRG UDC、IR及Panfrost存在；用户态GPU文件不动。独立PID1校验release/build ID后bind本次模块。
上板只用RAM一次性启动，不覆盖正式boot文件/默认5.15，保留原uhd2与全部NPU旧候选。

本轮窗口按5.15→uhd2→nodebug→5.15；同一微基准二进制、libc、NPU probe/SDK/输入SHA，
固定CPU2、2208/2016MHz公开频点、tmpfs目录策略与YOLO三个101轮context去10，报告温度。
微基准默认五重复、180秒外层超时，YOLO每进程60秒/组240秒；无编译重叠。
nodebug再以接收侧计数证明One-KVM视频帧推进/帧率/丢帧/错误，并核对manager页面/API与服务UDC。
DDR只读已有freq口；7.3缺真实DDR provider就记录缺失，不以门控时钟或虚构值对齐。
不发HID、不测声音、不ptrace视频进程，不写PWM/电压，不push/pin。
结束恢复临时帮助程序、CPU/亲和，回5.15核对12文件哈希/权限及四服务/UDC，释放全部锁。
离线主仓unittest 314项、8跳过，OK；新增release验证CMA/HDMI参数与模块目录隔离、已有gadget不重绑。
