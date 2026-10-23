# 2026-10-23：M2 RDMA 翻页与独立 TX 音频（离线）

接续 [M2 第一批实现](2026-10-23-display-m2.md)。本轮没有 SSH、串口、安装、重启、
HDMI 拔插或其他上板操作，没有申请板锁；未正式部署，也未修改部署锁定版本。
RDMA 翻页和独立 TX PCM 声卡已实现离线候选；**完整原生模式切换仍未实现**。
下面的 60 flips/60 vsyncs 是执行真实驱动函数的主机模型结果，不是物理输出验收。

## 分支与提交

VM 独立工作树 `~/src/linux-7.3-display-m2`，输出 `~/build/kernel-display-m2`；
`vim4-display-m2` 保留上一轮七个已推送提交，新增：

| 提交 | 内容 |
|---|---|
| `5c2797011d8e6` | linear binding 要求独占 RDMA 资源与完成 IRQ；M1 资源不变 |
| `0421cdac73af6` | vsync 前准备 RDMA 表；等待 DMA 完成与 vsync 两个条件；移除重复等待 |
| `f1727d69a7d30` | monitor binding 可显式声明 PCM DAI，纯 handoff 仍禁止音频写入 |
| `888bfccd5667e` | 独立 VIM4HDMITX 声卡、EDID ELD、静音/拔线生命周期及 packet 窗口锁 |
| `13dae97cc16ab` | bridge/CRTC 共用固定模式校验，给出 DRM 拒绝状态与调试原因 |
| `4684317569306` | 分别丢失 RDMA/vsync、延迟 IRQ 和翻页序列回绕测试 |
| `e24c11ebbe505` | 锁存失败不发成功 flip event；out-fence 返回 EIO，内部依赖正常结束 |

上述提交已快进推送至 `origin/vim4-display-m2`，HEAD 为 `e24c11ebbe505`。
正式 `vim4-kvm-7.3` 未由本任务推送。准备硬件候选时需要先合入届时最新的采集和
Wave5 提交，再重建；不能直接复用本轮基于 `c1315a95` 的构建安装到新正式基线上。

## 1080p60 翻页与安全退休

M1 的模式为 148500 kHz、2200×1125，名义 60Hz。29.97 flips/s 来自两个 vsync
才完成一次软件提交，并不表示输出是 1080p30；实际 PLL 可能使用 1000/1001，
上板仍需分别采集 vblank 频率和 flip 频率。

本轮对照固定厂商 `common_drivers@4cfb128d36f8`：

- `rdma/rdma_mgr.c` 的 `rdma_regadr_t7[]`：channel 1、word/value 表、
  `RDMA_AUTO_SRC1_SEL` 和 64 位表地址高位寄存器；触发源 `1` 为 VIU1 vsync。
- `mesont7.dtsi`：RDMA 完成中断为 SPI215，edge rising。
- `osd/osd_rdma.c:osd_rdma_irq()` 调用 `osd_update_vsync_hit()`；
  `osd_hw.c` 中它唤醒 RDMA done 队列，`osd_wait_vsync_hw_viux()` 等待此队列，
  `_osd_pan_display_layers_fence()` 在设置/等待后才释放 displayed buffer。

M2 新申请 `ff004400/100`，与 VDIN 的 `ff004800/400`、`ff009c80/4`、
`ff009e88/8`、`ff01042c/c` 不重叠。启动时拒绝已有活动自动 RDMA 通道；
不复位整个 RDMA/VPU，不操作 canvas、AFBC 或 VDIN 仲裁。
提交线程在下一次 vsync 前填好四组 OSD1 format/stride/alpha/address 描述符；
完成 IRQ 先停止 channel 1 重放并清除自身状态，再允许复用描述符内存。
只有 RDMA completion 和 arm 后的 VIU1 vsync 均已到达，才释放旧 framebuffer、
完成 flip。两种 IRQ 顺序均可；不会仅凭地址寄存器读回就宣告锁存。
atomic tail 不再额外等待一个 vblank。M1 仍使用原来的两次 vsync 退休路径。

100ms 内缺任一条件即 fault，旧/新两个可能被扫描的 framebuffer 均保留引用，
后续 plane check 返回 EIO；延迟到达的 IRQ 不会释放它们。
超时事件会被取消，out-fence 带 `-EIO`，内部 commit completion 完成并释放一次；
legacy 客户端不会收到一个可据以安全复用旧缓冲的成功事件，应退出并恢复基线。
这避免“只 pin 内存，但成功事件已让用户态重写旧帧”的漏洞。

## HDMI TX PCM 与 RX 共存

M2 DT 新建 `sound-hdmi-tx` / `VIM4HDMITX`：

```text
FRDDR_A → TDMOUT_A → TDM_A（I²S、两个 32-bit slots）
        → TOHDMITX I2S_IN_A → I2S_OUT → DRM hdmi-codec
HDMI RX → FRHDMIRX → TODDR_A → 原 VIM4HDMIRX
```

codec 由 DRM bridge connector 注册，ELD 使用 DRM 的 EDID 解析结果，不写私有
ELD parser。首批公开 S16_LE/S24_LE、2ch；codec/ELD 共同约束采样率。
TX 使用板级已有的 HIFI 1179648000 Hz 与 MPLL1 338688000 Hz 两个音频父源，
TDM_A 按 mclk-fs=256 配置。没有恢复旧声卡的 MPLL0 全局设置；RX 专用 ACR/PLL、
FRHDMIRX、TODDR_A 配置不变。编译 DT 测试比较解析后的 RX 时钟 provider/参数、
寄存器和声卡路径，确认没有因新增 phandle 编号而产生错误结论。

只有 KMS 已启用、EDID 为支持音频的 HDMI sink、HPD 连接时才允许 prepare。
稳定拔线立即关闭音频并清除 pixel/sink 状态，不等待用户态处理 hotplug；
重新启用时重设 ACR，保持用户要求的静音状态。AVI 与音频 InfoFrame 使用同一个
TPI selector/payload 窗口，新增 mutex 防止并发写串包。

本轮没有声卡枚举、实际播放、采集连续性或 ELD 文件的硬件证据。上板使用稳定
ALSA card ID，不能假定卡编号恒为 0。现有 RX 准备脚本按 `VIM4HDMIRX` 选择 mixer。
TX 的 FRDDR/TDM/TOHDMITX mixer 路由、MCLK/BCLK/LRCLK 和接收端音质须现场核对。

## 完整模式切换：未完成的具体依赖

EDID/DDC/HPD 已接 DRM 框架，但 M2 保留固件 ENC2/VPP/PLL/PHY。
720p、4K30/60、1080p 不同 clock/porch 仍被拒绝；支持范围没有扩大。
`mode_valid` 现在区分 `MODE_ONE_WIDTH/HEIGHT`、`MODE_NOCLOCK`、
`MODE_NO_INTERLACE/DBLESCAN`，其余不匹配返回 MODE_BAD；调试日志带完整 mode
和“firmware ENC2/VPP/PLL timing is fixed”原因。CRTC atomic check 使用相同规则。

不能直接把 `&vpu` 打开来完成切换：

1. `meson_vpu_init()` 整字写 `VPU_WRARB_MODE_L2C1`（word 0x27a2）；
   `t7_vdin_start_hw()` 正在使用该字 bit16，并使用 0x27a3 bit0。
   正常 VPU 的整段 MMIO claim 也与 split-vcbus 采集资源冲突。
2. `meson_venc_hdmi_mode_set()` T7 分支通过 SMC `0x820000ab/op9` 改成 ENC0，
   与本候选的 ENC2/VIU1/固件链不同。PLL 和视频时钟仍绕过完整 CCF 所有权；
   只放宽 mode_valid 或打开节点会引入未经解决的共享访问。
3. 现有 T7 VIC 表中 33 复用 1080p50，96/97 复用 2160p25/30，不能当成
   1080p25/4K50/60 的已验证参数。native bridge 的 RGB 配置与 YUV bus 声明也需统一。

厂商 `hw_clk.c:setting_enc_clk_val_24[]` 的 RGB8 基础参数如下，不能只换像素 clock：

| 模式族 | VCO kHz | OD1/OD2/OD3 | vid_pll_div / vid_clk_div |
|---|---:|---|---|
| 720p50/60、1080p24/25/30 | 5940000 | 4/2/2 | 5 / 1 |
| 1080p50/60 | 5940000 | 4/1/2 | 5 / 1 |
| 2160p24/25/30 | 5940000 | 2/1/2 | 5 / 1 |
| 2160p50/60 | 5940000 | 1/1/2 | 5 / 1 |

`hw_t7.c` 的 5.94GHz PLL 有三组锁定重试序列，4K50/60 与 fractional 还改变
CTRL3/4 参数；不能使用一个通用 PLL 初值替代。PHY 的 ≤150、≤300、≤600MHz
分别有独立 drive 参数，>340MHz 必须校验 sink SCDC、配置 scrambling/1:40。
`enc_cfg_hw.c:config_tv_enc_calc()` 用 hsync_st=5、vsync_st=1、FIFO latency=2
计算 progressive 时序；ENC2 寄存器地址比 ENC0 多 0x800 个 word。
完整实现还需同步 OSD/VPP 窗口、clock/PHY 锁定失败处理与 modeset disable 顺序。
本轮没有把这份核对表写成一套未接通的“完成实现”，该项仍明确欠交付。

## 离线验证与下次窗口

逐提交 checkpatch 为 0 errors/0 warnings（忽略 FILE_PATH_CHANGES 通用提示）。
驱动对象与 DTB 构建通过；C harness 覆盖 60 flips/60 vsyncs、两种 IRQ 顺序、
回绕、RMFB、分别缺失 IRQ、超时 pinning/事件/fence、HPD/DDC、PCM 生命周期与
真实音频寄存器序列。编译 M1/M2 DT 对比确认 TX/RX 路径和 RX 时钟不变。
完整 `make -j4 Image dtbs modules` 通过，2334 个模块，编译日志无 warning/error；
重型构建全程持 `/tmp/vim4-heavy.lock`，等待其他任务释放后才开始。
构建清单保存在 VM `~/build/kernel-display-m2/m2-build.json`：

| 产物 | 标识 / SHA-256 |
|---|---|
| 内核提交 | `e24c11ebbe50555278f088b45d3e17c385d8ef62` |
| release | `7.3.0-vim4kvm-uhd1+` |
| build ID | `1befb2ef113b61bb5b9ef6d868150e5cc20ad5db` |
| Image | `a2240b429263f9de752d89403355e7098a9384a0bdc7bc974fe7acaada6f9b8c` |
| M2 DTB | `86e3f50debb53050d3cfac8fc6c4f1ad3ed265dcd3b9bf8a9fee95efe4fa8809` |
| .config | `8af98a1fbefdf163c407f9f04bb31372178b8f8d7d6f00f5dff162b930c968bf` |

M1/M2 编译 DT 的显示、采集、时钟和 AXG 声卡 schema 校验通过；
HDMI RX/VDIN 与 Wave5 全部离线脚本通过。主仓
`python3 -m unittest discover -s tests -p 'test_*.py'` 为 223 tests、10 skipped，
无失败；跳过项不是本轮上板结果。这些结果均不证明硬件翻页速率或 TX 音质。

下次窗口排在采集与 Wave5 之后，先同步当时正式内核、重建并生成匹配完整模块；
持 board/heavy 双锁，使用 `display-once.py` 私有候选，一次性启动且默认基线不变。
先验证 HPD/EDID、RX 同时采集、RGB24/32 RMFB/disable、持续翻页和 Panfrost
CMA/dma-buf scanout；记录硬件 renderer、vblank 与 flips/s，不以离屏分数替代 scanout。
再用 `hw:CARD=VIM4HDMITX` 播放 48kHz/2ch，核对 ELD 与接收端音频，同时保留
RX 编码/音频采样。拔插输出 NEED_USER，最多等两分钟，未执行须记跳过。
模式切换要待上述原生资源/时钟实现完成后再进入窗口，不能在当前候选上宣称验收。
结束重启回当时默认基线，核对 build ID、服务/隔离监控、isolated=0、taint=0、
UDC configured、画面/一路编码/HID，并释放两把锁。
