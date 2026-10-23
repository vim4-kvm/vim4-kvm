# 2026-10-23：M2 原生 ENC2 模式切换（离线候选）

接续 [RDMA 翻页与独立 TX 音频](2026-10-23-display-m2-rdma-audio.md)。本轮补齐
EDID → DRM atomic modeset → PLL/VENC/PHY/SCDC 的实现，仍只有离线证据。
没有 SSH、串口、安装、重启或拔插操作，没有申请板锁；没有正式部署，也没有修改
`sources.toml` / `workspace.toml`。本记录不代表 4K、HDMI 音频或采集共存已上板通过。

## 分支与提交

独立内核工作树 `~/src/linux-7.3-display-m2`，输出 `~/build/kernel-display-m2`；
在 `e24c11ebbe505` 上分步新增：

| 提交 | 内容 |
|---|---|
| `df54ce21751d3` | 计算 PLL，独立 ENC2 时序与资源校验，厂商可执行对比测试 |
| `ed2b92c7df9dc` | 原生 display binding、bridge PHY 与 ENC2 属性 |
| `e2e7703eb40fa` | atomic 启停、尺寸切换、RDMA blank、PHY/SCDC、AVI/VSIF |
| `ad28721b2066a` | 仅 M2 DT 启用原生路径、独占 PLL；默认与 M1 不变 |
| `117a50b6cdfab` | 修正 ENC2 pixel/FE/PNX mux，增加可执行对比 |
| `12b0a76a773a6` | 拒绝低于 23Hz 的 timing，保证两次边界落在退休期限内 |

正式 `vim4-kvm-7.3` 不由本任务推送。上板前须合入届时正式分支最新的采集、SARADC、
Wave5 修改，重建并重测；本构建不覆盖其他任务部署。

## ENC2 与 VDIN 所有权

硬件依据固定为厂商 Linux 5.15 的 `common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49`：

- `arch/arm64/boot/dts/amlogic/kvim4.dts`、`kvim4n.dts` 设置 HDMI `enc_idx = <2>`。
  因此 VIM4 HDMI-OUT 用 ENC2；不能套用通用 T7 分支的 ENC0 默认值。
- `drivers/media/vout/hdmitx21/hw/hdmi_tx_hw.c:enable_crt_video_hdmi()` 的调用参数是
  `(1, 0, 2)`。pixel/FE/PNX mux 写值为 **2**，不能照抄函数内仍写“1: ENCP2”的旧注释。
  测试编译并执行这个厂商函数，与新驱动三个 mux 及对应 VID2 gates 对比。
- 普通 `meson_vpu_init()` 对 `VPU_WRARB_MODE_L2C1` 整字写入，与 VDIN 使用的
  word `0x27a2` bit16 冲突；VDIN 还使用 `0x27a3` bit0。本方案不调用该全局初始化，
  **显示侧不读改写这两个仲裁字**，保持采集驱动对它们的既有所有权。
  以后若需更改其他仲裁位，必须先统一双方访问入口与锁，不能分别裸 MMIO。
- VDIN 独占区仍为 `ff004800/400`、`ff009c80/4`、`ff009e88/8`、`ff01042c/c`；
  编译 DT 测试逐段检查 display 的十二个 MMIO claim 与它们不重叠。
  不写 canvas、AFBC、VDIN 时钟，不做全 VPU reset、频率修改或电源域循环。

显示独占 OSD1、ENC2（word 加 `0x800`）、RDMA channel 1、VPP 尺寸/scaler 窗口、
HDMI PLL `fe0081c0/20`、VID2 `fe0001e0/20`、VID divider `fe000204/4`；
TX bridge 独占 PHY `fe008200/18`。没有 claim 整块 VCBUS/HHI。
共享 CCF 控制器上的 `0xd8` / `0xdc` 使用该设备的同一个 regmap 做 masked update，
与 CCF 共用锁；不操作 RX 的 `0x128..0x134` 时钟字。
M2 禁用只读 HDMI PLL provider，避免另一个 provider 改写 OD/PLL；显示设备持有
SCMI 24MHz `HDMI_PLL_OSC` 引用，probe 校验参考频率及 provider 排他性。
SMC `0x820000ab/op9` 写入选择 ENC2 的值 1，区别于普通 meson 路径的 ENC0。

内存带宽及显示/采集并发仍需上板验证。

## 模式支持与计算

EDID 由 DRM helper 解析、枚举；bridge 和 CRTC 用同一个原生 timing validator。
下表由测试解析厂商 `hdmitx_common/hdmitx_mode.c` 的 timing，再执行双方 PLL/VENC
函数生成对比。表内表示离线参数通过，均为 progressive RGB888 / TMDS；不表示已点亮。

| 模式 | pixel kHz | Htotal × Vtotal | PLL VCO kHz | OD1 / OD2 / OD3 | frac（十进制） | 链路条件 |
|---|---:|---|---:|---|---:|---|
| 1280×720p60 | 74250 | 1650 × 750 | 5940000 | 4 / 2 / 2 | 65536 | sink 接受该模式 |
| 1920×1080p50 | 148500 | 2640 × 1125 | 5940000 | 4 / 1 / 2 | 65536 | 同上 |
| 1920×1080p60 | 148500 | 2200 × 1125 | 5940000 | 4 / 1 / 2 | 65536 | 同上 |
| 2560×1440p60 标签 | 241500 | 2720 × 1481 | 4830000 | 2 / 1 / 2 | 32768 | 厂商 VESA timing 实际约 59.950Hz |
| 3840×2160p30 | 297000 | 4400 × 2250 | 5940000 | 2 / 1 / 2 | 65536 | 含 HDMI 1.4 VSIF |
| 3840×2160p60 | 594000 | 4400 × 2250 | 5940000 | 1 / 1 / 2 | 65536 | sink 支持 594MHz、SCDC、scrambling |
| 1920×1080p59.94 | 148352 | 2200 × 1125 | 5940000 配方 | 4 / 1 / 2 | 33128 | 使用厂商 1000/1001 trim |
| 表外 1920×1200 timing | 154000 | 2080 × 1235 | 3080000 | 2 / 1 / 2 | 43690 | 验证通用计算路径 |

不增加 VIC → 固定时序/时钟查表。使用 EDID 的 active/porch/sync/total，按厂商
`config_tv_enc_calc()` 计算 HSO=5、VSO=1 与 FIFO/DE，不复用旧 meson 的错误 VIC97 表项。
VCO = pixel × 10 × 2ⁿ，选择 `[3, 6)` GHz，
由 24MHz 参考计算 M 和 17-bit frac；OD1≤4，剩余分频给 OD2，OD3=2，VID_PLL_DIV=5。
5.94GHz 使用厂商 lock 配方及有限次重试；1000/1001 分支不回退至会改变频率的整数配方。
VCO 超范围、PLL 不能计算的模式在 `mode_valid` 返回 `MODE_NOCLOCK`。

validator 还拒绝：interlace、doublescan、额外特殊 flags、超过 3840×2160、
小于 640×480、total 超界、低于 23Hz、porch/sync 错误及 FIFO 前肩不足；bridge 再拒绝
超过 sink 最大 TMDS、4:2:0-only 模式、超过 340MHz 却没有 SCDC/scrambling 的 sink。
DRM debug 日志保留完整 mode 和拒绝原因。M2 不宣告 YUV420、deep color、FRL、DSC、
HDR 或可变刷新率；显示缓冲仍是单 OSD1、无缩放、linear RGB24/XRGB8888/XBGR8888。

## atomic 生命周期与失败处理

原生 modeset 的顺序为：RDMA 提交 OSD disable → 等待旧扫描安全退休 → 停 ENC2 →
关闭 OSD fetch → 有界 PLL lock / 时钟 / VENC / VPP 几何设置 → 启动 ENC2 →
RDMA 锁存新 framebuffer → 等待完成 IRQ 与 vblank → 完成用户 flip。
RMFB/disable 用第五个 RDMA 描述符关闭 fetch，不拿旧 1080p 启动缓冲扫描 4K。
普通翻页保留每 vblank 退休模型和 timeout pinning。

bridge 先 AVMUTE，再配 PHY、源端 scrambling 和 sink SCDC `TMDS_CONFIG`：
超过 340MHz 写 `3`，源 SCRCTL=`0x21`、clock pattern=1:40；低速恢复 `0` / `0x20` / 1:10。
只有全部成功后解除 AVMUTE。SCDC 写失败保持静音并关闭 PHY/音频；CRTC fault 时也不启动 TX。
AVI/vendor VSIF 用 DRM HDMI helpers，packet selector 窗口仍由 mutex 保护。
原生模式和 bridge bus format 统一 RGB888，消除原先 RGB 编码与 YUV 声明不一致。
切换时静音、重设 ACR；`VIM4HDMITX` / `VIM4HDMIRX` 路由不变。

**仍需 U-Boot 提供可用的 1080p RGB888 初始链路。** probe 保留 M1 的地址/格式/时序
读回校验，沿用固件 VIU→ENC2 路由、secure 权限及矩阵初始设置；接管后的模式切换由
DRM 编程。本轮不声称无固件冷初始化、挂起恢复或任意启动格式已经可用。

## 离线验证与产物

在 VM 内核工作树复现：

```sh
dt=/home/deepdream/build/kernel-display-m2/arch/arm64/boot/dts/amlogic
python3 drivers/gpu/drm/meson/test_t7_modeset.py \
  --vendor /home/deepdream/src/linux/common_drivers \
  --dtb "$dt/amlogic-t7-a311d2-khadas-vim4-display-m2.dtb" \
  --output /home/deepdream/build/kernel-display-m2/vendor-mode-parameters.json
python3 drivers/gpu/drm/meson/test_t7_handoff.py \
  --dtb "$dt/amlogic-t7-a311d2-khadas-vim4-display-m1.dtb"
python3 drivers/gpu/drm/meson/test_hdmitx21.py \
  --dtb "$dt/amlogic-t7-a311d2-khadas-vim4-display-m2.dtb" \
  --baseline-dtb "$dt/amlogic-t7-a311d2-khadas-vim4-display-m1.dtb"
```

测试执行真实驱动与厂商 C 函数，比较八组模式的 VENC、PLL/M/frac、OD、ENC2 mux、
三个 PHY 档位；覆盖 PLL timeout、SCDC 失败/高低速回切、sink 限制、CRTC 失败、4K 几何、
RMFB blank、退休/停 encoder 顺序、flags/porch/低刷新率拒绝。
JSON 带厂商 commit，是生成的参数对照表。另跑 HPD/DDC/音频、60 flips/60 vsyncs 模型、
迟到 IRQ/timeout、VDIN/Wave5 全部离线脚本，以及 M1/M2 编译 DT、binding/schema 校验。

结果：六个新提交 checkpatch 均为 0 errors / 0 warnings（仅忽略 FILE_PATH_CHANGES）；
上述驱动测试、VDIN/Wave5 脚本、binding/schema 全部通过。
主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：223 项通过，跳过 10 项。

最终 `12b0a76a773a6` 已推送 `origin/vim4-display-m2`。持 Mac heavy 锁，在独立 O= 目录
执行 `make ARCH=arm64 CC=gcc -j4 Image dtbs modules` 通过；2334 个模块，release
`7.3.0-vim4kvm-uhd1+`，build ID `f1e0705b91a41c35d010cf37c4db2d626c706b8b`。
构建清单在 VM `~/build/kernel-display-m2/m2-build.json`，SHA256：

```text
Image 1a60554b2ddc14fee21fdd5d0ffa60d45f765cc647c4edbe11db5f9c4298d0ae
M2DTB 8235b78e032b0c90bee426f4736ca814a295aae93b4c416830b6a87364725c31
```

## 下次一次性启动窗口

排在采集、Wave5 之后，先合入届时最新正式内核、重建、重测并备份基线。
全程短窗口持板锁和 heavy 锁，默认启动项保持基线，
候选只能启动一次；RESET/重启回默认基线，恢复不依赖服务 stop 成功。

1. 一次性启动后读取版本、taint、pstore；检查 VDIN/显示资源绑定和 TX/RX 声卡、EDID/ELD。
2. 逐一切换表内 EDID 支持模式，采集卡抓图核对分辨率/刷新率；4K60 核对 SCDC 1:40，
   回到低速核对清除 scrambling。验证 RMFB、disable、重复切换与失链恢复。
3. 同时运行 HDMI-IN 一路编码和 RX 音频，测 1080p60 flip/vblank 是否均约 60/s；
   Panfrost 硬件渲染器 + linear dma-buf/PRIME scanout、producer fence 和 TX PCM 播放。
4. 用户在场时输出 `NEED_USER`，请求 HDMI-OUT 拔插；最多等两分钟，缺用户动作则跳过并记录。
   分开核对 HPD、EDID、恢复 modeset、音频恢复，不以 simpledrm 的历史行为替代验证。
5. 重启回默认基线，核对基线哈希/build ID、画面、一路编码、音频、HID/UDC configured、
   服务（含隔离监控）、isolated=0、taint=0、无新增 oops；最后释放两把锁。

## M3 计划：按厂商能力分步实现

每一步审核共享资源、离线测试、一次性启动验证，不提前宣告未实现的 DRM 能力。

| 阶段 | 厂商依据与范围 | 主线接口与验收重点 |
|---|---|---|
| 硬件层、光标、缩放 | `media/osd/osd_hw.c` 的 T7 OSD1..4/scaler；`drm/vpu-hw/meson_vpu_postblend.c` 的混合 | DRM overlay/cursor、zpos/alpha/scaling；核对 OSD2 路由、VIU1 vsync 和寄存器排他 |
| 解码 NV12 零拷贝 | `drm/meson_plane.c` 的 NV12/NV21；`meson_vpu_video_wrapper.c` 的 video 路径 | Wave5 dma-buf → PRIME → VD plane；验证 offset/pitch、CSC、fence 与退休，CPU 不搬帧，不引入私有 vframe ABI |
| AFBC | `drm/vpu-hw/meson_osd_afbc.c` 的 surface、完成/错误 IRQ | 区分 ARM AFBC modifier 与 Amlogic 视频压缩，逐项公开格式/布局，验证错误退休与 RX 共存 |
| HDR / 10-bit / 4:2:0 | `hdmitx21/hdmi_tx_main.c` 的 EOTF/色深/packet；`hw/hw_clk.c` 的 30/36-bit 时钟 | DRM colorspace/HDR metadata/max bpc、EDID/带宽校验、CSC/InfoFrame；4K60 RGB 10-bit 超预算，需 420/422 或降模式 |
| CEC | `media/cec/hdmi_ao_cec.c` 的 `cec_t7_data` / `amlogic,aocec-t7` | Linux CEC adapter、EDID 物理地址；核对 AO pin/clock/IRQ、TX/RX 拓扑，不做系统挂起测试 |
| VRR / QMS（条件项） | `hdmitx21/hdmi_tx_vrr.c` 的 game VRR/QMS、vtotal/EMP；能力查询受 sink QMS 限制 | 先确认 T7/sink 范围，再接 DRM VRR；SPI197 与当前 vsync 同源，须复用 IRQ/退休路径；实机证明前保持关闭 |

厂商 `hdmi_tx_main.c` 明确以 T7 不支持 FRL 为例绕过 FRL 流程；M3 以该边界规划。
