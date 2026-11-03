# 2026-10-31：kbase DMA性能追平与独立二分

结论：DMA差距来自短负载下的GPU频率历史；同heap-gfx、800MHz时7.3已追平5.15。
新增T7专用performance governor默认值与95°C GPU cooling map，64位heap实测通过。
override遗漏被独立复现为首个原生compute的MMU fault；dma-coherent恢复的最小对照通过。
实际scanout、GBM NV12→Wave5仍缺可靠布局元数据，**不提交可批准的产品路径方案**。
维护入口见[候选状态](../gpu-kbase-7x.md)，前次见[r5](2026-10-30-kbase-r5-window.md)。

## 资源、封存与恢复

UTC 05:29:34开始等待HDR r15双锁；06:29:40锁空闲后取得board→heavy独占，
确认5.15 hdrdual6、四服务active、UDC configured、串口空闲。等待约60分钟，未抢锁。
依次RAM启动base、performance、coherent、nooverride四个独立候选，06:55:18恢复并释放，
总窗口约25分38秒。无HID、声音、视频ptrace、PWM/电压写入、U-Boot/eMMC刷写或blob推送。

正式Image仍为f71b5c6289cb / 7.3.0-vim4kvm-uhd3+，build ID a3572361d542e5505bd159ad8a327cf364fe25f3。
完整原模块2351个加两个外部模块，每候选静态init先核验build ID再挂匹配模块集。
全部仅在kbase-r6-*-once私有目录，默认启动项/5.15/默认Panfrost DT未变。

| 板测performance候选 | SHA256 |
|---|---|
| mali_kbase.ko | 81cbf9d2354f6b168c0072b56ff85df3e2fab267bbfd3419083345824f1343dd |
| 64位heap模块 | 647ae98519a7ad8714ecb703f588b450f9ae0b05e9bdfc21fd452ada00b1de0b |
| DTB | 63e5b3c77f2370e41b535ad451770db3ace80f169275b952764ce8f6fea3b1c5 |

板测源码/完整归档位于VM ~/build/kbase-r6-board-performance，模块源码为performance-source；
最终series另在~/build/kbase-r6/release全量重放构建通过。不同绝对路径的debug信息导致ko SHA不同，
板测认定以上述封存为准，不把release的新SHA写成实际加载过的字节。

五助手退窗前恢复。5.15启动后One-KVM一度inactive，显式启动后再次完整核验：
四服务active、UDC configured、六个启动SHA与进入值一致，五助手原SHA/原先不存在状态一致。
证据下载后立即释放锁；稍后其他会话已再次占锁，没有再访问板子。

## DMA根因：同合同、频率、GPU时间与cache计数

相同24,883,200 bytes shader/SPIR-V与逐字读回，heap-gfx均为连续WC合同；
两核实现/池地址不同，不能说是跨重启的同一物理buffer。

| 条件 | 频率逐提交读回 | 10个稳态submit+wait均值ms |
|---|---|---|
| 5.15 heap-gfx | 800MHz | 1.574 |
| 5.15稍后heap-codecmm | 250MHz | 3.797 |
| 5.15稍后cached system | 250MHz | 3.713 |
| 7.3 base heap-gfx | 250MHz | 3.570 |
| 7.3 base default CMA | 250MHz | 3.578 |
| 7.3临时performance、heap-gfx | 800MHz | 1.522 |
| 同条件default CMA | 800MHz | 1.507 |
| 修复模块重新启动、heap-gfx | 800MHz | 1.493 |

5.15的cur_freq单位MHz，由clk_summary频率佐证；7.3 devfreq读回单位Hz。
**5.15也会降至250MHz**，不能把旧1.708ms当作所有idle历史下的固定性能。
7.3 simple_ondemand轮询无法对毫秒级突发及时升档；GPU timestamp诊断约3.400ms，
接近该组fence wait。保持相同heap/PM/cache路径，改为800MHz即降至约1.5ms，
排除了heap来源、每次唤醒或整块cache维护是本组主要差距的解释。
外部电源域始终持引用，未新增门控；没有据此宣称系统睡眠或所有内部PM延迟已验。

修复为0008-t7-devfreq-policy.patch：仅vim4平台选上游performance governor，其他平台仍simple_ondemand。
它保持可见的五档OPP与devfreq thermal上限，不修改电压、不绕过thermal约束。
这是一项产品性能策略，代价是活动频率常取最高档；未测功耗，不能宣称能效与5.15相同。

dma-profile.py在独立trace实例内启用具名DMA事件和arch_sync_dma_for_cpu/device kprobe，
ARM64参数/SG布局已由源码及pahole核对。逐提交begin/end marker及频率读取在计时之外。
plain轮次同时禁用事件，避免仅tracing_on=0仍保留kprobe trap开销；trace轮次另加GPU timestamp，
不将它的扰动后耗时当性能门禁。保存per-CPU overrun统计，均为0。

两核每个heap各10个计时样本：**24.9MB整块cache维护均0次/0字节，SG sync请求均0次**。
7.3样本区间arch cache字节总量为0；5.15各组仅有合计4/8/12KiB的全局小操作，未归因于Mali。
初始化和最终CPU读回可见24.9MB维护，发生在marker之外。故不能以“编译启用ION workaround”
推断它每次执行；MAP_ON_DEMAND与LEGACY_COMPAT两核源码配置也均关闭。
预编译的exporter-callback试验版因此未上板，未加入series；没有为了提速跳过cache维护。
页表MAIR/shareability编码仍是同份r44源码，未为性能修改。

## API、内存与并行

| 项目 | 5.15本轮 | 7.3修复模块本轮 | Panfrost历史 |
|---|---|---|---|
| EGL / GLES | 1.5 / 3.2 | 1.5 / 3.2 | 1.5 / 3.1 |
| Vulkan设备 | 1.3.231 | 1.3.231 | 1.0.354 |
| CL设备 / C | 3.0 / 3.0 | 3.0 / 3.0 | 3.0 / 1.2 |
| GLES三次均值FPS | 614.091 | 648.903 | 旧233.730，非本轮配对 |
| heap-gfx DMA三次均值ms | 1.770 | 1.509 | 旧8.038，非本轮配对 |
| CL latency µs | 79.66 | 48.00 | 无同子集 |
| CL SP float GFLOPS | 101.73 | 101.76 | 无同子集 |

均为真实Mali-G52，无llvmpipe。GLES同512×512 loop128 FBO、2秒预热/5秒计时及中心像素校验。
三个DMA修复样本1.478/1.556/1.493ms；独立profile提供了频率一致的十样本对照。
API查询与扩展原文完整保存，不是CTS声明。

64位heap模块在正常候选与policy修复候选均零kernel WARNING/BUG/oops、零GPU/MMU fault。
Vulkan原生device-local、host-visible、cached system、system-uncached、heap-gfx最小kernel通过，
default CMA在25MB profile中通过逐字校验，合计六种路径。
CL本轮通过上述前五类；测试器因将性能heap改为gfx而重复了一次gfx，
**default CMA的CL本轮未重测，沿用r5结果**，不把六次调用说成六种不同CL分配。
原生VK类型仍为UMA重合type0/flags0x7；WC system的64位mask未回退为32位。

修复模块的五档800/666.666666/500/400/250MHz均完成负载与频率读回，最后恢复performance。
HDMI NV12 3840×2160@60→Wave5 H.264，warmup60/measure600 frames：

| 条件 | FPS | source→encoded P95/P99 ms |
|---|---|---|
| 视频alone | 59.998290 | 11.385 / 14.147 |
| 并行GPU、26个DMA进程 | 59.998306 | 11.555 / 13.063 |

均success=true，无新增taint位；这些是板端端点、无payload-read，不是WebRTC延迟或码流画质验收。

## 两项平台修复的独立二分

| 保留/去掉 | 结果与维护依据 |
|---|---|
| 保留override，恢复dma-coherent | 三个16KiB原生/host/gfx负载均通过；删除dma-coherent并非这组最小负载的必要条件 |
| 不写override，保持非coherent DMA | PWR_OVERRIDE1读回0，首个纯device-local kernel即AS0 translation fault，立即TERM该项；没有导入DMA fd也能失败 |

负向fault为0x6c002c1/READ/source0x6c0，VA0x385a42b78，region诊断unmapped/free。
随后AS_ACTIVE/cache-clean超时并发生soft→hard reset；取日志后直接回5.15，不做现场驱动修补或重复提交。
这独立支持保留0006（亦与厂商/Panfrost初始化一致），不能把“clk/pwr不稳”模板当电压诊断。
删除dma-coherent仅保留为r44/5.15保守缓存合同；其必要性没有被证明，更没有证明所有coherent压力场景都安全。

故障强制终止还暴露destroy_kctx_worker进入旧system_wq的deprecated提示。
它不是正常候选加载/负载的kernel WARN，但属于待补兼容路径，未在本轮偷偷改成未经复测的模块。

## thermal与BO实际互操作边界

5.15只读sysfs中gpu_thermal没有cdev链接，源码95/105°C passive、115°C critical；
AMLogic gpufreq还包含私有cooldev机制，未将其猜测为已生效的标准绑定。
7.3新增独立kbase-throttle：95°C passive/5°C hysteresis、GPU states0..4，保留原MCU map。
实测gpu-thermal/cdev0→devfreq-fe400000.gpu、trip0→95000/passive、cur0/max4，绑定及trip作用路径存在。
未加热到95°C、未用emul_temp或写PWM，不能称真实过温限频闭环已触发。

render/scanout GBM BO导出到显示DRM handle继续通过。实际scanout工具取得现有CRTC/FB并要求完整
线性单平面元数据，blob不能建立该合同，故在SetCrtc前拒绝；没有改显示mode或破坏采集。
NV12 BO通过plane FD接口导出：98304 bytes、2 planes，但modifier=72057594037927935（INVALID）。
不能猜成LINEAR；Wave5的NV12布局协商/QBUF分支因此没有执行，更无编码输出结果。
这两项仍未通过，工具的恢复/编码正向路径也未被硬件验收。

## 验证与证据

W=1/Werror、modpost/BTF、UK11.39 UAPI字节/34 payload/40 ioctl、宿主runtime/heap模型通过。
0008 strict checkpatch零提示；DT编译只有与base相同的三条既有warning。
新增DT图引用测试覆盖GPU原本有/无phandle，证明既有GPU consumer与MCU map未被覆盖。

logs/kbase-r6-window保存四候选串口、vendor/base/performance profiles与overrun统计、cache-summary.json、
performance-positive-dmesg.txt、coherent/nooverride-result.json、scanout.txt、wave5-gbm-retry.txt、final.json。
首次baseline因诊断文件bisect.py遮蔽stdlib失败，没有执行GPU；改名gpu-negative.py后重测。
旧tracefs拒绝Python append初始化seek，改raw fd后取得完整追踪；失败轮次未计入数据。
