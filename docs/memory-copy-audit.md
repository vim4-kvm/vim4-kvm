# 7.3 内存与拷贝性能：离线审查及微基准

本轮离线，不访问板子、GPU文件，不改正式配置、不push/pin。
[YOLO分段记录](bringup/2026-10-30-npu-e2e-window.md)把约3.46ms增量定位到tmpfs fwrite，
尚未证明整个KVM所有拷贝都退化。**首要配置嫌疑是7.3的锁调试，不是已坐实的DDR低频或ADLA缺陷。**

## 证据范围

配置C5=`packaging/kernel/vim4.config`，C7=`packaging/kernel-edge/uhd2.config`；
VM `~/build/npu-integration/.config`的相关项与C7一致。C7候选源码为f71b5c6289cb。
源码K5为VM `~/src/linux` @80a07ad54，K7为`~/src/linux-7.3-npu-integration`。
厂商驱动V=`common_drivers/`，U为VM `~/src/u-boot` @b60ff51ece。
这些是可复核的源码/配置证据；下窗仍须保存运行内核config和cmdline，不能拿开发树当前HEAD冒充已运行二进制。

## 逐项比较与可能性排序

| 项 | 厂商5.15 | 7.3 | 判断/证据 |
|---|---|---|---|
| 锁调试（最高优先级） | C5:8751–8758的PROVE_LOCKING、DEBUG_SPINLOCK/MUTEXES/RWSEMS/LOCK_ALLOC均n | C7:9803–9809启用DEBUG_RT_MUTEXES/SPINLOCK/MUTEXES/WW_MUTEX_SLOWPATH/RWSEMS/LOCK_ALLOC、LOCKDEP；PROVE_LOCKING和LOCK_STAT为n | K7 lib/Kconfig.debug:1533–1553说明DEBUG_LOCK_ALLOC选择LOCKDEP并检查锁释放/重初始化；kernel/locking/lockdep.c:5942/5950获取释放记账、:6806释放范围检查；mm/page_alloc.c:1423在释放页检查持锁。未开启完整死锁证明仍有运行时成本，不应把PROVE_LOCKING=n解释为无锁调试 |
| 默认内存清零 | C5:8237 INIT_ON_ALLOC_DEFAULT_ON=y，但已有板上cmdline init_on_alloc=0 | C7:9218–9219 alloc/free默认均n | 两边INIT_STACK_ALL_ZERO=y（C5:8236/C7:9217），新页安全清零仍必需；没有7.3误开分配/释放清零的证据，不建议关闭栈初始化 |
| sanitizer/页调试 | C5:8648起UBSAN bounds、:8702起KASAN_HW_TAGS、:8709 KFENCE、:8671 PAGE_OWNER；编译开启不等于全部运行生效 | C7:9713 UBSAN=n、:9732 DEBUG_PAGEALLOC=n、:9735 PAGE_OWNER=n、:9736 PAGE_POISONING=n、:9753 DEBUG_VM=n、:9766 KASAN=n、:9768 KFENCE=n | 未发现7.3误开这些重型检查；KASAN_HW_TAGS还取决于硬件能力，不能仅以5.15配置称其必有每次访问插桩 |
| slab/符号/trace | C5有SLUB_DEBUG，DEBUG_ON=n | C7:9733 SLUB_DEBUG=y、:9734 DEBUG_ON=n；:9672–9685 DWARF/BTF，:9881 FUNCTION_TRACER | SLUB编译能力不等于默认poison/redzone；需看slub_debug cmdline。调试符号本身不逐次扫描拷贝，BTF须保留匹配模块；ftrace须看current_tracer/trace开关，不盲删诊断能力 |
| usercopy加固 | C5:8189 HARDENED_USERCOPY=y | C7:9228 n | K5/K7 include/linux/uaccess.h:102/104、:136/144调用check_object_size；7.3没有新增该加固成本。正式7.3当前基线已关闭，不应为性能再减弱PAN等安全机制 |
| CPU频率 | C5:591编译默认schedutil；实测实际performance | C7:649默认performance | r13两簇2208/2016MHz、probe CPU2、worker CPU1，全部采样一致；不能再用默认governor不同解释该受控窗口。未记录的idle唤醒、调度等待仍可能影响阶段wall |
| THP/folio/mTHP | C5:914–916 anon madvise；K5 mm/shmem.c:475默认SHMEM_HUGE_NEVER | C7:1080–1091 anon always、shmem/tmpfs huge默认never；K7 mm/shmem.c:1942起按order分配folio，:1988 mem_cgroup_charge，:2524有mTHP统计 | 默认tmpfs均非大页，不能只看到THP_ALWAYS就说tmpfs每次2MiB清零。匿名SDK堆可能不同；运行时mTHP各尺寸enabled、挂载huge=与shmem_enabled可覆盖默认。微基准并列default/nohuge，不能以folio名变化直接推导耗时 |
| memcg/清零/文件写 | 两边MEMCG=y；K5 mm/shmem.c:719 charge、:2003 clear_highpage；mm/filemap.c:3797 generic_perform_write | K7 mm/shmem.c:1988 charge、:2581 clear_highpage、:3245/3283 write_begin/end；mm/filemap.c:4346/4392 copy_folio_from_iter_atomic | 记账、锁、页分配、尾部清零及用户拷贝共同构成fresh write。不能删必要清零或记账。对比fresh/overwrite/read能分离一部分成本；还需cgroup、memory事件、vmstat增量 |
| 迁移/NUMA/zswap | C5:903/905 compaction/migration=y，ZRAM=m | C7:464 NUMA=y、:177 NUMA_BALANCING=n、:1062/1065–1066 compaction/NUMA migration/migration=y；:1010–1011 zswap默认on | 没有自动NUMA平衡扫描；T7不能因通用NUMA配置就当多节点平台。zswap通常在有swap且发生换出时起作用（K7 mm/zswap.c:90、:982起），不是每次匿名写必经压缩。r13未测交换增量，不能宣布在压缩所有输出；工具保留前后vmstat/swaps，后续看pswp*/pgscan/compact/pgmigrate |

### memcpy、uaccess与PAN/MTE/UAO

用户态memcpy来自同rootfs libc，同二进制仍须记录libc SHA与CPU feature/HWCAP，
不能将用户态libc memcpy与内核copy_from_user混为一条路径。
K5 arch/arm64/lib/copy_from_user.S:57–63、K7:64–82都包含copy_template.S；
本轮diff显示该模板主体相同，K7仅增加:44–53的ARM64_HAS_MOPS运行时alternative分支。
没有发现新版彻底更换整段普通拷贝循环的证据，编译器支持MOPS也不代表本CPU执行MOPS。
copy_to_user同样由模板构成（K5 :56、K7 :63），新异常恢复路径不等于正常每字节成本。

两边MTE/EPAN编译开启；C5:435 SW_TTBR0_PAN=y，C7:490 n。
K5 arch/arm64/include/asm/uaccess.h:153–219有PAN/TCO路径，K7:127–145按能力切换硬件PAN，
7.3的ldtr/sttr访问在该文件:239/337。能力alternative和硬件支持决定实际执行，
不能把MTE=y算成无条件逐访问标签开销，也没有证据表明UAO额外切换造成3ms。
**不建议关闭PAN/MTE/访问边界检查来追逐未定位的差距。**

### DDR/DMC：已有读回缺口，不等于已证明降频

V drivers/memory_debug/ddr_tool/ddr_bandwidth.c:871–919 freq_show调用get_freq，
ddr_band_op_t7.c:137–144的t7_get_dmc_freq_quick直接读PLL状态再解码（:385注册）。
这是频率/带宽观测驱动，不是标准devfreq governor；freq_store:859–867的pxp_debug_freq只是覆盖观测值，禁止当锁频。
V drivers/thermal/ddr_cooling.c:73–97是按thermal state写配置寄存器，不能等同通用DDR频率OPP管理。
C5:7502起AMLOGIC_DDR_TOOL/BANDWIDTH/T7、:7517起DMC_MONITOR主要提供厂商观测/控制能力。

U board/khadas/kvim4/firmware/timing.c:41说明多个pstate表示动态频率，:262–270启用的
LPDDR4项DRAMFreq={2016,0,0,0}；:476另一配置也只有首档。它证明有boot固件初始化设置，
不是当前板子BL2训练参数的直接证明；该2016与板上PLL口1008MHz的数值不能不核对定义就当两档频点。
两个内核共用未刷写的bootloader，故“Linux缺调频驱动必然降低DDR到默认低频”目前无证据。
同固件启动也不能证明运行中DDR绝对不变，secure firmware/thermal影响仍需读回。

7.3 T7 dtsi未提供可用DMC devfreq节点；r13仅GPU devfreq，候选中没有厂商aml_ddr读回。
已知t7_sys_ddr/ddr_pll_osc是时钟树名称，不是已验证的内存PLL测频口。
本工具只读已有aml_ddr/freq及已命名DDR/DMC devfreq；缺失时null/空对象，不编造频率。
后续若需新增7.3只读DDR provider，须先核实PLL资源/安全固件访问合同，独立审查；本轮不添加裸MMIO探针。

## 建议与需批准项

1. **优先建议独立锁调试关闭候选**：DEBUG_LOCK_ALLOC、DEBUG_RT_MUTEXES、DEBUG_SPINLOCK、
   DEBUG_MUTEXES、DEBUG_WW_MUTEX_SLOWPATH、DEBUG_RWSEMS设n，让olddefconfig重算LOCKDEP依赖。
   与正式uhd1也存在的同类配置区分，不能称NPU补丁引入。保留单独调试构建。
   这减少错误锁使用/生命周期问题的早期检测，不是关闭内存访问隔离；仍属于诊断覆盖取舍，
   **需用户批准后才做新候选A/B，不修改本轮正式配置**，效果尚未测定。
2. THP改madvise、zswap关闭、NUMA移除仅列实验假设；需要对应fault/交换/迁移证据及用户批准，
   不捆绑到锁调试实验。清零、安全边界和加固不作性能删减；符号/BTF也不因体积而删。
3. 首窗沿用原uhd2，只定位通用路径；如果fresh慢、rewrite/read相近，优先查分配/记账/锁；
   全部拷贝慢再查CPU/DDR/用户访问；匿名default/nohuge差异大再查THP。没有证据不改汇编。

## 独立微基准：同一二进制、每次≤3分钟

入口`tools/memory-bench.c`与`tools/memory-bench.py`，不调用NPU/视频、无SSH/部署或频率写入。
在ARM64 VM编译一次，记录二进制与libc SHA；两边只复制同一个文件，不各自重编译：

```sh
cc -O2 -Wall -Wextra -Werror tools/memory-bench.c -o memory-bench
timeout -k 3 180 python3 tools/memory-bench.py --binary ./memory-bench \
  --output NEW_RESULT --tmpfs /dev/shm --cpu 2 --repeats 5
```

该命令是下一窗口板上操作示例，本轮只在VM执行。板上调用者必须先持板锁/两个媒体锁并确认没有其他负载。
工具固定自己的CPU亲和并恢复，不控制频点；窗口操作者沿用已验证performance/min/max固定与恢复流程。
每组原始JSONL记录ns、逻辑传输bytes、minor/major faults、主动/被动切换；不能把逻辑bytes当实际DDR总线流量。

- memcpy hot从4KiB/64KiB/1MiB/4.8384MB/16MiB/64MiB跨尺寸，重复目标64MiB，预触页，
  volatile函数指针调用libc避免编译器消掉；小尺寸主要反映热缓存，不宣称DRAM带宽。
- fresh tmpfs pwrite、同文件rewrite、resident tmpfs pread到已触页缓冲、fwrite+fclose fresh分别测。
  pread覆盖内核到用户copy路径，但含VFS/页缓存查找，不是裸copy_to_user函数计时。
  fd创建/清理在直接syscall计时外；fwrite组含close/stdio flush，无fsync或持久化承诺。
- 64MiB匿名mmap逐系统页首次触碰与再次触碰，default与MADV_NOHUGEPAGE各一组。
  first-touch吞吐是映射覆盖字节/耗时，另报minflt/秒；不能将每页写1字节等同连续memset带宽。
- C alarm150秒，Python170秒杀自有进程组、173秒wait上限；临时文件放私有目录并收尾，
  至少256MiB tmpfs余量，峰值约256MiB匿名缓冲加16MiB文件。外层180秒为最后边界。
  失败保留输出/状态，输出目录已存在即拒绝。若内核D状态无法回收，停止窗口并报告。
- 1Hz采CPU频率/策略、温度类型、具名DDR读回；记录THP/mTHP、挂载、cmdline、cgroup、
  前后meminfo/vmstat/swaps。采样器恢复到原CPU集合，子进程固定CPU2；轮询调度有共同扰动。
  五次原始重复全保留、首组单列，不在同boot内做跨启动资格CI。

## 下一窗口≤20分钟

0–4分钟：5.15/服务/锁核对、备份启动/运行时文件；核对两kernel config、同二进制/libc SHA，
保存swap/THP/频率/温度和无视频消费者状态。禁止drop_caches、盲读MMIO或写电压/PWM。
4–7分钟A跑微基准（≤180秒），保存DDR 1008MHz口的同期读回，不写debug freq。
7–11分钟RAM一次性启动原uhd2，默认5.15不变；检查CPU条件与可用DDR/DMC devfreq只读节点。
11–14分钟B同命令；若DDR真实读回不可得，该项明确未补齐，不用门控/晶振名称替代，不声称同DDR条件。
14–18分钟回5.15，恢复频率/亲和，核对12文件哈希/权限、服务/UDC，释放锁；留2分钟余量。
不用HID、声音或ptrace视频进程，不在窗口改配置/驱动，不与编译并行。

离线验证：ARM64 VM实际编译并运行全部30种尺寸/阶段组合，校验读回、nohuge首次fault边界、
重复触碰fault减少、亲和恢复及拒绝覆盖；五次重复完整跑通，未运行板上微基准。
主仓unittest 313项、8跳过，OK（Linux执行测试在Mac跳过，另在ARM64 VM实际通过）；
`git diff --check`通过。本轮未修改任何正式config或构建新内核候选。
