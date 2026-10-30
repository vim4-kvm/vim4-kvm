# 2026-10-30：Mesa展开候选与10ms调频配对窗口

结论：展开候选将该GLES原循环由234.8提升至587.8fps，接近同窗显式展开；
10ms轮询将Vulkan暖提交3.20降至2.03ms，接近锁频2.00ms，**冷首发仍约8.1ms**。
10ms在runtime suspend空闲时未观察到额外CPU代价，保持active时增加约0.107个百分点整机CPU。
HDMI＋Wave5两窗均4K60。不能宣称产品GPU整体追平；展开是绕过，后端循环代码生成仍需修复。
方针仍为**代理建议，待用户确认**。本轮未push。

## 版本与安全边界

入场5.15.137-vim4kvm-hdrdual6，One-KVM/HDMI/manager active、UDC configured；
Mac按board→heavy取得两把lockf锁，全部板端操作均在锁内。NPU只在VM离线工作，不占板子，未动其文件。
板上测量期间本任务不并行编译；Mesa语料编译在全部板测结束后进行，VM的NPU离线编译按用户约定不影响板测。
不发送HID（被控机Mac mini M6）、不测声音、不ptrace、不写PWM或电压。

沿用已保留的213f2715 Image/匹配完整模块、此前仅增加d2cd4c6 cooling map的DT副本。
本轮没有安装4e239aec051a4模块：它仅把polling_ms默认50改10，本轮用现有polling_interval
在**同一已验证内核**内设置50/10，隔离该策略的影响；这不是该新模块二进制的启动验收。
临时gpu-once.conf经U-Boot RAM sysboot选择，无saveenv；5.15默认启动项不变。
私有Mesa原版26.2.6与候选unroll1并存，候选归档SHA为
`c75269107304cf21a87100c276d076cac2f48fc4ddadfe305775994f870f0e71`，上板逐文件manifest全部匹配。
EGL/Vulkan环境仅注入测试进程，未替换系统Mesa；原版与候选采用同一个探针二进制。

启动时机早于部署SSH命令返回，SSH因重启断开；启动后核对了临时启动文件和**完整manifest**，
确认私有运行时无缺失/哈希不匹配后才测量。没有据SSH连接断开推断安装成功。

## GLES三轮交错配对

同一探针SHA `3c5a40d7804b629e9857ac26199451498dd22cdc57ced513aae63ef2edfbbd2f`。
每轮顺序原版loop→候选loop→候选unroll→原版unroll，三轮；512×512 GBM/FBO、RGBA8，
2秒预热＋10秒稳态、每帧glFinish、无swap/vsync，回读另计。每项25秒超时，均退出0、像素179/128/128/255、gl_error=0。
manager在GPU主测期间停止，profiling=0，其他服务保持；结束恢复，CPU governor为performance。

| 26.2.6私有栈 | 原循环FPS三轮 | 原循环平均 | 显式展开FPS三轮 | 展开平均 |
|---|---:|---:|---:|---:|
| 原版 | 234.719 / 234.718 / 234.902 | 234.780 | 589.393 / 592.760 / 590.002 | 590.718 |
| unroll1候选 | 588.297 / 591.825 / 583.248 | 587.790 | 587.517 / 582.205 / 582.499 | 584.074 |

候选原循环提升2.50倍，与原版显式展开相差约0.50%；两种候选输入没有残余2.6倍差。
这验证了绕过的实际收益，不能证明展开是上游最优方案。厂商原循环614fps是上一窗口参考，
本轮未重测厂商，不将跨窗口差异当精确剩余GPU差。本轮没有GPU timer样本；源码分析引用上一窗口有效timer。

## Vulkan冷/暖与频率

候选私有PanVK，24,883,200字节同一uint DMA compute，default_cma_region，三次预热后20提交。
每配置三进程、各进程前空闲1秒；50→10→800MHz顺序配对三轮。每进程90秒外层超时、fence10秒，
全部退出0、6,220,800个uint完整校验通过；min/max只用既有250/800MHz OPP。

| 配置 | 冷首发ms三轮 | 暖20提交均值ms三轮 | 暖总均值ms |
|---|---:|---:|---:|
| 自由50ms | 8.243 / 8.079 / 8.064 | 3.183 / 3.226 / 3.201 | 3.204 |
| 自由10ms | 8.091 / 7.999 / 8.172 | 2.020 / 2.030 / 2.031 | 2.027 |
| 固定800MHz | 2.797 / 2.830 / 2.825 | 2.002 / 2.005 / 2.002 | 2.003 |

暖submit约0.056–0.058ms，各配置接近；收益主要在wait。10ms暖耗时下降36.7%，距锁频约1.2%；
冷首发未改善，符合任务在首次采样前完成的边界，仍需有界active/submit QoS boost候选。
trans_stat每进程首尾差：三轮50ms均250MHz驻留56ms、800MHz44ms；10ms均16/56ms；
锁频不驻留低档。这些差包含pipeline创建/CPU准备等整个进程，不是单独GPU执行占比，计时有4ms量化。
无Vulkan GPU timestamp，wait仍包含同步/cache/调度，不称纯GPU时间。

## 10ms轮询代价与温度代理

各状态用50→10→10→50，切换后等2秒、每项20秒；读/proc/stat、softirqs、温度、trans_stat和runtime状态。
下表为每配置两项平均；manager停止，KVM/HDMI保持原状态，没有ptrace。

| 空闲状态/配置 | 整机CPU% | intr/s | ctxt/s | TIMER softirq/s |
|---|---:|---:|---:|---:|
| auto/suspended，50ms | 0.587 | 1179.0 | 1292.1 | 109.8 |
| auto/suspended，10ms | 0.521 | 1130.3 | 1265.2 | 108.6 |
| PM on/active，50ms | 0.538 | 1206.4 | 1323.9 | 130.0 |
| PM on/active，10ms | 0.645 | 1269.4 | 1401.6 | 177.1 |

suspended两档无可分辨额外开销；active时CPU约+0.107个百分点、TIMER约+47次/s，ctxt约+78次/s。
这些是整机计数代理，不是GPU线程独占CPU或精确硬件唤醒次数；20秒短样本有后台噪声。
没有仪器功耗或已验证瓦特计数，不换算成瓦特。主测温区0为47.9–54.8°C；视频窗口升至58.5°C，
顺序/热惯性不允许把温差全部归因10ms，未触发thermal降频。

## HDMI＋Wave5回归

暂停One-KVM，HDMI保持；同一驱动基准3840×2160 NV12→H.264 20Mbps GOP60，
预热120帧、测3600帧。无GPU/候选GPU各60秒测量；候选GPU为同一原循环75秒、90秒外层超时。
编码项90秒超时，均success=true，GPU退出0且像素正确；结束恢复One-KVM。

| 项目 | 无GPU | 候选GPU并行 |
|---|---:|---:|
| FPS | 60.016 | 60.008 |
| 测量帧数 | 3600 | 3600 |
| source→encoded p99 ms | 19.675 | 19.675 |
| 整机CPU% | 9.789 | 14.385 |
| CMA收尾KiB | 505200 | 505200 |

两项输入3720帧、输出3720帧（含预热），PTS间隔最大16.685/16.691ms，taint保持0。
no-payload-read基准证明采集/编码计数推进，**未验证运动像素/码流内容、网页延迟或HDR**。
不能把它写成全产品验收或10ms视频并发代价：并发视频项已恢复50ms，隔离的是Mesa候选负载干扰。

## 回退与证据

最终5.15.137-vim4kvm-hdrdual6，boot ID `ebb827b8-5b68-40e7-bc13-86e665d59f43`；
One-KVM、vim4-kvm-hdmi、manager均active，UDC configured。首次SSH早于One-KVM启动，
随后确认服务已正常自动启动，未留inactive结论。
7.3退出前恢复polling_interval=50、min/max=250/800MHz、PM auto、profiling=1，taint=0。
无新增GPU timeout/MMU fault/Oops；临时boot文件已删，六个受保护启动文件SHA与入场逐一相同，两锁释放。
私有候选保留在/opt但默认服务不选择它；根分区约14G/29G、可用15G。

原始JSON、首尾频率/CPU/softirq/温度和恢复哈希：`logs/gpu-candidate-window/`。
window.py/post.py留在同目录；registry.bin无读取权限未复制，不影响所有JSON/负载日志的保留。
离线循环与语料审查见[循环代码生成](../gpu-loop-codegen.md)，后续不默认推广展开候选。
