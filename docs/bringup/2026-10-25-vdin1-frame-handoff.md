# 2026-10-25：VDIN1 逐缓冲交付与 RDMA 时序核实

结论：当前 5.15 原生 HDR 双路径的 VDIN1 以 RDMA 提前提交下一帧地址，
在下一次帧同步执行，之后再由下一次中断交付给 V4L2。不能把 `curr_wr_vfe`
解释为“中断时已经采完的帧”，也不能将 `last_wr_vfe` 交接直接算成可删除的
16.7ms 闲等。此前[延迟调查](2026-10-25-kernel-video-latency.md)将其列为优化线索，
本次用实际缓冲地址、待执行表、已执行表和交帧事件核实并纠正该解释。

## 核实方法

持有 board/heavy 双锁，运行既有 One-KVM H.264 观看者；不切换内核、不改输入、
分辨率、游戏模式或 RDMA 配置，不替换程序、模块，也不额外读取硬件寄存器。
内核 `5.15.137-vim4kvm-hdrdual6`；运行中及磁盘 `aml_media` 的 build ID 均为
`23e626b292b873cf1635f5dd2b1567200decb3f2`，与 VM 的 hdrdual6 已打包模块一致。
当前 VM 开发树的模块 build ID 不同，因此只用匹配的打包模块反汇编核实 ABI/偏移，
没有拿当前工作树构建产物猜运行结构体，也没有修改 VM 的现有改动。

使用独立 tracefs instance 和独立命名 kprobe 组，记录函数参数及普通内存中的
帧/缓冲/RDMA 表字段。没有清空或修改已有全局 tracer。每次采样 5 秒，结束删除
本次 instance 和探针。最终有效窗口 300 次 VDIN1 vsync、300 次寄存器 RDMA 完成、
300 次发布、300 次 V4L2 ready，3000 个事件，所有 CPU overrun/dropped events 均 0。

关键调用链：

1. `vdin_v4l2_start_tvin` → `start_tvin_service` 注册 `vdin_v4l2_isr`。
2. `vdin_frame_write_ctrl_set` → `vdin_set_frame_mif_write_addr` → `rdma_write_reg`：
   当前 `rdma=1`；写入的是软件 `reg_buf`，没有在这个调用中直接切换硬件图像地址。
3. `rdma_mgr_isr` 根据寄存器 DMA 完成状态调用 `vdin_rdma_irq`，后者调用
   `rdma_config(handle=3, trigger=0x4)`。将待执行表复制至 DMA 表并设置输入触发，
   不使用手动立即执行模式；VDIN1 DTS 的 `rdma-irq` 正是 0x4。
4. 下一次 RDMA 完成回调的 DMA 表中才出现上述新地址；同时可看到软件 pending 表
   已经是再下一个缓冲。以实际地址匹配，不仅比较变量名称或中断次数。
5. `vdin_vframe_put_and_recycle` → `vdin_v4l2_if_isr` → `vb2_buffer_done`，
   使用对应 vframe index 返回同一个缓冲。

`vdin_drv.h` 中 `curr_wr_vfe`/`last_wr_vfe` 的原注释也明确指出：当前中断配置
的地址因 RDMA 要到下一次中断才写入。普通 ISR 的 game-mode 分支不等同于当前
V4L2 ISR 的交接约束，历史普通 VDIN0 的降延迟结果不能直接套到这里。

## 同一缓冲的实际证据

取 index=5、luma 物理地址 `0xb0e00000`（寄存器值为地址右移 4 位）：

| 单调时刻（秒） | 事件 |
|---|---|
| 2094.255448 | `set_mif` 提交 index=5，rdma=1 |
| 2094.255450 | `rdma_write_reg` 将 `0x13cc=0xb0e0000` 加入待执行表 |
| 2094.255459 | RDMA 完成回调：已执行表仍是前一缓冲 `0xb020000`，pending 才是 index=5 |
| 2094.255466 | `rdma_config(3, 0x4)` 提交新的 7 项寄存器表 |
| 2094.272132 | 下一次 RDMA 完成回调：已执行表出现 `0xb0e0000`；图像写地址已切至 index=5 |
| 2094.288737 | 发布 index=5 |
| 2094.288740 | 同一个 index=5 进入 V4L2 ready |

追踪分析对 300 次 pending 表逐一匹配，全部对应当次提交地址；299 次可匹配的
已执行表全部对应上一拍提交地址。窗口内 298 个从提交到交付均完整的缓冲，
全部满足 **N 提交 → N+1 表已执行 → N+2 交付**，没有例外。
窗口头尾的在途缓冲不具备完整配对，不混入时长统计。

| 同一缓冲的间隔 | 有效数 | 中位数 | 最大值 |
|---|---:|---:|---:|
| 提交地址 → 对应寄存器 DMA 完成回调 | 298 | 16.678ms | 16.729ms |
| 对应寄存器 DMA 完成回调 → V4L2 ready | 298 | 16.629ms | 16.682ms |
| 提交地址 → V4L2 ready | 298 | 33.306ms | 33.358ms |
| 发布函数入口 → V4L2 ready 函数入口 | 298 | 3µs | 4µs |

这些间隔属于缓冲地址调度和交接，不是 HDMI 像素到浏览器的端到端延迟。
“RDMA 完成回调”只证明寄存器表已执行，不能当成整帧图像 DMA 完成。
VDIN1 当前只有 `vsync_int`，没有注册独立 write-done IRQ；源码中 HDMI 路径
也不会进入 VIU1/CAMERA 专用 `vdin_write_done_check` 分支。
本轮没有测出最后一个像素写完的精确时刻，不能据此声称绝对没有其他微小等待。

## 对优化结论的修正

若在 N+1 将当次 `curr_wr_vfe` 直接交出，会交出刚被 RDMA 选为本轮图像写目标
的缓冲；现有证据不支持它此时已经完整。删除延后交接的分支不是已成立的优化。
若继续降低延迟，应另行设计并验证地址提交/生效时序或真实图像写完成交付，
不能把 33.3ms 的“预约地址到交付”当成两帧图像采集，也不能承诺直接省 16.7ms。

本次未改变任何生产逻辑。原始记录位于本地忽略目录：
`logs/vdin-behavior-{trace,rdma-trace,table-ready-trace}.txt`、
`vdin-behavior-*-status.json`、`vdin-behavior-summary.json`、
`vdin-behavior-analysis.py`、`vdin-behavior-trace.py`、匹配模块的反汇编及观看者日志。
第一轮 Python 文本 append 对 tracefs seek 返回 EINVAL，未安装探针；改用原始 append fd。
一次窗口恰逢观看者已结束，只得到 VDIN0 的 RDMA 配置事件，保留但不作为 VDIN1 证据；
最终窗口先等待 VDIN1 活动 IRQ，再采样。探针始终在 finally 中关闭并删除。
收尾时 One-KVM/HDMI PID 仍为 4097/1094、服务 active，failed units=0，
taint 保持 12800，核实窗口无新增 Oops/BUG/WARNING；探针组和 instance 已清空。
