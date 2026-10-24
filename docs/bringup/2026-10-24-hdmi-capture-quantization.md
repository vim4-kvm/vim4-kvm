# 2026-10-24：HDMI 采集 ERROR 与 FDET 周期量化调查

当前仍在前置条件阶段，**未证明持续采集稳定，未进入 VD1 透传实现或透传验收**。
设计合同见 [HDMI 透传](../hdmi-passthrough-design.md)，颜色失败现场见
[颜色自环](2026-10-24-display-color-loop.md)。不合入正式内核、不正式部署。
另一个会话持有板子和 heavy 锁期间，本任务只做离线工作，不改变其候选启动状态。

## 固定基线与已确认事实

- VM 独立工作树 `~/src/linux-7.3-hdmi-passthrough`，分支
  `vim4-hdmi-passthrough`，基于 `vim4-display-color@c24465df1dd70`。
  原 `~/src/linux-7.3` 保持该颜色分支，不切换、不改其构建输出。
- 正式 `b1300eb808f43`（运行时 build ID `eeddb005…`）与颜色候选的
  `drivers/media/platform/amlogic/t7-hdmirx/` 功能代码相同；差异仅为 Kconfig
  说明及 RX/VDIN 的系统睡眠拒绝回调。这排除了该目录中的采集算法改动，
  **不能排除显示并发、共享资源或源端行为造成的回归**。
- [lowclock 收尾](2026-10-23-hdmirx-lowclock-closeout.md)最后功能候选仍为36/38；
  `c3e6a614` 仅诊断、当时未构建上板。不能将其增益校准或跨轮询判稳当作已证实修复，
  也不能仅按 ENOLINK/ERROR 判定两次现场同源。
- VDIN 对 RX 检查的 EAGAIN 返回 ERROR buffer，但原 `capture check` 日志省略 EAGAIN。
  ERROR buffer 的 sequence 回0还可能是未赋值的元数据，不能据此推断 DMA 序号复位。
  每帧两次 RX 检查中，第一次失败会跳过 timestamp/sequence 赋值。

## 离线诊断准备

内核 `1cb9654e3fb0f` 增加错误现场，不改变 PHY、准入、时序容差或恢复行为：
记录 EAGAIN、原始两路 meter（含 VALID）、SQO、PLL、alignment、clock ratio，
输出完整 measured/lease FDET 差异；link worker 在恢复之前保留失效状态。
这与 lowclock 诊断保持可比较字段，但未引入该分支未通过验证的功能改动。

原生 [hdmirx-soak.c](../../tools/hdmirx-soak.c) 不读像素、无 GStreamer，保持输入 EDID/HPD，
用标准 QUERY_DV_TIMINGS/S_FMT/REQBUFS/STREAMON/DQBUF 测持续队列。
按真实 stride/可见高度校验 NV12 payload，允许分配尾部 padding；逐帧输出 JSONL，
先保存 flags、bytesused、sequence、VDIN IRQ frame-done timestamp 和 DQBUF 时间再判错。
两者均为 CLOCK_MONOTONIC；不是光学延迟。ERROR、序号不连续、时间倒退、断信号或
停流失败均返回失败，不自动重启掩盖故障。不读像素不能证明图像完整性，需另用运动标记校验。

命令在已持双锁、停止实际采集所有者后运行，输出须选择新文件：

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror tools/hdmirx-soak.c -o /var/tmp/hdmirx-soak
/var/tmp/hdmirx-soak /dev/video0 36601 > NEW.jsonl
```

36601个连续60Hz完成帧覆盖约610秒，避免边界取整导致不足600秒；
不使用包含启动时间的进程墙钟充当有效采集时长。
同时保存 RX/VDIN 只读状态和内核日志，区分预期 modeset 失锁与计时区间内自发错误。
离线真实 C harness 注入第250帧错误、序号跳变、时间倒退、POLLERR与停流失败，
验证报告失败、保留首个错误及 STREAMOFF/REQBUFS(0) 清理；正常路径覆盖 u32 sequence 回绕。

## 待批量对照

先取得 Mac heavy → board 两把 lockf 锁；失败就等待，不从日志推断另一会话已结束。
核对实际 build ID、保护文件、默认启动项、服务和硬件占用，再创建自己的候选目录。
用户接线/看屏/拔插仅通过 `/tmp/codex-kernel/need-user.txt` 与 `user-done.txt` 协议，
不覆盖其他会话待处理请求。单次窗口尽量合并：

1. Mac mini 真实源1080p60/4K60下，对照正式内核、颜色候选与诊断候选；
   固定实际 timing、格式、EDID、运动源及采集队列，分别≥10分钟。
2. 自环在相同1080p60输出下对照，区分原始固件输出与 Linux modeset；
   保存 TX/RX 两侧状态、HPD及失效前日志，自环禁止音频回送。
3. 若仅颜色候选失败，以相同 DT/负载复现后再二分；若基线也失败，继续按拒绝原因定位，
   不把 PHY恢复后的零计数当作源端最初停钟的证明。
4. 根因修复及真实源/自环长测均通过，才进入无换线启动、零拷贝透传与音频验收。

无换线启动的初步源码检查：当前 U-Boot `cmd_hdmitx21.c` 在 EDID parsing 失败时
无条件回退720p，发生于普通 `hdmitx output` 内部。因此只在 RAM 设置 `outputmode=1080p60hz`
再执行 `vout output` 不能解决该路径。不能删除 Linux 的 fetch/AFBC/保留内存/RDMA/SRAM
安全检查来绕过；后续须验证有界的原生接管合同或可证明不依赖 EDID 的固件命令路径。

## 第一批真实源诊断（短测，非长测验收）

用户通过文件协议确认暂停 KVM 使用后取得双锁，入场确认正式 eeddb005、manager974ab40、
UDC configured、taint0，保存保护文件。保持 Mac mini → IN、OUT → 真实显示器；
不改 EDID。新增证据接续 [另一会话交付失败](2026-10-24-display-color-user-handoff.md)。

采集工具的 `--count-errors` 持续出队并统计，ERROR 仍报失败且不算可用帧。
`--markers` 使用物理桌面的运动源，按实际 stride 在上/中/下三处检查 magic、校验和、
相同16bit帧号及NV12黑白/中性色度；这能发现采样位置的撕裂，不能证明全图每个像素。
另计源帧号重复，避免将重复画面当作新内容；每帧保存原始 V4L2 标志。

| 对象，4K60 | 出队/有效/ERROR | 出队fps /有效fps | ERROR率 | ERROR帧三处标记完整 |
|---|---|---|---|---|
| 正式基线，无像素读取 | 601/509/92 | 59.999/50.899 | 15.31% | 未检查 |
| 正式基线，运动标记 | 601/462/139 | 59.999/46.099 | 23.13% | 139/139 |
| 诊断1，运动标记 | 601/569/32 | 59.999/56.799 | 5.32% | 32/32 |

每段仅约10秒；基线标记段还与候选文件传输部分重叠，不能作为公平性能对比或长期结论。
诊断1所有601帧标记一致、仅3次源帧号重复；RX保持ready、stream_stops=0。
错误现场均为 `measurement error=-11`，PLL/SQO/align=1，两路meter VALID且时钟匹配，
无 `invalid qualified FDET`。暂定位于双次测量不一致；仍需取得两个原始快照差异。

诊断候选1为 `99093e68cb8b6`，build ID `749015c8d8c567fe54e073701d676defbe6fcd02`，
完整 Image/DTBs/2339模块构建完成；68项host fixtures及三提交strict checkpatch通过。
除RX拒绝日志外，两个确定性回归先在旧代码失败、修复后通过：
`0758b280a2ca6` 保留拒绝的READY帧时间戳/序号；`99093e68cb8b6` 防止正常STREAMOFF
继承上一帧EAGAIN而误报stream_stops，保留真正ring错误与DMA停止失败。
这些改动没有去掉ERROR标志或改变图像准入。

第一次选择候选时，操作者未等待stage完成即重启，UART证明未找到已发布候选，
自动回正式基线；记为无效启动尝试。第二次确认stage退出0、STAGED_ONLY及完整路径后，
RAM sysboot成功，PID1使用该build ID私有完整模块，watchdog30s、panic_on_oops1。

## 两次测量差异与修复候选

`059b1d8117a97` 仅打印被拒绝的两次完整FDET。真实Mac mini 4K60下，
限频捕获的拒绝对均为几何/极性相同、period差1–2 ticks，例如2777825→2777824、
2777823→2777821；两路meter有效、PLL/SQO/align均1。第二个诊断窗口601帧中63个ERROR，
三处标记均完整，没有失锁。证据 `fdet-pairs.log`、`diagnostic-4k-markers-2.*`。

`03cabbd5cd714` 将两个问题分开处理：每个24bit周期计数用upper/low/upper读取，
拒绝跨字节进位的读撕裂；两个各自完整的时序用**既有500ppm租约比较**判定一致，
几何/极性仍须逐字段相等，并验证两次测量的范围后发布较新值。未增加租约容差、
未改PHY参数或物理失锁门禁，也未将ERROR帧交给显示。此前双次计数要求精确相等，
与租约允许计数器量化的既有合同矛盾。

新增实际C测试重放量化（旧代码失败）、模拟落在500ppm以内的跨字节读撕裂，
同时保留porch变化、60/59.94、非法测量与物理失锁拒绝。68项host fixtures通过，
strict checkpatch零error/warning/check。完整Image/DTBs/2339模块构建完成；
修复候选build ID `d4775f984ffd2db3a4ca185e7dd15a946eb1f8f2`，Image SHA256
`e2ee08820603031425e6cf27e9695ebd3ea494b15384edc93ec618ad76ab70b5`。
尚不能将此扩大为lowclock 36/38中所有QUERY/PHY失败均已解释或修好。

## 厂商5.15同源对照

5.15的1535项登记文件和版本化Image/initrd/kvim4n DTB逐项匹配，虚拟介质为空。
仅在新建小配置中引用既有产物，RAM sysboot选择；默认7.3及完整模块不改。
运行时将rpt_edid_selection设1并加载同一RTK EDID（SHA256
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`），未调用持久保存。
两端实际均3840×2160p60、SDR、YCbCr444、8bit。

原生vfmcapsrc NV21 → appsink，在同一运动源检查三个高度的亮度帧号，单调时钟计时，
120帧预热后36001帧：599.980658秒、60.002fps，最大取样间隔17.800ms；
invalid/torn/GStreamer corrupted均0，重复22、跳号22，驱动frames_dropped为0。
重复/跳号保留为内容节奏观测，不等同于损坏或内核丢帧。该接口没有7.3的同一V4L2 ERROR
标志合同，不能把corrupted=0改写成“5.15 VDIN ERROR计数为0”。源码/证据在
`logs/hdmi-passthrough/scripts/vendor-integrity.c`、`vendor-4k-long.*`及1Hz样本。

源码复核：One-KVM VIM4的Wave5路径为v4l2src → plane_bridge → encoder_source，
桥接复制FLAGS但未显式拒绝CORRUPTED；通用linux.rs的V4L2 ERROR丢弃路径排除了vim4构建。
不能先验认为One-KVM“静默跳过ERROR”，或从浏览器60fps推出原始ERROR为零。
本轮不改应用；下一轮消费者须在分发前遵守ERROR与帧租约合同。

本任务日志在 `logs/hdmi-passthrough/`；整体实现与恢复状态见
[透传实现记录](2026-10-24-hdmi-passthrough.md)。修复后长测待追加。
