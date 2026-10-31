# Bifrost同块回跳修复与GPU上电轮询候选

2026-10-30，承接[完整系列失败窗口](bringup/2026-10-30-gpu-loop-window.md)。
本轮仅离线：未访问板子，未操作NPU文件/worktree，未push。方针**用户已于 2026-10-30 确认**。
默认保留仅GCM；修复系列与内核快轮询均须重新过硬件正确性门禁，不能引用失败系列的FPS。

后续[修复系列实测](bringup/2026-10-30-gpu-repair-window.md)：原循环/展开全帧与原版逐字节一致，
GPU timeout/fault零增量；完整系列原循环339.7fps，对照GCM272.4、厂商614.1fps，仍未追平。
快轮询冷首发4.91ms（旧boost核4.68ms），无明确收益；独立trace的shader等待约2.14ms，
超过10µs快路径预算。该内核候选不推广，不继续延长忙等；下文保留离线设计与产物证据。

## 故障隔离：0005暴露同块分支偏移错误

M为Mesa26.2.6，固定源码SHA与builder见[运行时记录](bringup/2026-10-30-gpu-runtime.md)。
在原版、0003、0003＋0004、0003＋0004＋0005之间编译同一原循环，检查最终ISA而非只看CFG。

| 阶段 | 热循环最终分支 | 离线结论 |
|---|---|---|
| 仅0003 GCM | clause_8条件跳到独立回跳块，后者JUMP clause_8 | 回跳目标正确；已有板测像素证据 |
| 加0004跳转/空块清理 | clause_8条件退出到clause_14；fallthrough clause_12再JUMP clause_8 | 没有出现本次目标编码错误；不等于0004已独立通过硬件收敛验证 |
| 再加0005一致回边 | clause_8条件回跳竟编码为clause_0 | 重进前置块并重置计数器，无法达到128次退出条件；与反复timeout及全零输出相符 |
| 再加0006偏移修复 | clause_8条件回跳clause_8 | 保留计数器递增，目标正确；仍待硬件验证 |

根因是M `src/panfrost/compiler/bifrost/bi_layout.c:71`的`bi_block_offset`：
后向分支先减去当前块中起点之前的clause，然后遍历更早的块；
目标恰好是当前块时没有停止，反而把所有前置块都扣进偏移。
0005使条件回边与loop header归为同块（`bi_opt_control_flow.c:135–141`），触发这个潜伏的layout错误。
本次确定的错误是**分支目标编码**；没有据此证明所有reconvergence/scoreboard风险都已排除。

[0006](../packaging/gpu/patches/0006-bifrost-self-branch-offset.patch)在`bi_layout.c:116`同块时立即返回，
不修改条件方向、clause终止位、活动线程掩码或现有寄存器编码。
解码器对零偏移显示“likely an infinite loop”，这是只看偏移的提示；本循环有递增计数和条件退出，不能据此判死循环。

新增Mesa自身`Layout.SelfBranchExcludesPrecedingBlocks`用例
（`src/panfrost/compiler/bifrost/test/test-optimizer.cpp:12`）：
有非空前置块、同块两个clause及后继块，分别检查同块头部0、同块后部-2、跨块后向-5、前向+3个quadword。
真实旧函数失败两项（-3替代0、-5替代-2），修复后通过。
此前MIR测试只检查CFG目标指针，没有经过最终layout偏移计算，故漏掉此错。

上游化次序：先独立提交不依赖GPU型号/探针的layout修复与通用单元测试；
0005的uniform回边变换另行审查、硬件验证，不能因偏移已修正就绕过原有收敛保护。
0006在本仓补丁序列中还给已有测试的EXPECT_EQ条件加花括号，避免gtest宏产生dangling-else告警。

## 剩余GLES差距：逐tuple热区

同窗硬件参考：仅GCM原循环273.2fps，显式展开约583fps，厂商原循环612.7fps。
下表是GCM首个片段变体的clause_8；一tuple有FMA和ADD两个槽，表中省略无用目的值。

| tuple | FMA槽 | ADD槽 | 含义 |
|---|---|---|---|
| 0 | FMA r1 × 1.01 ＋ r2 | NOP | r2为已外提的p.y × .01，r1为循环携带依赖 |
| 1 | FROUND.rtn 上一结果 | IADD counter ＋ 1 | fract取整与计数器已配对 |
| 2 | FADD 结果减取整值 | ICMP counter ≥ 128 | fract收尾与比较已配对 |
| 3 | NOP | BRANCHZ | 条件退出/继续 |
| 独立回跳clause | NOP | JUMP loop header | GCM每次继续多一个tuple与clause边界 |

原版未外提时热区约6tuple/次；仅GCM约5，修复布局约4；显式展开整个shader268tuple，
平均约2.09tuple/次（含首尾）。修复布局的动态热区约512tuple，仍高于展开版，不能承诺完全追平。
`bi_schedule.c:294–303`让块内指令依赖终端分支，`:1993`按block调度，
`:2018`起处理flow control；独立回跳不能自然与上一块算术配对。
下一项最有依据的改动是**修正同块编码后，验证受保护的条件直接回边**，减少每次迭代独立JUMP；
本轮不再叠加未建立正确性证明的跨迭代调度或扩大uniform guard。

clause头部/常量是打包格式的一部分，不能每遇一个头就硬加一条指令或一个周期。
`bi_layout.c:32–65`的打包模型中4tuple占3个指令quadword，独立1tuple JUMP至少再占1个，
未免费打包的常量还要额外quadword；删独立回跳确实减少热路径clause和取指内容。
真实头部处理、分支重定向/取指等待仍没有独立计数，静态压缩字数不能换算其运行延迟。

限制与排除项：

- FMA→FROUND→FADD是真实循环携带依赖；counter/compare已占空闲ADD槽，不能把删除它们等同减少两个tuple。
- 热区没有纹理、load/store消息；ATEST/BLEND在退出尾部。`bi_scoreboard.c:30`起的消息等待不能直接解释每次迭代差距。
- 7个工作寄存器、零spill/fill；展开版6个，同低于v7的32寄存器满线程门槛（`bifrost_compile.c:3965`），没有该门槛导致的占用率断崖证据。
- NOP不证明寄存器端口冲突；尚无硬件计数把端口、依赖等待、分支延迟、clause切换分别量化。
- `bifrost_compile.c:3945–3979`以静态arith tuple/24等估算吞吐，不乘循环次数，也没有真实分支/每clause头部延迟模型；不能用0.667静态cycles预测FPS。

仅检索已有GPU日志/构建材料，没有找到厂商shader二进制、shader cache/program binary、malioc输出。
已有厂商API/timing/像素日志不包含ISA，本轮不访问板子，也不执行猜测的libmali私有接口。
因此无法离线给厂商逐指令对照，不能反推其是否展开或具体调度。

## Mesa离线结果与复现

新卷`vim4-gpu-loop3`，旧卷只读；全部编译/测试/打包容器`--network none`。
复现用[build.sh](../packaging/gpu/build.sh)的`GPU_VARIANT=loop-repair`，明确应用0003–0006；
默认`loop-codegen`仍只应用0003，实验展开默认关闭，失败的`loop-layout`仅供复现。

| 固定shader-db 11,123共同变体 / 3,744文件 | 原26.2.6 | repair3 |
|---|---:|---:|
| 代码bytes | 6,820,512 | 6,784,144（-0.533%） |
| 指令 | 567,027 | 565,518 |
| 静态cycles总和 | 41,848.333 | 41,820.125 |
| loop数 | 178 | 178 |
| spill / fill | 20 / 41 | 20 / 41 |
| 最大工作寄存器 | 61 | 61 |

223变体统计改变，10项寄存器增加；共同键无缺失。修复只改变分支立即数，
这些静态数与失败完整系列相同，直接说明**静态统计相同不代表代码正确**。
探针首片段25指令/18tuple/5clause/368bytes/7寄存器/1loop/零spill；
另一blend变体仍62指令/13clause，未放宽保护条件以追逐探针成绩。
noop仅证明G52编译路径与目标编码；其黑像素退出1是预期，不是硬件像素或性能通过。

最终Meson测试、ELF闭包/ICD/manifest及归档SHA见本页末尾验证表。
前缀`/opt/vim4-mesa-26.2.6-repair3`，不替换系统Mesa；每进程隔离沿用[gpu-compare.py](../tools/gpu-compare.py)。
实验展开的全库+3.74%、局部最高9.5倍代码体积代价仍见[语料分析](gpu-loop-codegen.md)。

## 冷恢复：先验证睡眠轮询，而非提前写电压/频率

K为VM `~/src/linux-7.3-gpu`，分支`vim4-gpu-panfrost`。
板测runtime resume约2.98ms，内部power_on约2.42ms发生在boost之前；
soft reset约3.7µs是另外的端点。已有trace未细分power_on内部阶段，不能分摊2.42ms。

| 阶段 | 源码证据与边界 |
|---|---|
| 外部电源域 | `drivers/pmdomain/amlogic/meson-secure-pwrc.c:97`经SMC；不在本次power_on函数体内，不能把该2.42ms全归SMC |
| runtime恢复/复位 | `drivers/gpu/drm/panfrost/panfrost_device.c:419–456`；时钟/复位的GPU_PM_RT条件分支不适用于当前amlogic标志，genpd是另一层 |
| quirks与mask | `panfrost_gpu.c:475–476`初始化平台quirks/选择现有core mask；现有函数trace没有单独计时 |
| L2→shader→tiler | 原`panfrost_gpu.c:453–494`依次写PWRON并按10µs睡眠间隔等待READY；超时预算分别20/20/1ms；修复后位置`:478–493` |
| 睡眠等待 | `include/linux/iopoll.h:46–65`调用usleep_range；配置HIGH_RES_TIMERS=y、HZ=250、PREEMPT=y。可能存在调度返回成本，但不能因HZ=250就声称一次固定睡4ms |

内核提交`4ccae3570a97e`增加`panfrost_gpu_wait_ready`（`panfrost_gpu.c:452–468`）：
每阶段先1µs间隔、名义最多10µs原子轮询，未就绪再回退原10µs睡眠轮询，剩余预算扣除10µs。
不改L2→shader→tiler顺序、READY精确mask、寄存器值、OPP、电压、50ms autosuspend或QoS策略。
三个阶段快路径名义忙等总预算30µs，MMIO/执行开销不包含在该名义数字内；不做20ms长忙等。
收益取决于硬件是否在快阶段就绪，**未证明可以消除2.42ms**。
该候选沿用通用iopoll接口而不添加T7特定寄存器/DT参数；上游提交仍需提供实际阶段时延与CPU代价，
若READY主要晚于10µs，则应撤回无收益的忙等，而非继续延长忙等追分。

比较本地同版本上游：Panthor `drivers/gpu/drm/panthor/panthor_gpu.c:257–275`先等PWRTRANS、发上电、再等READY，
间隔100µs；Lima `drivers/gpu/drm/lima/lima_pmu.c:20–24`按100µs/100ms等待PMU命令，`:73`起提醒过低硬件SW_DELAY会不稳定。
两者硬件/协议不同，不据此并行T7的L2/shader上电或猜测延时寄存器。
调长autosuspend可减少恢复次数但延长上电驻留，功耗代价尚未测，本候选不混入该改动。

完整Image/dtbs/modules、Panfrost W=1 C=2 sparse通过；仅保留既有vdso `__kernel_getrandom`声明警告。
strict checkpatch为0 error/warning/check（新增文件通用FILE_PATH_CHANGES经审查忽略，SPDX检查正常执行）。
新增`tools/testing/panfrost/test_ready.py`编译真实helper，覆盖快成功、慢回退、超时、额外mask位拒绝和剩余预算；
既有boost/PM夹具也通过。夹具不模拟MMIO时序或调度器，不代替上电板测。无DT改动，未重跑dtbs_check。
主仓kernel-edge配置不变。Image与原核一致是因Panfrost为模块；下次仍用同构建完整模块集，禁止只凭release混装。

## 下一独占窗口：测量≤20分钟

入场/启动/回退另计；先核对锁、默认5.15、服务/UDC和启动文件SHA。
所有编译预先结束，只通过U-Boot RAM选择候选；不HID、不音频、不ptrace视频进程，不写PWM/电压。
锁频只选现有OPP并保存恢复值，PanVK开关只给测试进程。所有子项timeout，单项小于10分钟。

| 项目 | 预算 | 硬门禁与端点 |
|---|---:|---|
| GCM/repair3短正确性 | 3分钟 | 原循环/展开各先跑0.01秒、外层10秒超时；GPU_DUMP_PATH保存完整512×512 RGBA，与对应着色器变体的原版逐字节比较，且GPU timeout/MMU fault/故障恢复reset新增计数为0（正常PM soft reset单列）。异常立即否决，不跑FPS；正常重启恢复后再继续 |
| 原循环/展开三轮交错 | 5分钟 | 仅门禁通过后，原版/GCM/repair3相同surface，2秒预热＋10秒稳态、每进程25秒超时；GPU timer/disjoint、CPU、温度、trans_stat；厂商612.7fps仅历史参考 |
| 原核/快轮询核冷暖Vulkan | 5分钟 | 各三轮闲1秒后冷提交＋暖20次，单组90秒超时；独立短function_graph trace标注L2/shader/tiler等待helper和power_on/soft_reset/resume，不与普通计时混测；函数内联不可见时注明未分段，不扩大到全系统跟踪；记录频率及现有max/thermal限制 |
| HDMI＋Wave5回归 | 5分钟 | 沿用已有4K60输入/编码工具，无GPU/有GPU各60秒，核对帧/PTS/延迟、CMA、完整像素和GPU错误；不宣称HDR已验收 |
| 空闲代价/设置恢复 | 2分钟 | CPU/IRQ/温度/驻留为功耗代理，无功耗计不报瓦数；恢复sysfs，回5.15，核对服务/UDC/启动文件SHA |

任何全帧不一致、进程超时、GPU错误增量非零均停止候选验收；不以中心像素非零代替全帧正确性。
若没有硬件计数或完整trace，明确保留原因未分解，不能用静态tuple比值承诺追平。

## 最终离线产物

验证材料保留于本机`build/gpu-loop3/`、Docker卷`vim4-gpu-loop3:/output`，内核日志VM `~/build/gpu-fast-ready-*.log`。
干净官方源码依次应用0003–0006后，六个改动文件与实编源码逐文件一致。
恢复旧函数作失败回归后强制删除全部Panfrost compiler对象并重编，避免还原文件时间戳导致旧对象被误复用；
最终再次运行layout测试、全Meson测试、ISA探针和完整语料，最终语料报告与上表逐字节一致。
本轮未安装运行时到板子。

| 检查/产物 | 最终结果 |
|---|---|
| Meson | 51组通过、6组跳过、0失败；layout旧函数两断言失败、新函数通过 |
| 运行时闭包 | 51个ELF、381个manifest文件；私有ICD/相对RPATH/依赖检查通过，无builder动态依赖路径 |
| Mesa归档 | `build/gpu-loop3/mesa-26.2.6-repair3-arm64.tar.xz` |
| 归档SHA256 | `d8d76d3646cbfd7e3b14ec561668efb2df263bb814b25e2ef71749db06223c15` |
| 内核分支 | `vim4-gpu-panfrost@4ccae3570a97e15190126597e2050e400f770433` |
| Image SHA256 | `5b850638dfa74de0233431a14ddd547e39caec895d1451620ac9c8d389ee79f7` |
| panfrost.ko SHA256 | `1f00b9e891b58a5797781fae59782ccaf7b914cf3f08ca39d12a48c397c91edf` |
| 主仓 | 全量unittest 311项、跳过7项、无失败；shell语法与diff检查通过 |
