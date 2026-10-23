# 5.15 / 7.3 性能基线协议

摘要：目标为同一 VIM4、同一根文件系统下，7.3 全能力且性能不低于厂商
5.15.137-vim4kvm。完整配对性能项仍**待测**；已完成
[5.15启动往返与GPU栈短测](bringup/2026-10-23-vendor-boot-gpu.md)，其余方法尚待执行。
整夜采样见 [待确认计划](overnight-performance-plan.md)。启动步骤和风险见
[厂商一次性对照启动](vendor-boot-baseline.md)。

## 入口与证据

```sh
python3 tools/perf-baseline.py plan --backend=stock > /tmp/perf-stock.json
python3 tools/perf-baseline.py plan --backend=edge > /tmp/perf-edge.json
python3 tools/perf-baseline.py compare /path/to/metric.json
```

plan 只输出命令模板，不执行、不 SSH、不安装工具。执行者逐项代入环境变量，
不要直接把整个计划交给 shell。每项一个新的 `$OUT`，stdout/stderr、退出码和
超时均保存。`perf-sensors.py` 是供未来板上窗口运行的只读 1Hz 记录器，输出独占创建。
原生采集/编码沿用 [驱动基准](driver-benchmark.md)，构建在采样前完成。

每个运行保存：内核 release/build ID/Image/DTB/完整模块清单哈希、cmdline、固件、
根文件系统与包版本、应用/manager/插件和基准二进制 SHA256、进程 PID/affinity、
浏览器实际版本、源刷新率、输入/输出尺寸/格式、实际编码器、码率/GOP/QP/质量、
EDID、音频采样率/周期/缓冲、网卡路径/MTU、CPU/GPU/编码器/DDR频率、governor、
风扇曲线/环境温度/供电方式。应用配置与媒体文件另作 SHA256 清单，不收凭据。
同一用户空间指相同安装包/应用/数据；内核对应插件及 Mali/Mesa ABI 是明确记录的
必要差异，不能在 A/B 之间 apt upgrade。诊断固定频率和生产默认 DVFS 分开成两组。
保持相同 CPU affinity；当前运行器只在 7.x 固定 0–3，需显式记录并为诊断配平。

## 配对、互斥与判定

所有项目取得 Mac 的 `/tmp/vim4-board.lock` 与 `/tmp/vim4-heavy.lock`，持续覆盖启动、
采样及恢复；使用既有 `/usr/bin/lockf` 嵌套持锁方式。板端原生工具的 flock
不能替代这两把锁。板子、HDMI 源、接收 Mac、网络对端均不得并行编译、部署、
性能测试、抓栈或交互操作；各负载串行。只允许本轮规定的低频传感器采样伴随负载。
调试器、perf/strace、录像校验另开轮次。原生基准停实际采集应用；端到端测试恢复
同一 One-KVM 服务、只留一个观看者。停启前记原状态，结束恢复，超时停止整轮。

每个配置至少三组 A/B/A（A=5.15，B=7.3）；按启动分块批量跑各项，再重复三组，
相邻组可共享末/首 A，至少七个启动块。冷却至同一温区（起点相差 ≤2°C），
无升级/后台备份；源先稳定，至少预热15秒。CPU/内存另先跑15秒预热，启动不预热。
两端 A 波动超过该项容差，标受干扰并保留，不能放大容差直到通过。

| 指标策略 | 7.3 相对相邻 A 均值的门槛（每组均通过） |
|---|---|
| throughput | 帧率、events/s、MiB/s、Mbps、GPU场景分数 ≥95%；I/O另比较p95/p99延迟 |
| latency-ms | 视频/音频/HID及分段P50/P95/P99不得增加超过 max(5%, 2ms)；每个分位单独门禁 |
| errors | 丢帧/丢包/冻结/不一致标记/音频断续/内核错误必须为0；没有5%错误预算 |
| boot-s | 启动各端点不得增加超过 max(5%, 1s) |
| power-w | 同吞吐同画质时平均与P95功率 ≤105%，另报每帧/每任务能耗 |
| temperature-c | 同环境同风扇下稳态温升不得增加 >2°C；触发节流单列，不能靠降吞吐过关 |

这些是预先固定的测量容差，并非允许永久降低产品性能。高噪声项需提高测量精度，
不改门槛。频点/驻留时间是解释变量，不能单独宣称快慢；必须同时通过性能及功耗门禁。
功能缺失填“能力缺失”，工具/传感器/测量端点缺少填“测量缺失”，均无数值且不算通过。
程序崩溃、超时或已支持路径启动失败填“失败”，不能降格成能力缺失。没有全覆盖不宣布追平。

compare 每次接受一个配置的一项指标，格式如下（groups 至少三组，不能复制样本凑数）：

```json
{"status":"ok","direction":"higher","policy":"throughput","groups":[
  {"before":{"value":60,"valid":true,"config_sha256":"64位实际SHA256","evidence":"A1/raw.json"},
   "candidate":{"value":59.8,"valid":true,"config_sha256":"同上","evidence":"B1/raw.json"},
   "after":{"value":60,"valid":true,"config_sha256":"同上","evidence":"A2/raw.json"}}
]}
```

config_sha256 是两边相同的负载/公共用户态/测量设置清单哈希，内核与必要后端差异
放每轮独立 manifest。`valid` 必须由原始记录审查后填写；工具不自动证明配置、画质、
样本数或日志真实存在，不解析所有第三方输出。任何一项非通过都返回非零。
缺失项可直接输入 `{"status":"能力缺失"}`。该工具是单指标门禁，不能替代整套验收。

## KVM 主链路

主矩阵：1080p60、2160p60；capture、Wave5/厂商 MultiEnc H.264、H.265、硬件 JPEG
分别测；软件编码器若产品启用也独立列行，禁止静默回退。H.264/H.265 分别12/60Mbps，
GOP60/相同刷新策略，JPEG质量80；缩放、HDR/高位深另扩展，不能混入同一统计。
设置 `$WIDTH/$HEIGHT/$BITRATE` 后执行 plan 对应命令，以 khadas 运行厂商后端，
不删除 `/tmp/vpu_mutex.map`。900帧预热、7200帧测量（60Hz至少120秒），低帧率会延长，
240秒超时为失败；报告实际wall时间、输出/输入计数、PTS间隙、CPU、pad分位数与CMA。
实时源限制吞吐上限，60fps只证明达到输入速率，不代表离线编码峰值。

运动源在 Mac：

```sh
/tmp/vim4-latency-source 180 --motion --verify-coherence > "$OUT/source.jsonl"
# 源稳定后，在同一Mac另一终端启动plan中的接收命令
python3 tools/latency-summary.py "$OUT/source.jsonl" "$OUT/receiver.json"
node tools/one-kvm-smoke.mjs "$URL" --exclusive --seconds=120 --warmup=15 --audio
```

codec/码率在测试前设置并核实实际输出；smoke 会逐编码测试，必须按其轮次拆结果。
视频延迟是源开始绘制→浏览器提交合成器，另跑无像素回读轮次测呈现FPS/间隔；
不能叫光学端到端。按 [延迟协议](latency.md) 时钟误差≤2ms、每窗口≥1000有效标记，
P50/P95/P99/max、无更新尾段、漏回调、实际源帧率全报；同PTS分段不能相加。
60Hz呈现/解码均≥59fps且间隔无>250ms停顿，不能仅凭相对5.15通过。
每种保留编码另跑30分钟同连接，首尾120秒窗口，处理16位帧号回绕；延迟增长≤16.7ms。
单独录像解码核验三处ID、SPS/profile、码率、细线及颜色，不能在计时轮次写码流。
物理HDMI光子→接收屏光子用≥240fps相机同时拍源/接收屏同一帧标记，120秒、
至少1000匹配事件；相机量化误差>2ms时该容差不可判，换光电设备或填测量缺失。

音频：固定48kHz立体声，并扩展44.1/96kHz独立项。同步源加
`--sync-audio=实际HDMI设备名`，plan的AV命令每轮180秒；先用
`node tools/one-kvm-av-sync-check.mjs --calibrate=known-offset.mp4 --expected-ms=120`
校准同浏览器回环。报告音画偏移P50/P95及漂移、非静音/连续性。**AV偏移不是音频单向延迟**。
单向绝对音频另用同一多通道声卡同时采集源参考电输出和接收播放输出：
`arecord -D "$LOOPBACK_DEVICE" -f S32_LE -r 48000 -c 2 -d 180 "$OUT/audio-loop.wav"`，
每2秒一脉冲，逐脉冲互相关，以录音采样数差/48000计算延迟；先直连校准两通道差。
每轮约90脉冲，报告P50/P95/max，P99至少1000脉冲（≥34分钟）再判；无接线/设备填测量缺失。
光学视频、音频绝对延迟不能从分段均值或AV偏移推算。

## 解码与 GPU

解码逐 H.264、HEVC、VP9、AV1、AVS2、MPEG1/2、MPEG4/Xvid、MJPEG、VC1、AVS，
按 [媒体能力表](parity/media.md) 的位深/分辨率子集建行。Wave521C 不因名称含Wave5就
假定能解码；当前7.3对应项标能力缺失，禁止在性能窗口尝试未过安全门禁的vdec驱动。
准备≥120秒、哈希固定的1080p与4K I/P/B片源放tmpfs（空间不足固定本地文件并记I/O），
先离线参考解码验证帧数/CRC，再执行plan管线，显式填入经 `gst-inspect-1.0` 确认的
硬件元素/解析器/封装解复用器，如 `qtdemux` / `h264parse`；不用decodebin自动软解。
厂商若仅有私有播放器，须补能导出完成帧数与wall时间的适配器；当前命令是待发现的
模板，不能声称厂商解码基准已可直接运行。sync=false跑到EOS，以正确输出帧/总wall时间
计吞吐；素材重复拼成≥120秒实际测量量，另设180秒看门狗，排除启动15秒；逐codec三组。
缺少硬件消费程序填测量缺失，已知缺驱动才填能力缺失。

GPU已知证据：厂商源码是Mali midgard/bifrost私有内核接口；[7.3实测](bringup/2026-10-21-edge-gpu-devfreq.md)
为 Mali-G52 r1 / Panfrost、Mesa 25.2.8。离线旧包清单
`logs/preflash-backup-20261013-123403/home-and-packages.txt` 只有Mesa EGL/GLVND/GLES包，
没有libMali包证据；不能由内核驱动推断当前5.15具有匹配闭源用户态。
后续[短窗口](bringup/2026-10-23-vendor-boot-gpu.md)确认5.15只有Mesa EGL vendor，
实际渲染为llvmpipe，未找到专有libMali；不能拿其19分与M1/Panfrost925分作硬件比较，
实际surface尺寸也不同。硬件对照仍缺匹配用户态。下列只读发现命令每轮各存一份：

```sh
dpkg-query -W '*mali*' '*mesa*' '*egl*' '*gles*'
ldconfig -p
ls -l /usr/share/glvnd/egl_vendor.d /usr/lib/aarch64-linux-gnu/libEGL* /usr/lib/aarch64-linux-gnu/libGLES*
eglinfo
LD_DEBUG=libs glmark2-es2-drm --off-screen --size 1920x1080 --benchmark 'shading:duration=15'
```

发现轮次不计分；记录实际加载库真实路径/哈希、EGL vendor、GL renderer/version、
内核模块。私有libMali若需隔离前缀，预先安装到独立路径，用进程LD_LIBRARY_PATH选择，
不替换系统Mesa链接。两边固定同一glmark2源码/场景/分辨率/GLES API；无法共用GBM时
选择双方支持的同一pbuffer GLES负载，保留源码和输出像素校验；接口不可比则分别报告。
plan的离屏/DRM场景120秒，各另预热15秒；完整glmark2套件也跑三组，各场景独立比较，
不能让总分抵消单项回退。kmscube跑120秒只验scanout/错误/帧节奏，vsync封顶不代表GPU峰值；
timeout预期SIGINT退出需确认程序结束。DRM测试独占显示，停compositor，M1不支持的项
标能力缺失；不能为跑分覆盖显示任务的候选。不得写未经校准的GPU电压表。

## 通用性能、启动、供电与 DVFS

| 项目 | 命令、采样与补充规则（均三组A/B/A） |
|---|---|
| CPU | plan cpu-single分别选每个capacity簇的代表CPU，cpu-all=8线程，120秒；sysbench events/s，另报P95 latency，affinity固定 |
| 内存 | plan memory读及另轮`--memory-oper=write`，各120秒；256MiB大于缓存，单线程及8线程各跑，报告sysbench传输口径，不能称DRAM物理总线峰值 |
| 存储 | plan顺序读写，另各轮改`--rw=randread/randwrite --bs=4k --iodepth=1/16`；15秒预热+120秒，BW/IOPS与clat P95/P99。SCRATCH仅专用挂载点中新建2GiB普通文件，先顺序写准备并sync，禁止原始块设备/现有用户文件。至少留4GiB空间；eMMC/SD/USB各列，不刷缓存掩盖差异，写入有磨损预算 |
| 网络 | 有线、Wi-Fi各固定接口/IP/信道/位置，对端`iperf3 -s -B "$PEER"`；plan正向及另轮`-R`，各120秒+15秒omit；单流主项，4流另列，TCP重传另报。UDP另用`-u -b 已固定目标码率`记丢包/jitter；Wi-Fi不得与P2P任务并行 |
| HID | plan input每次原生窗口≤40秒，20轮积累每种事件样本，主指标浏览器send→同Mac原生收到，视频开/关分组；同钟校准≤2ms、匹配事件数。按[input验证](input-latency.md)汇总；P99不足1000样本则待测，勿将此结果称USB总线独立延迟；纯gadget写→USB报告需逻辑分析仪/共同触发，缺仪器填测量缺失 |
| 启动 | 每内核至少5次；保存plan的systemd-analyze、`journalctl -b -o short-monotonic`和外部UART时间戳；分别计RESET→内核首字、PID1→manager可用/首个有效视频/首个实际HID，轮询`curl --fail --max-time 1 "$URL"`只证明HTTP。冷启动/热复位分开，人工串口停留排除，pstore不算启动计时 |
| 空闲 | 无观看者、无benchmark，服务组合固定，稳定5分钟后plan idle采300秒；温度/功率P50/P95、CPU/GPU/DDR驻留，外接显示/USB状态一致 |
| 满载 | plan load 600秒，预热前300秒、后300秒稳态；同时运行1Hz sensors记录器。另开GPU专用满载和4K60 KVM生产负载600秒，禁止同时跑CPU/GPU基准凑一个不可比数字；持续节流可延长但两边相同 |
| 频率 | sensors每秒读CPU/devfreq/governor/runtime状态；前后另存`cat /sys/kernel/debug/clk/clk_summary`和cpufreq time_in_state；厂商Mali/DDR私有节点先从当前驱动找实际只读路径，不写猜测地址。runtime suspended时cur_freq是缓存，不能当实频 |

传感器 `hwmon power*_input` 通常为µW、energy为µJ，须按具体驱动确认单位与测量域；
没有传感器不记0W。整板功率优先用同一USB-C/直流功率计1Hz导出CSV（W、时间戳、
PD电压/电流），扣除仪器通道偏差但不扣除系统背景功耗；功率路径/回供相同。
温度改用相对环境温升，不拿CPU百分比或温度估算瓦数；自动风扇转速及噪声策略一起保存。

## 排队预算

先约45–60分钟做只读清单、GPU栈发现、一次性5.15短启动与7.3恢复门禁；如果缺闭源
GPU库/解码适配器/看门狗证据，结束窗口补离线准备，不当场试驱动。首轮核心筛查约2小时，
只能报初筛。正式三组按七启动块、每块约90–120分钟（媒体矩阵、通用负载与冷却），
加30分钟连接耐久/图像与音频外部测量约4–6小时：预计总计15–20小时，拆成多个独占窗口。
全codec解码、高位深/扩展存储接口和全部GPU场景具备能力后另加4–8小时；失败恢复另留1小时。
显示任务短窗口不适合塞入这套性能验收。细化逐项串行预算后，完整核心矩阵预计
22–24小时；当前排队以 [整夜执行计划](overnight-performance-plan.md) 为准，不把本节
初估15–20小时当作可截断采样的硬时限。
