# 2026-10-23：T7 H.264 首次超时与厂商启动链对照

承接[多 fd 与 STREAMOFF 修正](2026-10-23-vdec-multifd.md)。本轮定位
`dec timeout=500`，不正式部署。原始证据保存在本机 `logs/vdec-timeout/`。
厂商同一样本 600 帧/EOS 对照已完成；本轮 7.3 候选仍待共享锁，尚无正确帧结论。

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
