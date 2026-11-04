# P0-2 性能与常开功耗合并窗口（完整配对未执行）

本页管后续窗口的操作与停止条件，未执行项不记通过。导航：[独立 CPU idle 候选](#独立-cpu-idle-候选)、[窗口 B 不排](#窗口-b-不排)。

[本轮记录](../bringup/2026-11-02-p0-2-pm-window.md)：按总板时30分钟及停止指令结束，实际896.195秒。
仅5.15 A1 idle完成；signal中途取消；编码、B、后续A及schedutil诊断均未启动，四项门禁未验。
已恢复Mainline、两个overlay身份/服务/UDC/画面通过，全部板票释放。下述6–8小时为完整方案估算，不是本次授权。
B 身份按当前安装 uhd6 及已登记模块 overlay 收据核对；不得用原整包模块 ID 拒绝已登记 overlay，也不得跳过身份检查。

当前默认身份见[主线入口](../kernel-mainline.md)，不得沿用历史候选名。A 为厂商对照，B 为本次正式构建；主组保留每个启动块预检时各簇实际 governor。上次 5.15 两簇实录均为 performance，见[原始结果](../bringup/p0-2-quick-evidence.json)。
uhd6 已登记 tested_build，board/vim4-board-runtime、vim4-kvm-run 均匹配完整 release。
[安装记录](../bringup/2026-11-01-hdr10-r14e-installed.md)有服务 active 和 UDC configured；
[上次 P0-2](../bringup/2026-10-31-p0-2-performance.md) 的 uhd5 匹配失败已解除。每次启动仍验实际身份与服务。

| 顺序 | 操作、时长和证据 |
|---|---|
| 准备 | 离线在 heavy 票据下按[驱动基准](../driver-benchmark.md)准备 build/p0-2/vim4-driver-bench，核哈希，释放 heavy。准备已验双内核入口及回当前 uhd6 的恢复证明。禁止复用旧 5.15 默认项证明。 |
| 就绪，10 min/启动 | FIFO board 票据内按[短窗口规程](../board-window.md)切内核、collect 身份、启动项、服务、UDC。固定环境温度、供电、散热、应用版本、码率和信源。保持同一 4K60 SDR 输入，温度回到同一起点。工具预检实际输入、服务 active、流客户端与 WebRTC、UU 桌面会话数。 |
| A/B 每阶段 | 在独立 board-queue run 票据下运行 python3 tools/perf-quick.py pm-phase PHASE --output BLOCK/PHASE；每个启动块独用一个 BLOCK，同块所有阶段共享父目录中的 boot-policies.json，重试用同父目录的新阶段目录。boot ID 或逐 policy 策略变化即拒绝。idle、signal 分别 5 min（各预留 12 min 票据），h264、h265 分别 10 min（各预留 20 min 票据）。sampling 排斥 heavy；队列等待、冷却、切换不计入采样。跨票据有其他负载时重新冷却，身份/环境变化则该块作废。 |
| idle / signal | idle 保持 HDMI 锁定，停止 One-KVM 并核实 inactive；signal 保持服务 active，要求 stream/status 的 clients、webrtc/status 的 session_count、UU 桌面 sessions、VNC connection_count 都为零，recording 为 false。RTSP 仅公开 service_status，连接数标「未核实」，只接受 stopped。停服务前复查；未找到公开的管线外部订阅总数，phase.json 单列「未核实」。两者比较常开服务的空闲开销。现有 M6 准备流程可切 HDR 和恢复前台，未找到可独立关闭物理输出并恢复的已验流程；无信号功耗仍缺测。 |
| h264 / h265 | 同一物理输出全屏 perf-motion.html；沿用 perf-quick.py source，确认运动页未被遮挡。原生阶段独占采集、停 One-KVM 后按原状态启动。3840×2160p60、12 Mbps、GOP60，120帧预热、36000测量帧；管线时限按 57 fps 加 20 秒余量计算（654 秒），外层及恢复另留票时。记录 H.264/H.265 FPS、实际尺寸、缓冲数、CPU、sink→src p50/p95；前 300 s 升温，后 300 s 检查温度是否稳定，仍在爬升则稳态未证实。接收测量另循原 P0-2 receiver 流程，同钟且 ≥1000 有效标记才报端到端延迟。 |
| 诊断 | 主组完成后单独在 uhd6 重做四阶段，各命令追加 --schedutil。逐 policy 记录原 governor 并恢复；核对 phase.json 与恢复后的 sysfs。诊断样本不计入主组。CPU 85°C vs 厂商 95°C 只记录何时触发及对应吞吐。 |
| 判定 | 每阶段保留 pm.jsonl；编码阶段取 C 基准实际测量起止（板上 monotonic 微秒），遥测从预热前覆盖到 bench 退出后；按 phase.json 的 common_interval 选取共同区间，再对 time_in_state 和 idle usage/time 做末减首，空闲阶段用完整采样段，重启/计数回退作废。用 type 关联 zone/cdev，观察 GPU 频率、限频、风扇百分比；5.15 私有 DVFS 另读 /sys/class/mpgpu/cur_freq，缺节点则标缺测。uhd6 默认 kbase/governor_vim4，95°C、0–4 档 map 已在正式 DT；无自然触发则只报告观察到的状态。风扇命令百分比不能换算声压。无整板实测读数入口，标缺测；外接功率计可按[基线协议](../performance-baseline.md)提供同时间轴 CSV。PD 合同和单轨 hwmon 均不能代替整板瓦数。 |
| 失败与恢复，5–10 min | 无 4K 缓冲池、服务失败、异常温度、丢帧或恢复错误，停止该组；取消时先停整个远端负载单元；票内最多两次核实单元 inactive 或已回收。仍活跃或状态未知时保留目录、写交接、禁止重启 One-KVM；失票时结束状态本地记缺测。确认停止后记录结束状态，恢复 governor、服务及状态 API，关 sampling 后取回数据。回传失败按 retained_remote 找回，恢复失败查 recovery-required.json。保留双方原始 JSON、journal、信源与采样票据；不缩为1080p。恢复 governor/服务，核验 HID、LUN、管理面。过期交接下一张票据，按已验路径回本次进入前默认 uhd6，再验身份/画面/服务/UDC。 |

主组按同日同 epoch 三组 A/B/A（相邻 A 可共享，共七个启动块），每块含操作、冷却约 45–60 min，另加诊断 45–60 min 和原接收端窗口。预算约 6–8 小时加接收/排队。遵守每票 ≤30 min。按[基线协议](../performance-baseline.md)及其比较器判定，缺测项保留未验。

每阶段在 phase.json 保存预检、开始和结束的 HDMI/服务状态。5.15 在读取 info 前后检查 hw_info 锁定位；uhd6 在采集前后只做 QUERY_DV_TIMINGS。要求逐行 3840×2160、60±0.5 Hz。开始不符不启动遥测，结束不符保留数据并判该阶段失败，照常恢复已改设置。这些快照只证明取样时刻的状态。

## 执行协议

参数、采样配置和报告字段以[运行器](../../tools/perf-quick.py)及其帮助为准，以下保留环境与恢复约束。

## 独立 CPU idle 候选

正式 DT 的 PSCI power-down disabled。若常开基线显示值得优化，另约 45–60 min 用只改 idle 的 kbase DT 比较每核驻留、中断/定时器、HID 和首帧尾延迟；不混入上述 A/B/A。

## 窗口 B 不排

整机 sleep 中断远程管理、采集与 USB。RX/VDIN/Wave5、CRG/handoff 有明确拒绝路径，厂商恢复/唤醒闭环未证实。本产品不安排整机 sleep。
