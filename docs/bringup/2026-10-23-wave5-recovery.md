# 2026-10-23：Wave5 恢复前置修复与厂商复位审查

**任务 C 未完成，不能把本分支作为自动恢复版本部署。** 已实现并离线验证 FIO 排空轮询、
复位错误传播和固件拒绝检测；没有实现 watchdog/job_abort、运行时隔离、固件重载或多实例恢复。
厂商 SDK 的超时复位与 T7 5.15 resume 使用不同掩码，SAFETY 又依赖固件 SLEEP 成功；
现有证据不足以证明它能在真实固件挂死后安全保留其他实例。遵守硬件行为不猜测的约束，
停在底层候选，未安装候选、未注入板端超时、未重启，也未更新部署锁。

前置：[离线分析](2026-10-22-wave5-hevc-hang-analysis.md)、
[现场保护验证](2026-10-22-wave5-hevc-field.md)、
[尺寸保护部署](2026-10-22-edge-wave5-deploy.md)、
[当前 M0 基线](2026-10-23-display-m0-r4.md)。

## 分支、源码与证据边界

VM `vim4-build` 独立 worktree `/home/deepdream/src/linux-7.3-wave5-recovery`，
分支 [vim4-wave5-recovery](https://github.com/vim4-kvm/linux/tree/vim4-wave5-recovery)，
准确起点 `47878a0c611d1e1deb3699c4f225963a37a218c0`。
未切换或改动原 `/home/deepdream/src/linux-7.3`；检查时原工作树 HEAD 实际为
`0196fe22ecf01`，因此显式按提交建分支，没有把目录名当成版本依据。
提交 `473b3ba430c01a865faad165f4ef16226d564371`
（`media: wave5: propagate FIO and reset sequencing failures`），仅上述驱动与测试两个文件。
已推送到 fork，并用 ls-remote 核对远端提交一致；没有推送已部署分支。
作者/提交者使用本轮指定环境变量，没有修改 VM git 配置。

厂商来源固定为：

- VM `~/src/linux`：`80a07ad5406d57855c996285ae75a50a1b9147ae`；其
  `common_drivers`：`4cfb128d36f8511b2db1bd13c08d5704347ded49`。
- 本地 `build/encode444/vendor-src`：`numbqq/encoder_libs_aml`
  `4c38af2b398d00a906c26aa166d630a9f73d3f9e`，检查时干净；
  `build/jpeg-libs` 同提交，相关 `enc_driver.c` 内容相同。
- CHIPS&MEDIA 参考实现为固定 7.3 基线的 `wave5-hw.c`（保留原版权），并对照上述
  SDK 的 VPU API 说明；未取得独立的 Wave521C 寄存器手册，不能把通用 API 说明
  当作当前 T7 固件在挂死状态下的硬件保证。另核对了
  [上游 Wave5 实现入口](https://github.com/torvalds/linux/tree/master/drivers/media/platform/chips-media/wave5)，
  实施与行号仍以固定本地版本为准。

没有复制厂商受限源码或固件入库。下表路径的 SDK 前缀为 `multiEnc/`；
内核厂商路径前缀为 `common_drivers/drivers/media_modules/frame_sink/encoder/multi/`。

## 超时、总线停止、软复位与硬复位

| 证据位置 | 已确认行为与限制 |
|---|---|
| SDK `amvenc_lib/AML_MultiEncoder.c:824–851,2328–2332`；`vpuapi/include/vpuconfig.h:77–79` | 分段等待 IRQ，用累计时间判断编码超时；编码 60000ms、busy 10000ms。超时调用 SAFETY 并返回失败，调用点没有验收 reset 返回值，不能视作恢复成功证明 |
| 5.15 `vpu_multi.c:1390–1401` | WAIT_INTERRUPT 是有界、可中断等待，超时返回 `-ETIME` |
| SDK `vpuapi/vdi.c:1515–1544` | Wave521C 持续发起 FIO 读取，直到 bus status **等于 `0x3f`**；超时失败。不是只等一次 FIO_READY |
| SDK `vpuapi/enc_driver.c:674–746` | 先清 BUSY；CONFIG0 bit16/22 与 CONFIG1 bit26 分辨 backbone/vcore/dual。vcore/combined 的 stop 为 `0x7`，GDI stop 为 `0x100`，逐项等 idle。厂商失败分支会解除相应 stop，本候选保守保留已发 stop |
| SDK `vpuapi/enc_driver.c:749–794` | SAFETY 在排空后 SLEEP；写 RESET_REQ `VP5_RST_BLOCK_ALL`，等 RESET_STATUS=0，清 RESET_REQ，解除 bus stop，再执行 WAKEUP |
| SDK `vpuapi/enc_regdefine.h:100–111` | RESET_REQ/STATUS 偏移 `0x50/0x54`；ALL 为 **`0x0fffffff`**，命名的 VCPU/VCLK/MCLK 位只到 bit26，未解释 bit27 |
| SDK `vpuapi/enc_driver.c:439–454`；`vpuapi/vdi.c:1588–1624` | ReInit 另一条路径额外等 VCPU_STATUS=`0x40`，随后 reset mask 用 **`0x07ffffff`**。不能混成一个未经验证的统一序列 |
| 5.15 `vpu_multi.c:3421–3459` | resume 同样用 `0x07ffffff`，随后 remap、INIT_VPU/CORE_START；不是活跃编码器超时恢复验收 |
| SDK `vpuapi/vdi.c:696–709`；5.15 `vpu_multi.c:436–440,1863–1866` | HWReset 经 RESET ioctl，但内核 `vpu_hw_reset()` **只返回 0**，没有硬复位或 DMA 停止确认 |
| 5.15 `vpu_multi.c:324–339,980–1006` | 真正的硬复位只在上电流程看到：电源/时钟启用后，RMW `0xfe000044` bit28，清位 assert、置位 deassert，各有 5ms 延时。这里没有活跃 DMA 排空证明，不能用来兜底隔离失败 |

7.3 基线的 T7 idle=`0x3f`、reset mask=`GENMASK(26,0)` 保持不变。
现代集成的独立 VCPU backbone status=0 与上述 SDK 的 VCPU_STATUS=0x40 也不是同一寄存器，
不能交换判值。本轮没有读取/写入板端寄存器来猜测这些差异。

## 固件启动与实例上下文

SDK `vpuapi/enc_driver.c:274–275,291–355` 的冷启动会写固件到 common memory，
配置 remap/code/temp、AXI/IRQ，发 INIT_VPU/CORE_START，等 BUSY 清零并检查 RET_SUCCESS。
ReInit `:378–381,475–531` 只有 code base 改变时重新写固件并做 INIT。
SAFETY 的 WAKEUP `:573–661` 使用现有 common memory 配置 remap，发 WAKEUP/CORE_START，
**并不重新从文件加载固件**。因此不能把一次 WAKEUP 成功写成“固件已重载”。

SDK `vpuapi/include/vpuapi.h:4638–4658` 描述 SAFETY 可回到当前帧之前且不影响其他实例，
FORCE 则需重新初始化、设置参数和注册帧缓冲。实现 `enc_driver.c:749–752` 仍要求
SLEEP 成功；没有“固件连 SLEEP 都不响应时如何保全其他实例”的证据。
冷 INIT 与保留已有实例不是可互换的恢复动作。

7.3 的 firmware loader 在 `wave5-vpu.c:194–233`，只在 probe 调用；
`wave5-vpuapi.c:18–40` 的初始化封装还会在 PC 非零时调用 ReInit 后统一返回 `-EBUSY`。
本轮未把这些 probe 路径直接复用于运行时恢复。

## 实现范围

仅修改内核 `drivers/media/platform/chips-media/wave5/wave5-hw.c`，新增同目录
`test_reset.py`：

- `wave5_fio_readl():133`、`wave5_wait_fio_readl():156`：把间接读取完成与目标值到达分开；
  总线未 idle 就再次读取，共用原有 10 秒截止时间。剩余预算为零时直接超时，避免
  `read_poll_timeout(timeout=0)` 变为无限等待；轮询允许睡眠。
- `wave5_fio_writel():175` 返回超时，init/reinit/wake/reset 的所有调用点检查返回值。
- `wave5_vpu_reset():1408`：在 MMIO 前验证 mode/mask；重新读取配置能力；
  stop 写未确认或 idle 未到，不发 RESET_REQ；stop/reset 失败不主动解除已发 stop；
  解除 stop 失败不进入 WAKEUP。T7 SAFETY 的 SLEEP 顺序按 SDK 放在 drain 后，
  非 legacy 的 SLEEP 相对顺序保留。
- init/reinit/sleep/wake 调用命令检查时不再丢弃失败码，RET_SUCCESS=0 明确返回错误。
  原 helper 在传入非空 fail_res 时，除 STILL_RUNNING 外会返回 0；这些调用点没有消费
  fail_res，可能把固件拒绝当作成功。本轮没有改变逐帧命令的错误码 API。

这些改动未给复位新增运行时调用者。原命令 busy 等待本就有 10 秒上限，IRQ completion
本就有 60 秒上限；本轮新增的是可靠的 FIO/固件错误检测，**不是逐任务 watchdog**。

## 尚未具备的隔离与取消边界

基线 `wave5-vpu-enc.c:1648–1651` 仍无 job_abort；
`drivers/media/v4l2-core/v4l2-mem2mem.c:416–434` 在取消运行任务时无超时等待。
仅在 watchdog 中 job_finish 会让 `:869–881` 继续进入 vb2_streamoff，
`drivers/media/common/videobuf2/videobuf2-core.c:2190–2223` 会强制归还仍 ACTIVE 的缓冲，
而 `:2674–2683` 的 queue_release 会解除/释放整个队列。
因此在 stop 失败时只保留 `vb_work`、跳过驱动的 buf_done、或设置 queue_error，
都不足以保留导入 DMA-buf 的 attachment、映射与 backing storage。

还需要完成：覆盖提交前取消与迟到 IRQ 的单次完成状态机；有整体截止时间的 job_abort；
隔离后的 ioctl/close/remove/module 生命周期及完整缓冲所有权；确认适用 T7 的复位掩码；
明确采用保留上下文的 WAKEUP 还是冷重载后重建其余实例，并验证失败分支。
这些是本任务未完成项；没有把离线 mock 的 DMA idle 当作硬件证明而接上自动复位。

## 验证与板子状态

独立 O=`/home/deepdream/build/kernel-wave5-recovery`，首次从既有
`kernel-wave5-deploy` 复制 `.config`、Module.symvers、vmlinux，执行 olddefconfig/modules_prepare。
其 vmlinux build ID=`3a61b75bccf8c46e9411dee92928999884bbfc7f`，并非当前 M0 Image；
配置 SHA256=`86746fde4d0e6d377264466262a27b4953206ce5e07441c8b870eee5ca05957f`。
这是离线模块编译/BTF 依赖，**不是本分支完整 Image/模块发布包，不能直接混装到板子**。

最终编译在 Mac heavy 锁内执行：

```sh
/usr/bin/lockf -t 600 /tmp/vim4-heavy.lock orb -m vim4-build bash -c '
cd /home/deepdream/src/linux-7.3-wave5-recovery &&
make O=/home/deepdream/build/kernel-wave5-recovery ARCH=arm64 -j8 \
  M=/home/deepdream/src/linux-7.3-wave5-recovery/drivers/media/platform/chips-media/wave5 \
  MO=/home/deepdream/build/kernel-wave5-recovery/wave5 modules'
```

实际退出 0，含 `CC wave5-hw.o`、`MODPOST Module.symvers`、`LD wave5.ko`、`BTF wave5.ko`，
无编译 warning/error。模块 SHA256
`cb3b2b772dc62f71caac344717fad275ece6587c1df558f195469d85eb2dfd17`，
build ID=`f462fef1606db3acaa129d83ed951d9beacd2e74`。未构建完整 Image/dtbs/modules。

`checkpatch.pl --no-tree --strict`：C diff 363 行、测试文件 315 行各
**0 errors / 0 warnings / 0 checks**；`git diff --check` 通过。
全部 Wave5 `test_*.py` 通过，包括既有 buffers、32 组 cleanup、geometry、
20 组尺寸/8 组关闭顺序、3 项观察器、intra_refresh、profiles，以及新增：

```text
Wave5 FIO/reset: 47 deterministic MMIO fault/order cases passed
```

新增测试提取实际 C polling/reset/sleep/wake 和本内核的 iopoll 宏，使用 ASan/UBSan、
虚拟时间和脚本化 MMIO；覆盖迟到 idle、永不 idle、读写不完成、共用截止时间、
RESET_STATUS 不清、SLEEP/WAKEUP 拒绝/超时及解除 stop 失败。
故障注入只在此离线设备模型里，**没有提供模块参数/debugfs 注入**。
先接入实际 SLEEP/WAKEUP、保留原失败码处理时，测试确实在期望 `-EIO` 处断言失败，
修正后通过；证据 `negative-firmware.log`。这些测试不能证明真实 DMA 或并发恢复正确。

主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：191 项、5 skipped、OK。
日志在本机忽略目录 `logs/wave5-recovery/`；源文件编辑副本在
`build/wave5-recovery/source/`，正式候选在 VM 独立 worktree。

板端只执行以下只读查询，没有拿板锁、停启服务、加载模块、发送 HID 或改变 EDID：

```sh
ssh -o ConnectTimeout=10 vim4 'uname -r; systemctl is-active one-kvm vim4-manager;
cat /sys/class/udc/*/state; cat /proc/sys/kernel/tainted; ls -l /dev/hidg*;
cat /sys/kernel/notes'
```

实际文本输出为 release `7.3.0-vim4kvm-uhd1+`，两服务均 `active`，UDC `configured`，
taint `0`，`/dev/hidg0`–`hidg3` 存在；GNU note 解析得到 build ID
`f483ea42fee88be39ea67c43478638be67334d6e`。原始数据 `board-readonly.raw`。
这只确认查询时仍在指定基线，**不是本轮恢复操作或真实 HID 可用性的验收**。
并行任务的测试窗口不属于本轮结论。

未执行板端故障注入、10 次恢复、恢复后的 4K60、KVM 回归或 final-window 正式部署。
没有候选上板，因此没有本轮“恢复基线”操作；保留原部署与 sources.toml/workspace.toml。
