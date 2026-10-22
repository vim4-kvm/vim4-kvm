# 2026-10-22：Wave5 非对齐 HEVC 挂起离线分析

仅离线分析、局部修复候选和取证工具；**没有证明固件卡死根因，没有实现通用超时复位恢复**。
本轮未连接板子、未取得板锁、未安装或重启。并行正式部署的瞬时状态不属于本轮证据；
不把此前的基线恢复记录写成本轮恢复成功。非 8 对齐 HEVC 仍保持禁用和应用 H.264 回退。

## 输入与交付

现场依据：[首次失败](2026-10-22-edge-hdmi-modes.md)、
[最终复核](2026-10-22-edge-hdmi-modes-final.md)。两次 1366×768 HEVC 超时，
第二次使用专用插件和 Main/5.1；退出/重启挂起，最终物理 RESET。
缺少线程栈、寄存器和返回码，不能确定等待链或由 SSH/SysRq 不响应断言固件死循环。

VM `vim4-build` 独立工作树 `/home/deepdream/src/linux-7.3-wave5`，
分支 `vim4-wave5-hang`，起点 `e0346697f2503`，原工作树保持干净、未切分支。

- `a64f5e574234b8f7d0eb4de4ae420654bb0bba7a`：尺寸入口保护、关闭时保留 IRQ 分发、C 仿真回归。
- `60b16c739a45aa4541a260f40320723a2245da0a`：有界进程观察器及离线测试。

未推送。脚本和测试在内核 `drivers/media/platform/chips-media/wave5/`，
主仓仅新增本记录及索引，不提交主仓，也不改其他任务文件。

## 几何：已证实的差异与仍未知的原因

7.3 的 `wave5-vpu-enc.c:wave5_set_enc_openparam()` 把 V4L2 crop 尺寸用作
固件 `pic_width/pic_height`，并非固件的四个裁剪偏移。
`wave5-hw.c:wave5_vpu_enc_init_seq()` 将原宽高直接写入 `W5_CMD_ENC_SEQ_SRC_SIZE`；
无旋转 HEVC 的 `wave5_set_enc_crop_info()` 直接返回，四个固件裁剪偏移仍为零。

5.15 内核 `common_drivers/.../encoder/multi/vpu_multi.c` 主要提供寄存器映射、DMA、
IRQ 与电源接口，序列参数在用户态 SDK 构造。本轮对照本地已存在的
`build/encode444/vendor-src`，`numbqq/encoder_libs_aml` 提交
`4c38af2b398d00a906c26aa166d630a9f73d3f9e`（干净），没有复制其固件或受限源码入库：

- `multiEnc/amvenc_lib/AML_MultiEncoder.c:408,530–559`：原宽高传入；无 90/270 度
  旋转的 HEVC 高度非 8 对齐时，`confWinBot = 8 - height % 8`。没有对应的 HEVC 右裁剪补偿。
- `multiEnc/vpuapi/enc_driver.c:1222–1225`：HEVC 的 SRC_SIZE 高度取 `ALIGN(height,8)`，
  **宽度仍原样写入**。AVC 保持原宽高。`vpuapifunc.c:CalcEncCropInfo()` 的 32/16
  补齐主要用于旋转/镜像，不能直接作为所有非对齐 HEVC 的修复。
- SDK 的重建图像通常 HEVC 对齐 8、AVC 对齐 16，HEVC 旋转/镜像再涉及 32；
  7.3 RAW 协商的行宽对齐 32、高度对齐 16 是另一个内存布局约束，不能代替编码可见尺寸。

| 请求 | 7.3 无旋转 HEVC 序列宽×高；右/底裁剪 | 厂商默认路径宽×高；右/底裁剪 |
|---|---|---|
| 1366×768 | 1366×768；0/0 | 1366×768；0/0 |
| 1440×900 | 1440×900；0/0 | 1440×904；0/4 |
| 1680×1050 | 1680×1050；0/0 | 1680×1056；0/6 |
| 1920×1080 | 1920×1080；0/0 | 1920×1080；0/0 |

这是源码计算对照，不是实测寄存器或 SPS。高度补齐可作候选，但不能解释
1366×768：两边的上述参数相同。
将宽度改成 1368、右裁剪 2、保留 RAW stride 1376 是待验证假设，未找到厂商等价路径；
也未证明额外像素的读取/填充行为。不能宣布只补 conformance window 就修好了。

## 内核不可退出：源码证实，现场归属未证实

| 路径 | 行为与边界 |
|---|---|
| `wave5_vpu_wait_interrupt()` | 已使用 `wait_for_completion_timeout()`，`VPU_ENC_TIMEOUT=60000ms`；不是缺少 timeout 的裸 completion 等待 |
| `v4l2_m2m_streamoff/ctx_release → v4l2_m2m_cancel_job()` | 活动任务设 TRANS_ABORT 后调用可选 job_abort，再以无超时、不可中断的 `wait_event()` 等 TRANS_RUNNING 清除；Wave5 编码器没有 job_abort |
| `device_run → start_encode` | 被接受的逐帧命令异步等待 IRQ，没有逐任务软件 watchdog；丢 IRQ 就可能永久保留活动任务 |
| `finish_encode → get_output_info` | 任意错误直接返回，不调用 job_finish；GET_RESULT 查询失败和固件编码失败均可走到这里 |
| `start_encode` 的部分提交失败 | 返回错误缓冲、切 STOP 后最终仍返回 0，device_run 认为存在活动任务；也可能等不到预期完成 IRQ |
| 旧 release | 公共 helper 先移出 instances/IRQ 分发，再 ctx_release 取消活动任务；正常的迟到完成 IRQ 也可能被丢弃 |
| `stop_streaming` | 在 M2M 取消之后才进入，内部 60 秒 completion 等待救不了前面的无限 wait；报告队列错误循环也缺整体截止时间 |
| `enc_close` | DESTROY 有最多 11 次 STILL_RUNNING 尝试；busy 轮询单次上限 10 秒，不等于进程关闭整体有界 |

修改 completion 不能解决 M2M 取消等待，SIGKILL 也不能使其完成。
busy 轮询使用零 sleep；若一次 MMIO 访问卡死，软件超时也未必能执行。

## 已实现的保守候选

1. `S_SELECTION` 原先只把 crop 限制在目标尺寸内，能绕过 HEVC 的 step 8。
   现在拒绝小于最小尺寸、HEVC 非 8 对齐或 AVC 奇数尺寸；失败不改变实例 crop。
   `wave5_vpu_enc_check_open_param()` 再做对齐检查，避免内部/旧状态绕过用户入口。
   保留已有格式协商；没有扩展 HEVC 非对齐支持。
2. 编码器 release 在 `dev_lock` 下先 STREAMOFF 两个队列，实例仍可接收 IRQ；
   活动任务结束后再进入原公共 helper，移出 IRQ 分发、释放 context 和固件资源。
   不能直接把 ctx_release 整体搬到 unlink 之前，因为它会释放 IRQ 回调使用的 context。

第二项仅修复正常完成 IRQ 与 close 竞态；**固件不完成或 GET_RESULT 失败仍可能 D 状态**。
未增加 job_abort 或改变公共 M2M 等待；现场是否涉及该竞态尚待取证。

## 有条件复位候选：尚未实现

复位不是单实例操作。厂商 `Vp5VpuReset()` 先禁止总线请求、检查排空、再写 reset，
失败会返回；5.15 内核的 `vpu_hw_reset()` 本身甚至只是返回 0 的占位实现。
7.3 现有 `wave5_vpu_reset()` 也会在 bus/FIO/reset 失败时退出。
T7 已适配的 `bus_idle_value=0x3f`、`reset_mask=GENMASK(26,0)` 应保留，不能套 TI 数值。
FIO helper 当前只在一次间接访问完成后检查返回值，并未持续重读 bus-idle；
写 FIO 超时也只记 debug、没有上传错误。这些都不适合当作未经核验的恢复成功凭据。

后续恢复状态机应满足：

1. watchdog 与 job_abort 共用恢复流程，串行化提交/IRQ/取消，覆盖“已标 running、
   尚未发命令”竞态；最多 finish 一次，close 同步销毁工作项。
2. 保存 BUSY、VINT、QUEUE_STATUS、GET_RESULT 错误和源缓冲身份；总截止时间覆盖
   查询、DESTROY、排空和复位。DESTROY 失败后须协调整个核的所有实例，不能单独复位。
3. **确认 DMA 停止后**才报队列错误、归还缓冲、完成 M2M 任务；清迟到 IRQ 并重建固件，
   初始化失败拒绝新任务。复位失败时须保留导入 DMA-buf/映射/队列所有权，不能仅保留
   `vb_work`。需硬件隔离或完整延迟回收设计；本轮没有安全退出证据，停止在设计阶段。

## 离线验证与构建

`test_hang.py` 提取实际 selection、固件参数校验前缀和 release C 函数，ASan/UBSan：
20 组尺寸/格式组合和 8 组流状态/活动任务关闭通过。确定性注入取消时完成 IRQ，
不使用 sleep 模拟内核竞态；单独换回旧 selection 或旧 release 时分别断言失败。
模拟器假定 IRQ 可达，不能证明固件无响应恢复或内核实际并发正确。

```text
Wave5 selection/firmware geometry (20 cases) and close/IRQ ordering (8 cases) passed
selection negative exit 1: Assertion `ret == (supported ? 0:-EINVAL)' failed
release negative exit 1: cancel_job: Assertion `ctx->linked' failed
```

既有 buffers、encoder_cleanup（32 cases）、geometry、intra_refresh、profiles 全通过。
`test_hang_observer.py` 两项通过：不退出子进程的受控截止时间、忽略 TERM 后 KILL 的
自有子进程组；没有访问视频设备。复现工具仅运行了语法检查及默认 plan，未执行编码。
本机日志 `logs/kernel-edge/wave5-hang/` 保存 Wave5、构建与主仓离线结果。
主仓 unittest：160 tests、5 skipped、OK；C checkpatch：0 errors、0 warnings。

独立输出 `/home/deepdream/build/kernel-wave5-hang`。取既有 `kernel-7.3-final` 的
`.config`、Module.symvers、vmlinux 作为模块编译/BTF 基础，运行 olddefconfig、modules_prepare。
配置 SHA256 `64df2a7789045390e22f06175f084913a4dd0873c75e152cf05ae6ba4c7232ba`。
这不是本分支的完整 Image/模块发布包，不可把此模块直接混装到板上。
重型 make 全程仅持 `/tmp/vim4-heavy.lock`，未取得板锁。

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build bash -lc '
  make -C /home/deepdream/src/linux-7.3-wave5 \
    O=/home/deepdream/build/kernel-wave5-hang ARCH=arm64 -j8 \
    M=/home/deepdream/src/linux-7.3-wave5/drivers/media/platform/chips-media/wave5 \
    MO=/home/deepdream/build/kernel-wave5-hang/wave5 modules'
```

首次遗漏 MO，补加后因本 worktree 残留对象被拒绝；清理自己的生成对象后，
上述命令最终退出 0，实际输出包含 `MODPOST Module.symvers`、`LD [M] wave5.ko`、
`BTF [M] wave5.ko`。模块 SHA256：
`e2cf48c70db89daf9f30fe1343833c20b6591baacf364691a2b0f94f24c47af1`。

## 待执行的板上验证

`reproduce_hang.py` 使用 videotestsrc，每次一档；不自动停服务、安装或重启。
先停止占用编码器的应用，核验设备、插件、内核/模块 build ID 和固件，另存串口日志。

未来将脚本复制为 `/tmp/reproduce_hang.py` 后，**在含安装与恢复的完整双锁窗口内**执行：

```sh
# 示意窗口入口；不能只锁住下面的单次编码而把安装/恢复放在锁外。
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  /path/to/reviewed-wave5-board-window
# 以下是窗口内的板端命令；DEVICE/PLUGIN 必须换成已核验的实际路径。
sudo python3 /tmp/reproduce_hang.py --execute --device "$DEVICE" \
  --plugin-path "$PLUGIN" --output /tmp/wave5-hevc-1366 \
  --codec h265 --width 1366 --height 768 --timeout 45
```

默认只输出计划；显式运行保存 gst.log、kernel.notes、
run.json，以及 TERM 前、KILL 前和结束时各 `/proc/PID/task/TID/{stack,wchan,status,syscall}`、
interrupts、meminfo、dmesg。到时先采栈，TERM 等 5 秒，再采栈，KILL 等 3 秒；
诊断进程也有截止时间。仍存活返回 125，停止窗口，不重复编码/重启。
45 秒不含诊断和 TERM/KILL 时间；系统锁死时观察器也可能停住，仍需准备现场 RESET。

先验 H.264/H.265 的 640×480、1368×768、1920×1080 正常 EOS；再以
`--frames 100000 --terminate-after 3` 验带流退出。对 1366×768、1440×900、1680×1050，
当前候选应拒绝 HEVC、允许 H.264；另用 V4L2 客户端验 S_SELECTION 的 EINVAL 和 crop 未变化。
ffprobe 核对尺寸/帧数，ffmpeg 全量解码，另验边缘、色度和填充行。
之后才考虑高度补齐候选；不盲试宽度补齐。

原故障复现须另选旧非对齐候选并具备物理复位条件，本分支 guard 不会触发它。
通用恢复仍需注入丢 IRQ、GET_RESULT/提交失败、复位成功/失败、多实例和晚到 IRQ。

验证结束的完整窗口必须按用户要求恢复原基线，再重启核验运行 build ID
`52d5e46fb006230785110a1fa5ba0dd1383b732f` 和 `vim4-manager active`，并比较模块集。
本轮没有执行上述板端命令，**没有本轮板端实际输出或恢复证据**。
