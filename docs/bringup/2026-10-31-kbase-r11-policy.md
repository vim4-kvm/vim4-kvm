# 2026-10-31：kbase厂商默认策略补齐

承接[r10](2026-10-31-kbase-r10-uhd5.md)，两仓门禁未过的提交已按用户授权推送备份：
主仓gpu-kbase-7x@9b7419f、内核gpu-kbase-7x@9e1726aeb4b3f；未合入正式。
主仓合入origin/main@be81255，后续窗口直接运行本工作树已合入的main版board-window，
不再从工具特性worktree加载副本。HDR10、透传和manager工作树未修改。

## 只读证据与实际策略

先排队等HDR10交还5.15；票据117只做基线身份核对、live DT/具名sysfs读取及各一次
有界DMA/CL SP诊断，不替换r9缓存的七轮性能基线。等待既有heavy完成后才sampling。
5.15为MALI_MIDGARD_DVFS，GPU没有devfreq trans_stat/time_in_state节点；
此事实与缺失接口均记录，不虚构驻留表。诊断10–20Hz只读频率/利用率辅助观察，不作为新基准。
DMA诊断采到250MHz，CL SP主要800MHz、包含250MHz爬升。
实际metrics周期100ms，pm_poweroff为400000 2 0，power_policy为always_on。

live GPU节点是`/bifrost`，不是r9元数据脚本曾查找的`/valhall`或`/soc/gpu@fe400000`。
它的tbl为六项phandle：250/400/500/666.7/800/重复800MHz，sc_mpp=1、num_of_pp=4；
没有def_clk、max_clk、turbo_clk。r7将另一份基础DT的def_clk=0视作实际参数不成立。
固定V@80a07ad5的K/platform/devicetree/mali_clock.c按实际缺省路径设置
cfg_clock=table_size-2=4、def_clock=cfg_clock=4，bst_gpu=210由platform_gx.c初始化。
scaling.c:mali_decide_next_status在util>210时可以直接跳至def_clock，而非逐级爬升。

同一状态机还使用软件num_cores_enabled计数：初值sc_mpp=1、上限4，低负载先消耗
软件PP状态及保持周期，再降频。它的实际硬件setter是no-op；这不意味着计数可从DVFS删去。
r10只复刻频率阈值/保持，漏掉该计数和跳档，导致短暂间隔后的频率历史不等价。

两边利用率均来自r44的time_busy/time_idle，先取整数百分数，再乘255/100；
5.15在kbase周期hrtimer回调推进策略，r10在devfreq delayed work另行采样。
devfreq默认DEFERRABLE在CPU空闲时可延后监控，厂商hrtimer仍会唤醒。
候选改用DEVFREQ_TIMER_DELAYED，保留100ms，不宣称两个独立计时器相位完全相同。

## 修复与离线验证

1f8c2d9补live参数对应的跳档、软件PP计数保持及非deferrable轮询。
boost_level=4、boost_threshold=210为只读模块参数；五档、up/down阈值与keep_count=5不变。
没有改变电压、电源域、实际shader核心数、thermal QoS或使用performance默认。
空闲仍按厂商状态机回落250MHz，软件PP不是另一个硬件门控实现。

宿主差分测试编译真实governor决策函数与GPL厂商mali_decide_next_status，覆盖
两种OPP表排序×五档×四个PP状态×六个保持计数×101种可达利用率，共24240种组合，
逐项比较频率、保持计数与软件PP状态。测试夹具保留Amlogic版权/GPL声明。
仅重编外部模块，沿用r10的uhd5 Image/BTF/完整基础模块；W=1/Werror、ABI及
实际modprobe前置依赖通过，主仓358项unittest通过（11环境跳过）。

本轮候选继续EGL私有前缀、Vulkan/OpenCL ICD，不覆盖Mesa、不推专有blob。
One-KVM服务级并行脚本和接收器都补35秒有界HTTP就绪等待；不因首次连接被拒立即失败。
采样器只读具名GPU频率/利用率，负载阶段切换时记录trans_stat，不ptrace或读寄存器。
七轮原脚本/探针不变，额外观察器单列记录；5.15七轮继续复用缓存。

## 上板结果

源端SDR，使用同一r9探针/heap-gfx/5分钟空闲/2秒间隔，七轮；没有重测七轮5.15基线。
额外10Hz具名sysfs观察器有开销，记录与主样本分开，不声称完全无扰动；P95为七轮最大值。

| 项目 | 5.15缓存中位数/P95 | r11默认中位数/P95 |
|---|---|---|
| DMA ms | 1.692/3.618 | 1.535/3.570 |
| GLES FPS | 616.361/617.773 | 646.280/648.065 |
| CL latency µs | 78.32/79.14 | 53.19/56.54 |
| CL SP GFLOPS | 101.69/101.71 | 101.74/101.76 |

本次四项均达缓存门槛，SP为基本持平，不据七轮小差值推断长期性能优越。
驻留表实际出现10次250→800MHz跳档；约300秒空闲的3015个频率样本均为250MHz。
首轮SP的10Hz样本158次800MHz、14次250MHz、1次400MHz，含启动与退出，不能等同逐kernel驻留。
5.15诊断SP采到267次800MHz、32次250MHz；两边频率采样率不同，不直接将计数相减。
trans_stat支持本次跳档/驻留分析；单独time_in_state不存在，保留errno而不造数据。

默认DT：EGL1.5/GLES3.2像素正确、VK1.3.231、CL设备/C3.0，六类VK/CL内存均过，
所有已运行项零WARN/BUG/oops/GPU fault；不是CTS。mpgpu连续/半占空均值89.89/45.01%，空闲末全0。
GPU emul_temp=96000使state0→1、800→666.7MHz；清0后state0和800MHz恢复，五档均过。
GPU空闲末/负载末48.1/51.2°C，5.15缓存49.3/53.5°C；未做仪器功耗，不能据此宣称能效更好。

驱动基准4K60、600帧：无GPU59.998059fps、DMA并发59.998078fps。
One-KVM服务在连续GLES负载并发下，35秒实际WebRTC样本全部3840×2160、推进2106帧，
约60.17fps（边界/解码批次影响，不代表源端超过60Hz）。服务27个采样首个55.20为启动瞬态，
其后稳定约60；末20个编码FPS为59.965–60.018，中位60.003。没有HID、声音或ptrace。

第二DT仅恢复dma-coherent：六类最小VK均过，但首个原生CL kernel返回-14并触发job slot1
GPU fault0x51。r44 gpu/backend/mali_kbase_gpu_regmap_jm.h将其命名INSTR_INVALID_ENC，
**不是AS0页故障**。首fault即停、未继续CL/性能。该独立负向证据支持保留删除dma-coherent；
不能据此断言缓存失效的微观路径已全部定位，也不把负向DT称为可交付候选。

## 回退与交还

负向DT回默认5.15后四服务active，但NetworkManager DHCP失败、eth0无IPv4而carrier=1。
窗口自动SSH恢复因此超时；另取仅恢复票据，通过串口先恢复五个助手，再正常重启5.15，
没有热解绑网卡、改网络配置、写PWM/电压或刷U-Boot。SSH/DHCP随第二次正常启动恢复。
最终四服务active、UDC configured、八项boot/登记SHA和原kernel build ID全部一致，
五个临时助手恢复通过。cmdline仅reboot_mode从watchdog_reboot变为normal，已独立记录，
其余token逐项一致；没有修改工具的严格身份门禁来隐藏差异。

main版精简cleanup已执行成功，含r10遗留归属marker的空模块挂载目录已安全删除。
140份JSON/日志/脚本等证据逐项SHA验证；scp仅遗漏root私有registry.bin缓存，不是测量证据。
三张票据分别为只读诊断、候选窗口和故障后恢复，均已释放；没有第三次候选试验。
正常默认路径的API/性能/温控/并行门禁已满足，**回退自动化仍有DHCP恢复边界**，
必须作为[待审集成清单](../gpu-kbase-uhd5-integration.md)的限制，不自行改变正式默认路径。

证据：logs/kbase-r11/、logs/kbase-r11-window/，含live DT、原始驻留、manifest、UART、
负向故障、final-identity.json、final-state.json和evidence-receipt.json。
