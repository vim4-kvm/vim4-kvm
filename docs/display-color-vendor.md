# T7 SDR HDMI 颜色：厂商对照基准

本轮基准为 VM `~/src/linux/common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49`。
下面是源码路径与预期写入，**不能代替同一 sink 的实际读回和自环验收**。
7.3 保留 DRM connector/bridge、HDMI state/helper 和标准属性；不引入 amhdmitx 私有框架。

## 有效颜色链

SDR XRGB8888 → VIU OSD → 每层 HDR2 matrix-I RGB→709 limited → OSD/VPP YCbCr
混合 → VPP POST2（厂商 HDMI 路径通常关）→ HDMI formatter → TX CMS CSC0 → TMDS。
VDIN HDR2 是独立输入核，不能用它替代 OSD HDR2。T7 OSD 不走其他芯片常用的
`0x3910..0x391d` 矩阵；写入这些系数不能证明实际颜色转换。

厂商入口：

- `drivers/media/enhancement/amvecm/set_hdr2_v0.c:hdr_func()`，SDR OSD 的
  `HDR_BYPASS | RGB_OSD`；`set_hdr_matrix()` 选择 OSD1/2/3 bank，写矩阵和使能。
- `drivers/media/enhancement/amvecm/amcsc.c` 的末尾输出处理：非 LCD/dummy ENC
  输出关闭 POST2。`set_hdr2_v0.c:mtx_setting()` 提供可直接复用的 POST2 709→RGB 配方。
- `drivers/media/vout/hdmitx21/hw/hdmi_tx_hw.c:hdmitx_set_dispmode()`、
  `config_hdmi21_tx()`、`hdmitx21_vp_conf()`；`hw/reg_ops.c` 经 SMC 读写 TOP/COR。
- `drivers/media/vout/hdmitx21/hdmi_tx_video.c:construct_avi_packet()`、
  `hdmi_tx_infoframe.c:hdmi_avi_infoframe_config()` 与 packet bank 写入。

`hdmitx_csc_config()` 中存在另一套 CSC 系数计算，但函数没有实际矩阵寄存器写入，
不能把这些局部变量当作 T7 生效配方。`config_hdmi21_tx()` 的 `csc_en` 也只计算，
真正相关写入是 CSC0 的 preset。S1A/S7/S7D 的 VPU HDMI 矩阵分支不适用于 T7。

## 矩阵、控制与范围

`rgb2ycbcr_709`（系数 /1024）：

```text
 186   627    63
-103  -345   448
 448  -407   -41
pre = 0,0,0; post = 64,512,512 （10-bit 域）
```

`set_hdr_matrix()` 的 matrix-only/core-off 路径仍将 MATRIXI_EN_CTRL 写 1；
CTRL bit13 关闭 HDR core、bit16 选择 matrix-only、bit14 置位，MATRIXO 使用 identity，
bit17 清零、bit15 置位。HDR_BYPASS 关闭 EOTF/OETF/ogain/cgain LUT；不能只关 core
却继续继承 LUT enable。T7 不走仅适用于 G12A/G12B rev-A 的 always_full_func。
VPP0 使用 OSD1_HDR（CTRL=`0x38a0`），matrix-I enable 在 bank+0x3b，
matrix-O enable 在 bank+0x3c。厂商明确拒绝 OSD3_HDR + VPP_TOP0；T7 没有 OSD2 HDR core，
不能按三个 OSD plane 的名字分别编程这三个 bank。切换须在 fetch-off、旧帧退休后执行，
OSD SRAM 域保持持有；只领取 VPP0 OSD HDR2，不修改 VPP1/2 的路径。

POST2 `MATRIX_YUV709_RGB` 的原始寄存器配方：

```text
39a0=04ac0000 39a1=073104ac 39a2=1f251ddd 39a3=04ac0879 39a4=00000000
39a9=00000000 39aa=00000000 39ab=07c00600 39ac=00000600 39ad.bit0=1
```

输入 limited 10-bit 的偏置为 -64,-512,-512。厂商 `mtx_setting()` 先写使能，
再写系数；7.3 在停 ENC2 后先写完整系数再使能，避免输出瞬间使用旧系数。
RGB limited 需要标准 Broadcast RGB 控制及真实范围变换；本基准普通 SDR TX 配置
没有根据 `fmt_para.cr` 切换 CSC preset，不能把字符串 `limit` 当作电平已经正确。

## 格式、时序和 AVI

以下全部为 SDR 8bpc、BT.709；采样结构由输出选择，OSD framebuffer 仍是 RGB full。

| 格式 | VPP→TX 域 | HDMI_SETTING pre/post | TX CSC0/CSC1 | P2T / input mask / output map | AVI Y / Q / YQ |
|---|---|---|---|---|---|
| RGB | 709 limited YCbCr444 | pre=3，post=0 | 0x65/0，两个高字节0x08 | 0 / 0x2a / 0x0440 | 0 / 由实际 packet 决定 / 0 |
| YCbCr444 | 709 limited YCbCr444 | pre=3，post=0 | 0/0，初配高字节0x08 | 0 / 0x2a / 0x0440 | 2 / 普通构造器limited / 0 |
| YCbCr420 | formatter 对444下采样 | pre=3，post=4，bit20=1 | 0/0，初配高字节0x08 | 0 / 0x2a / 0x0440 | 3 / 普通构造器limited / 0 |

`hdmitx21_vp_conf()` 的后续 YUV 动态配置会把 CSC0 高字节改成0；区分首次 modeset
与后续 `CONFIG_CSC`，不能把两个调用阶段的字节混成一份配方。8bpc formatter 为
`(2<<22)|(1<<10)|(2<<2)`；420 再加2。GCP deep-color enable 为0；10/12bit 不属本轮矩阵。

| 模式 | VIC | pixel / TMDS RGB与444 | TMDS 420（仅EDID允许时） | SCDC / scrambling |
|---|---:|---|---|---|
| 1080p60 | 16 | 148.5 / 148.5MHz | 74.25MHz | 0 / 关闭 |
| 4K30 | 95 | 297 / 297MHz | 148.5MHz | 0 / 关闭 |
| 4K60 | 97 | 594 / 594MHz | 297MHz | RGB/444为3 / 开启；420为0 / 关闭 |

厂商 AVI：underscan、BT.709、16:9、active-aspect=picture、ITC=0、YQ=limited、
pixel-repeat=0；1080p60 VIC16、4K60 VIC97。普通 TMDS 4K30 把 AVI VIC 清0并发 HDMI1.4
VSIF VIC1。DRM helper 允许其自身符合规范的 AVI/VSIF 选择；差分要对齐语义和实际时序，
不能为了逐字节相等覆盖 helper 的决定。RGB Q 必须回读，不能根据 CSC=0x65 推测。

## 成对差分证据合同

用本板 RX 作为两种内核共同的 HDMI sink，保留同一根自环线、同一份 EDID、同一图案及
同一精确 timing；这样同时满足寄存器对照和原始帧校准，减少插拔。另接显示器的样本
必须记录其 EDID SHA256，不能跨 sink 冒充配对。

每档保存内核/build ID、cmdline、sink EDID/哈希、实际时序/位深、OSD HDR2 input/output
矩阵及使能、POST/POST2/0x3910 矩阵、HDMI_SETTING/formatter、TX CSC/input mask/map/
P2T/GCP、完整 TX/RX AVI、SCDC 和原始帧。只读已核对的控制/矩阵寄存器，避开 LUT
自增端口。TX packet bank selector 必须串行、读后恢复，不能打断音频 packet。

差分分列“相同”“有解释的实现差异”“未解释差异”；后两者不能自动算通过。
最终仍要求每色块每次原始采样在声明转换后误差≤2，黑白电平正确。
普通厂商路径未真正实现的 full/limited 组合明确标记，禁止仅改 AVI 充当参考。
实际执行结果另写本次 bringup 记录，本页不预填通过结论。
