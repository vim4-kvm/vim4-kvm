# T7 平台电源候选批量上板清单

本页仅排队，**本轮未执行**。源码、六个小提交和离线结论见
[离线审查](platform-pm-offline.md)。先跑不请求系统睡眠的候选验证；
整机 sleep 必须等设备恢复和唤醒契约就绪后另开窗口，不以本候选的 EBUSY 保护充当通过。

## 批量窗口 A：CPU idle、GPU cooling、功耗与回归

预计 **3–4 小时**，含一次性启动、冷却与失败恢复余量；不含三组厂商性能配对。
取得 board/heavy 双锁，全程覆盖启动、测量和回基线；板子及对端不并行编译/测量。
本轮只在此登记，不获取锁、不连接板子。

| 顺序 | 内容与通过条件 | 预算 |
|---|---|---:|
| A0 | 记录当前正式内核/DTB/完整模块/build ID、服务和 USB/LUN 状态；确认串口、一次性入口、Stock 回退及外部复位可用；核对 PID1 watchdog 实际持有和 30s 配置 | 15min |
| A1 | 离线预备同次 Image/全部模块/五个 DTB 的哈希清单，一次性启动候选；确认未改默认启动，八核与网络/根盘正常，无新增 Oops/taint | 15min |
| A2 | CPU cpuidle：每核 `state*/name/latency/residency/usage/time`，确认 PSCI 状态出现且有实际驻留；比较空闲前后 `/proc/interrupts`、定时器与时钟漂移，循环单核/全核短负载唤醒，不写 `/sys/power/state` | 20min |
| A3 | 两簇 CPU 全部可用频点升降频往返，核对 secure bin、time_in_state、PWM/电压及实际负载；生产默认 governor 与共同 schedutil 诊断分别记录；不改 OPP 电压 | 20min |
| A4 | GPU 五档往返及 simple_ondemand 自动负载/空闲切换，核对 devfreq、runtime 状态、regulator/PWM 保持、渲染像素与错误；禁止写 GPU 电压 | 15min |
| A5 | GPU 温控：核对 gpu-thermal passive trip 的 cdev 链接；在仪器/温度监护下逐档限制 cdev 再释放，验证真实负载频率上限/吞吐与无错误。自然热试验不触碰 critical；不临时改生产 trip 或用手写频率冒充自动温控 | 15min |
| A6 | 同环境/原风扇/同供电：空闲稳定5min+采样5min，CPU、GPU、4K60 KVM 各10min，负载串行；整板功率计1Hz、六区温升、风扇、DVFS驻留、吞吐、每任务能耗，冷却另计 | 50–65min |
| A7 | PM 属全局改动，跑仓库九类全量回归；覆盖运动画面与音频连续性、编码、HID、虚拟介质、管理面、存储/网络基本服务；真实 HID 与声音不能用节点/服务状态代替 | 30min |
| A8 | 正常重启回原正式基线，确认 build ID、USB/HID、画面/声音和服务；保留全部失败与 pstore/journal/UART，恢复原 governor/cdev/服务/负载设置 | 15min |

先比较 CPU idle 唤醒尾延迟，再评估其节能；若 9ms 等级状态影响 KVM/HID 尾延迟，
记录并回退候选，不能只依据空闲瓦数合入。GPU `runtime suspended` 时 cur_freq 是缓存，
需要负载中观察 cdev 的限制是否生效。功率计缺失填测量缺失，不用温度推算瓦数。
手动 cdev 只验限频通路；若自然温度未触发 95°C，自动温控仍待测。须在控温条件或
另行离线构建的低阈值测试 DT 下验证 trip 自动响应，不把手写 cdev 算自动温控通过。

性能正式门禁按 [性能基线协议](../performance-baseline.md)：三组 A/B/A，至少七启动块，
同负载/用户空间/环境/风扇/测量端点；吞吐≥95%、同吞吐功率≤105%、稳态温升≤+2°C、
错误为0，并检查各延迟分位。这些是测量容差，目标仍为不低于厂商5.15。
PM 子集每块 60–75min，七块加启动/冷却/恢复预计 **8–10 小时**；如并入
[整夜完整计划](../overnight-performance-plan.md)，复用同一组采样，不另重复占板。
厂商当前缺匹配硬件 GPU 用户态时，GPU A/B 填测量缺失，不能与 llvmpipe 分数比较。

## 批量窗口 B：设备 PM 与整机 s2idle/deep（暂不可执行）

预计前置实现齐备后 **4–6 小时**，优先白天、有串口和独立复位的独占窗口。
本候选的 RX/VDIN/Wave5 prepare、CRG suspend、DRM handoff 仍拒绝 sleep，
必须有各自正式替代与退出证据；不能临时解绑/改 return 0 来消除阻塞。

| 门禁 / 阶段 | 必须具备的证据 | 预算 |
|---|---|---:|
| B0 恢复方案 | 一次性入口已验证；独立外部复位/MCU 或人在场 RESET。Meson watchdog 在 suspend 停计数，PID1 RuntimeWatchdogSec=30 不能独自满足此项 | 20min |
| B1 驱动前置 | RX/VDIN/Wave5/PCM/DRM/UDC 均有停止提交、DMA/IRQ quiesce、失败回滚与上下文恢复；共享域依赖和 I²C/风扇恢复明确。先保存无负载和活动流测试证据 | 40–60min |
| B2 唤醒前置 | 外置 HYM8563 INT 线路明确，或 meson-vrtc→AO/BL31 定时唤醒契约已确认；不得假定 rtc0 可唤醒。先只用一个确定的定时源，保留 UART 与外部复位 | 30min |
| B3 PM 分阶段测试 | 单独候选配置开启 PM_DEBUG；在通过前述恢复门禁后，从 freezer/devices/platform/processors/core 逐级 `pm_test`，每级确认返回、恢复链路及无泄漏，失败停止。pm_test 也调用设备 PM，不能绕过门禁 | 30–45min |
| B4 s2idle | 定时唤醒10次，每次10–20s，另一次长于30s确认正常睡眠不被误复位；空闲后再活动负载/应用重建，核对唤醒原因、恢复时延、各驱动错误与能耗 | 30–45min |
| B5 deep | 先单次10–20s再10次循环；确认真实进入 SYSTEM_SUSPEND、DDR/域上下文恢复、功率下降和准时唤醒。预定外部复位上限，不能在无安全恢复时等待 PID1 watchdog | 30–45min |
| B6 各唤醒源 | 定时源通过后分别 Power/AO GPIO、IR、Ethernet WoL、USB host 与 gadget remote wake；每类10次、去除其他唤醒源，报告不支持与缺线路。Wi-Fi/WOWL 另协调，不占用 P2P 任务状态 | 45–60min |
| B7 全量与恢复 | 每轮后真正采集/编码/声音/HID/虚拟介质、CPU/GPU/网络/存储正确；最后九类全量和回正式基线，清除试验 alarm/唤醒配置并保留日志 | 45min |

单次超时、硬锁、掉盘、异常温度、DMA/IRQ 错误或恢复后无声/无画面即停止该阶段，
由独立复位回正式基线后保存证据，不连续试下一个来源。失败定位仍在功能分支做，
不能降低唤醒次数/负载或永久常开更多域来记通过。

## 取得可信 GPU 电压表后的附加窗口

当前无该表，**本候选不执行调压**。先离线记录电压表来源、板型、bin/温度适用范围，
对照 PWM 实测标定、schema、升压先于升频/降频先于降压与错误回滚；再准备新候选。

首次电气资格预计 **60–90min**：万用表/示波器观察各频点稳态电压、瞬态、
负载切换和最低/最高温区边界，五档双向循环，不试表外电压。电气通过后按窗口 A
的 GPU 600s 热稳态、像素正确性、功率/温升/吞吐与三组配对验收执行；
时间可并入上述 A/B 块，不能用一次短测宣称全 bin/温度范围调压稳定。
