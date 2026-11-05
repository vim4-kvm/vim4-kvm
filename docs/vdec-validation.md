# 解码标准验收

使用 Linux media 的接口规范和标准码流证明驱动行为；规范不意味着准备上游投稿。
内核代码规则见[内核](subsystems/kernel.md#内核驱动开发与验证)，板窗口及恢复统一走
[board-window](board-window.md)。本页描述工具合同，不代表实板已经通过。

## 离线准备

[Fluster 锁](../packaging/kernel/vdec-fluster.toml) 固定源码提交、实际测试集名、
选择的 profile、解码器名和时间预算。H.264/MPEG-2 在 7.3 用 stateless，HEVC 用
stateful；5.15 先检查同格式的 stateful 解码器是否实际可用。没有 JPEG 测试集，
MJPEG 继续用既有样本，结果不能标作 Fluster 一致性通过。

[准备入口](../packaging/kernel/prepare-vdec-fluster.py) 默认只读已有的干净锁定源码，
输出所选测试集；显式下载才联网。码流留在宿主，Fluster 校验发布者的 MD5，
准备器再保存源归档及解压输入的 SHA256。中断后可用原输出目录重试，保留下载缓存，
重新校验、提取输入。封存后不能原地改动；按清单导出时不带下载缓存。
下载站拒绝部分请求时可用离线 `--seal-cached`：只从摘要正确的归档重新提取输入，
仍保留完整测试集及不可用项的原因；包含不可用码流的窗口不启动解码进程。
导出的源码保留 Fluster 原许可证与版权。板上只运行已经传入并核验的内容，不下载码流。

MPEG-2 的上游套件使用像素比较，必须提供 ISO 参考解码器；空 `result` 不是缺少
MD5，也不能自行改成 FFmpeg 输出作为判据。用户授权仅本地验证后取得 ISO 归档，
用[参考构建器](../packaging/kernel/build-vdec-mpeg2-reference.py)验证锁定哈希，再以
Fluster 的 Meson 配方构建。授权不包含将参考源码、二进制或码流入库、发布。

调试配置用[片段](../packaging/kernel/vdec-debug.config)合并正式配置，运行
`olddefconfig` 后把完整配置哈希写入私有候选锁，再用[build.sh](../packaging/kernel/build.sh)
构建新 release 的整包。不要修改已验收配置；不能混用生产 Image 与调试模块。

## 窗口与结果

[vdec-window.py](../packaging/kernel/vdec-window.py) 的 `compliance`、`fluster`、
`performance` 接受离线准备的 `--validation-plan`；默认不 SSH。
执行仍需原有显式执行标志、内核 manifest 和现场/一次性启动条件。
原先仅面向历史内核的诊断动作保持原准入限制。

验证计划分成以下几组，具体字段校验见入口中的 `validate_acceptance_plan`、
`require_acceptance_kernel` 和三个 `run_*` 函数：

| 内容 | 用途 |
|---|---|
| 内核侧、候选根、保护文件和逐文件工具/输入哈希 | 实际 release/build ID、只读模块挂载、生产启动文件、性能 CPU 策略及看门狗一致后才操作驱动 |
| 可选私有驱动与源码差异 | 模块迭代必须对应同一 Image/BTF，保存基准源码、差异摘要、模块摘要/vermagic 和实际加载 build ID，不覆盖正式模块 |
| 已建立的 board-window 名、串口、原应用视频检查 | 复用该窗口的基线 proof；无论成功失败都收集结果并调用 return-baseline，不另建恢复流程 |
| 测试时长、恢复保留时间 | 窗口不能超过项目上限；已有板票必须足够。测试耗尽预算时保留未运行状态并退出 |
| Fluster bundle 哈希、测试集、开始位置/数量 | 同一套件可拆成多个窗口，两版内核使用相同输入；每次只启动一个码流进程 |
| compliance 节点、格式、带帧头输入和 media 节点 | 配置输入格式后运行 streaming；media 拓扑用 `-M` 单独检查，视频用 `-d` 并自动关联 Request API 的 media fd；保留版本、完整输出及每个 summary |
| 性能管线、运动输入、同步模式及具名时钟文件 | 不修改 CPU/DVFS 策略；不扫描任意 MMIO；同步采集处理进程 CPU 和实际时钟读数 |

Fluster 每个窗口先实际运行 `list -c`。解码器或参考解码器不可用就停止；退出零但
没有所选码流 JSON 也算错误。原始 JSON/日志和逐项状态一并保存，未到达和窗口外的项
仍为未运行。超时终止 Fluster 和它的子进程，停止后续码流；不能据进程已杀断言 DMA
已停止，失败留下恢复标记，禁止自动卸载重载。内核日志、kmemleak 和原始测量另存。
内核启动诊断必须在操作解码器前检查，不能等测试结束才发现启动时已有 splat。
上传、远端运行和结果采集共用同一个租约预算；远端另设进程超时，不能只依赖 SSH
超时。恢复预算不足时写交接记录，不在票据过期后发起重启。
Fluster 计划可同时带节点列表，在同一调试内核窗口先跑 compliance，再跑标准流；
compliance 也启用首个失败/警告即退出。
锁定版本的 `-m` 会覆盖 `-d` 并遍历 media 下所有节点，不能用它给单个视频节点
附加 media 检查，否则会在其他 codec 输入配置前提前测试它们。结果必须恰好包含
所请求设备的一个总结，发现额外设备或缺少总结即失败。
计划的 `fluster_followups` 可在首组通过后追加已封存的测试子集，逐组输出独立
结果目录，全部共用原截止时间。像素 Fail 或解码 Error 按流记录后继续收集；
Timeout、内核 BUG/WARNING/KASAN、DMA 停机失败或挂死立即停止并恢复。
每流结束都检查内核日志；预算不足时保留 Not run，下一窗口从未运行项继续。
`window-status.json` 的 success 表示窗口安全完成，conformance_passed 才表示
所选码流全部通过，不能以进程退出零替代逐流结果。生产配置窗口可以验证
功能和像素，仍核运行配置哈希，但必须与尚未完成的调试内核锁/内存验收分开记录。

compliance 本身有覆盖边界：所用上游版本的 `testRequests()` 不生成 stateless
codec 的完整控制，收到缺少控制的 ENOENT 后停止该 Request 流检查。独立的
MMAP streaming 仍可运行，并对返回 ERROR 的缓冲检查 sequence 等队列语义。
因此既不能把它写成“完全不跑流”，也不能把缓冲往返通过写成有效像素解码通过；
保留实际跳过项及 ERROR 缓冲证据，真实 stateless 出帧和参考正确性由 Fluster 补足。

性能程序[源码](../packaging/kernel/vdec-benchmark.c)只统计实际 fakesink 渲染/丢帧，
不映射和比较像素。最大吞吐不按时钟限速，实时播放测完整时长；后者明确记录 sink
的 lateness/drop 策略。提前 EOS、首帧/出帧停滞和 drain 超时都失败。原始结果含
墙钟、启动耗时、帧间跨度、FPS、CPU 时间，不能把软件管线自检当作硬件性能。
共存计划保留 KVM 服务，并在同窗口启动独立视频接收器；两边原始时间与丢帧计数
用于核对重叠区间。必须保存输入运动证据，静态画面不能代替性能验收。

## 记录口径

每套件报告通过/总数，另列失败、超时、未运行和不支持；不把缺失工具记为通过。
7.3 与 5.15 对照逐条解释差距，私有 ABI 接不上标准工具时注明实际替代方法，不能
虚构标准工具结果。实板记录从[索引](bringup/README.md)进入；KUnit 与旧样本只补充
对应边界，不替代 streaming、一致性、调试内核和同板性能证据。
