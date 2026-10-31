# kbase r5：MMU 故障隔离与 WC heap 合同

后续[r6窗口](bringup/2026-10-31-kbase-r6-window.md)已复测64位heap、独立证明override必要、
定位并修复DMA升频差距、补GPU thermal绑定；本页保留r5联合修复的原始归因边界。

结论：离线找到两处平台 parity 差异：缺失 T7 PWR_OVERRIDE1 初始化；候选继承的
dma-coherent 与厂商非 coherent DMA API 路径不同。r5 同时修正，不能凭一次联合试验
判定哪项单独足以消除 r4 故障。新增独立内存负载和真实 WC heaps，不修改正式内核行为。
实际[r5窗口](bringup/2026-10-30-kbase-r5-window.md)零fault，API/内存/BO导入通过；
DMA性能与thermal绑定仍有差距。[r4窗口](bringup/2026-10-30-kbase-r4-window.md)是修复前证据。

## 故障解码与定位边界

r4 的首个硬件异常为 GPU_FAULTSTATUS=0x00ff0388，DDK 解码 SHAREABILITY_FAULT，
地址 0x3ff7fffa80。AS0 随后记录 raw status=0x6c002c1：低 8 位 0xc1，
TRANSLATION_FAULT；[9:8]=2 READ；[31:16]=0x6c0 source。
VA 0x2a6843288 与下一进程的 0x68b276758 均报告“Memory is not mapped on the GPU”。
不能只凭 VA 数值判断它属于 dma-buf、JIT、tiler heap 或 ring。旧进程 region 图未封存，
事后不能恢复其分配归属。后续 JS 的 0x4002 = BASE_JD_SW_EVENT | 2，
即 JOB_CANCELLED，是软件取消事件，不能解释成 MMU exception type。

新增第七块补丁在既有 fault worker 的 context 引用内、VM 锁保护下打印 region 起始页、
页数、alloc type、flags、JIT list 状态；free/unmapped 明确打印，protected fault 不打印。
它帮助区分 imported UMM/native/growable；native 内部 ring 与 tiler 的准确用途仍可能需要
用户态分配记录，不能把 JIT list 状态当作完整 heap 类型。没有新增寄存器扫描接口。

## 与厂商路径逐项复核

| 路径 | 结论与行动 |
|---|---|
| T7 reset / 时钟 / 域 | 厂商 platform/devicetree/mali_kbase_runtime_pm.c 的 mali_hw_init 在 reset 后写 PWR_KEY=0x2968a819、PWR_OVERRIDE1=0x200fff；当前 7.3 Panfrost 的 amlogic quirk 也写同值。r4 dump 为 0。第六块在 kbase_pm_init_hw 成功 reset 后、hw issues/coherency/core power-up 前应用具名平台 hook；复位失败不写。域继续常开，不增加门控、不改电压/SMC |
| DMA coherency | 5.15 mesont7.dtsi 为 system-coherency=0，mesong12a-bifrost.dtsi GPU 无 dma-coherent。r4 保留上游 GPU 的 dma-coherent，导致 DDK 同为 ACE-Lite=0，但 DMA API 可跳过 cache 维护。r5 专用 DT 删除该标志并显式 system-coherency=0，匹配厂商；默认 Panfrost DT 不改 |
| dma-buf reservation | r1 三处 map/unmap 使用 unlocked helpers，由核心管理 reservation 锁；没有持锁后再次 unlocked 的叠加。attach/detach 与 CPU begin/end 配对保留 |
| SG / DMA 地址 | 导入遍历 sg_dma_address/sg_dma_len，保留映射后 nents 语义；没有改成 sg_phys 或复制其他设备的 DMA 地址。新 exporter 每次 map 建独立 SG 并通过 importer 的 DMA API 映射 |
| GUP / mmap | 新 GUP 参数适配不改 pin/unpin 生命周期；USER_BUFFER 才走 GUP，DMA fd 导入不用 GUP。vm_flags_set/clear 仅替代直接位写；未改 mmap offset、vm_ops、页所有权 |
| 页表属性 | mmu/mali_kbase_mmu_hw_direct.c 的 MAIR/memattr、outer-shareable PTW 与条目编码未被适配补丁改变。system_coherency 沿用 ACE-Lite，不能把 Shareability fault 直接等同于 MAIR 索引错误 |
| r3 timer/workqueue | 保留原 bound/unbound 选择与 timer callback；没有改变 GPU cache flush/MMU command 顺序。宿主模型验证初始化合同，真实并发压力仍未验 |
| shrinker / devm / of | 保留 r3 的 shrinker_free 同步注销、devm 资源与手工 enable/disable 分工、OPP node 引用修复。没有新证据要求改模型；并发回收/系统睡眠未验 |
| PM / clocks | 外部域持引用、bus 常开、core 由原 kbase 管；五档 OPP 对齐现有平台，不写 PWM。r4 的“unstable clk/pwr”是驱动超时诊断模板，不能据此断言电压不稳 |

## WC heaps 与离线门禁

实现、厂商来源、上游提案关系、生命周期限制和容量差异见
[heap 合同](../packaging/kbase/heaps/README.md)。模块与 kbase 一起构建，独立候选
reserved-memory 节点提供 128 MiB reusable CMA，正式树没有新的 exporter 或行为改动。
不提供 heap-secure，不把任意 CMA/system heap 改名。

build.py 自动执行运行时 API 模型、T7 reset key-protected 寄存器模型、实际 mmap
代码的 host VMA/DMA 边界测试、UK 布局与 UAPI 字节比较、两个模块 W=1/Werror/modpost。
check-style.py 审查完整 series；新两块无风格提示，heap C 单独 strict checkpatch。
这些检查不模拟 GPU MMU、DMA cache、真实调度或 fence 竞争，不能代替板测。

## ≤30 分钟窗口

先取得 board→heavy 双锁，确认 5.15、串口空闲、四服务/UDC，记录六个启动文件 SHA。
候选完整模块、DT、Image、init 与运行时快照均先验证 SHA，再临时安装助手。
只从 RAM sysboot 选择独立 kbase-r5-once 路径，默认项与默认 DT 不变。

1. 加载两个模块，核对 /dev/mali0、两个真实 heap、UK、PWR override 读回、完整 dmesg。
2. 每进程独立的 VK 16 KiB kernel：device-local、host-visible、cached system、default CMA；
   再测新增 WC system/gfx。原生 device-local 通过独立 staging copy 校验；UMA 内存类型
   可能同时有 device-local/host-visible 标志，打印 flags，不声称物理内存分离。
3. CL 同类分配、单个 4096-word kernel 与逐字读回；DMA 导入使用 clImportMemoryARM，
   不支持或属性错误明确记录，不能伪装成执行通过。
4. EGL/GBM FBO GLES 像素校验；独立 GBM BO 导出到显示 DRM 的 PRIME handle 冒烟，
   用 GPU_GBM_EXPORT=render 或 scanout；linear 是另加 LINEAR 要求的负向诊断，两栈均不支持。
   该步骤不等同于实际 scanout，也不是 Wave5 编码格式/stride 验收。
5. 之前全部无 fault 才做三次 GLES/25 MB DMA 配对、CL latency/SP 子集、五档 devfreq
   读回与 thermal 绑定、HDMI+Wave5 alone/with-GPU 对照。与本轮 5.15 使用同一探针。

每项带 timeout，均小于 10 分钟；轮询 dmesg，首个 DEVICE_LOST/MMU fault 终止该项，
保存完整日志。只有恢复明确完成且没有新 fault 才继续独立项；WARN/BUG/oops 或
恢复不能建立立即终止整窗。没有现场改驱动、猜电压或盲扫寄存器。
最后恢复五个助手、正常回 5.15、四服务 active、UDC configured、六个启动 SHA 与原助手
SHA 一致，再释放双锁。清旧窗口只处理已下载证据的 kbase-window/kbase-r3-window 及其归档；
不碰其他会话目录或 usb 状态目录。

下次优先比较同为25 MB的cached CMA/WC heap-gfx，解释本次DMA 3.571ms与5.15
1.708ms差距；读取具名GPU core/bus时钟与缓存属性，不以CL元数据5MHz代替实际时钟。
另需在专用候选DT补GPU thermal map后再验绑定；当前95°C map指向MCU，不是GPU。
此后才做同一GBM BO的实际scanout或符合Wave5格式/stride的编码，当前仅验证PRIME导入。
最终exporter改为厂商相同的64位DMA mask，避免高地址system页初次维护走bounce；
这项退窗后的修正仅离线验证，先完成新heap/高地址页复验，再开展其余项。
