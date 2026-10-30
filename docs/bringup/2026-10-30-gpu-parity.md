# 2026-10-30：GPU 完整性审查与默认降频候选

结论：Panfrost 是完整的上游 DRM 渲染驱动，不是占位驱动；但当前 VIM4 系统尚未证明
达到厂商 5.15 的全部功能和性能。尤其 GLES 3.2、可用于产品的 G52 Vulkan、OpenCL、
HDR DMA 互操作和配对性能仍有缺口。不能把“能渲染”写成“厂商能力全部追平”。
本轮仅板上只读文件检查，无 GPU 负载、服务操作、重启、HID 或声音测试。
用户态打包和后续验收见 [GPU 候选方案](../gpu-parity-plan.md)。

## 固定比较对象及行号约定

以下路径均为 VM `vim4-build` 内源码，相对各自根目录，行号在本轮核对：

- U：`~/src/linux-7.3-hdmi-integration`，`213f271505411`，正式 7.3。
- G：`~/src/linux-7.3-gpu`，`vim4-gpu-panfrost`，从 U 创建，独立工作树。
- V：`~/src/linux`，`80a07ad5406d57855c996285ae75a50a1b9147ae`。
- C：V 下 `common_drivers`，`563cff9dab2c8cd44590bf57c8ffaa7e2dae35e1`。
- B：`~/src/u-boot`，`b60ff51ece0fb05456261b1aabb043db6bd923d5`。
- M：`~/build/gpu-userspace/mesa-25.2.8`，官方 tarball SHA256
  `097842f3e49d996868b38688db87b006f7d4541e93ce86d2f341d8b3e7be7c93`。

下表缩写 P=`drivers/gpu/drm/panfrost/`，K=`drivers/gpu/arm/midgard/`，
D=`arch/arm64/boot/dts/amlogic/`。`U:P/panfrost_gpu.c:257` 即正式源码的明确 file:line。
表中VIM4 DTS指`D/amlogic-t7-a311d2-khadas-vim4.dts`。
既有 [电压审查](2026-10-22-p2-gpu-voltage.md) 和
[PM 审查](../archive/platform-pm-offline.md) 为历史证据，本轮重新检查了关键消费路径。

## 内核差距

| 项目 | 厂商 5.15 有 | 正式 7.3 现状 | 缺口与 KVM 影响 |
|---|---|---|---|
| ID、核心、L2、勘误 | kbase 按 GPU ID 选 features/issues（V:K/mali_kbase_hw.c:35、434），读取核心/L2（V:K/mali_kbase_gpuprops.c:200、328）；C:D/mesont7.dtsi:4723 声明 num_of_pp=4 | U:P/panfrost_gpu.c:230 有 G52 model，:257–311 读 L2/MMU/AFBC/shader mask，:314–378 归一 ID、选勘误并打印 | 既有日志 ID 0x7402 r1p0；不能把 DT 的4当本轮真实核心/L2测量。候选启动需保存实际 masks、L2 features；影响吞吐，未见缺识别路径 |
| 时钟、全部实际频点 | C:D/mesont7.dtsi:4725–4749，双路径 glitch-free clock，实际 tbl 为250/400/500/666/800MHz，顶档重复预热 | U:D/amlogic-t7.dtsi:1078–1100，800MHz默认、core/bus/reset；VIM4 DTS:93–117 已含相同五档 | 频率表已齐，不增加另一通用表的285MHz或未启用的850MHz；仍须同负载驻留/吞吐对照 |
| 电压随频率 | C:D/mesong12a-bifrost.dtsi:43 起各档 voltage=1150；V:K/platform/devicetree/mali_clock.c:433–454 仅 clk_set_rate；V .config:6902–6903 为私有DVFS、非MALI_DEVFREQ | U:VIM4 DTS:207–220 为700000–922000µV PWM regulator且always-on，:906 接 mali-supply；U:P/panfrost_devfreq.c:133–199 在纯频率表时不把 regulator 交给OPP | **未证明厂商实际Linux路径逐频调压**，也未证明闭源固件绝不调压。1150 无有效微伏单位证据，不能乘1000；耗电/温升能力待测 |
| efuse/SMC | B:arch/arm/mach-meson/t7/bl31_apis.c:512 与 oscring.c:130 可取/打印GPU leakage/ring；B:board/khadas/configs/kvim4.h:19 为启动830mV，firmware/timing.c:1037 指PWMAO_E | OPP具备speed-bin入口（U:P/panfrost_devfreq.c:105），T7未提供GPU逐频bin映射 | 未找到GPU电压映射或可审查SMC调压契约；CPU bin不可挪用。保持启动PWM，不试压 |
| governor | 私有DVFS阈值表，V .config:6903 | U:P/panfrost_devfreq.c:96、256，50ms simple_ondemand，45/5阈值；OPP核心调频 | 已有框架，是否性能不低于厂商需实测，不以阈值相同为目标 |
| thermal cooling | C:D/mesont7.dtsi:2992 有gpufreq cooling描述，:3067 有95/105/115°C trips；GPU zone本身未见相应cooling-map，不能直接认定实际绑定有效 | U:P/panfrost_devfreq.c:268 注册devfreq cooling；U:D/amlogic-t7.dtsi:1509 有相同温区；VIM4 DTS:569 默认只绑定风扇，GPU map仅在pm-test.dts:9 | **本轮把已有95°C passive GPU map移到默认VIM4 DTS**；无需猜功率系数。影响过热持续吞吐和保护，实机降频未验 |
| runtime PM/genpd | V:K/platform/devicetree/mali_kbase_runtime_pm.c:219–221 明确T7因reset影响工作而不做pm_runtime_put_autosuspend；C:D/mesont7.dtsi:4722 接GPU域 | U:P/panfrost_drv.c:992–996 默认50ms autosuspend；panfrost_device.c:432–498 空闲检测、关核心、恢复reset；但panfrost_drv.c:1089 的amlogic_data无GPU_PM_RT，故时钟/复位门控分支不执行。单域由core管理（panfrost_device.c:168），T7_MALI_TOP无ALWAYS_ON（drivers/pmdomain/amlogic/meson-secure-pwrc.c:452） | runtime PM已默认启用，非仅实验profile；供电always-on，外部clock gating欠证明，suspended不等于电压归零或关钟。厂商T7的reset限制也是不能直接开启通用PM标志的具体依据；历史恢复不替代当前候选功耗/域状态验证 |
| 复位/故障恢复 | V:K/backend/gpu/mali_kbase_jm_hw.c:494、878 在JM/hwcnt异常路径prepare/reset | U:P/panfrost_job.c:657–801 停scheduler、处理剩余中断、reset/重排；panfrost_device.c:432 恢复硬件 | 路径齐备不能证明所有硬挂死可恢复；不在本轮注入故障。并行KVM时超时恢复必须验证不损坏帧池 |
| AFBC/AFRC | 同一G52硬件；厂商GPU压缩与VDIN私有AMLY压缩不是同一格式 | U:P/panfrost_gpu.c:287 导出AFBC features；include/uapi/drm/panfrost_drm.h:234；M:src/panfrost/lib/pan_props.c:240–260 明确AFBC和AFRC能力判断 | G52是v7，AFRC要求v10，属于硬件不适用，不是移植欠账。AFBC需要Mesa/显示modifier交集；不能据GPU支持认定VDIN/Wave5支持AFBC |
| counters/perf | V:K/hwcnt/mali_kbase_hwcnt_gpu.c:214、330 处理JM dump，Gator配置V .config:6904 | U:P/panfrost_perfcnt.c:48 有采样、:71 单owner启用；DRM PERFCNT ioctl，非通用perf_event PMU | 可做GPU硬件计数；尚缺双方可比的带宽/cache/memory-stall记录。不能把有perfcnt称为已有perf stat GPU事件 |
| fdinfo/利用率 | 厂商mpgpu utilization，不等于DRM客户端统计 | U:P/panfrost_drv.c:746–785 fdinfo引擎/频率/周期统计，profiling门控；:1035–1063 开关。manager已接Panfrost | 功能已有，profiling成本及manager真实sudo CPU预算尚未达标，见[第三轮](2026-10-30-kernel73-gap-r3.md) |
| MMU/大页 | V:K/mali_kbase_gpuprops.c:200 读MMU参数；K/mmu/mali_kbase_mmu.c:1712、2357 区分2MB/4KB页和huge head | U:P/panfrost_mmu.c:372–380、812 为4K/2M页；panfrost_gem.c:196、483 为大对象对齐/heap；不是所有buffer都可用2M | 无“大页完全缺失”；碎片、SG和对齐影响真实命中，需要相同CMA/内存压力对照 |
| dma-buf/共享内存/视频显示 | V:K/mali_kbase_mem_linux.c:1227、1430 导入dma-buf；已有厂商Vulkan→codecmm→Wave521历史验证 | U:P/panfrost_drv.c:951 PRIME导入；panfrost_gem.c:281–399 映射与CPU cache同步；T7 dma-coherent | 具备机制，不代表VDIN→GPU→Wave5→显示已互通。格式、modifier、连续物理内存、fence/所有权/缓存同步仍须逐段像素和生命周期验证；对HDR/缩放是产品阻塞项 |

## 共用 rootfs 的实际用户态

2026-10-30 `ssh vim4` 只读：运行 `5.15.137-vim4kvm-hdrdual6`，
`/sys/module/mali_kbase/version:1` 为 `r44p0-01eac0 (UK version 11.39)`。
先审阅V:K/mali_kbase_core_linux.c:3552–3650，确认gpuinfo读取已缓存属性后，
读`/sys/class/misc/mali0/device/gpuinfo:1`得到`Mali-G52 4 cores r1p0 0x7402`；
这证明本板实际四核，L2容量/分组仍未从当前安全文件接口取得。
`dpkg -l` 证实 Mesa `25.2.8-0ubuntu0.24.04.4`、GLVND `1.7.0-1build1`、
ocl-icd loader `2.3.2-1build1`；没有mesa-vulkan-drivers，没有OpenCL vendors目录。
原始文件在忽略目录 `logs/gpu-parity-20261030/board-packages.txt`、`board-stack.txt`。

| API/切换 | 5.15厂商路径 | 7.3共用rootfs | 产品差距 |
|---|---|---|---|
| EGL/GLES | 私有libMali strings有GLES3.2；系统EGL仍选Mesa，在5.15可能llvmpipe。私库未注册EGL vendor | panfrost_dri.so存在；既有真实Panfrost GLES3.1 Mesa25.2.8日志见[五档验证](2026-10-21-edge-gpu-devfreq.md) | 未在本轮7.3启动确认；GLES3.1低于厂商3.2，不能靠升级或版本override声称补齐 |
| Vulkan | `/usr/lib/vim4-kvm/gpu/mali.json:5` 指向私库，api_version1.3.231；SHA与manifest吻合；历史真实compute验证1.3.231 | 无PanVK库、无系统Vulkan ICD。M:src/panfrost/vulkan/panvk_physical_device.c:271–281 对v7默认拒绝，必须显式实验开关 | 缺安装之外还有成熟度缺口；G52不等同G610的Vulkan认证。HDR转换/缩放不能直接认为可替换 |
| OpenCL | 私库导出clGetPlatformIDs/clGetPlatformInfo，但strings无可靠CL设备版本；没有注册CL ICD | 只有loader，无Rusticl库/ICD | 厂商CL版本也待设备API查询，不能由OPENCL_1.0符号版本或编译器字符串推断。Rusticl可打包，G52设备版本/扩展和clpeak仍待验 |
| runtime选择 | 主仓board/vim4-kvm-run:20–21 显式选择私有Mali Vulkan | 同文件:51 在7.3取消VK_ICD_FILENAMES；EGL由GLVND的50_mesa.json自动探测Panfrost | 已有按内核选择机制，无GPU alternatives项；不能把kbase私库用于Panfrost。新Mesa应私有前缀、逐进程选择，不覆盖共享rootfs |

Mesa官方[能力表](https://docs.mesa3d.org/drivers/panfrost.html)列G52 GLES3.1、
Vulkan1.3和OpenCL3.0，但Vulkan实验支持默认拒载；这些是驱动项目能力，非本板实测。
[Rusticl说明](https://docs.mesa3d.org/rusticl.html)要求显式驱动启用和LLVM依赖。
精确25.2.8行为以本轮已校验tarball为准，不把网站最新表当安装版本保证。

## 性能证据与本轮边界

未找到可用于宣称“5.15硬件GPU vs 正式213f2715硬件GPU”的配对基准。
[10月23日记录](2026-10-23-vendor-boot-gpu.md)的19分是5.15 llvmpipe、4096×2160；
925分是7.3 M1候选Panfrost、1920×1080，后端/尺寸/构建均不同，不能相除。
10月21日五档往返和10月30日40秒负载证明历史功能，不能替代glmark2/vkmark/clpeak配对。
厂商GPU HDR转换历史与7.3整链也没有同条件性能对照。

本轮实施仅DT默认cooling；OPP频率、supply和autosuspend原本已有。
不新增电压、不改主仓packaging/kernel-edge配置，不动NPU工作树，不推送。
离线检查和产物最终状态见[候选方案](../gpu-parity-plan.md)。
