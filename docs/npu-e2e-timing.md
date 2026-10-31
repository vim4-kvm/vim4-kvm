# NPU 端到端分段：离线分析与下一窗口

最新[分段上板记录](bringup/2026-10-30-npu-e2e-window.md)：增量集中于fwrite，计时扰动目标未获确认，DDR/累计视频计数仍缺；以下保留离线分析与原清单。

基于[四启动对原始记录](bringup/2026-10-30-npu-boot-pairs.md)，本轮离线，不访问板子或GPU文件。
没有已证实可删除的7.3驱动开销，不改驱动、不生成uhd3、不push/pin。
保页例外仍为**用户已于 2026-10-30 接受**。

## 残差能说明什么

旧 `measure.py` 在 Popen 前到子进程 wait 返回后立即测 wall，之后才计算输出 SHA；
`wall−create−destroy−ΣSDK elapsed` 含输入读取/malloc、动态装载/进程启动退出、
stdio日志、路径格式化、文件打开/写入/关闭、float有限值扫描、调度和父进程唤醒。
不是纯输出时间，也不含后续张量哈希；平均除总轮数会摊入冷启动固定成本。
原始程序没有逐段时间戳，无法从旧记录逆推出各项毫秒数。

现存CSV的进程wall/总轮数（四boot等权，含冷轮/create/destroy）为：

| 模型 | 5.15 ms/轮 | uhd2 ms/轮 | 总wall均值比变化 |
|---|---:|---:|---:|
| VGG16 | .676691 | .740863 | +9.48% |
| DenseNet | 2.144742 | 2.252481 | +5.02% |
| YOLOv8n | 37.696864 | 41.299409 | +9.56% |

YOLO残差增加3.516084ms，相对约30ms SDK是约11.7%，相对完整约37.7ms循环则约9.3%；
进程wall实际差3.602545ms。以上是本次工作负载的观测差，不是已获得置信资格的总体端到端退化。
这说明SDK门禁不足以覆盖真实端到端体验，后续同时报告两种端点，不能只看SDK平均值。

## 步骤与两版内核路径证据

厂商根为主仓 `common_drivers/drivers/adla/kmd/drv/`，下表简称V；
新根为VM `~/src/linux-7.3-npu-integration/drivers/misc/adla/drv/` @f71b5c6289cb，简称N。
内核根K5为VM `~/src/linux`，K7为上述integration树。路径/行号为本轮只读核对结果。
闭源SDK只有头文件接口，不能凭函数名断言其内部调用顺序或频次。

| 步骤 | 原计时归属 | 5.15/7.3路径、差异及结论 |
|---|---|---|
| input_set/output_get；输出反量化/拷贝 | SDK elapsed内 | tools/npu-probe.c:105–113包住两调用；请求FLOAT32。公开头文件nn_sdk.h:585声明output_get。若SDK在两调用内做反量化、拷贝、分配或ioctl，均已计时，不能再计入残差；返回指针可能在后续CPU读取时才发生缓存缺失，具体内存归属未证明 |
| ioctl往返、REQBUF与缓存维护 | 随SDK调用位置，通常在create/SDK/destroy对应区间 | V/N port/platform/linux/adlak_fops.c:192–211接FLUSH_CACHE；V common/adlak_mm.c:347–370按is_partial/offset/size派发；V/N port/os/linux/mm/adlak_mm_os_common.c:520–594逻辑相同，未见7.3新增逐轮整块维护 |
| cache范围/方向 | 同上，CPU后续读的缓存状态可外溢到残差 | 同文件:528/564仅cacheable缓冲同步；:541/576非partial用req.bytes，partial用offset/size，SG逐段对应；device方向TO_DEVICE，cpu方向FROM_DEVICE。不能按输出长度擅自缩短SDK申请的范围 |
| 底层DMA cache实现 | SDK同步调用内部 | K5 arch/arm64/mm/dma-mapping.c:17–26走__dma_map_area/__dma_unmap_area，cache.S:232–250依方向选clean/invalidate；K7同C文件:15–31走clean_poc_nosync/inval_poc_nosync，kernel/dma/direct.h:59–85再批量屏障。两版标准实现有差异，但不是证实重复同步的依据，删屏障不安全 |
| 用户映射cached/uncached | 映射调用内部；访问缺失成本落到实际访问阶段 | V/N同mm文件:434–485均remap_pfn_range，USER_CACHEABLE标志；pgprot_writecombine在#if 0内，不生效。vm_mmap创建PROT_READ/WRITE普通用户页属性；7.3用vm_flags_set替代直接写flags。没有“7.3新改成uncached”证据。:707(V)/712(N)的writecombine是另一个内核vmap分支，不能当SDK用户映射属性 |
| mmap/munmap、分配 | 取决于SDK何时调用，probe本身没有每轮申请/释放输出 | V common/adlak_mm.c:111–130仅REQBUF且mmap_en时映射；V/N同mm文件:626起vm_mmap，UID mmap为fops.c:402–412；N:644锁内remap，:657/671失败回滚；正常unmap N:696、V:691。7.3修锁/失败回滚，没有新增正常逐轮映射；SDK是否每轮重新请求需要具名跟踪验证 |
| 页错误、页大小 | malloc/文件页/CPU访问所在阶段 | K5 .config:400、K7 ~/build/npu-integration/.config:452均ARM64_4K_PAGES。V/N remap_pfn_range预建PFN映射；不能将所有fault归于ADLA映射。输入malloc/fread、libc stdio、tmpfs新文件页仍可能缺页/分配；旧记录无fault计数 |
| DMA-buf与IOMMU | 不应凭平台配置推断调用 | V/N ADLA源码无dma_buf_begin/end_cpu_access调用，走厂商cache ioctl；ATTACH外部物理页不是通用dma-buf导入。N amlogic-t7.dtsi:27–49无iommus/dma-coherent，非一致性DMA路径；两版mm文件:138–225用dma_map_sg/page，设备自管MMU见common/mm/adlak_mm_smmu.h:34–48的4K/2M/1G页表。CONFIG_IOMMU_DMA=y不代表ADLA接系统SMMU；SDK若另外使用dma-buf须独立证据 |
| 文件输出 | SDK elapsed外 | probe:139–153的fopen/fwrite/fclose，tmpfs仍有VFS、页分配、从输出buf拷贝及stdio flush；两版都走普通文件系统写路径，不是ADLA ioctl。旧probe忽略fclose错误，本次改为明确失败。无fsync，不能称落盘持久化时间 |
| 有限值扫描/日志 | SDK elapsed外 | probe:168–175逐float isfinite，另有printf/路径构造。反复读取SDK返回指针可能暴露内存缓存/DDR差异，但不证明其为uncached；调度等待会计入任意阶段wall，需CPU/切换计数辅助辨别 |

尚不能确定3.5ms属于哪一项，也没有“多余整块invalidate/重新映射”的调用次数证据。
尤其SDK反量化、输出分配与厂商DMA同步不能仅凭残差被重复归账。

## 分段接口与开销预算

`tools/npu-probe.c MODEL INPUT ITERATIONS --timing`，可与`--profile`组合，但诊断不与性能组混用。
`npu-validate.py run --timing`也可转发此选项，分段存result.json的stage_timings_ms及probe.log，缺行则拒绝；旧baseline的probe SHA不同，
不能直接用compare接受新probe的性能资格；本次诊断单独比输出SHA。
原`iteration=… elapsed_ms=…`格式及起止调用不变；没有在input_set/output_get之间加时钟或日志。
所有新增逐轮结果缓存在预分配且预触页记录中，destroy后统一打印：

- `sdk_ms`与原elapsed逐字符同值；`open/write/close_ms`分别是stdio阶段（write不等于物理盘IO）。
- `scan_ms`单独覆盖有限值扫描；`other_ms`覆盖日志、路径构造、输出验证和循环统计。
- `e2e_ms`从本轮SDK起点到扫描结束，等于以上六段之和；`gap_ms`为上一轮末到本轮起点。
  `begin/end_ms`为单调时钟绝对值；稳态周期用e2e+gap，冷轮独立。输入初始化有`timing_input_ms`。
  `timing_first_output`在结束后打印首轮输出地址/长度，结合诊断期间保留的maps辨认SDK返回缓冲归属；
  不代表每轮地址都不变，也不读取destroy后的缓冲。
- context级getrusage记录minor/major faults与主动/被动切换增量，只有首尾两次，不按轮增加系统调用。
  它不能给每段fault归因；必要时下一窗短诊断仅跟踪自己的probe。
- 单输出每轮新增6次clock_gettime，YOLO三输出14次；无新增逐轮malloc/额外输出拷贝。
  `clock_call_ms`为20000次预校准均值，`extra_clock_calls_max`给出上界调用数；
  校准耗时与最终输出耗时分别报告`calibration_ms/timing_emit_ms`，不可摊入生产循环。
  新probe进程wall含这些诊断成本，不能直接与r12旧probe wall做端到端资格比较。
- `<1%`为必须在板上确认的目标：先检查时钟预算`calls*clock_call_ms/min(暖SDK)<.01`，
  再做同boot关闭/开启分段的交替短context对照。时钟估算不含所有指令和缓存扰动，
  未经实测不能保证硬上限；若超过预算或差异无法分辨，诊断仅用于定位，不混入性能CI。

宿主测试以SDK替身运行实际C文件，验证三输出字节一致、SDK字段不变、各段时间闭合、
gap非负、profile组合与非有限输出失败；不模拟硬件性能。Mac及ARM64 VM均按
`-std=c11 -O2 -Wall -Wextra -Werror`使用实际SDK头文件编译对象成功；未链接/运行板上SDK。

## 下一窗口：≤25分钟，只定位、不补四对门禁

1. 0–4分钟：等GPU结束，5.15默认/服务/锁核对；备份启动与运行时文件，固定同probe/SDK/模型/输入SHA。
   两kernel同CPU频点与放置、同tmpfs输出位置；不写PWM或电压。记录DDR能力：
   A只读已审阅`/sys/class/aml_ddr/freq`；B先盘点已知devfreq/CCF可得状态，
   不盲扫MMIO，不写debug freq。若无真实DDR读回，明确缺失，纯驱动资格仍不确定。
2. 4–10分钟A：stop流并确认无消费者，保存间隔≥2秒的两次视频raw/encoded/丢帧计数，
   必须静止；若仍推进就固定相同背景并标条件不齐。先验证计时开销预算，
   每模型三个context、V/D1000去50、Y101去10，保存原逐轮完整输出/分段/CPU温度频率/PM。
   同boot短context开关交替只作扰动诊断，不更换较慢性能样本。
   `/api/stream/status`的clients/fps不足以证明计数静止：One-KVM stream_manager.rs:793–805
   仅取pipeline FPS，内部shared.rs:525–541虽有encoded计数，并未在该API完整暴露。
   窗口前须确认已有具名日志/接口可读累计计数；拿不到就如实单列缺口，不用stop成功冒充证明，
   不为造计数而打开视频接收者，不改变HDMI HPD/EDID。
3. 10–16分钟B：uhd2 RAM一次性启动，同样证明静止计数和采集分段；不更改DPM策略。
   附`/proc/PID/maps/smaps`与输出指针归属诊断；如需ioctl/mmap/munmap/cache调用计数，
   独立≤30秒、只过滤本probe的trace，绝不ptrace视频进程，不将该组作为低开销延迟数据。
   按阶段比较wall与fault/切换，write差大先分辨tmpfs分配/复制，scan差大再查CPU读/DDR。
4. 16–20分钟：回5.15，核对哈希/权限、服务、UDC与原CPU/亲和设置，释放全部锁。
   余量5分钟。每个子进程≤60秒，单项≤10分钟；无HID、声音或现场驱动改动。

本轮没有uhd3，所以不安排候选资格门禁。若定位后产生修复，另预登记≤30分钟平衡启动对，
同时报告SDK与端到端暖均值/P50/P99/max及启动层CI；CI跨界或条件不齐仍判不确定，
不能将本次每边一启动诊断升级为总体≤5%证明。

离线验证：Mac及ARM64 SDK替身测试通过；主仓首次全测312项、7跳过，唯一失败为并行GPU会话
尚未登记的`docs/bringup/2026-10-30-gpu-repair-window.md`，未改动该文件或替其登记。
对方补齐索引后，最终主仓全测312项、7跳过，OK（本机build/npu-kernel/e2e-unittest-final2.log）；
`git diff --check`通过。板上开销与分段归因均未实测，不报告为通过。
