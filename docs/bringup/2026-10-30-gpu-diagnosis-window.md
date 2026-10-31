# 2026-10-30：GPU 性能差距分解窗口

结论：该合成GLES场景的主要差距来自循环编译，非低频驻留或持续PM往返。
显式展开128次运算后，私有Mesa约567fps、厂商约573fps；GPU timer区间仅相差约4.6%。
Vulkan冷/短负载显著受频率影响，锁800MHz后稳态约2.00ms，而厂商三轮均值约1.75ms；
尚未取得Vulkan GPU时间戳，不能将剩余wait全算纯GPU执行。CL最小map与独立transfer均通过，未复现map死锁。
**不能据此宣称产品功能/性能整体追平**：着色器特定优化、短测和合成buffer写入不等于HDR/KVM产品链。
方针**用户已于 2026-10-30 确认**：上游实现为主，必要时保留kbase/libmali临时后备。

## 入场、版本与测量条件

用户授权独占；先确认5.15默认、One-KVM/HDMI/manager active、UDC configured，再取得Mac
board→heavy两把lockf锁，覆盖全部板端操作。NPU会话已结束，本轮不访问其VM工作树。
源码、驱动、系统25.2.8/私有26.2.6及RAM启动方法沿用
[上一窗口](2026-10-30-gpu-acceptance.md)：正式213f2715 Image/同次模块，保留DT副本仅加d2cd4c6的GPU cooling map。
默认启动项、原Image/DTB不替换；U-Boot RAM sysboot临时gpu-once.conf，无saveenv。

工具在首轮测量前完成ARM64 Werror编译；修正timer启动disjoint清除后的最终二进制，
在候选启动间隙编译，不与任何测量重叠；回5.15后重跑厂商基线，比较表均用同一最终二进制。
测量命令均有外层超时，GLES单项25秒、CL map60秒、CL transfer180秒；没有单项超过10分钟。
不发键鼠/HID、不测声音、不ptrace、不写PWM/电压；所有锁频只使用现有800MHz OPP。

三栈均为真实Mali-G52，GBM/FBO 512×512，RGBA位数均8/8/8/8；无swap/vsync。
每项先预热2秒，再计10秒（3轮）；每帧draw＋glFinish，回读在计时之外。
原循环与显式展开均为128次顺序依赖运算，所有三轮中心像素均179/128/128/255；不等于全图像素验证。
独立timer采样每项5秒，其额外查询开销不混入普通FPS。

## GLES三栈复测与GPU区间

| 项目 | 5.15 libmali | 7.3 Mesa25.2.8 | 7.3 Mesa26.2.6 |
|---|---:|---:|---:|
| 原循环FPS三轮 | 613.19 / 614.25 / 614.33 | 229.42 / 229.93 / 229.26 | 232.11 / 231.48 / 231.67 |
| 原循环平均FPS | 613.926 | 229.538 | 231.753 |
| 显式展开FPS三轮 | 572.58 / 572.33 / 573.85 | 558.84 / 556.34 / 558.34 | 571.63 / 566.26 / 563.78 |
| 显式展开平均FPS | 572.922 | 557.842 | 567.225 |
| 原循环GPU timer，ms/帧 | 1.404 | 4.154 | 4.133 |
| 展开GPU timer，ms/帧 | 1.515 | 1.607 | 1.584 |
| 原循环draw主机时间，ms/帧 | 0.0236 | 0.1105 | 0.1012 |
| 原循环finish主机时间，ms/帧 | 1.6030 | 4.2438 | 4.2113 |
| 原循环进程CPU时间，ms/帧 | 0.1894 | 0.3509 | 0.3271 |

有效timer样本均gpu_disjoint=0。最初厂商样本将启动/预热阶段事件混入，读到8/16，已丢弃；
修正为预热后先读并清除GL_GPU_DISJOINT_EXT，再计时，最终两项均为0。
Mesa26.2.6的timestamp实现见`src/gallium/drivers/panfrost/pan_context.c:873–895`，
读硬件timestamp buffer并按频率换算；GPU区间仍可包括GPU流水线空洞，不等于只计ALU指令。

原循环GPU区间差约2.73ms/帧，而同一次timer采样主机整帧差约2.75ms；
主机剩余区间差约0.02ms。draw、CPU、GPU区间有重叠，**不可把各行当作互斥份额相加**。
私有栈展开使GPU区间减少约2.55ms，解释约93%的原GPU区间差；按普通FPS换算，
消除了约95%的端到端帧时间差。这是该shader的受控干预效果，不是所有应用的归因比例。
展开后私有GPU区间比厂商同展开版本慢约4.6%，普通FPS慢约1.0%；相对厂商原循环仍慢约7.6%。
厂商展开反而略慢，不能直接全局提高Mesa展开上限。

## 锁频、PM、profiling与CPU

入场profiling原本为1。基线保持服务active；受控项暂时停止manager，避免其采样重开profiling，
其余KVM服务保持原状态；结束恢复manager及全部sysfs。下表均为私有Mesa，同一原循环10秒。

| 设置 | FPS | 负载期间观察 |
|---|---:|---|
| 自由调频、profiling关 | 234.663 | 61次200ms样本中60次800MHz、1次250MHz（启动阶段） |
| 固定800MHz | 234.612 | 全部800MHz |
| 固定800MHz＋PM on | 234.629 | 全部800MHz，无持续唤醒收益 |
| 上项＋profiling开 | 234.512 | fragment引擎忙碌估计约94.45%，vertex-tiler很小 |
| 固定800MHz＋PM on＋展开 | 588.281 | 单轮诊断值，不替代三轮主表 |

profiling窗口约11.72秒，fragment累计ns增量约11.065秒，cycles增量约8.852G，
两者之比约800MHz；子进程CPU约7.6%单核。fdinfo计时含IRQ/流水估计误差，忙闲并集并不精确。
原循环锁频/PM/profiling差异均小于0.1%，不能解释2.7倍差距；不同服务状态之间不做精确CPU开销归因。
noafbc/nocrc单轮约230.31/228.98fps，未出现显著增益，不能据此改默认压缩策略。

## Vulkan：冷/暖、submit/wait和频率

同一24,883,200字节uint写入程序，复用buffer/pipeline，每次三次预热后测20次。
每组最后6,220,800个uint全量校验通过。厂商heap-codecmm，候选default_cma_region，均为现有连续heap。
系统Mesa无ICD，三轮instance创建-9；未引入软件Vulkan结果。

| 场景 | submit均值ms | wait均值ms | total均值ms |
|---|---:|---:|---:|
| 厂商三轮，每轮20次 | 0.0199 / 0.0298 / 0.0186 | 1.5831 / 1.6486 / 1.9385 | 1.6030 / 1.6784 / 1.9571 |
| 私有默认三轮，每轮20次 | 原文保留 | 原文保留 | 3.0957 / 2.4103 / 3.4375 |
| 私有受控：自由调频 | 0.0912 | 3.2059 | 3.2971 |
| 私有受控：800MHz | 0.0556 | 1.9411 | 1.9967 |
| 私有受控：800MHz＋PM on | 0.0565 | 1.9504 | 2.0069 |

本轮锁频使该短负载total下降约39.4%，保持唤醒未再改善稳态；submit仅占锁频total约2.8%。
默认冷首发约8.30ms，固定800MHz约2.80ms，固定800MHz＋PM on约1.97ms。
这些首发各为一个样本，不能据此给PM算精确百分比；也不能与稳态频率收益相加。
固定800MHz私有均值约2.00ms，厂商三轮均值约1.75ms，参考差距约14%；
厂商未锁频且候选受控项只一组20次，尚不足以宣布稳态严格追平。
没有Vulkan GPU timestamp，wait包含GPU执行、同步/cache和调度；剩余差距不能分成纯ALU/带宽的精确比例。
旧4.25倍冷提交比值不再用作稳态结论。

## CL map定位与HDR范围

最小map程序：4KB/1MB/64MB，普通/ALLOC_HOST_PTR，每组3次，厂商约0.184秒、私有约0.713秒，
全部fill/map/finish/unmap/finish及数据检查通过。独立clpeak transfer：厂商21.51秒、私有51.48秒，均退出0。
私有大buffer map带宽约3.83GB/s，写/读约6.2–6.5GB/s；原始结果保留，不能把慢map混同死锁。
旧120秒包住完整clpeak，单是transfer就需约51秒；本轮没有复现锁死，支持“全程序预算不足”的解释，
不能反推旧运行每个阶段的准确耗时。本轮改为分项有界诊断，没有延长全局超时后冒称驱动已修复。

7.3没有已接通、可直接复用的同一产品HDR/scaler入口：当前主线采集路径为NV12；
已有厂商AMLY GPU路径`gst-plugin-vfmcap/src/codecmm-pool.c:80`固定使用heap-codecmm。
本轮未临时改造大工具或重配源端HDR。4K60 GPU转换/缩放须作为下一项，先适配主线buffer/allocator，
再分别验像素、同步/退休及吞吐；本轮合成GLES/写buffer不能证明HDR4K60可达。

## 收尾与证据

最终`5.15.137-vim4kvm-hdrdual6`，boot ID `e46725fb-fb93-4809-8824-0af660729701`。
One-KVM、HDMI、manager active，UDC configured；无诊断进程遗留，根分区12G/29G、剩余16G。
候选退出前核对min/max=250/800MHz、simple_ondemand、PM auto、profiling=1，与入场一致；
候选taint=0、未见GPU timeout/MMU fault/Oops。删除两个临时boot文件，六个受保护启动文件SHA与入场完全一致。
两把锁已释放，未push。私有运行时与本轮scratch结果保留，不被默认服务选择。

原始JSON、trans_stat、fdinfo、CPU、timer结果及串口日志在忽略目录`logs/gpu-diag-window/`。
`vendor-initial.json`是修正disjoint清除前的数据；主表使用最终vendor.json及system/private.json。
受控项分别在free、800、800-on、profile、unroll、vk-free、vk-800、vk-800-on/result.json。
最终探针SHA256 `3c5a40d7804b629e9857ac26199451498dd22cdc57ced513aae63ef2edfbbd2f`；
DMA探针`a1aef7d75dc6415198e6e881be7551f1233b936da2162167bc2beb9295baffc8`；
CL map探针`1deffaf633cb4bb68cbe0d30fc9a0540cf7ab5481e57a19478844799b1d4a4d4`。

后续优先级：Bifrost循环展开成本模型/精确着色器优化；Vulkan固定频率下GPU timestamp与带宽分离；
实际HDR/scaler路径。暂不改PM/governor默认值或猜测平台寄存器配置。
主仓离线unittest：308项、7项跳过、无失败；GPU timer探针在测量前ARM64 Werror编译，并在三栈实际运行。
