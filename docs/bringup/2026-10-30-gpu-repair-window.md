# 2026-10-30：同块回跳修复与快轮询上板窗口

按[离线修复清单](../gpu-loop-repair.md)执行；方针**用户已于 2026-10-30 确认**。
所有数据是固定合成负载的有限验证，不代表GPU API/CTS或产品HDR性能已追平。

## 入场与候选

取得Mac的board→heavy两把lockf锁，并持有工作区board锁后才访问板子。
入场为5.15.137-vim4kvm-hdrdual6，未发现运行的NPU门禁进程；One-KVM、vim4-kvm-hdmi、manager均active，UDC configured。
未读改NPU文件/worktree；主仓并行NPU修改保留。未发HID（被控机Mac mini M6）、未测声音、未ptrace视频进程、未写PWM/电压，未push。
模块安装/静态PID1编译均在首项测量前结束，测量期间本任务无编译；VM进程快照亦未见编译。
每个GPU负载有10/25/90秒等超时，配对批次外层360秒限制；各项小于10分钟。

Mesa原版、仅GCM与repair3（0003–0006）均为26.2.6，私有前缀隔离，未替换系统Mesa。
repair3归档SHA256 `d8d76d3646cbfd7e3b14ec561668efb2df263bb814b25e2ef71749db06223c15`，传输后相同。
原版/GCM/厂商使用同一个已有GPU探针，原循环和显式展开仅以进程环境变量选择。
PanVK开关仅传测试子进程，没有修改全局ICD。

第一启动使用已验证e99220d902834 boost核及其完整只读模块，避免把Mesa修复与新内核混为一次干预。
第二启动为`vim4-gpu-panfrost@4ccae3570a97e`快轮询核，同次完整模块通过私有PID1只读挂载。
该系列还含88b3的等价workqueue弃用告警修正；两核是具名候选系列配对，不声称是位级单补丁隔离。
暂存tar SHA256 `93c0b297f8f95dfb5f0e3bc4ced573afa0b4adc044345731ecbf6bf31df560fe`。
因Panfrost为模块，两核Image与build ID相同，不能只凭Image/release识别模块候选。
新候选独立于旧目录，位于`/var/lib/vim4-kvm/gpu-repair/a894778bb3020cccc21d8b8e41fd4de423a8f3ed`。
复用已验证GPU cooling DT副本以保留HDMI/MAC配置；U-Boot RAM sysboot选择，未saveenv，默认5.15入口不变。
第一次快轮询启动因归档保留构建用户属主，PID1在module directories检查处拒绝并自动回5.15。
仅对本候选目录规范root属主后重新一次性启动成功；未绕过校验，未混载模块，失败串口单独保留。

## 正确性与GLES配对

512×512 GBM/FBO、RGBA8、每项2秒预热＋10秒稳态、draw＋glFinish，无swap/vsync，回读不计FPS。
5.15先做同窗三轮；7.3关闭manager采样、profiling=0、10ms采样，CPU performance，结束恢复。
先执行原版/GCM/repair3各原循环和展开的短负载门禁，保存完整1MiB RGBA，逐字节与对应原版比较。
六个门禁负载均退出0，GCM和repair3两种着色器均全帧一致；门禁GPU timeout/fault计数零增量，才继续性能项。
随后三轮配对亦无新增GPU错误。5.15两图、三套Mesa六图、新核两图共十张完整RGBA具有同一SHA256：
`c296f080f24ccffb54d835d0643b8ab3a34c1706ee76cb87bb5ac170f226702f`。
没有采用新像素容差；该抽查不覆盖divergent循环、导数、纹理或产品色彩路径。

| FPS三轮 / 平均 | 5.15 libmali | 7.3原版26.2.6 | 7.3仅GCM | 7.3完整修复系列 |
|---|---:|---:|---:|---:|
| 原循环 | 614.815 / 614.271 / 613.082 | 234.707 / 234.783 / 234.904 | 272.068 / 272.106 / 273.050 | 340.238 / 339.423 / 339.486 |
| 原循环平均 | 614.056 | 234.798 | 272.408 | 339.716 |
| 显式展开 | 574.265 / 573.965 / 575.512 | 583.016 / 581.630 / 582.080 | 587.476 / 581.248 / 582.556 | 586.314 / 584.880 / 592.393 |
| 显式展开平均 | 574.581 | 582.242 | 583.760 | 587.862 |

完整修复系列原循环较GCM提升24.7%、较原版44.7%，仅为厂商原循环55.3%吞吐，尚需约1.81倍提升才能追平。
与热区5→4tuple的预测方向一致，但不能由此将每项分支/依赖等待精确分摊。
同窗厂商参考与历史612.7fps接近；展开版接近厂商并不等于保留循环、API或产品HDR路径追平。
无已打包CTS小子集参与本轮，固定全帧检查不能证明完整系列对所有uniform/divergent shader均正确。

## 冷恢复：快轮询没有有效收益

两核使用同一GCM PanVK、同一uint DMA compute（24,883,200字节），进程前空闲1秒；
每进程首提交、3个预热、20次暖提交，所有6,220,800个uint完整校验通过。普通计时与trace分开。

| 项目ms | 原boost内核e992 | 快轮询4ccae |
|---|---:|---:|
| 冷首发三轮 | 4.730 / 4.735 / 4.562 | 5.406 / 4.674 / 4.655 |
| 冷首发均值 | 4.676 | 4.912 |
| 暖提交每轮均值 | 2.028 / 2.009 / 2.017 | 2.053 / 2.016 / 2.021 |
| 暖提交总均值 | 2.018 | 2.030 |

新候选没有改善冷首发，均值约+5.0%，首轮偏慢；三样本不能证明稳定回退5%，但足以否定本轮存在明确收益。
频率/PM前后状态及驻留在JSON中；未使用新OPP、写电压或永久锁频。

独立function_graph实例只过滤具名GPU函数及新wait_ready helper，结束切回nop并删除。
按源代码调用顺序将新helper的三次调用对应L2、shader、tiler，不读未审核MMIO。

| 单次独立trace | 原boost | 快轮询 |
|---|---:|---:|
| runtime resume μs | 2679.833 | 2646.125 |
| soft reset μs | 4.208 | 4.000 |
| power_on μs | 2410.166 | 2418.917 |
| L2等待helper μs | 未分段 | 270.292 |
| shader等待helper μs | 未分段 | 2140.208 |
| tiler等待helper μs | 未分段 | 0.958 |
| devfreq resume μs | 241.709 | 205.916 |

L2和shader均超过10µs快轮询预算，仍进入睡眠回退；shader占本次power_on约88.5%。
helper耗时包含硬件就绪和睡眠/唤醒成本，不能单凭该trace断言2.14ms全是硬件本征延迟。
不增加忙等时长、不并行化L2/shader上电、不推广该候选；保留归档用于复现，后续先区分硬件等待与调度睡眠。
这组trace带跟踪开销，不能直接与普通冷首发数字相减求其他阶段时长。

## HDMI＋Wave5及收尾

新快轮询内核上再跑完整系列原循环/展开短像素门禁，两项均通过后才做并发。
暂停One-KVM以独占编码器，HDMI保持；3840×2160 NV12→H.264、20Mbps、GOP60，预热120＋测3600帧。
无GPU/有repair3 GPU各60秒，GPU负载75秒；完整系列始终使用repair3前缀，没有把GCM写成full。

| 指标 | 无GPU | 完整修复系列并发 |
|---|---:|---:|
| 编码FPS | 59.997795 | 59.998063 |
| source→encoded p99 ms | 19.529 | 19.660 |
| 整机CPU% | 9.852 | 12.484 |
| 收尾CMA KiB | 505200 | 505200 |
| thermal0起止°C | 52.0→54.6 | 55.1→60.0 |

各3720输入/输出帧、success=true，GPU负载正常退出、像素正确，最终taint=0，无新增GPU timeout/fault。
采集基准是no-payload-read，未验证运动像素、保存码流、网页延迟或HDR；本轮没有功耗仪，温度/驻留不等于功耗达标。
GLES早段GPU主要驻留800MHz，thermal0约53.9°C；并发最高60°C，没有人为加热或触发95°C实际thermal trip。
退出候选前min/max=250/800MHz、polling=10ms、PM auto、profiling=1，服务active、UDC configured；未改持久频率设置。

最终回到默认5.15.137-vim4kvm-hdrdual6，boot ID `2b5b3554-517e-4bb3-82a2-893e61f5d0aa`。
早期SSH接通时One-KVM尚未启动，随后确认其正常active；One-KVM、HDMI、manager最终均active，UDC configured。
六个受保护文件（edge Image/DTB、extlinux、kernels.json、runtime-build.json、uEnv.txt）SHA逐项OK；
厂商`/boot/Image`与`/boot/dtb/amlogic/kvim4n.dtb`亦与入场相同。候选未登记为默认入口。
测量未超过20分钟预算，另计准备、启动与一次暂存权限拒绝后的回退/重试；无单项超过10分钟。
硬件操作结束后释放板锁；主仓测试及本地提交不占板子。
主仓全量unittest：312项、跳过7项、无失败；文档链接/体积及diff检查通过。

原始JSON、RGBA、串口、错误与trace在`logs/gpu-repair-window/`；运行脚本和内核暂存归档在`build/gpu-repair-window/`。
