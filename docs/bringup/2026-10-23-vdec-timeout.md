# 2026-10-23：T7 H.264 首次超时与厂商启动链对照

承接[多 fd 与 STREAMOFF 修正](2026-10-23-vdec-multifd.md)。本轮定位
`dec timeout=500`，不正式部署。原始证据保存在本机 `logs/vdec-timeout/`。
厂商同一样本输出 600 帧/EOS；7.3 候选 compliance 47/47，但输出 20 帧全零图像
后超时。43 次硬/线程 IRQ 证明固件已执行；STREAMOFF 两侧均成功，未再崩溃。
按首错停止，已恢复入口基线并完成 300 秒编码和真实 HID 冒烟。

## 启动链审计

逐项厂商出处、S4 v11 差异及安全固件预装依赖见[审计明细](2026-10-23-vdec-timeout-audit.md)。
确认旧 FIFO 的 padded WP 越过 END，已修正；SMC 参数匹配厂商不等于已经证明
S4 stateless 微码协议兼容，须以本轮 PC、FIFO 与 IRQ 对照为准。

## 离线改动与验证

`vim4-vdec`：`2084efcdfe05c`。FIFO 边界修正之外，在 AMRISC 启动前和首次
超时各抓一次 43 个白名单寄存器及 hard/thread IRQ 次数，发生在 stop/reset
销毁现场之前。首次超时对该 fd 的两条队列报错并拒绝再次启动任务；确认 DMA
停止后仍按原所有权规则回收，不以再次喂入尝试掩盖首错。

实际 C 函数离线测试 20/20，包括 FIFO 最大合法 payload、越界/空输入、只清
padding、首次超时前快照与队列错误、故障 fd 不触碰硬件，以及 85b32081 的
STREAMOFF 空硬件上下文与另一 fd 所有权。strict checkpatch：0 errors、
0 warnings、0 checks。

持 heavy 锁在独立 `O=~/build/kernel-vim4-vdec-timeout` 完整构建 Image、两个
DTB 和模块，`package-vdec.py --once` 校验同次构建、vermagic/BTF、源码及每文件
哈希后打包，无 warning/error。当前包 `build/vdec-timeout/current-bundle`，VM
`~/build/vim4-vdec-timeout-bundle`，含精确 vmlinux、配置、符号与模块调试副本。
内核 build ID `b8d4f55c74a067fc2be18fb231c3738abc26114a`；VDEC 模块
`7ad792ddbf488c21bcec52189430b765c0862959`。

| 产物 | SHA-256 |
|---|---|
| Image | `14dae921897820c29364386376df39ba4f66ac9ee959620e0375949707fd266a` |
| VDEC DTB | `67189483760a0eaf4a26a2641397eed29ac652c5ff74812b7e045e147d12c038` |
| modules.tar.gz | `34ce78266c33e72dfcf3578b101695317fcdfa5b1eba68a15aa013adb02a000c` |
| VDEC 安装模块 | `4926020a377fda0c8233094062e2cd298e785f8501623d0eb7a7387a9ea06f57` |

## 现场执行边界

两次窗口分别取得 heavy→board 双锁，开始时动态保存当时正式基线及原 Wave5。
厂商窗口先确认 PID1 watchdog active、stop_after_panic=0；同一 640×368 样本
真实产生输出后才读 43 个寄存器，保存解码前/中/后 interrupts、clk/genpd。
不覆盖默认启动，不持久安装 5.15。

候选为 RAM 一次性启动、私有模块目录，顺序 probe → power → MDEC 十三步 →
compliance → 同一 640×368 样本 → 1080p。首错停止；恢复最多等待 180 秒，
超时报告需要 RESET 并停止。每次结束验证入口基线、五文件、原 Wave5、服务、
UDC、真实 HID 和 300 秒 H.265 动画采样，清理私有文件后释放锁。

小样本/1080p 通过后才考虑 4K。硬件支持 H.264 4k30，但当前 stateless 前端仍
限制 1920×1088，扩展前必须审查缓冲和固件合同，不能把被钳位的尺寸写成 4K 通过。
小样本额外用 strace 记录 ioctl，直接检查 STREAMOFF；此诊断运行的 CPU/耗时
含追踪开销，不作为解码性能结果。T7 不使用旧 ESPARSER，按厂商 frame-based
VLD 路径喂入；硬件能力依据见[资源审计](2026-10-22-vdec-hardware-audit.md)。

## 厂商活体结果

UTC 03:26:29–03:33:28 持双锁。RAM sysboot 到 5.15.137-vim4kvm，build ID
`389f77352dc8ab21aa80d8cf36819bb9da31d7ee`；PID1 独占 watchdog、30 秒超时，
`stop_after_panic=0`。同一样本 SHA-256
`449bf8a077c6b4a9d2b356c644f373042ee0c7a0842e34e15e3f15acddcce9f8`，
`amlv4l2h264dec ! identity ! fakesink sync=true` 输出 600 个 buffer 并到 EOS。
活动时 vdec_status：640×368、frame_count=8、drop/fra_err/hw_err 均零。
这是功能与寄存器取证，未对厂商输出做逐帧像素比较。

```text
vdec-1: GIC-0 124 Edge, before=0, active=20, after=1223
READ_BACKEND --vendor-paddr
{"complete":43}
ACTIVE_DUMP_COMPLETE_DECODER_RUNNING
VENDOR_EOS_BUFFERS 600
```

5.15 没有 `/dev/mem`，使用已有 `aml_reg/paddr` 只读接口：只提交地址选择，
一次读取结果，不提交寄存器写值。43 个地址先整体校验白名单，并逐个与厂商
dos_registers.h 的 word index 对照；采集总超时 15 秒，未发生 SError/复位。
顺序快照期间解码进程持续运行，但硬件可能在帧间停机，不能把某次 MPSR=0 或
MASK=0 判作失败。关键值：

| 地址 / 寄存器 | 厂商活动值 |
|---|---|
| fe320004 MMC_CTRL0 / fe320008 MMC_CTRL1 | ffff / 32（MMU bit3=0） |
| fe320114 MBX_SSEL / fe320118 DBUS_DISABLE | 0 / 0 |
| fe3201d0 IRQ / fe3201d8 MASK / fe3201dc FIQ_SEL | 0 / 0 / 0（帧间采样） |
| fe320c04 MPSR / fe320c18 MPC_P / fe320d00 IMEM_DMA_CTRL | 0 / 0 / 0 |
| fe322638 MDEC_PIC_DC_CTRL / fe3226c8 REC_CANVAS | 0002a008 / 00030302 |
| fe322740 secure swap / fe32274c DPB_STATUS | 06a68000 / 2（PIC_DATA_DONE） |
| fe322754 LMEM / fe322720 workspace | 9f6ac000 / 9f6c0000 |
| fe323100 START / fe323108 END | 9f900000 / 9faffff8 |
| fe323104 CURR / fe323114 WP / fe323118 RP | 9f9119a8 / 9f911da0 / 9f911b80 |
| fe32311c LEVEL / fe323068 BIT_CNT | 220 / 1 |

正常重启回入口 `eeddb005df059a850853876d52ef603aa1af192b`，五个受保护文件、
原 Wave5 文件/加载 ID、服务、UDC 与 taint 均与入口一致。300 秒 3840×2160
H.265 动画采样：59.99854 fps、freeze/drop/loss/PLI 均零、最大回调间隔
37.7ms；真实键盘 down/up、绝对/相对鼠标、点击和滚轮通过。临时 vendor 目录与
独立 sysboot 配置已清理，锁已释放。原始结果见 `vendor/restoration-complete.json`。

恢复采样后 RX 状态另有 `stream_stops=1,last_stop_reason=dma-wait,
last_stop_error=-11,faulted=0,dma_idle=1`。journal 在 335.621 秒仍连续收到
raw/encoded=18336、last_frame_ms=0；336.125 秒浏览器结束 H.265 后切 H.264，
336.169 秒重开采集，339.195 秒预览自动停止，之后才读状态（stream_frames=176）。
本启动 journal 无 tmds-invalid 或 readiness revoked；据此归为采样后的管线
切换/关闭记录，未观察到采样内 RX 失锁，仍保留该计数，不把它写成零。

## 7.3 候选现场结果

排队等待显示任务释放双锁，UTC 2026-10-24 04:30:22–04:38:00 执行一次窗口。
命令入口如下；辅助脚本和完整输出保存在本机 build/logs，不是正式部署工具。

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-timeout/field.py
```

入口仍是 `eeddb005…`，候选为上列 `2084efcdfe05c` 同次完整包。PID1 持 watchdog，
Runtime=30s；候选 panic=20、panic_on_oops=1。安全固件预装服务退出状态为零，
包 SHA-256 与厂商相同；journal 记载 `tee preload video fw ok`。

| 步骤 | 实际结果 |
|---|---|
| probe | 通过；默认上电门禁拒绝自动 open，无 SError |
| power | 通过；SMC 域核验与 RESET0 单读、下电成功 |
| MDEC 十三步 | 全部通过，最后下电；`mdec.log` |
| compliance | **47/47，Failed 0、Warnings 0**；`compliance.log` |
| 640×368 H.264 | **失败**；20 帧全零后首次 `dec timeout=500`，停止后续阶段 |
| STREAMOFF | OUTPUT、CAPTURE 均返回 0；runtime suspended、faulted=0 |
| 1080p、4K | 小样本失败，均未运行；不报告解码速度或 CPU 占用 |

```text
Total for aml-vdec-drv device /dev/video1: 47, Succeeded: 47, Failed: 0, Warnings: 0
[56.478241] dec timeout=500
[56.478366] h264 snapshot timeout irq=42 hard=43 thread=43 swap=0x6a68000
42: 43 0 0 0 0 0 0 0 GICv2 124 Edge vdec-1
04:32:01.135112 VIDIOC_STREAMOFF [VIDEO_OUTPUT_MPLANE] = 0
04:32:01.135370 VIDIOC_STREAMOFF [VIDEO_CAPTURE_MPLANE] = 0
RAW_BYTES 7065600 REFERENCE_BYTES 211968000 COMPLETE_FRAMES 20 EXACT_ALL False
```

以上 ioctl 行是保留参数/返回值的摘录，完整 strace 见 `h264-ioctl.log`。
每帧 I420 为 353280 字节，20 帧 MD5 均为
`a45154bf88428c38ee1781a029385aac`，与同尺寸全零帧一致；逐帧软件参考均不匹配。
不能把 buffer 完成数当作正确帧。超时只出现一次，之后同 fd 队列 EIO、QBUF
被拒绝，未再次启动硬件；85b32081 的 STREAMOFF 修复已在此次真实超时路径验证。

43/43 同组寄存器对照见[审计表](2026-10-23-vdec-timeout-audit.md#现场寄存器差分)。
候选超时 PC=0x35b、MPSR=1，SPS scratch 已从主机初值变为与厂商相同的
0x81039828，FIFO RP/CURR 已前进、WP 落在 END 内。当前可排除“完全没有加载/
启动固件”或“mailbox IRQ 完全未接通”；不能据此证明 secure 微码 ABI 全部兼容。
超时状态为 DECODE_NEWPIC=0xf3，尚缺的是像素输出及该作业的完成，不是简单增大
500ms 就能验收。优先对照 canvas LUT、实际输出 DMA 地址/内容和逐帧协议状态；
本轮没有证明具体的 DDR 安全权限或 canvas 时钟故障，不据猜测写全局控制位。

## 恢复、提交与清理

候选通过普通 reboot 回基线，04:32:42 已响应，未触发 SError、NULL panic 或
watchdog 兜底。UART、上次 kernel journal、现场 dmesg 均无这些异常。pstore
归档前后两个 dmesg 条目哈希相同；console 条目更新为正常启动/重启日志。
阶段脚本失败时打印的保守 `RESET_REQUIRED` 提示不是实际复位原因，也不代表
DMA 停机失败；驱动只读状态和 STREAMOFF 成功证据保存在 `h264-ownership.txt`。

`candidate/restoration-complete.json` 和恢复前后快照证明：

- build ID 回到 `eeddb005df059a850853876d52ef603aa1af192b`；五个保护文件、
  cmdline、taint=0、panic 配置、原 Wave5 文件及加载 ID 均与本次入口逐项相同。
- One-KVM、manager、wave5-monitor active，UDC configured；无私有模块挂载或实验
  模块，未需 usb-pd-init。watchdog 仍由 PID1 持有，Runtime=30s、Reboot=60s。
- 300 秒 3840×2160 H.265 动画采样 **60.00185 fps**，freeze/drop/loss/PLI
  增量均 0，最大呈现间隔 38.3ms。RX stream_stops 前后均 0、faulted=0。
- 真实键盘 down/up、绝对/相对鼠标、点击和滚轮全部通过。

板上两次窗口各自的 payload、一次性启动目录、输出与 stage receipt 已清理，
双锁已释放；默认启动和正式部署锁未改变。`vim4-vdec` 的 `2084efcdfe05c` 已推送。
本轮新代码依赖尚未正确解码的实验前端，不合入正式分支；已通过的时钟提供者、
binding 与默认 disabled 节点已在此前合入，不重复合入或把本轮失败路径正式启用。

保留当前 Mac/VM bundle、精确 debug 输入及原始证据；核对其全部哈希后，仅删除
本任务旧 multifd 包与完整 O= 输出，明细见 `logs/vdec-timeout/cleanup.json`。
下一轮先离线补齐像素 DMA/固件协议差分，现场仍从同一小样本开始；正确帧通过
前不推进 1080p/4K。
