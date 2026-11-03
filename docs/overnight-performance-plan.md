# 5.15 / 7.3 分窗性能执行矩阵

> 第二轮用户决定：不执行完整56窗矩阵。只运行快速A/B/A，目标总占板≤45分钟，
> 硬上限64分30秒；1800帧/codec、30秒视频采样，仅p50/p95快速初判。
> M6只经MCP浏览器启动一次运动源，批末关闭，不开SSH、不测声音。
> 标记dispatch→呈现代理值包含HTTP送源和源绘制调度，不能当标准源绘制延迟。
> 下列完整预算仅保留为正式验收参考，不再排队执行。

摘要：替换旧22–24小时连续占板计划。P0-2只测视频、CPU与内存，不测声音；
GPU复用[uhd5 r11](bringup/2026-10-31-kbase-r11-policy.md)。完整矩阵预算
**56个窗口、21小时19分15秒占板**，超过3小时，因此本轮只执行离线准备和
**2160p60 H.264 60Mbps的一组A/B/A**（3窗、64分30秒上限）。未完成项不能判通过。
预算由 `python3 tools/perf-baseline.py matrix` 输出；排队等待不计占板。

## 窗口与配对

A=5.15，B=开跑时 `packaging/kernel/sources.toml` 的最新tested_build。
P0-1统一候选未完成时，可用当前uhd5验证工具；标为预演，统一候选就绪后全部重测。
固定来源锁副本、Image/DTB/模块/固件/私有用户态哈希，不能按release名字判断相同。
不重新构建内核、不切换其他任务的Linux分支，不把普通安装包当RAM候选归档。

每个矩阵分段按 **A0→B1→A1→B2→A2→B3→A3** 配对；A1/A2可共享为
相邻组后/前对照，每个B必须独立采样。分段优先排完七个样本再进入下一分段，
避免完整块横跨多日。一个窗口只做本段；下一票有人等待时排到队尾。
同批候选用 `board-window boot-candidate` 链式RAM启动，批次结束一次
`return-baseline`；A采样前按需返回5.15。默认启动始终5.15，恢复失败停止。

跨窗口必须同物理HDMI源、同运动程序/素材哈希、同公共用户态及浏览器、
同采集/编码/网络/affinity/DVFS设置、同日期与温区（起点差≤2°C）。
基线缓存使用 `board-window baseline --settings public-settings.json --files ...`，列全5.15内核、启动文件、
应用和插件；保留source_time/reused。缓存只提供身份与短接收基线，不能替代本矩阵
原生编码或像素延迟的A样本；复用同一样本不能凑出三个独立B。
源、codec、码率、浏览器或接收机器写入settings；变更后更新JSON重新测量。

每组冻结epoch（包含离线构建结束时间和源/用户态/设置清单）。窗口之间任何构建、
升级、部署或源设置变化，即使最终哈希相同，该组也作废，开启新epoch、重新A/B/A。
采样重叠heavy、源不推进、时钟失准、尾段冻结或A漂移超限均保留原始数据并标受干扰/失败。
跨日A缓存失效；需要新增A时另计窗口，不能拿昨天的数配今天的候选。

## 串行矩阵与预算

下表是**每个A或B样本**的窗口；共8段×7样本=56窗。预算含启动、服务就绪、
温区确认、传感器、恢复与证据收尾。超时停止本窗；不延长租约补样本。

| 分段 | 负载与配置 | 测量硬上限 | 额外预算 | 单窗上限 |
|---|---|---:|---:|---:|
| native-0/1 | 1080p60：capture、H.264 12/60Mbps、H.265 12/60Mbps、JPEG Q80，按顺序每3项一窗 | 3×240秒 | 480秒 | 20分×2窗 |
| native-2/3 | 2160p60：相同六项 | 3×240秒 | 480秒 | 20分×2窗 |
| receiver-0 | 1080p60，H.264/H.265×12/60Mbps，各像素延迟及无回读呈现两轮 | 8×165秒 | 360秒 | 28分 |
| receiver-1 | 2160p60，相同八轮 | 8×165秒 | 360秒 | 28分 |
| quality | 两尺寸×（H.264/H.265各12/60Mbps、JPEG Q80）；另轮录像，120帧预热+1800帧；离线解码/三处ID/profile/细线颜色核验 | 10×90秒 | 480秒 | 23分 |
| cpu-memory | 两capacity簇单核、8线程CPU；1/8线程内存读/写；各15秒预热+120秒 | 7×135秒 | 480秒 | 23分45秒 |

每样本合计182分45秒，七样本共1279分15秒。不包含失败重测、额外冷却或新增恢复窗；
若无法在预算温区启动则退出，重新排队。各原生计时轮900帧预热+7200帧，
240秒watchdog；receiver含15秒预热+120秒采样，165秒watchdog。
录像轮有I/O，不能计入吞吐或CPU对照；离线分析不持板锁。
sysbench内存报告程序传输MiB/s，不称DRAM物理带宽。CPU/内存开始前先预热。

首组每个A/B/A窗：2160p60 capture及H.264 60Mbps两项（2×240秒），
同配置像素延迟/无回读呈现（2×165秒），额外480秒，共21分30秒/窗。
三窗64分30秒，仅一组不能满足三组门禁。完整矩阵剩余仍需56窗；首组只在
日期/epoch/设置/证据全部匹配时抵扣对应样本，不能简单用56减3。
本轮结束后停止排队，由用户决定剩余矩阵的执行时间。

## 执行与证据

1. 先离线构建所有二进制，运行原生夹具与全套unittest。构建用
   `tools/board-queue run --heavy --who P0-2 --purpose build --max-min 30 -- ...`。
   Python/JS不需编译；记录Swift源程序、ARM64基准、依赖和源码SHA256。
2. 真正上板才用 `tools/board-queue run --who P0-2 --purpose perf-key-A0 --max-min 30 -- ...`。
   `board-window collect --readonly`保存服务、UDC、dmesg、身份。运动源先稳定，
   不向开发M4注入HID；源与receiver须同钟，不能将M6源日志直接与M4墙钟相减。
3. 采样前 `board-queue sampling on`；确认status显示sampling，用离线队列测试验证
   heavy互斥，不能真的启动编译来验证。禁止编译/部署/ptrace及额外观看者。
   `perf-sensors.py`全程1Hz，缺失传感器保留缺失，不记0。
4. 原生工具以khadas运行，停实际编码应用、保存原状态并有界恢复；不删活跃vpu锁。
   端到端恢复同一One-KVM，仅视频独立页面：
   `node tools/latency-receiver.mjs "$URL" 120 --one-kvm --expect-codec=h264 --verify-coherence`。
   实际解码推进后预热；source/receiver日志经 `latency-summary.py` 匹配，同钟≤2ms，
   ≥1000有效标记才判P99。无回读另轮，不能混计回读扰动。
5. `sampling off`后收集失败/返回状态、打包原始证据并立即释放。原始stdout/stderr、
   退出码/timeout、source、receiver、sensor、driver JSON、manifest均保留，不覆盖失败。
   只确认音频服务状态，无音频采样。稳定性上限10分钟；旧30分钟增长项本轮待测。

单指标compare使用schema=2：每run除value/valid/config_sha256/evidence，另含
run_id、backend（stock/edge/stock）、day（本地日期）、epoch、source_sha256。
epoch从完整清单和构建记录生成，不能手填相同字符串掩盖构建。
`perf-baseline.py summary metric-*.json`逐项汇总，任一待测/失败返回非零。
工具不自动证明原始日志存在或时钟/画质合格，审查者仍需核验；一组输出为待测。
判定沿用[协议](performance-baseline.md)，缺失项不给通过，分段分位数不能相加。
