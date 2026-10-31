# 2026-10-30：保留循环候选、正确性与冷恢复实测

结论：仅GCM原循环约273.2fps，较原版234.8提升16.4%，仍远低于同窗厂商612.7fps。
**完整系列失败**：中心RGBA全零、连续GPU调度timeout，不能引用其FPS或部署0004/0005组合。
GCM全帧与原版逐字节一致。QoS恢复boost把冷首发约8.12降至4.90ms，暖提交约2.01ms；
400MHz用户上限和cooling state 4均能夹限。独立trace定位power-on约2.42ms，仍是后续重点。
方针**用户已于 2026-10-30 确认**，本轮未push。

## 入场、候选与约束

入场5.15.137-vim4kvm-hdrdual6，One-KVM/HDMI/manager active，UDC configured；
Mac按board→heavy持有两把lockf锁覆盖所有板端操作。VM进程快照未见编译；NPU按用户说明只离线分析，未动其文件/工作树。
工具准备、ARM64 Werror编译、模块打包均在首项测量前完成；板测期间无本任务并行编译。
不发HID（被控机Mac mini M6）、不测声音、不ptrace，不写PWM/电压，不人为加热。
所有负载有25/90秒等单项超时；遇完整系列失败即停止，不为凑足三轮继续已知错误负载。

第一阶段沿用保留213f2715内核/匹配模块、此前GPU cooling DT副本；polling_interval临时10ms，结束恢复50ms。
第二阶段内核`vim4-gpu-panfrost@e99220d902834`，Image build ID
`a894778bb3020cccc21d8b8e41fd4de423a8f3ed`，包含10ms及50ms QoS恢复floor。
同次2337模块经modules_install剥离debug并压缩到独立目录，不与保留模块混装。
静态PID1在systemd前校验release/build ID，以只读bind mount挂载完整模块；串口确认matching modules，findmnt确认ro。
复用已验证GPU cooling DT副本保留HDMI/MAC配置，未直接使用未经板型校准的裸构建DT。

候选位于`/var/lib/vim4-kvm/display-m1/a894778bb3020cccc21d8b8e41fd4de423a8f3ed`，
通过U-Boot RAM `sysboot mmc 1:2`选择，没有saveenv；重启自动回5.15。
kernel暂存归档SHA `4f2e410ef46796b6567f8e7dbd16d33c20753615e1deafcda8240d7758e0a9db`，传输前后相同。

Mesa26.2.6原版、仅GCM(loop2)、完整系列(layout2)私有前缀并存，后两者逐文件manifest零不匹配，
归档哈希与[离线候选](../gpu-loop-candidates.md)一致。未替换系统库或全局ICD，实验PanVK仅注入测试进程。
新探针SHA `72caf198683a9cd45966af64a07fa4674727ce747a31b4bee3fda7aee0c391e4`，三栈和厂商均用同一二进制。

## GLES配对与完整系列失败

512×512 GBM/FBO、RGBA8、2秒预热＋10秒稳态，每帧draw＋glFinish，无swap/vsync，回读不计FPS。
厂商先同窗三轮；七系manager停止、profiling=0，CPU performance，其余服务保持。
每轮原版loop/unroll→GCM loop/unroll；完整系列失败后正常重启清除GPU状态，再从头运行三轮有效对照。

| 项目 | 5.15 libmali | 7.3原版Mesa | 7.3仅GCM | 7.3完整系列 |
|---|---:|---:|---:|---|
| 原循环FPS三轮 | 613.226 / 611.548 / 613.316 | 234.588 / 235.028 / 234.667 | 272.251 / 274.110 / 273.258 | 首项失败，停止后续 |
| 原循环平均FPS | 612.697 | 234.761 | 273.207 | 无有效值 |
| 显式展开FPS三轮 | 573.434 / 571.919 / 572.424 | 585.605 / 581.988 / 582.070 | 581.984 / 582.841 / 582.488 | 未运行 |
| 显式展开平均FPS | 572.592 | 583.221 | 582.438 | 不适用 |

GCM仍比厂商原循环低约55.4%，相当于厂商44.6%吞吐，不能宣布不展开追平。
显式展开已接近/超过厂商同展开负载，但不等于厂商原循环、API或产品HDR链已追平。

完整系列首个loop项退出1：中心`0,0,0,0`，原版/GCM/厂商为`179,128,128,255`，gl_error均0。
异常项10.239秒仅20帧、finish占10.236秒；内核连续`gpu sched timeout`、js=0、status=0x8。
**这些数值只描述失败，不是有效性能**。没有因此发送HID、解绑GPU或强制修改电源；正常重启恢复。
不能只凭MIR图、全库统计和host测试证明硬件reconvergence/scoreboard正确；
尚未在硬件分开测试0004与0005，不把失败唯一归于某一个补丁。完整系列并发与后续三轮取消。

## 正确性抽查

新增`GPU_DUMP_PATH`在稳态计时结束后回读完整RGBA，普通性能项不设置它；运行时选择器清除父进程继承值。
每张512×512×4共1048576字节。仅GCM原循环、显式展开分别与原版对应图**逐字节零差异**；
厂商两图亦与Mesa原版相同。六张图共同SHA256：
`c296f080f24ccffb54d835d0643b8ab3a34c1706ee76cb87bb5ac170f226702f`。
没有引入新容差。完整系列已被中心像素差异与GPU timeout否决，未再次运行以取全帧。
未发现已打包/已安装可直接运行的dEQP/piglit入口，本轮未临时构建；不将离线Mesa单元测试当作板端CTS通过。
本抽查是固定合成shader，不覆盖divergent break/continue、嵌套循环、纹理/导数或真实产品色彩。

## 冷首发、暖提交与夹限

两内核使用同一仅GCM私有PanVK和24,883,200字节uint DMA compute，default_cma_region；
每进程前空闲1秒，三个预热样本后20次暖提交，各3进程。全部6,220,800个uint完整校验通过。

| 设置 | 冷首发ms三轮 | 暖均值ms三轮 | 冷/暖总均值ms |
|---|---:|---:|---:|
| 保留内核，临时10ms、无boost | 8.216 / 8.067 / 8.083 | 2.034 / 2.015 / 2.022 | 8.122 / 2.024 |
| QoS boost候选，自由频率 | 5.373 / 4.658 / 4.663 | 2.039 / 1.993 / 1.996 | 4.898 / 2.009 |

冷首发改善约39.7%，仍未到暖2ms。两组为分启动配对，不能将全部差异机械归给单个内部阶段。
候选每轮开始时cur_freq=250MHz、runtime suspended；提交后先进入800MHz，空闲后恢复低档，未永久锁最高频率。

| 约束项 | 冷/暖ms | 驻留与结果 |
|---|---:|---|
| 用户max_freq=400MHz | 6.625 / 3.673 | trans_stat仅400MHz增加100ms，800MHz不增加；通过后恢复800MHz上限 |
| GPU cooling cur_state=4 | 8.230 / 5.667 | 状态前后均4，仅250MHz增加148ms，高档均不增加；随后恢复原状态0 |
| PM control=on | 5.494 / 2.006 | 通过，结束恢复auto；该单样本不能据此给PM计算精确收益 |

cooling测试只写现有cdev状态，使用既有OPP；没有写温度、PWM、regulator或新增电压。
这证明boost服从thermal框架的频率上限，**没有验证95°C实际过温触发过程**。

## 独立PM分阶段trace

独立function_graph实例，限具名GPU函数；不ptrace、不改全局tracer，不与普通性能项混算。
首次实例set_graph_function不可写，未启动负载即退出；改用实例set_ftrace_filter后成功。
实例最终切回nop并删除，未留下全局trace配置修改。

| 候选内核恢复阶段 | 一次独立trace耗时 |
|---|---:|
| panfrost_device_runtime_resume总计 | 2983.792μs |
| GPU soft reset | 3.666μs |
| GPU power_on | 2415.041μs |
| MMU reset | 2.208μs |
| devfreq resume，含QoS更新 | 547.458μs |
| 首次AS获取 | 16.250μs；后续约1.8–2.3μs |

该trace首提交submit/wait=0.101/5.104ms，且带trace开销，不替代上表普通样本。
所选meson_secure_pwrc_on未出现调用，不能由此宣布SMC永远无代价；未取得独立BO/上传阶段trace。
power_on在当前boost之前；后续应评估先完成受上限约束的频率恢复，再power_on的时序和PM正确性，
本轮未临时改顺序上板。不要将不同样本的2.98ms与暖2.0ms当作严格可加分解。

## HDMI＋Wave5与收尾

完整系列已失败，改用仅GCM并发；JSON中的phase名full是脚本阶段标签，实际环境前缀为loop2，不能误写成layout2通过。
暂停One-KVM避免多编码消费者，HDMI保持；3840×2160 NV12→H.264、20Mbps、GOP60，预热120＋测3600帧。
无GPU/仅GCM GPU各60秒，GPU负载75秒，90秒外层超时；全部退出0，GPU像素正确。

| 项目 | 无GPU | 仅GCM GPU并行 |
|---|---:|---:|
| FPS | 59.997957 | 59.997965 |
| source→encoded p99 ms | 19.554 | 19.583 |
| 整机CPU% | 9.786 | 12.037 |
| 收尾CMA KiB | 505200 | 505200 |

各输入/输出均3720帧（含预热）、success=true，taint=0，无新的GPU timeout（候选启动只运行GCM）。
这是no-payload-read计数基准，不验证运动像素、码流、网页延迟或HDR。
候选出现system_wq弃用告警，非本轮旧系列timeout；后续离线改为等价的system_percpu_wq，
提交`88b3d1626e2ae`，完整构建、W=1/sparse、strict checkpatch及两个PM夹具通过，未再上板。
更新后构建目录panfrost.ko SHA为`3454cc0c400b7f984e0d828298b83067e8ba72415df8a4c95099a70a619c8dd2`；
本轮42MB暂存tar仍代表实测e992，不能混入新模块。以上性能结果都属于e99220d902834。

退出候选前polling=10、min/max=250/800MHz、PM auto、profiling=1、cooling=0，服务恢复、UDC configured。
最终5.15.137-vim4kvm-hdrdual6，boot ID `a3da7a6e-6682-4cba-8b09-9a256eb7b76e`；
One-KVM、HDMI、manager均active，UDC configured。六个受保护启动文件哈希与入场完全一致，
临时boot文件已删，两把锁释放，私有候选目录未成为默认入口。

原始JSON、RGBA、串口、内核错误与PM trace在`logs/gpu-loop-window/`，所有运行脚本在`build/gpu-loop-window/`。
registry.bin因权限未复制，测量JSON和负载日志均已保留。后续优先隔离0004/0005的硬件故障，
保留GCM候选与原版对照；在此之前禁止把完整系列的静态收益解释为实际性能收益。
主仓unittest：311项、7项跳过、无失败；探针ARM64 Werror编译与全帧硬件验证通过。
