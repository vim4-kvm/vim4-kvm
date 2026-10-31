# 保留循环的Mesa候选与冷恢复boost

2026-10-30，承接[循环分析](gpu-loop-codegen.md)与[板测975d8ae](bringup/2026-10-30-gpu-candidate-window.md)。
本轮离线，未访问板子，未动NPU/uhd2文件或工作树，未push。
方针**用户已于 2026-10-30 确认**。候选没有硬件性能/正确性验收，默认部署锁不变。

后续[上板结果](bringup/2026-10-30-gpu-loop-window.md)：**完整系列被硬件否决**，中心像素错误且反复GPU timeout，
不得部署或引用其FPS，0004/0005尚未分别归因。仅GCM约273.2fps、全帧与原版相同，仍未追平厂商612.7fps。
QoS候选冷首发约4.90ms、暖2.01ms，夹限通过；power_on约2.42ms在boost之前，仍有优化空间。
以下保留离线统计，不能解释成该失败系列的实际运行收益。
实测内核e992有workqueue弃用告警，已离线以88b3d1626e2ae修正；新模块未上板，不复用下方旧模块SHA作其证明。

最新[离线故障隔离与修复](gpu-loop-repair.md)：0005暴露`bi_block_offset`同块回跳偏移错误，
条件回边误指前置clause_0，重置循环计数。新增0006与旧函数失败/新函数通过的layout单元测试；
`loop-repair`仍须全帧像素相等、GPU timeout增量为0后再测性能，默认只GCM不变。
冷恢复另有4ccae3570a97e短忙等后回退睡眠的候选，不把离线构建当作2.42ms已改善。

## Mesa三个独立补丁

固定26.2.6及sealed builder与[上轮输入](gpu-performance-candidates.md)相同；新卷`vim4-gpu-loop2`，旧卷不改。
展开的0001/0002未应用；仍使用原驱动32次展开阈值，128次探针保持真实循环。

| 补丁 | 内容与边界 |
|---|---|
| [0003](../packaging/gpu/patches/0003-bifrost-loop-invariants.patch) | Bifrost v6/v7在late algebraic后、局部移动和指令选择前调用现有`nir_opt_gcm(false,false)`。不做value numbering、不启用texture跨循环hoist，沿用GCM的内存/推测执行限制 |
| [0004](../packaging/gpu/patches/0004-bifrost-jump-cleanup.patch) | 控制流清理识别`BI_OPCODE_JUMP`，不只识别`bi_is_branch`；清理不改变条件目标的空前向fallthrough。处理空前驱指令列表，避免读取list哨兵；仍保留原后向reconvergence保护 |
| [0005](../packaging/gpu/patches/0005-bifrost-uniform-backedges.patch) | NIR divergence分析后，仅v6/v7、无discard、无divergent loop且所有if条件一致的整个shader允许后向线程化；其余保持保护。新增MIR用例覆盖含空块的回边、允许/禁止两种条件。此项是实验，未声称完成硬件reconvergence证明或上游审阅 |

定位结果：原版进入指令选择前NIR的`fmul p.y,0.01`就在loop内；0003后在loop前，
后端也只在前置块生成一次FMA，因此本例是NIR放置问题，而非后端把已外提的乘法重新物化。
0004进一步发现原`bi_is_branch(JUMP)`为false，解释了此前仅盯住后向保护仍不足以解释的保留块。
没有另加局部调度器改动：先测新的block/clause形状，避免混入第三种归因。

默认builder改为`GPU_VARIANT=loop-codegen`（只0003）；`baseline`显式保留原版，
`loop-layout`显式应用0003＋0004＋0005，`bounded-unroll`才应用实验展开0001/0002。
`loop-jumps`用于只应用0003＋0004的独立对照。
不再用patch目录通配符应用所有补丁。展开默认关闭，原先全库+3.74%、局部9.5倍体积代价继续有效。

## 离线验证与统计

各阶段Meson测试51组通过、6组跳过、无失败；0005的MIR回边测试通过。
固定shader-db语料，11123个共同变体、3744个有机器码统计的文件；只比较相同路径/阶段/变体键，覆盖一致。
cycles为静态启发式总和，不含动态循环次数，不代表执行时间；寄存器为静态使用数。

| 阶段 | 总bytes | 总指令 | 静态cycles总和 | loop数 | spill/fill | 最大寄存器 |
|---|---:|---:|---:|---:|---:|---:|
| 原版 | 6820512 | 567027 | 41848.333 | 178 | 20/41 | 61 |
| 0003 | 6811312 | 566445 | 41824.375 | 178 | 20/41 | 61 |
| 0003＋0004 | 6788272 | 565647 | 41820.667 | 178 | 20/41 | 61 |
| 0003＋0004＋0005 | 6784144 | 565518 | 41820.125 | 178 | 20/41 | 61 |

0003改变84个变体，10个变体寄存器使用增加，但未新增spill/fill；全库bytes约-0.135%。
0003＋0004和完整系列均改变223个变体；仍有10个寄存器增加、无新增spill/fill。
完整系列全库bytes约-0.533%，保留178个loop；不能用静态cycles的小幅变化预测动态循环收益。
曾检测到复制build缓存后ctx布局不一致导致spill/fill移位，相关结果弃用；
后续强制删除Panfrost compiler对象并重编，才使用最终统计。复现应从固定源码干净构建，避免复制旧对象缓存。

原探针首个片段变体：原版27指令/20tuple/6clause/7寄存器、1循环、零spill；
0003仍27/20，但7clause、432字节（原416），loop热体从5tuple＋回跳1tuple变为4＋1。
不变量外提新增前置clause，不能把“静态总代码没有减少”误判为动态无收益，也不能直接换算FPS。
完整系列首个片段变体25指令/18tuple/5clause/368字节、7寄存器、1循环、零spill，静态cycles0.667；
热循环体为4tuple并直接条件回跳header，去掉独立回跳clause，约512个动态热区tuple（原约768）。
另一blend变体仍62指令/13clause，保守的一致控制流条件没有覆盖所有变体；不放宽guard来追逐探针数字。
所有noop黑像素退出1是预期；不引用模拟器FPS。

## 冷首发：已知路径与未能离线计时的部分

K=VM `~/src/linux-7.3-gpu`。已有同窗数据：自由50/10ms冷首发8.13/8.09ms，固定800MHz约2.82ms；
暖提交分别3.204/2.027/2.003ms。频率干预使冷首发减少约5.3ms，但这是整体干预效果，
**不是精确的内部阶段时长**。上次另一窗口锁频＋PM on冷首发约1.97ms只是单样本参考，不能给PM分摊精确百分比。

| 路径 | 源码证据与判断 |
|---|---|
| 测量边界 | `tools/mali-dma-probe.c:143、165、215`：导入/映射、pipeline创建和命令录制在timer前。不能把这些API全部计入8.1ms；驱动可有首次提交的延迟工作 |
| Mesa首次提交 | Mesa `src/panfrost/vulkan/jm/panvk_vX_gpu_queue.c:33、79、232、307`准备job/依赖/BO并调用PANFROST_SUBMIT；首次上传/内核映射是否仍延迟到submit必须trace验证。warm submit约0.056ms，不能据此推断cold submit和GPU wait各阶段 |
| runtime PM | K:drivers/gpu/drm/panfrost/panfrost_job.c:211在调度提交前`pm_runtime_get_sync`，:220分配MMU AS；驱动恢复含soft reset、L2/core power-on、MMU reset和IRQ恢复（panfrost_device.c:419–456） |
| 域/时钟 | T7 DTS:1090含MALI_TOP genpd；`drivers/pmdomain/amlogic/meson-secure-pwrc.c:97`经SMC开域。amlogic兼容数据没有GPU_PM_RT，不能宣称每次resume都走该标志下的clk_enable/reset分支；genpd恢复仍是另一个层次 |
| 起始频率 | `drivers/devfreq/devfreq.c:385`更新resume_freq，:1184恢复它；它可能已经是空闲降到的250MHz。此前trans_stat证实空闲后从250开始；“保持上次频率”核心已经做了，并不等价于保持最后繁忙频率 |
| 调频延迟 | panfrost_devfreq.c原record_busy只记账；10ms采样能改善连续暖提交，首个任务可能在首轮采样前结束。50ms autosuspend（panfrost_drv.c:995）调整会改变PM往返，却不能单独解决低起始频率 |

未离线获得SMC、clock、PM reset、AS/页表及上传各自的毫秒数，不伪造分解。
下一窗口用具名runtime-PM callback/clock/devfreq事件与自己的submit/wait端点配对，先核对事件是否存在，
过滤GPU设备；trace独立于普通性能采样，不ptrace视频进程或盲读MMIO。

## 内核候选

分支`vim4-gpu-panfrost`提交 **e99220d902834**，基于10ms候选4e239aec051a4。
恢复完成后通过`DEV_PM_QOS_MIN_FREQUENCY`请求最高既有OPP的短时下限，50ms后撤销；
devfreq的QoS notifier同步更新目标，经过`devfreq_get_freq_range`的用户/thermal最大频率夹限（devfreq.c:131–160、699）。
不是在job spinlock内切时钟，不新增OPP或电压；没有永久保持最高频率。
空闲最后频率保存、调长autosuspend和异步提交boost均未混入本候选。

初始化注册request；suspend先同步取消expiry并清除floor，再挂起devfreq；fini先取消再移除request。
设备PM串行化resume/suspend，remove必须遵循既有停作业/停PM生命周期。
新增`tools/testing/panfrost/test_boost.py`用实际函数编译C夹具，覆盖无devfreq、恢复、到期、挂起取消和退出取消；
它不是内核workqueue并发或硬件电源恢复的证明。50ms boost的功耗、热上限实际夹限与异常恢复仍待板测。

完整Image/dtbs/modules、W=1/sparse GPU目录、原PM恢复夹具、新boost夹具通过。
strict checkpatch代码检查0 error/warning/check；新增文件的通用FILE_PATH_CHANGES提示经审查，
已将测试目录登记MAINTAINERS，仅该提示在最终检查中忽略。无DT变更，不重跑dtbs_check。
Image SHA `5b850638dfa74de0233431a14ddd547e39caec895d1451620ac9c8d389ee79f7`；
VIM4 DTB `9e78f8657bfd2f57029c09f3d43e6ec48ecb55cfcfa81e7e74927beb63fd4308`；
panfrost.ko `f32f23a6a6d980485fd68a6f51399a1130d708c7669ea3baf8d6e482c234468a`。
输出`~/build/gpu-panfrost-20261030`、日志`~/build/gpu-boost-*.log`；不改主仓kernel-edge配置。

## 下一独占窗口：测量不超过20分钟

另计5.15入场确认、锁、两个候选启动/回退。所有构建提前完成，5.15默认不变，候选仅U-Boot RAM选择。
须暂存完整匹配Image/DTB/模块与恢复方案，**不能把本轮模块直接混入保留内核**。

| 项目 | 预算 | 端点与判定 |
|---|---:|---|
| 原版/GCM/完整布局，原循环交错三轮 | 5分钟 | 同一512×512 GBM/FBO，2秒预热＋10秒稳态，每项25秒超时；附一次显式展开对照、独立5秒timer且disjoint=0；新布局先验像素，再引用FPS |
| 原10ms核与boost核冷/暖Vulkan | 5分钟 | 各3轮，进程前空闲1秒；首提交、3预热、20暖样本，90秒外层超时。另测PM on及现有400MHz max，证明boost不能越过上限；结束恢复全部sysfs |
| GPU PM/clock事件独立诊断 | 2分钟 | 自有负载、具名事件、短trace，关联resume→首job→完成；没有事件就明确缺项，不扫寄存器 |
| HDMI＋Wave5与新Mesa并行 | 5分钟 | 既有4K60 NV12→H.264基准无GPU/有GPU各60秒，计帧/PTS/时延/CMA及GPU错误；不HID、不音频、不ptrace，不宣称HDR已验收 |
| boost空闲代价和设置恢复 | 3分钟 | 空闲→burst→空闲，温度/驻留/CPU/TIMER代理；核对floor到期不常驻、服务与UDC、启动文件SHA，回5.15 |

独立材料与日志在本机`build/gpu-loop2/`及Docker卷`vim4-gpu-loop2:/output`。
默认GCM归档`mesa-26.2.6-loop2-arm64.tar.xz` SHA
`35f161ce3544ebbd11fcf9226929e9688d8388f38c795b74491ec463cd415cab`；私有前缀`/opt/vim4-mesa-26.2.6-loop2`。
ELF依赖闭包、ICD私有前缀及manifest检查通过，未安装到板子。
实验布局归档`mesa-26.2.6-layout2-arm64.tar.xz` SHA
`42c9c8d2108b587f037d280617b05ab5c1c4f8999f3a0a0455a393b2321781e7`，
前缀`/opt/vim4-mesa-26.2.6-layout2`，同样通过ELF/ICD/manifest检查。
最后一次打包前重跑完整语料，汇总与上表完全一致；干净源码应用0003–0005后与实编源码逐文件一致。
主仓unittest：311项、7项跳过、无失败；未把尚未运行的板端项目标为通过。
