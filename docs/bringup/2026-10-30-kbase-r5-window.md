# 2026-10-30：kbase MMU/WC heap 修复及三栈配对

结论：r5 在7.3上零WARN、零GPU/MMU fault，EGL/GLES/VK/CL查询、六类内存kernel、
GBM BO导出与显示DRM导入通过。GLES/CL达到本轮5.15水平，25MB Vulkan DMA仍约慢一倍；
GPU cooling注册但未绑定thermal zone，不能推广为默认。
本页板测哈希属于release3；退窗后发现并修正exporter DMA mask，release4仅离线通过，见末节。
[修复与合同](../gpu-kbase-mmu-heaps.md)说明源码审计及下一窗口；[r4](2026-10-30-kbase-r4-window.md)为修复前证据。

## 窗口与固定输入

先发现HDR2A3持board/heavy双锁，等待其释放；此前没有连接板子。
本会话UTC 2026-10-31 04:59:57取得双锁，确认5.15 hdrdual6、四服务active、UDC configured。
05:11:28已完成回退、证据复制及释放锁，总计约11分31秒。Mac本地任务日期10月30日。
只用vim4-kvm-kbase-r2和VM linux-7.3-kbase，未动HDR/主/Panfrost工作树。

| 封存对象 | 值 / SHA256 |
|---|---|
| 正式内核基线 | f71b5c6289cb3254690e57292327e73514f0715f，7.3.0-vim4kvm-uhd3+ |
| build ID | a3572361d542e5505bd159ad8a327cf364fe25f3 |
| Image | 9daea7a17e228cb5ef93b6b9cc926ccce43ec3b8eafb1b22aee447fdcfcb7000 |
| mali_kbase.ko | 19f41217a32db1f8e44e80146616473a3cfca980e355c9cb4543014bc94c488a |
| vim4_kbase_heaps.ko | f4b12d22f600137e4f81f97f9cdbb460980ffa0f8f390afa98786a4fd9ea3936 |
| 候选DTB | a2ce787f9064983b7c558c1b2820bf58b4c2952b2c442fd33ad8e2afe6dee3ea |
| 完整候选归档 | d71a4897cab5990c9c909ead2ee88a2b151863de95214afd1a0b578c8dc12d46 |

VM封存为~/build/kbase-r5/release3和~/build/kbase-r5-board-final；完整原模块集2351个，
另加两个外部模块并depmod。静态init先校验release/build ID再bind私有完整模块目录。
RAM sysboot选择/var/lib/vim4-kvm/kbase-r5-once/a357…/extlinux.conf；未改默认启动文件。
五个助手按runtime manifest临时同步；UK保持r44p0-01eac0 11.39，blob SHA不变且未上传源码仓库。

## 故障修复的证据与归因

r4首先报SHAREABILITY_FAULT，随后0x6c002c1 = TRANSLATION_FAULT/READ/source0x6c0。
JS 0x4002是软件JOB_CANCELLED，不是MMU异常码。旧VA日志报告unmapped，不能事后认定是dma-buf/JIT/ring。

本轮联合修复两项：成功GPU reset后写厂商/上游Panfrost相同的T7 PWR_OVERRIDE1；
候选删除dma-coherent，显式system-coherency=0，恢复5.15的DMA API维护路径与DDK ACE-Lite选择。
本轮5.15实树/bifrost/system-coherency为0，GPU及root均没有dma-coherent，核实了离线DTS结论。
7.3读回override=0x200fff，/dev/mali0出现，私有GPU compatible绑定mali。
没有修改SG/GUP/MAIR等路径来掩盖错误，没有电压/时钟猜测或新增域门控。

所有后续负载及最终完整dmesg均零WARNING/BUG/oops、零GPU/MMU fault/DEVICE_LOST。
说明联合修复足以通过本组负载；**没有单独回退任一项的A/B，不能宣称唯一根因已证明**。
新增fault-region诊断因没有故障而未在硬件触发，不补造旧进程region归属。

## 三栈API与配对性能

| 项目 | 5.15 libmali，本轮 | 7.3 kbase+libmali，本轮 | 7.3 Panfrost，历史 |
|---|---|---|---|
| EGL / GLES | ARM 1.5 / 3.2 | ARM 1.5 / 3.2，像素校验通过 | 1.5 / 3.1 |
| Vulkan设备API | Mali-G52 1.3.231 | Mali-G52 1.3.231 | 1.0.354，实验 |
| OpenCL设备 / C | 3.0 / 3.0 | 3.0 / 3.0 | 3.0 / 1.2 |
| GLES FPS，三次均值 | 619.825 | 648.419 | 233.730，非本轮配对 |
| Vulkan DMA submit+wait ms，均值 | 1.708 | 3.571 | 旧中位数8.038，非本轮配对 |
| CL kernel latency µs | 80.30 | 51.05 | 无同子集样本 |
| CL SP float GFLOPS | 101.73 | 101.75 | 无同子集样本 |

硬件均为Mali-G52，没有llvmpipe/lavapipe。相同blob与工具，5.15先测、7.3后测。
EGL/GL/VK device/CL device扩展集合分别28/98/95/52，两侧完全相同；不是CTS或全功能证明。
私有EGL前缀及独立VK/CL ICD继续使用，不注册伪GLVND vendor、不覆盖Mesa。

GLES相同512×512 GBM/FBO、loop128 shader、2秒预热/5秒稳态：
5.15三次620.568/620.135/618.772；候选649.168/648.047/648.042 FPS，中心像素校验通过。
DMA相同24,883,200 bytes/6,220,800 words shader，三次逐字校验PASS：
5.15 heap-codecmm 1.750/1.815/1.558ms；候选default_cma_region 3.553/3.589/3.571ms。
这是原验收同负载的不同内存exporter配对，**不是同cache属性/同heap的严格吞吐归因**。
未在本轮补测25MB WC heap-gfx；缓存属性、core/bus时钟等贡献留待下一窗分离。
GPU/温度未统一锁定，不能把约4.6%的GLES增益当作普适性能收益。
5.15 clpeak打印的“5MHz”是设备元数据，未用它代替实际时钟。

## 内存二分与heap互操作

每项独立进程、16KiB/4096 words，只提交有界kernel并校验全部输出。

| 分配路径 | VK | CL |
|---|---|---|
| 原生device-local | PASS | 普通CL buffer PASS |
| host-visible | 直接map目标读回PASS | ALLOC_HOST_PTR PASS |
| cached system导入 | PASS | clImportMemoryARM PASS |
| CMA导入 | 5.15 codecmm / 7.3 default CMA PASS | 两侧PASS |
| 新system-uncached | 7.3 PASS | 7.3 PASS |
| 新heap-gfx | 7.3 PASS | 7.3 PASS |

VK原生两项实际均选memory type0、flags=0x7，这是UMA重合类型；device-local项没有导入dma-buf，
通过staging copy校验，不能宣称获得物理独立显存。CL同样不保证离散显存驻留。
新heap模块实际创建WC system pages和独立CMA连续WC buffer，不使用别名。
CMA池128MiB、物理范围校验、模块不可卸载等限制见[heap合同](../../packaging/kbase/heaps/README.md)。

最初ARGB8888 RENDERING|LINEAR的GBM BO创建两栈均退出2，errno可能保留旧值，
不能把这个ENOENT重新归因为缺heap。补测同一BO创建的标准用法：
ARGB8888+RENDERING和XRGB8888+SCANOUT，两栈均成功分配、导出dma-buf，
在显示card0的**另一个DRM文件**PRIME_FD_TO_HANDLE得到handle1、stride1024并关闭自己的handle。
LINEAR附加要求不支持；内部拒绝原因未反汇编确认。
这是BO分配/导出/显示DRM导入冒烟，FBO像素校验是另一对象；
没有把该BO真正scanout，也没有将其送入Wave5，不宣称完整端到端显示/编码互操作。

## devfreq、thermal与HDMI/Wave5

userspace governor逐档800/666.666666/500/400/250MHz运行完整DMA shader并读回精确目标频率，
五档均PASS，finally恢复simple_ondemand。没有写PWM或电压。
GPU cooling_device3注册为devfreq-fe400000.gpu，cur_state=0/max_state=4。
但gpu-thermal下没有GPU cdev绑定；DT既有map为phandle0x51、30..100，指向MCU，
GPU节点无被引用phandle。95°C trip的存在不证明GPU被thermal限频，**绑定验收失败**。
本轮未触发过温，也未现场修改DT。

HDMI 3840×2160@60 NV12→Wave5 H.264 high 5.1，20Mbps/GOP60，预热60帧、计时600帧：

| 项目 | 单独视频 | 并行GPU |
|---|---|---|
| 稳态fps | 59.998304 | 59.998300 |
| source→encoded P95 ms | 11.388 | 11.530 |
| 同端点P99 ms | 13.007 | 14.599 |
| 全板CPU % | 3.537 | 14.396 |
| VPU IRQ / capture IRQ | 601 / 600 | 601 / 600 |

并行期间完成26个独立DMA进程；两个bench success=true、660输入/输出帧、taint均4096仅外部模块位。
source→encoded是板端端点，不是WebRTC端到端延迟；本轮不保存/解码码流，不是画质验收。
并行CMA快照采于GPU仍活动时，不能将差额解释为泄漏或声称已通过长期内存压力测试。

## 离线检查、恢复与后续

两个模块W=1/KCFLAGS=-Werror、modpost/BTF通过，UK 34种payload/40个ioctl及UAPI字节不变。
实际包装函数host模型、T7 protected-key重复reset模型、heap mmap与pool越界/溢出模型通过。
新两块补丁及heap C strict checkpatch零提示；旧series仅保留已审阅提示。
DTS源码编译与display-m0均有同三条既有warning，没有新增DT诊断。
主仓完整unittest 317项通过，10项因本工作树环境跳过；没有把跳过记为执行通过。

证据位于本工作树logs/kbase-r5-window：build-manifest.json、vendor/candidate各查询/负载文本、
api-extension-compare.json、parallel.json、video-*.json、candidate-final-dmesg.txt、final.json。
retired-windows.tar.gz完整保存旧两窗21文件/104,528,202 bytes，retired-proof.json逐文件SHA核验后，
才删除板上kbase-window/kbase-r3-window及其内部大归档；未碰其他会话或USB状态目录。

五助手原内容/原本不存在的文件、六个启动SHA全部核验恢复；5.15 hdrdual6四服务active、UDC configured。
未发HID、未测声音、未ptrace视频进程、未推blob、未刷eMMC/U-Boot。
后续优先补GPU thermal候选map、cached/WC大buffer吞吐对照，再验真实scanout/Wave5导入与压力/睡眠。
这轮解决执行正确性阻塞，不代表默认切换或完成API/性能全量parity。

## 退窗后的64位DMA mask修正：尚未复测

最后源码审计发现，新exporter设备原设32位DMA mask；5.15 system-uncached用64位。
对于高于4GiB的普通system pages，初次DMA map若走bounce，维护的可能是bounce页，
不能保证原页的cached清零别名已被清理。16KiB测试通过不覆盖这类延迟cache驱逐风险。
提交源码改为64位mask，确保初始维护面向原页；heap-gfx仍经独立池alloc-ranges与物理范围
检查限定在4GiB以下，不需要借32位mask实现池范围合同。

VM ~/build/kbase-r5/release4已重新完成两个模块Werror/modpost、ABI和host模型，strict风格通过；
heap模块SHA为ac508a4e378155493aad704a6cafae00c6c744188ff14e4f73487226aa96d939，
其source SHA为ae91c195ba705733c49a8fa57a6886bc07f7b3ad7b01ef4c2dd9aaa6d1f58ddb。
对应heap64-build-manifest.json/heap64-build.log另存本窗logs，未覆盖release3板测封存。
再次检查发现HDR2_R15已占board/heavy锁，没有再次连接板子。**64位mask版未上板**，
不能把本页小buffer、BO与并行结果写成最终heap模块的硬件通过证明。
下窗先重验新heap及高地址system pages，再做25MB WC/cached配对与thermal绑定。
