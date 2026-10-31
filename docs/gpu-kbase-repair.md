# kbase r3 离线语义修复

结论：修正首窗两个初始化WARN的已知原因，并补齐栈timer、OPP引用及fence返回语义。
宿主合同检查、7.3 Werror模块构建、modpost和UK11.39 ABI对照通过；**尚未再次上板**。
本轮只在vim4-kvm-kbase-r2与独立VM候选工作树中工作，不访问板子，不动HDR工作树。
失败原文见[首窗记录](bringup/2026-10-30-kbase-window.md)，方案见[候选维护](gpu-kbase-7x.md)。

## 根因与修复

日志kernel/workqueue.c:5938的调用栈为alloc_workqueue→kbase_mmu_as_init→
kbase_device_misc_init→kbase_platform_device_probe。旧DDK为mali_mmu队列传flags=0；
7.3要求显式WQ_PERCPU或WQ_UNBOUND，否则WARN并补PERCPU。新增第五块
[运行时API补丁](../packaging/kbase/0005-runtime-api.patch)，将17处alloc_workqueue统一经过
兼容层：7.3给原bound队列加WQ_PERCPU，已有UNBOUND保留。没有把原bound改为unbound，
也不改变原max_active/优先级。job fault队列短名改为kbase_fault_resume，消除名字截断提示。

日志kernel/time/hrtimer.c:1944的栈为__hrtimer_setup→hrtimer_setup→kbase_vinstr_init。
7.3此处检查fn非NULL。r1宏传NULL后才写function，满足编译而违反运行时合同。
现在9处普通timer与1处栈timer均通过带callback的kbase_hrtimer_setup[_on_stack]初始化；
兼容层在新核一次性setup，在旧核保持init→设置function，未改时钟类型或定时模式。
不再定义伪装旧hrtimer_init的NULL宏。

reset路径原本只有成功分支cancel，超时回调唤醒线程后仍可能未返回；现在每次
kbase_pm_wait_for_reset返回都先hrtimer_cancel，再判断结果/destroy，硬复位重启timer也在cancel之后。
JM工作项均为静态/堆对象或父对象成员，没有发现待补INIT_WORK_ONSTACK的实际栈work；
不对堆对象误用destroy_work_on_stack。源扫描与调用点复核不代替真实并发压力测试。

## 扩展语义审查

| 边界 | 本轮发现/处理与未验范围 |
|---|---|
| work/timer回收 | JM reset/PM/vinstr/hwcnt使用对象生命周期内的队列，终止路径cancel/flush/destroy后释放；修正栈reset timer超时路径。CSF/test源码也统一包装，但G52只构建JM，不宣称CSF运行验收 |
| dma-fence | 7.3 signal返回void，r1封装无条件返回0丢失重复signal错误。现在经dma_fence_lock_irqsave/unlock_irqrestore保护检查/信号，保留-EINVAL；使用7.3公开锁接口而非已封装的fence->lock字段。未新增隐式同步模型 |
| dma-buf/SG | map/unmap三处仍用unlocked包装获取reservation锁，保留DMA SG地址及CPU access配对；不添加第二层重复锁，不把CPU地址当DMA地址。像素、fence交接和Wave5导入仍待实测 |
| shrinker | owner与分配的核心shrinker分离，private_data回找owner；先shrinker_free再销毁上下文/池，依赖核心注销同步合同；ENOMEM由init返回。未发现需要添加第二份owner引用的具体证据，OOM/并发回收仍未压测 |
| devm/reset/clock | 平台devm结构/reset/clk由设备核心释放，手工prepare_enable/PM引用由错误路径与term成对回收；没有对devm对象再kfree/clk_put，也没有同时注册重复清理action |
| pm_runtime | resume_and_get失败不遗留get引用；bus/reset失败put_sync并disable。仍持域至remove，未新增空闲门控或系统suspend能力，不把已有5.15行为扩展成已验证睡眠parity |
| of/OPP | 自定义OPP表解析缺失of_node_put：普通OPP不兼容的早退、分配失败、正常结束均补父引用释放；非法core mask补child/parent释放与table回收；负的OPP count不再传kmalloc_array |
| IRQ资源 | 首次大写探测改optional API，避免正常小写DT引发误导性ENXIO；EPROBE_DEFER立即传播，不被小写重试覆盖。实际IRQ失败仍返回错误 |
| mmap/GUP/普通timer | 保留已编译的新GUP参数、vm_flags接口及timer_delete语义；上下文终止有同步timer删除。没有改变用户页所有权、pin/unpin与mmap锁边界；fork/退出/内存压力仍需硬件窗口 |

这次审查覆盖编译路径和关键生命周期消费点，不是对旧DDK全部并发、故障恢复或安全性的完整证明。
未为了推测性问题加入新抽象/引用计数。

## 离线门禁

[check-semantics.py](../packaging/kbase/check-semantics.py)在build.py应用完整series后自动执行：
扫描C源码，拒绝绕过兼容层的raw timer/workqueue调用、timer.function后赋值及显式NULL回调；
提取实际兼容头包装代码，分别以5.15/7.3宿主API模型Werror编译并执行，验证setup时回调、
stack初始化选择及bound/unbound flags。旧r2源码会被源门禁拒绝，避免只凭再编译进入下一窗口。
模型不模拟真实中断/调度，不将它称为内核运行测试。

四块原补丁保持固定，第五块追加到series；DT仍单独重放。
strict风格门禁只增加允许第五块的3条LINUX_VERSION_CODE提示，普通风格诊断不忽略。
最终G52模块W=1、KCFLAGS=-Werror、modpost/BTF通过；UK payload/编码和UAPI字节保持r2一致。
宿主完整unittest为317项、13项因独立工作树缺少子仓等环境跳过，无失败。

封存输出在VM ~/build/kbase-r3/delivery，含完整build.log、modinfo、ABI记录、
runtime/、runtime-files.json和probes/，boardTested=false：

| 项目 | SHA256 |
|---|---|
| mali_kbase.ko | 4ff4bbf3490d34a3f5f59e3b8b92f33c6199f6ae0d7dcf533ec1f1f26163359d |
| 0005-runtime-api.patch | 1fbc8936ca0d8b8a8f2e28f8003560eea7c51567f2e6afea2743bec48e2cf4be |
| runtime-files.json | 2166af94c5bb956b6e74b1d6a8f74e64d14240c961d523447ae68b8b63dd74fa |

Image、Module.symvers、config、DT及ABI输入保持r2固定值；未重新构建Image。

## 运行时助手与封存

首窗内核实际是7.3.0-vim4kvm-uhd3+，并不是新命名的kbase release。
当前board/vim4-board-runtime与vim4-kvm-run源码已列入uhd3；首窗产品包记录仍是10月27日版本，
而runtime-build.json的running/构建记录还是uhd1。故拒绝发生在实际部署助手与候选不匹配，
不是Panfrost/kbase的GPU选择分支。没有保存当时助手全文，不能进一步断言旧文件的逐行内容。

不扩大成7.3.*任意放行。新增board-runtime check-kernel RELEASE只检查已知release且不启动服务；
测试真实脚本在uhd3下分别调用mainline HDMI/gadget入口，未知版本仍拒绝。
vim4-kvm-run保持7.3的Wave5后端，GPU依据fe400000.gpu实际绑定的mali驱动选择
受UK与blob SHA校验的Python启动器；用私有Vulkan/CL ICD和临时EGL/GLES/GBM前缀。
Panfrost分支清理继承的blob环境，不覆盖系统Mesa。宿主替身应用测试覆盖两种绑定的实际执行路线。

board安装器/Ubuntu board包都包含同一packaging/kbase/run.py为
/usr/lib/vim4-kvm/python/vim4gpu.py，避免另写一份选择逻辑。
build.py输出runtime/快照：board-runtime、kvm-run、两个mainline prepare、vim4gpu.py，
以及runtime-files.json逐文件SHA，并在总manifest固定该清单SHA。
这仅是候选材料，没有在线安装，也不表示现有板上服务已经修复。

下次stage须先备份当前对应文件，再在双锁窗口应用完整运行时快照并核对每个SHA；
check-kernel只证明release路线，仍须检查候选build ID/完整模块/依赖库与实际服务状态。
退窗按备份逐文件恢复原助手（新文件原先不存在则删除），再次核对原SHA。
不得仅更新kvm-run、遗漏实际拒绝启动的board-runtime，或改旧runtime-build.json来伪造验证。

## clpeak与下一窗口

已有ARM64 builder的clpeak 1.1.2 --help确认支持选择项目。
[clpeak-subset.py](../packaging/kbase/clpeak-subset.py)不再默认全程序：
固定platform/device 0，仅跑--kernel-latency（30秒）及--compute-sp（90秒），
每项timeout后最多5秒KILL，日志与退出码分开保存，不选global/transfer bandwidth或DP。
同一binary/SHA、同一项目/计时方式、频点/热状态两侧一致；版本不支持这些选项直接拒绝。
没有上板证明子集一定完成；预算超时仍算该项失败，不拿部分输出算通过。
build.py的probes目录带齐该脚本与run.py，直接在两种kbase内核复用。

≤30分钟建议分配：

| 时间 | 门禁 |
|---|---|
| 窗口前离线 | 构建/语义/ABI/风格检查、完整Image模块与DT、runtime/probes SHA封存；准备原助手逐文件备份与恢复清单 |
| 0–3分钟 | 等HDR结束、5.15及双锁空闲，核对原哈希/服务/UDC；应用可回退的助手快照并验证check-kernel；保存5.15真实API与CL/GLES/VK对照 |
| 3–6分钟 | RAM一次性启动，核对build ID/私有完整模块、/dev/mali0、WARN零新增、HDMI/gadget路线与加载日志；任何失败即取证正常回退 |
| 6–10分钟 | 三API真实Mali查询/扩展、GBM/FBO三轮与DMA compute配对；拒绝软件设备，记录冷暖口径 |
| 10–14分钟 | CL两个有界子集；比较5.15同负载结果，不使用旧全程序45秒超时数据 |
| 14–18分钟 | dma-buf导入/像素/显式同步冒烟、devfreq五档与thermal绑定读回；不写PWM，不注入真实高温 |
| 18–24分钟 | HDMI→Wave5无GPU/并发GPU对照，保持源Mac mini M6不受HID/声音影响；禁止ptrace |
| 24–30分钟 | 正常回5.15，恢复原助手并核对启动/运行时哈希、服务和UDC，释放双锁；不在板上改驱动或延长窗口排障 |

若5.15两项CL尚无同条件样本，0–3分钟装不下全部基线：应缩减性能轮数或另窗配对，
不可挤占回退预算。本轮没有安排或执行这份上板清单。
