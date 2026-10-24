# 2026-10-23：T7 VDEC 多 fd 所有权与解码窗口

本轮继续[p0 访问窗口](2026-10-23-vdec-p0-window.md)，先修复每 fd 上下文与
单个硬件实例的归属，再一次性启动候选验证；不正式部署。原始证据保存在
本机 `logs/vdec-multifd/`。

## 离线修正

`vim4-vdec` 提交 `81881d4ff170309f6affc76870fb3c468873c897`，已推送 fork：

- 每次 open 分配独立 fh、控件、m2m 上下文和两条 vb2 队列，分别持有 runtime PM
  引用。设备故障仍返回 EIO；T7 上电与 MDEC 门禁仍默认拒绝 udev 自动 open。
- 用 `open_count` 阻止有 fd 存活时运行 sysfs 诊断，不将文件数限制为一。
- 仅在 m2m 的 device_run 中绑定固件扩展加载的硬件上下文；H.264 中断从
  `v4l2_m2m_get_curr_priv()` 取当前任务。初始化或关闭其他 fd 不覆盖当前任务。
- 每帧的 reset、固件加载、寄存器恢复与停机仍在同一个 m2m 任务内。确认 IRQ/DMA
  停止后清空硬件指针，再完成任务。停机失败则保留 DMA、上下文、模块和 DOS 租约，
  故障设备拒绝后续任务；不因其他 fd 关闭而释放不明所有权的缓冲。

调度合同依据本地 7.3 `drivers/media/v4l2-core/v4l2-mem2mem.c`：
`v4l2_m2m_try_run()` 在已有 curr_ctx 时不启动其他任务；cancel_job 等待正在运行的
任务完成；job_finish 才释放当前所有权。驱动的 device_run 同步等待固件完成或超时，
无另一个私有并发硬件队列。

`test_t7_lifetime.py` 17 项通过，实际编译驱动函数的测试覆盖两个 fd 独立队列和 PM
引用、open 中途失败回收、关闭非活动 fd、A/B/A 任务切换、固件失败及停机失败隔离。
这些是离线故障后端测试，不等于多路真实解码验收。checkpatch strict 为零
errors/warnings/checks。

第二个提交 `f84df9685f31fa3852cd57dbacf3e50114cc4b3e` 修复等待窗口时发现的
内部 dma-buf 引用问题：`vb2_dc_get_dmabuf()` 增加 dma-contig refcount，
`vb2_buffer_in_use()` 在 num_users>1 时判为占用，而 `videobuf2-v4l2.c:575–576`
据此置 QUERYBUF 的 MAPPED。旧代码在 buf_init 就导出保护引用，会使未 mmap 的
空闲缓冲带 MAPPED；这来自离线源码对照，未把它写成已观察到的现场失败。
第一次完整包尚未上板，已取消排队并重建，不重复运行已知有问题的包。

改为每任务首次 MMIO 前导出源/目标全部 MMAP 平面（包括 DPB 引用），确认 DMA
停机后才释放。持源→目标两队列 mmap_lock，直到停机，防止 CREATE_BUFS 在作业
中加入未固定的 DMA 目标；目标锁使用嵌套子类。`v4l2_m2m_streamoff()` 与
ctx_release 均先 cancel/wait，随后才执行 vb2 释放，避免倒置等待。
停机失败仍永久保留导出引用，但释放软件 mutex，便于进程退出和后续重启。
新增实际函数测试逐个注入四个导出失败点，核对稀疏队列、引用回收、锁释放与
故障引用保留；任务测试证明固定引用失败时不触碰 MMIO。

## 候选与现场边界

本轮上板包的完整 Image、VDEC/基线布局 DTB、2335 个模块在独立
`~/build/kernel-vim4-vdec-multifd` 构建，包内核对 source、vermagic、split BTF 与
每文件哈希。上板包对应 `f84df9685f31f`，manifest 与故障模块另存
`logs/vdec-multifd/tested-manifest.json`、`tested-aml-vdec-drv.ko`。
kernel build ID `b7e6da3393428b664de3b30c7c3857bfbc0e3538`，VDEC 模块 ID
`aeca1f56d4ca7c5988a9e8df92f68f82f3bf0c1e`。Image 与首个未上板包相同，
VDEC 模块已变化，按 source、模块 ID 与包哈希一起识别。

| 产物 | SHA-256 |
|---|---|
| Image | `927db636451c32e5d6e677661d76827dfbab1c06357a5f0e2d40b743ea1dc37f` |
| VDEC DTB | `67189483760a0eaf4a26a2641397eed29ac652c5ff74812b7e045e147d12c038` |
| 完整模块包 | `50ff147e00439518f5f8f1e4f66db3995e92b410d0046c008c5b28c6e8da92f4` |
| VDEC 安装模块 | `cfe554bcc9799df16c8233f23a4191923b17d04832c170fd8b8c027d2803c6b3` |

现场全程持 heavy→board 双锁，PID 1 持 watchdog，Runtime=30s、Reboot=60s。
只使用 RAM 一次性入口和私有只读模块挂载；默认启动、基线五文件不变。
首错停止，保留证据并重启回基线；180 秒未恢复则报告需要 RESET 并停止。

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-multifd/field.py
```

顺序为 probe → power → p0 外部快照 → MDEC 十三步 → compliance →
640×368 同一厂商样本 → 1080p。每个解码阶段使用单实例，超时退出，输出 I420
与软件参考逐字节和逐帧 MD5 比较。

厂商 H.264 功能报告支持 4k30，`h264_multi/vmh264.c:1093–1147` 允许到
4096×2304 分类，不能写成硬件不支持 4K。但本候选沿用 S4 格式表，最大
1920×1088，尚未审查并扩展 4K 固件/缓冲合同；不能把缩放或被钳位的尺寸算作
4K 解码。只有前级全部通过且前端支持所需尺寸才运行 4K，不能绕过格式约束。

## 现场结果

排队等待其他任务释放双锁后，UTC 2026-10-24 02:44–02:53 执行一次窗口。
入口仍为 `eeddb005df059a850853876d52ef603aa1af192b`，不是候选或其他任务的新包。
`watchdog-entry.log` 和 `watchdog-candidate.log` 均确认 PID 1 使用硬件 watchdog，
Runtime 30 秒；候选 panic=20、panic_on_oops=1。

| 步骤 | 实际结果与证据 |
|---|---|
| probe | 通过，无授权的自动 open 被拒绝，无 SError；`probe.log` |
| power | 通过，SMC 域核验及 `DOS_SW_RESET0=0x0`；`power.log` |
| p0 快照 | 2144 项完整；vdec/vdec_0=799999987 Hz，vdec_1 enable=0，DOS/两条 APB=166666664 Hz；`p0-verification.json` |
| MDEC 十三步 | 全部通过；GCLK 首读 0、写后 0x3ff，MDEC_PIC_DC_CTRL=0x2a100，最后确认下电；`mdec.log` |
| compliance | **47/47，Failed 0、Warnings 0**；second open、unlimited opens 均 OK；`compliance.log` |
| 640×368 H.264 | **失败并停止**，同一 600 帧样本；驱动报 dec timeout=500，随后 STREAMOFF 空指针 panic；`h264.log`、`stages-uart.log` |
| 1080p、4K | 前级失败，均未运行；无正确帧或速度结论 |

关键原始输出：

```text
test second /dev/video1 open: OK
test for unlimited opens: OK
Total for aml-vdec-drv device /dev/video1: 47, Succeeded: 47, Failed: 0, Warnings: 0
REGISTER_STEP_COMPLETE 12 step=12 value=0x2a100 failed=0
[   56.350707] aml-vdec-drv fe320000.video-codec: dec timeout=500
[   75.742305] Unable to handle kernel NULL pointer dereference at virtual address 0000000000000b80
[   75.761490] pc : release_canvas_index+0x20/0xf8 [aml_vdec_drv]
[   75.774206]  aml_h264_exit+0x60/0x158 [aml_vdec_drv]
[   75.774810]  vb2ops_vdec_stop_streaming+0x38/0xb8 [aml_vdec_drv]
[   75.821145] Rebooting in 20 seconds..
```

一次 gst 流内驱动共报十次超时，不是十次重新上板或重跑脚本。软件参考已生成，
但硬件输出未完成，不能声称逐帧匹配。本次是 ESR `0x96000004`、地址 `0xb80`
的普通 NULL 解引用，**不是此前 DOS MMIO 的 SError**。串口保留完整调用栈、
寄存器及自动重启；归档 pstore 位于 `pstore-after.tar.gz`（含 systemd 已归档条目）。
约一分钟内自动回基线，无需人工 RESET；不凭 reboot_mode 单独区分 panic 重启与
watchdog 复位的最终触发者。

## 失败后的离线修正与合入边界

`85b3208142860` 修复本轮引入的清理回归：m2m 作业确认 DMA 停止后清空
`hw->curr_ctx`，而 `h264_release_decode_spec()` 在 STREAMOFF 仍从它取上下文。
改从调用 fd 的 `ctx->codec_priv` 释放 canvas；关闭非活动 fd 也不会释放活动 fd
的 canvas。新增实际 C 函数回归覆盖硬件指针为空、另一个 fd 仍占硬件、重复 finish，
**18 项离线测试通过**。此修正不解释固件解码超时，且未再次上板。
`82ae76b512a6d` 补齐 binding 第五条 vdec-p0 时钟，均已推送 `vim4-vdec`。

通过的独立资源描述合入 fork `vim4-kvm-7.3`：
`bbc9a0f9e19cc`（binding）与 `8b2553f7b3c62`（默认 disabled 的 T7 VDEC 节点），
接在并行显示任务的 `2cc04af44e3d4` 后，不改其工作树，不正式部署。
正式分支已有的 DOS 时钟提供者未重复合入。新节点 disabled，不创建 VDEC 设备，
不启用驱动、不触碰寄存器；实验前端、全局 PM 改动及未通过的解码路径均未合入。

binding 的 dt-doc-validate、定向 dt_binding_check、三个普通/audio-test/display-m0
DTB 的 CHECK_DTBS 通过，strict checkpatch 为零 errors/warnings/checks。
与精确 `9d33f6ad` 参考的全部既有 DT 属性比较一致；新增 canvas 消费者会改变
dtc phandle 编号，比较按目标节点路径归一化引用及其参数，而非忽略数字差异。
上述三种 DT 输入在 `9d33f6ad..2cc04af4` 间未变化。证据：
`validated-dt.log`、`validated-dt-compare.log`、`formal-checkpatch.log`、`formal-push.log`。

下一轮先离线定位解码超时（固件完成/中断/解码状态），保留本轮确切故障模块。
现场从 compliance 和同一 640×368 单实例重新开始，必须验证超时后 STREAMOFF
不崩溃；小样本逐帧正确后再进 1080p。4K 还需单独审查前端尺寸和缓冲上限。

## 恢复与冒烟

UTC 02:47:30 前已回到入口基线，02:52:53 完成冒烟及清理并释放双锁。
`restoration-complete.json`、`restored-after-smoke.json` 证明：

- 内核 ID 回到 `eeddb005df059a850853876d52ef603aa1af192b`，五个保护文件哈希、
  cmdline、panic 配置与入口完全一致，无私有模块挂载、无实验模块，taint=0。
- 原 Wave5 文件 SHA-256 为
  `e88df353c730e5d82bbef8335788a28d5f71cfc7a4e1b8b5854ef00046d4b667`，
  加载 ID `8e2dedd2579d126adb8ba710eec2082ec1753b05`，均与入口一致。
- One-KVM、manager、wave5-monitor 均 active，UDC configured，未需 usb-pd-init。
- `one-kvm-smoke.mjs --exclusive --mode=h265 --seconds=300 --warmup=5`：
  3840×2160，59.9987 fps，freeze/drop/loss/PLI 增量均 0，最大呈现间隔 37.6 ms。
  这是基线编码恢复测试，不是候选 H.264 解码性能。RX stream_stops 前后均 0。
- `one-kvm-usb-check.mjs --exclusive --hid-only`：keyboardDown/Up=1，
  absoluteMouse=true，relativeMouse 有移动，click/wheel=true。

已删除板上本轮 payload、一次性候选目录、硬件输出和本轮 stage receipt；
pstore 归档保留作为证据，默认启动与正式部署锁未改变。
