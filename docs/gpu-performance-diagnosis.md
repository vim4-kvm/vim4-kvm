# GPU 性能差距：离线测量复核与下一窗口

结论：旧GLES结果是可复现的串行离屏负载差距，但尚不能归因为纯GPU执行慢2.7倍；
旧Vulkan4.25倍是一次冷提交的主机等待时间之比，不是稳态compute吞吐之比。
本轮修正测量边界、预热及分段计时，增加G52循环展开A/B和受控频率/PM/fdinfo诊断。
没有足以证明内核漏配的证据，因此不改`vim4-gpu-panfrost@d2cd4c6c981e9`，不猜寄存器或电压。
本轮没有连接板子，NPU独占会话未受干扰，未读取/修改VM的NPU工作树。
方针仍为**代理建议，待用户确认**；上板操作需要另一个独占窗口。

后续[实测分解窗口](bringup/2026-10-30-gpu-diagnosis-window.md)：显式展开使私有Mesa由约232升至567fps，
厂商同展开版约573fps；有效GPU区间由4.133降至1.584ms，厂商同展开版1.515ms。
连续GLES锁频/PM无显著收益，原循环fdinfo忙碌估计约94%；短Vulkan锁800MHz由3.30降至2.00ms，
PM on未改善稳态。最小CL map与独立transfer均通过，旧全程序120秒预算不能证明map死锁。
该shader的性能接近证明了优化可行性，不代表API/所有负载或实际HDR产品链已追平。
GPU timer通过`GPU_TIMER_QUERY=1`或`gpu-compare.py --gpu-timer`单独启用，预热后清除初始disjoint，
末尾非零disjoint的数据必须丢弃，不与无query的FPS混算。

后续[离线编译/调频候选](gpu-performance-candidates.md)：Bifrost独立展开成本预算，
原循环已得到与显式展开相同的G52统计且无spill；内核4e239aec051a4将devfreq轮询改为10ms。
均未上板，不能把编译统计或构建通过当作FPS、功耗与产品HDR性能验收；下一窗口测量预算20分钟。

## 测量是否同条件

复核原始`logs/gpu-board-20261030/`的vendor-final.json、gbm-candidate.json及compute.json：

| 条件 | 判断 |
|---|---|
| GLES尺寸、表面 | 比较表使用同一GBM/FBO探针、512×512 RGBA纹理，均无EGLSurface；未混用原surfaceless/pbuffer失败数据。新增输出实际RGBA位数以验证实现差异 |
| 交换、vsync、同步 | 没有eglSwapBuffers，因此不是显示vsync上限；每帧glDrawArrays＋glFinish，强制串行提交，含驱动/调度等待，不能代表异步队列最大吞吐 |
| 着色器工作 | 同一highp GLSL、128次依赖fract循环、相同全屏三角形；中心像素三栈均179/128/128/255。但单像素一致不证明全图一致、ISA或指令效率等价，厂商ISA尚未取得 |
| 帧数/预热 | 各三轮、每轮10秒，以时间而非固定帧数结束；没有预热，首帧lazy compile/分配/升频混入。GLES原seconds在glReadPixels之后计算，意外含最后一次回读，现已修正 |
| Vulkan | 同一SPIR-V、24.88MB、同一uint模式、完整逐字回读；heap分别codecmm/default_cma_region，均连续但映射/缓存实现不等价。原计时仅QueueSubmit→WaitForFences，不含分配、pipeline创建、CPU同步/回读，但含首次提交的PM/升频/隐式cache维护 |
| 环境 | CPU performance；GPU负载期间未保存trans_stat/profiling周期，不能据另一个五档测试证明基准本身一直800MHz。两内核分组测试，温度/启动/缓存/顺序存在差异 |

因此保留旧API、像素、视频并发、DVFS和PM验证，也保留622.7/~232fps作为**旧冷启动串行负载观察**；
不能把它标成精确的shader IPC差距。Vulkan中位1.893/8.038ms只能表示旧冷提交口径，
不可与新预热后多提交均值混算，也不能据其归因heap或纯ALU。

## 原因排序与源码证据

路径缩写：P=VM `~/src/linux-7.3-gpu/drivers/gpu/drm/panfrost/`（d2cd4c6）；
V=VM `~/src/linux/drivers/gpu/arm/midgard/`（80a07ad5406d）；
M=VM `~/build/gpu-runtime-26/mesa-26.2.6/`（tarball b9436b3e…31a92）。
以下是影响排序的假设，不是已经证实的性能修复。

| 优先级/原因 | file:line与已知事实 | 下一步判别 |
|---|---|---|
| 1 GLES循环编译/调度 | M:src/panfrost/compiler/bifrost/bifrost_compile.h:140，max_unroll_iterations=32；本探针循环128。原G52 drm-shim NIR转储确有loop；本轮显式128次展开版本NIR无loop。厂商是否展开未知 | 相同频率、相同GBM/FBO、原循环/显式展开三轮A/B；分别保存BIFROST_MESA_DEBUG=shaders转储，统计clauses/寄存器/溢出。debug输出另跑，不计FPS |
| 2 冷提交/升频 | P:panfrost_devfreq.c:90、228，50ms轮询、45%阈值；:46 交OPP设置频率；单次2–8ms工作可在首个调频周期结束前完成 | 保存trans_stat首尾和负载中cur_freq；对照默认/固定800MHz，不直接把轮询改短或阈值改低 |
| 3 PM往返与提交/fence | P:panfrost_drv.c:995为50ms autosuspend；P:panfrost_job.c:211、278为runtime get/put，:257–265启用周期统计；P:panfrost_device.c:432恢复reset。V:platform/devicetree/mali_kbase_runtime_pm.c:219–221明确T7不做put_autosuspend | Vulkan冷样本与三次预热后20次提交分开；host submit/wait拆开，auto/on对照。连续GLES帧间~4ms远小于50ms，PM不是其2.7倍差距的首要解释 |
| 4 BO缓存/映射、heap | P:panfrost_gem.c:302–349导出buffer CPU同步；:452解释coherent CPU缓存约束；:548–620导入buffer同步限制。P:panfrost_mmu.c:812支持4K/2M。DMA计时未含显式CPU读回，但提交仍可能含cache/映射处理 | 同样连续heap、相同字节数，复用buffer与pipeline重复提交，比较submit/wait；不要将一次冷DMA写入当整个HDR处理性能 |
| 5 AFBC/tile/tiler heap | M:src/gallium/drivers/panfrost/pan_screen.c:54–55有noafbc/nocrc选项，:773有v7 AFBC component-order限制；pan_job.c:653选择tile size；M:src/panfrost/lib/pan_tiler.c:57–83解释lazy heap及层级 | 一次只改noafbc或nocrc，单独记录modifier/编译dump；当前一个三角形、RGBA写入、无纹理采样，不先断言tiler heap耗尽；AFBC不解释纯storage-buffer compute |
| 6 核心/L2掩码 | P:panfrost_gpu.c:433在l2_present==1时返回全掩码，:461–478按shader_present开核；原日志shader=0xf、L2=1，已覆盖四核，不是只用第一颗核 | fdinfo周期/引擎数据与固定频率核对；不把仅支持一core-group的通用注释误当T7少核证据 |
| 7 T7平台初始化/AXI/QoS | P:panfrost_gpu.c:109–115与V:platform/devicetree/mali_kbase_runtime_pm.c:188–189的PWR_KEY/PWR_OVERRIDE1相同。P:panfrost_gpu.c:166–167及panfrost_regs.h:228用IDVS默认0xf，与V:backend/gpu/mali_kbase_pm_driver.c:2939–2955一致 | 已检查的T7初始化路径没有证明缺少某个QoS值；不复制未知寄存器。7.3 DT的core/bus、800MHz双时钟路径见arch/arm64/boot/dts/amlogic/amlogic-t7.dtsi:1078–1100；厂商mesont7.dtsi:4726–4749也用双路径800MHz。bus约166MHz不是GPU只跑166MHz的证据 |
| 8 L2/AXI override | V:backend/gpu/mali_kbase_pm_driver.c:528–581的L2 override在未指定size/hash时直接返回；V:mali_base_hwconfig_features.h:87–94的G52表没有L2_CONFIG特性。P:panfrost_mmu.c:55–56按coherency选择shareability，DT已dma-coherent | 没有依据声称厂商在T7启用了特殊L2/QoS增强；平台带宽与cache计数仍待真正perfcnt。不得用缺乏适用证据的CPU/其他Mali寄存器表修补 |

## 本轮实施

- [GLES探针](../packaging/gpu/gpu-probe.c)：两秒预热；稳态计时在最后一次glFinish之后、glReadPixels之前截止，回读单独统计；输出draw/finish/进程CPU时间及RGBA位数。
  清理GL对象改在解绑context之前。`GPU_UNROLL128=1`为显式展开诊断，默认仍是原循环；不是已证明的驱动性能补丁。
- [DMA探针](../tools/mali-dma-probe.c)：可选第四个参数1–100次测量，先打印三个预热样本（首个为冷样本），再输出每次submit/wait/total和稳态均值；一次分配/pipeline复用，最后完整回读。每次fence仍有10秒超时，外层需90秒超时。
- [gpu-diagnose.py](../tools/gpu-diagnose.py)：只采自己的GPU子进程，不ptrace、不扫视频进程。保存trans_stat、200ms频率/PM、fdinfo周期/引擎ns、/proc/PID/stat和主机输出。
  可临时固定频率、power/control或profiling，结束/失败/TERM恢复；超时保留已有输出并终止整个子进程组。
  忙闲估计取两个引擎增量的最大值，不相加重叠时间；不是精确硬件busy并集。profiling另跑，避免把其开销混入普通FPS。
- [gpu-cl-map.c](../tools/gpu-cl-map.c)：4KB/1MB/64MB、普通/ALLOC_HOST_PTR、每组3次map→finish→unmap→finish；逐阶段flush日志及map event时间，60秒外层超时定位究竟停在哪一步。

没有板端运行结果，不能宣称展开版已缩小差距。没有内核改动，因此不重建Image/模块、不运行针对新增内核代码的checkpatch；
保留原分支d2cd4c6。三份C工具ARM64 `-Wall -Wextra -Werror`编译；loop/展开版均通过drm-shim着色器编译，
noop像素校验仍按预期失败（无真实执行），不可引用模拟器FPS。日志位于`build/gpu-diagnosis/`。
主仓unittest：308项、7项跳过、无失败；新增回归覆盖引擎重叠不重复相加、失败恢复设置、超时保留证据并终止子进程。

## clpeak map超时的源码解释

本轮核对clpeak1.1.2（Ubuntu包1.1.2-1），源码归档SHA256
`7bc7beba6b3307290650abc4f13fe9389b271c1a64601fa333461516950d745b`。
[transfer_bandwidth.cpp:11–20、165–198](https://github.com/krrishnarraj/clpeak/blob/1.1.2/src/transfer_bandwidth.cpp#L165)
使用ALLOC_HOST_PTR及20轮blocking map/finish/unmap/finish；common.cpp:67–69将GPU传输上限设512MB。
此前120秒限制包住**整个clpeak**，前面的带宽、浮点、整数和transfer已消耗预算。
只看到最后输出map标题，无法证明首次map永久等待；也可能是大buffer迁移/20轮累计时间耗尽预算。

M:src/gallium/frontends/rusticl/api/memory.rs:1828–1837排队同步map；core/memory.rs:1547–1596在非纯user memory路径
执行read→buffer_map；M:src/gallium/drivers/panfrost/pan_resource.c:1737–1748在同步映射前flush并等待BO（INT64_MAX）。
所以真实的fence等待/host staging复制与测试预算不足均可导致现象，尚无锁环证明。
下一窗口先单独`clpeak --transfer-bandwidth`（180秒），再跑最小map工具；记录阶段时间和event。
如果小buffer单次map也卡住，才进一步定位Rusticl队列事件/BO fence；不提高全局超时后直接宣称修复。

## 下一独占窗口（每项不超过10分钟）

KVM服务状态每项入场记录，GPU主测时可停应用并在结束恢复；不发HID、不测声音。
先完成所有编译再上板，NPU与GPU性能采样顺序执行。

| 项目 | 时长 | 判别目标 |
|---|---|---|
| 三栈GLES原循环、展开版；同一GBM/FBO、三轮×10秒 | 5分钟 | warm/steady/readback分离，full-rate GPU是否仍差2.7倍；单像素不能替代完整图像验证 |
| 7.3默认、固定800MHz、800MHz＋PM on | 3分钟 | `gpu-diagnose.py --mode private --seconds 20 --frequency 800000000 --pm on --output NEW -- PROBE 20 /dev/dri/renderD128`；与无override同负载对照 |
| 单独profiling周期采样 | 2分钟 | 同命令另加--profiling；用drm-cycles和engine ns判断CPU提交空洞/执行占用，不能把trans_stat当busy比例 |
| Vulkan冷/预热/20次复用提交，固定频率和PM各对照 | 3分钟 | `timeout -k 5 90 PROBE shader.spv HEAP 20`，分离submit与wait；先比较同条件，再讨论4.25倍 |
| 独立CL transfer＋小buffer map复现 | 4分钟 | 单独transfer180秒；`timeout -k 5 60 gpu-cl-map`；用同一ICD隔离方式在厂商/私有栈分别跑 |
| 可选AFBC/CRC、shader dump | 3分钟 | 单变量、独立输出，不把debug转储计入FPS；如busy不高优先查提交，不先改tile/寄存器 |

GPU诊断合计约20分钟，另加一次性启动/恢复。若使用PM on或锁800MHz，只作为短诊断设置，
不能作为默认性能修复；完成后核对原min/max、PM、profiling和服务状态。
