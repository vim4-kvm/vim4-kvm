# 2026-10-23：Wave5 E01 ROI、任意 GOP 与 VUI/SEI 的剩余合同

与 [动态参数／LTR／GOP 离线实现](2026-10-23-wave5-e01-runtime-gop.md) 配套。
本表区分标准 ABI 缺口、驱动未实现和固件支持未确认，**不把字段存在或另一 IP 的
实现当作 Wave521C 当前固件支持证明**。

## ROI：固件有 map，当前内核没有标准 map 控件

厂商 encoder_libs_aml `4c38af2b398d00a906c26aa166d630a9f73d3f9e`：

| 证据 | 实际语义 |
|---|---|
| `multiEnc/vpuapi/enc_driver.c:1923–1929` | PIC_CUSTOM_MAP 地址；enable bit0、average QP 从 bit1 起，以及 lambda/mode/coef-drop 位。 |
| `multiEnc/amvenc_lib/AML_MultiEncoder.c:96–119,1183–1218` | AVC 每 16×16 MB 使用 packed byte，QP 在 bit2..7；输入是绝对 QP 0..51，并非标准意义上的有符号 delta QP。 |
| 同文件 `1224–1280` | HEVC 每 64×64 CTU 一个 64bit custom map，含四个 sub-CTU QP、模式／drop／lambda，不可直接照搬 AVC map。 |
| `vpuapi/include/vpuapi.h:3035–3050` | VpCustomMapOpt 的地址／enable／average-QP 合同；引用的物理地址是厂商用户态内部实现，不应作为 V4L2 控件暴露。 |

本轮基线 `include/uapi/linux/v4l2-controls.h` 没有 ROI delta-map 控件；这不意味着
上游没有讨论。已查到作者原始补丁：
[PATCH v7 2/5, media: uapi: Introduce new control for video encoder ROI](https://lore.kernel.org/linux-media/20260924-enc_roi_enable-v7-2-6fa7413af23c@oss.qualcomm.com/)，
Message-ID `20260924-enc_roi_enable-v7-2-6fa7413af23c@oss.qualcomm.com`，
2026-09-24。原邮件的
[公开存档副本](https://lists.openwall.net/linux-kernel/2026/09/25/31)
可读取，lore raw 在本环境返回 403；没有将搜索摘要作为合入证明。
提案为 ROI_MB_DELTA_QP（__s8 数组）及 ROI_MB_SIZE 查询，由 Iris 接入。
本轮不在本地抢占提案的 uAPI 数字、不新增厂商私有 ioctl，也不声称此提案已合入。

后续应跟随最终标准 ABI；新增／回移 uAPI 必须单独成 series，先明确：

- MB/CTU 网格基于 OUTPUT 存储尺寸还是 CROP 可见区域，边缘 padding 如何覆盖；
- delta→绝对 QP 的基准、与 RC／逐层 QP／min-max 的优先级。不能把 delta byte
  原样交给绝对 QP map，尤其 RC 开启时基准来自固件；
- map 是对下一源帧一次生效还是持续生效、与 source index／重排／Media Request
  的对应，以及改变 CROP/格式后的数组尺寸行为；
- 驱动分配的 map DMA 至相应 source 完成或固件实例销毁前保持；超时复位失败
  仍交给现有隔离保留，不能为释放 map 绕过 DMA 安全规则。

当前状态：**ROI 生产路径未实现**，不能归因为固件不支持。跟进此标准提案比新增
私有“ROI buffer 地址”控制更有利于后续跟进 Linux。
标准 ABI 与驱动 map 转换实现完成后，另排约 15–20 分钟小尺寸窗口：负／正 delta、
可见区边缘及 padding、运行中 map 更新、B 重排、两实例、超时保留与复位后重开。

## 任意 GOP：现有标准 hierarchy 只能表达一部分

标准 B_FRAMES、H264_HIERARCHICAL_CODING_*、HEVC_HIER_* 已用于候选的多 B／
分层 B/P。`drivers/media/platform/samsung/s5p-mfc/s5p_mfc_enc.c` 和 Venus 是使用
标准层级控制的内核先例；不能再称层级编码缺 ABI。

但这些控件不能表达每一项的 pic_type、POC、ref_l0/ref_l1、temporal_id 任意图。
厂商 CUSTOM_GOP 最多 8 项并不自动形成标准用户接口。若要公开任意图，应提出
标准 compound 数组，说明显示／编码顺序、引用 POC 的相对原点、周期边界、
随机访问点、最大参考数、QP/RC 优先级及 codec/profile 约束，并以跨厂商实现审查。
可参考已有 compound codec 控件的设计方式，**没有找到可直接复用的任意 stateful
encoder GOP 图控件先例**；stateless decoder DPB 控件不是替代品。

分层 bitrate 已有标准 L*_BR，但厂商 fixedBitRatio[8] 是逐 GOP 项的比例字节，
并非逐层 bps。需要定义每层分配给多张图片的规则以及量化误差、总码率约束，
不能把标准 bps 直接写进 8bit ratio。该项本轮仍未实现。

## VUI 色彩：格式字段有 ABI，T7 固件输入尚未证实

色彩通过标准 OUTPUT S_FMT 的 colorspace、xfer_func、ycbcr_enc、quantization 表达，
不需要新增“colour primaries”私有控件。当前驱动保存并返回这些字段，但未承诺其
已写入 SPS；不应把格式回显当作码流色彩验证。

关键源码：

- `multiEnc/amvenc_lib/libvpmulti_codec.c:276–282,417–477,584–697`：厂商保存色彩
  元数据后，分别解析／改写 AVC 和 HEVC SPS，再插回用户态码流。
- `multiEnc/vpuapi/include/vpuapi.h:3054–3063,3397`：声明 HevcVuiParam；但
  `Vp5VpuEncInitSeq()` 和 `Vp5VpuEncParaChange()` 没有对应的 VUI 写寄存器实现。
  CHANGE mask bit23 的声明也没有相应写入分支。声明不是可工作的实现。
- [TI Wave5 参考代码](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/tree/drivers/media/platform/chips-media/wave5/wave5-hw.c?id=c1c8d6fad88e20ce43320f4914bf8891963af478)
  `wave5_vpu_enc_init_seq():2203–2214` 有 VUI_HRD_PARAM 与 VUI_RBSP_ADDR，VUI
  长度左移 4；其
  [API 定义](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/tree/drivers/media/platform/chips-media/wave5/wave5-vpuapi.h?id=f9b87f015f572022879995ae1e8c3a0472dbf8ef)
  明确长度单位为 bit。这是可继续验证的 Wave5 合同，尚不是这版 T7 legacy 固件的
  已确认能力。需要进一步确认固件版本／适用产品、metadata endian、buffer 读取期限。
- `Documentation/userspace-api/media/v4l/dev-encoder.rst:9–17` 不鼓励驱动在 CPU 上
  生成／重写完整 header；因此没有把厂商用户态 SPS 改写搬进内核。

当前状态：**VUI 生产路径未接通，固件支持未确认**，不能写成“固件不支持”。
后续候选应使用固件消费的 VUI RBSP 元数据，明确 AVC/HEVC 不同语法和 DMA 所有权；
先离线证明 buffer 失败回收／隔离保留，再通过一次性启动小尺寸验证 SPS 与 ffprobe
colour_range/colour_space/colour_transfer/colour_primaries。BT.709 limited/full、
BT.2020 PQ/HLG 至少各一例；需要单独约 15–20 分钟，不计入当前功能验收。

## HDR SEI：标准 compound 已有，Wave521 发送合同未确认

V4L2_CID_COLORIMETRY_HDR10_CLL_INFO 和 HDR10_MASTERING_DISPLAY 已有，
无需新增标准 HDR10 控件。Venus `venc_ctrls.c:318` 起展示标准 compound→固件属性的
现有实现。任意用户 SEI payload 则不能用上述两个固定结构替代，需要另讨论 ABI。

本主线 Wave5 driver 的 PIC_PREFIX/SUFFIX_SEI_INFO 与 NAL_ADDR 目前写零；
TI 上述参考实现也写零。厂商 `multiEnc/` 未发现相应 Wave521 SEI 发送实现。
SDK 中实际可工作的 `amvenc_265/.../vpuapi/wave4.c:849–853` 属于 WAVE4，
不是 WAVE5；不可用“相似寄存器”推断地址、字节顺序、长度、编码顺序与 NAL/RBSP
边界都兼容。其他 `vcenc/` 编码 IP 的 HDR 实现也不计为 Wave521C 证据。

当前状态：**HDR SEI 生产路径未接通，固件支持未确认**。没有注册“设置成功却不
生效”的 HDR 控件。下一阶段须获得 Wave521 固件发送合同，再把这两个标准结构
打包到驱动持有的 DMA buffer，定义首帧／IDR 重复、动态更新及错误时生命周期。
小尺寸正向、反复改值、IDR 重复与超时持有另需约 10–15 分钟板上窗口。

本轮新增 AVC NAL type6、HEVC prefix39/suffix40 的 SEI 解析：payload type/size
扩展字节、mastering-display type137（24 字节）、content-light type144（4 字节）、
emulation-prevention、截断／错误长度／trailing bits，以及未知消息保留。
命令：`python3 .../wave5/test_geometry.py --hevc-sei file.hevc`，AVC 用 `--avc-sei`。
默认离线测试使用独立语法向量；这些结果不能当作固件 HDR 输出证据。
