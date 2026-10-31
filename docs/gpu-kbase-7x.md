# VIM4 7.3 kbase 后备候选

当前转入[uhd4基线上的uhd5候选](gpu-kbase-uhd5.md)，正式内核基线8bca939d6bbd3。
下列r6/r9记录保留其原始内核与测量范围，不代表uhd5已通过。

[r9队列首用](bringup/2026-10-31-kbase-r9-queue.md)：模块/ABI及339项宿主测试通过；
平台层新增mpgpu只读缓存，修正DEVFREQ metrics定时器回收。5.15七轮默认策略已缓存，
7.3候选受工具目录冲突阻塞，尚未启动；新默认策略性能与温度仍未完成配对。

[r7离线候选与等锁超时](bringup/2026-10-31-kbase-r7-offline.md)：取消performance默认，
改为独立`governor_vim4.ko`复现厂商五档阈值/保持计数；
本轮已构建，尚未上板，不把r6的performance成绩算作新默认策略的验收。
厂商实际配置为MALI_MIDGARD_DVFS，不是另一编译分支中的simple_ondemand 30/5。
performance仅保留为显式调优选项，不能据此宣称产品性能/能效对齐。

[r6实测与二分](bringup/2026-10-31-kbase-r6-window.md)：同heap-gfx、800MHz时DMA 1.493ms，
追平5.15的1.574ms；根因为突发任务未及时升频，新增仅T7的performance governor默认值。

| 当前门禁 | 状态 |
|---|---|
| API查询/像素/基本执行 | r6为EGL1.5、GLES3.2、VK1.3.231、CL设备/C3.0；r9新候选待测，非CTS |
| 64位heap | 六类VK路径通过；CL五类本轮通过，default CMA CL未重测 |
| 正常候选WARN/fault | r6正常候选零WARN/BUG/oops/fault；r9未加载，负向去override的历史对照会fault |
| 默认策略性能 | 5.15七轮已缓存；新7.3默认策略待配对；r6高频成绩不作为该门禁通过 |
| thermal/并行 | r6有95°C map绑定、五档/59.998fps；r9待测，真实温控未触发 |
| 实际scanout / GBM→Wave5 | 新互操作能力未通过；非现有5.15默认视频路径，独立验收，不以PRIME handle成功替代 |

尚不满足完整互操作门禁，保留候选，不提交可批准的产品路径方案或改变默认GPU。

[r5窗口](bringup/2026-10-30-kbase-r5-window.md)：零fault，三API/六类内存与BO导入通过，
GLES648 FPS、CL51µs/101.75 GFLOPS；DMA3.571ms落后5.15，GPU thermal绑定仍缺。
[MMU/heap合同与后续窗口](gpu-kbase-mmu-heaps.md)解释联合修复的归因边界。
该页退窗后的heap DMA mask64位修正已在r6复测，不混用各封存版本的哈希。

[r4历史诊断](bringup/2026-10-30-kbase-r4-window.md)：当时GBM被缺失的system-uncached/heap-gfx阻断；
VK1.3.231与CL3.0设备查询通过，但VK DMA执行DEVICE_LOST/MMU fault；后续修复结果见上方r6状态。

[r3再次上板](bringup/2026-10-30-kbase-r3-window.md)：零WARN加载及KVM助手启动路径通过，
首个GBM/EGL设备探针退出2，按门禁回5.15；该轮尚无候选API或性能通过数据。

[r3离线修复与新窗口门禁](gpu-kbase-repair.md)修正timer/workqueue及生命周期问题，
新增运行时快照与CL分项预算；该离线记录保留当时的门禁与窗口清单。

[首个上板窗口](bringup/2026-10-30-kbase-window.md)已完成：/dev/mali0出现，但workqueue/hrtimer
新增WARN，运行时助手也拒绝候选；已回5.15。候选不能用于产品或继续性能验收，需先离线修复。

结论：**基本GPU执行与API已验证，产品parity未完成**。保留厂商 r44p0-01eac0、JM UK 11.39，
将内核 API 适配与 T7 平台层作为外部模块补丁维护；不向正式内核并入整棵 DDK。
相同 libmali 实测保持 GLES3.2、Vulkan1.3.231、OpenCL设备/C3.0及扩展集合，
但不代表CTS、完整DMA互操作或性能全量通过。当前 blob **不支持直接注册GLVND EGL vendor**。
默认GPU选择保持原状，Panfrost＋Mesa上游路径和kbase能力/性能后备均保留，待实测决定默认值。

r2的[EGL选择、电源范围和补丁重放](gpu-kbase-integration.md)推荐ICD产品路径＋独立GLES私有前缀，
不实现GLVND shim；任务空闲策略与厂商方向一致，系统suspend尚未达成parity。

固定产物、检查和限制见[离线记录](bringup/2026-10-30-kbase-offline.md)。
既有性能基线和探针见[三栈验收](bringup/2026-10-30-gpu-acceptance.md)，
旧冷提交/CL超时数字须同时遵守该页链接的测量口径修正。

## 来源与更新路线

补丁按责任重放：0001为内核API/Kbuild兼容，0002为T7域/bus/reset平台，0003为devfreq/thermal注册，
0004仅候选DT（GPU coherency、独立CMA、GPU cooling map），0005为timer/workqueue/fence生命周期，
0006为T7 reset override，0007为fault region诊断，0008为仅vim4的devfreq默认策略，
0009用schedule_work代替JM路径的旧system_wq；7.3映射system_percpu_wq，旧内核保持原语义。
WC exporter独立在heaps/，不混入DDK。0006依据厂商/Panfrost初始化，r6去掉它独立复现原生compute fault。
删除dma-coherent的必要性未证明；仍以5.15缓存合同保守保留，不能称它是必需的fault修复。
heaps实现的是厂商WC合同，并非已被上游接受的system-uncached；将来优先替换为等价的公开接口。

每次升级先固定新内核commit/config/Image/完整模块集，再按上述主题重放；更新build.py内核锁定值及
白名单时审查实际差异，不能绕过检查。UK与blob SHA保持绑定，逐项比较UAPI字节/34种payload/40个ioctl；
再做W=1/Werror、modpost、strict风格、runtime/heap宿主模型与主仓unittest。
新增/删除的内核API集中兼容头；不把语义变化伪装成同名宏。DT生成器与候选DTS一起更新，保留既有phandle
和MCU fan map。下一窗至少覆盖六类内存、同合同heap性能/cache计数、GPU频率、thermal绑定与60fps并行。
构建通过不代表cache、PM、跨设备同步或睡眠通过；故障恢复/内存压力/实际scanout需单列验收。
正常小版本预计以兼容层及这些门禁为主；涉及DMA/MMU/PM语义变化时按新移植窗口预算，不能承诺零维护。

本轮r6新增独立95°C passive GPU map（0..4级），保留MCU map，已实测绑定及trip路径；尚未热触发。
dma-profile.py创建独立trace实例，记录DMA API与具名arch cache事件；探针逐提交marker与频率读回位于计时外。
原生两核物理地址不能跨重启视为同一buffer；优先比较两边heap-gfx的连续/WC合同，并辅以cached system对照。
既有同源比较显示5.15也会降至250MHz；只有记录频率/trace状态的配对才用于归因。
性能主样本关闭trace与timestamp探针，独立trace样本检查cache次数/字节与GPU耗时。
实际显示/编码互操作、故障清理旧system_wq提示仍需收尾；不以查询表覆盖这些缺口。

V=`~/src/linux@80a07ad5406d57855c996285ae75a50a1b9147ae`，
K=`drivers/gpu/arm/midgard`；以git archive导出固定提交，不复制厂商构建目录的旧.o/.ko。
正式7.3基线=`f71b5c6289cb3254690e57292327e73514f0715f`。
独立VM worktree=`~/src/linux-7.3-kbase`，分支`gpu-kbase-7x`；正式/HDR/Panfrost工作树均不修改。

截至2026-10-30，[Arm Bifrost发布页](https://developer.arm.com/Downloads/-/Bifrost%20Mali%203rd%20Gen%20GPU%20Architecture)
的公开索引列出G52专用`BX304EG52-SW-99002-r54p3-02eac0.tar`（2026-09-23），以及r49系列。
页面明确要求版本兼容的DDK；本轮网页主体下载表受服务限制，包列表由同一官方页面搜索索引取得。
**未下载、未编译新包，未找到其7.3支持承诺，也未证明其JM UK与此blob兼容**。
G76 r56或CSF驱动不构成G52支持证据。不能改版本常量伪装UK11.39，更不能只按r4x/r5x名字混用。
后续审查新包须核对JM版本协商、完整ioctl布局/语义、支持GPU和已移除的历史接口，
再决定回移内核API/安全修复，或一起更新获得授权的匹配用户态。

## 已确认的移植面

下表文件相对V:K，兼容头为V:`include/linux/version_compat_defs.h`。
模块补丁顺序见[series](../packaging/kbase/series)，不改UAPI定义；DT单独作为第四块重放。

| 边界 | 7.3适配与核查 |
|---|---|
| 外部Kbuild | 7.3外部构建以模块目录为cwd，修正src绝对路径；将旧EXTRA_CFLAGS接入ccflags-y，否则CONFIG_MALI_DEVFREQ等宏未生效；删除已不存在的include路径 |
| dma-buf | mem_linux.c的map/unmap及mem.c释放路径改用unlocked包装，核心获取exporter reservation锁；继续使用SG DMA地址，DMA_BUF namespace显式导入；attach/detach/CPU access保留 |
| dma-fence | 7.3 signal返回void，适配原int封装；删除已移除的fence_value_str字段。内核sync_file显式fence路径编译通过；不据此宣称具备所有DRM隐式同步语义 |
| mm/GUP/VMA | pin_user_pages_remote去掉vmas参数，本地pin/get_user_pages去掉末尾vmas；以vm_flags_set/clear操作只读flags；原锁和页释放配对保留，未做内存压力验证 |
| shrinker | 嵌入owner保持稳定，另分配核心shrinker，以private_data回找owner；分配失败返回ENOMEM，释放经shrinker_free等待核心生命周期；替换已删除__GFP_ATOMIC检查 |
| movable pages | 厂商默认未启用PAGE_MIGRATION_SUPPORT；新接口需单独生命周期移植。本候选明确禁止7.3启用该选项；未调用路径仅保留编译占位，不能称页迁移已支持 |
| timer/debugfs | timer_delete与hrtimer_setup兼容包装；no_llseek改为NULL（不提供seek）；MIN/MAX及固件in_range与新内核命名冲突修正；debugfs其余入口编译通过 |
| platform/of/file | remove回调为void；unsigned offset转到file_operations.fop_flags；仅匹配候选专用compatible；misc设备原样，不引入厂商mpgpu class接口 |
| DMA/IOMMU/SG | dma_set_max_seg_size现为void；kbase使用GPU自己的MMU，沿用T7直接DMA路径，不引入厂商IOMMU私有接口，不等于已验非连续buffer/外部IOMMU |
| devfreq/OPP | 通用devfreq＋五档OPP；T7离线候选改为vim4五档策略，其他平台仍simple_ondemand；thermal由devfreq核心约束，私有PREHEAT接口不启用 |
| thermal | of_devfreq_cooling_register、max_state=4；新增95°C GPU map已绑定，保留MCU map；真实过温闭环未触发，不使用未校准IPA模型 |
| pm_runtime/reset | 小平台层持有runtime引用直至remove；复位数组含CAPB3和MALI；失败路径回收bus和PM引用；不在每个空闲任务间重置域 |

兼容性主要集中在已有兼容头和`platform/vim4/`，其余是API调用点小改动。
版本条件覆盖已确认的变化；**只验证了7.3这一配置，不承诺同一补丁可直接构建所有中间版本**。
信号重复提交的旧错误返回、VMA与shrinker并发语义仍需运行时检查，不能用无告警代替审计。

## T7平台合同

7.3 DTS已有core/bus时钟、两个reset、`T7_MALI_TOP`域与五档OPP。
域由`drivers/pmdomain/amlogic/meson-secure-pwrc.c`的T7表管理，通过既有secure pwrc SMC供电，
模块不直接调用厂商SMC；GPU自身的T7复位override见r5具名平台hook。
电压保持现有always-on PWM供电，
候选删除GPU的mali-supply引用，使kbase不向OPP注册regulator；regulator节点本身不变。
这延续厂商Linux只调频的固定电压策略，不能据此推断闭源固件行为。

平台先持域引用、开bus、释放reset，通用kbase持core时钟；终止按相反顺序回收。
持域是遵守厂商T7“空闲reset影响GPU”的限制。内部shader power gating仍由DDK处理，
但外部域/时钟的runtime节能、系统suspend/resume均未验，不能宣称功耗追平。
cooling注册不依赖新增电压模型；GPU绑定与trip作用路径已验证，真实热限幅和功耗仍待验。

## 内核选择、打包与复现

独立候选DTS继承display-m0，换`khadas,vim4-mali-kbase-r44p0`并删mali-supply；
r5另按厂商设置system-coherency=0且删除dma-coherent，新增专用WC heap/CMA节点。
模块也只匹配该compatible，没有arm,mali-bifrost fallback；Panfrost因此不能绑定候选GPU，
kbase不能绑定默认GPU。不要热解绑切换，两者通过重启选DT切换。
下一窗可额外在一次性启动项使用`modprobe.blacklist=panfrost`；若initramfs提前加载，
还须在候选initramfs中处理，黑名单不能代替DT互斥。默认initramfs/启动项保持原状。

构建器也能从显式给定的**完整保留DTB**复制候选，用fdtput改上述属性并添加heap节点，
保持原phandle、HDMI/USB/MAC和其他配置，不拿通用板DT覆盖运行profile：

```sh
python3 packaging/kbase/build.py --vendor "$HOME/src/linux" \
  --kernel-source "$HOME/src/linux-7.3-kbase" \
  --kernel-build "$HOME/build/uhd3" \
  --dtb "$HOME/build/uhd3/arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-display-m0.dtb" \
  --output "$HOME/build/kbase-7x/new-build"
```

Ubuntu24.04 ARM64 VM，Python3.12、GCC、git、make、fdtget/fdtput及完整已构建内核输出，
无下载步骤。输出必须是新目录；校验vendor、内核worktree及build/source版本，
ABI对比后执行W=1、KCFLAGS=-Werror和modpost；完整日志、modinfo、输入/输出SHA入manifest。
stage仅含`lib/modules/RELEASE/extra/mali_kbase.ko`，**是内核包的附加片段，不是可独立替换完整模块集的包**。
组装候选时将其合入同一次Image/模块集，再depmod、生成候选initramfs；保留manifest中的
Image、Module.symvers、config和保留DTB哈希检查。不能只比较vermagic，更不能混装BTF模块。
不需要厂商amlogic-thermal或独立memory_group_manager，使用DDK内置native memory manager。

## 用户态与许可证

锁定libmali SHA256为`536ee80c17dc5c54e7c6ff029ca43270da8efc3fdc5b3aeb263f364419368494`。
readelf确认依赖libdrm.so.2、Wayland client/server、pthread、dl、stdc++、m、c、gcc_s；
没有DT_NEEDED libGBM或X11，GBM由blob自身导出，不能因此推断该构建支持X11窗口系统。
不替换系统libgbm/libEGL/GLES或系统Mesa。dmaheap分配、GBM依赖的DRM设备以及modifier仍需实测；
kbase只提供/dev/mali0，不会产生Panfrost renderD节点。GBM探针应选实际显示DRM card节点，
不能把消失的Panfrost renderD128路径写死。

Vulkan有vk_icdGetInstanceProcAddr，OpenCL有clIcdGetPlatformIDsKHR，可使用私有JSON/ICD。
**没有__egl_Main**，给它写GLVND EGL vendor JSON会失败。首窗复用已有vendor模式的
LD_PRELOAD直接EGL/GLES/GBM导出（历史探针）；r2改用专用前缀，通用GLVND应用集成需另取已授权、UK匹配且实现该ABI的库，
或开发并验证适配层。本轮未实现GLVND桥，不创建误导性的EGL vendor JSON。

[run.py](../packaging/kbase/run.py)提供显式逐进程选择：核对已加载的UK11.39、/dev/mali0和blob哈希，
临时生成Vulkan与CL ICD；命令结束清理。默认只选ICD，显式GLES模式用
`python3 packaging/kbase/run.py --graphics direct -- COMMAND ...`。尚未上板验收，不接入正式服务。
后续沿用board/vim4-kvm-run模式，将视频后端选择与GPU驱动选择分开：7.3仍使用Wave5，
GPU依据实际绑定驱动和UK再选用户态，不能仅凭7.3 release就选Mesa或blob。
GLVND可用时仅逐进程指定EGL vendor文件；Vulkan/CL同理，不全局注册使共用rootfs的另一内核误选。

kbase源码许可证保留GPL-2.0及原作者/版权，部分文件标有Linux-syscall-note；
分发修改过的模块须提供相应源码、补丁、许可证和可用构建材料。
libmali是专有组件，原打包标注CLOSED；公开可下载不等于获得再分发权，
Arm通用[EULA](https://developer.arm.com/Downloads/-/Mali%20GPUs%20User-Space%20Binary%20Drivers)
也不能自动授权第三方Amlogic构建。发镜像前须核对该blob随附许可或供应商授权。
本轮只提交源码补丁/工具/文档，blob不进入Git、模块stage或公开产物。

## 后续成本与≤30分钟窗口

每次内核升级：新独立worktree与输出、审阅API变化、刷新版本条件、W=1重编和modpost、
UAPI字节/布局检查、同次Image/完整模块包、DT差分，再跑设备/API/DMA/视频/PM门禁。
预计普通升级半天至一天；涉及MM、shrinker、fence生命周期时2–5个工作日，
均为本轮范围的工程估计，不是Arm支持保证。还需独立跟踪DDK安全修复，
固定老blob使用户态编译器/安全修复受供应商约束，这部分维护成本高于Panfrost。

下一独占窗总预算30分钟，所有命令须timeout并有TERM→KILL上限；首错停止并正常回退：

| 分钟 | 门禁 |
|---|---|
| 0–4 | 按board→heavy双锁协调HDR会话，核对完整候选与回退；一次性RAM启动候选，无saveenv；确认只有kbase绑定、/dev/mali0、UK11.39、GPU四核、无probe/MMU/reset错误 |
| 4–8 | 同blob真实EGL/GLES、Vulkan physical device、CL device/C版本与扩展；GLES显式direct模式，VK/CL先验证纯ICD模式；拒绝软件设备。GBM使用实际DRM显示节点；失败即记录能力阻塞 |
| 8–14 | 复用gpu-compare.py、gpu-probe、mali-dma-probe，匹配512² FBO/shader/循环、CPU/温度/频点；三轮GLES及冷暖Vulkan逐字像素；与提前保存的5.15同条件样本配对 |
| 14–18 | CL小buffer map/unmap和有界clpeak；CMA dma-buf导入/compute/CPU回读；同步fd交接。不能把该冒烟当GPU→Wave5整链已通 |
| 18–23 | 固定HDMI4K60→Wave5，先无GPU再并发GPU，记录帧数/序号/p99/CPU/错误/CMA；不发HID、不播放声音、不改变Mac mini M6 |
| 23–26 | 五档OPP短往返、cooling绑定/频率上限、空闲→渲染恢复；本候选域应保持active，无真实热触发则thermal闭环未验；不写PWM或强制过热 |
| 26–30 | 正常回原默认内核，核对启动文件与服务、取日志释放锁；boot/API失败时剩余时间全部用于恢复 |

窗口前离线备齐同次Image/完整模块集/extra kbase、候选initramfs、manifest及DT；
必须额外比对实际rootfs运行时助手/注册清单与候选release和build ID的合同；
单有board/vim4-kvm-run源文件支持release不足以证明已部署的vim4-board-runtime支持。
新WARN和probe返回失败同样阻断，不因/dev/mali0存在就继续设备或负载测试。
保留5.15与正式7.3启动文件哈希。一次性RAM入口沿用
`sysboot mmc 1:1 any ${pxefile_addr_r} /gpu-once.conf; reset`，不saveenv、不改变默认项；
只有用户安排且HDR释放锁后才stage。各项单命令timeout，最迟第26分钟进入回退。
配对必须固定同一probe哈希、GBM/FBO尺寸、shader/迭代、CPU亲和/频点与温度，
GPU→Wave5未连通则单列失败，不以CPU拷贝冒充零拷贝；保留冷暖提交不同口径。
本窗不测系统suspend、不注入过热、不对Mac mini M6发送HID。

30分钟不足以包含两次完整启动加全量三栈基准和长稳态功耗；若缺同条件5.15样本，
本窗只判功能，下窗另做配对，绝不拿622fps或1.89ms旧值直接判追平。
预计基础上板排障1–3天、GLVND方案与DMA/视频集成再2–5天；
长稳态/CTS/安全回移需另排1–2周以上。首个30分钟窗口不能完成产品验收。
