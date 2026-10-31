# 7.3 VDIN HDR2硬件映射：可行性与实现计划

用户已于2026-10-30确认采用VDIN HDR2→SDR NV12→Wave5主路径。
**正式7.3已经启用受限PQ硬件映射，应做补齐和规范化，不是从零打开HDR2。**
GPU tone-map shader、DMA适配和编译器优化全部暂停，保留既有提交；GPU仅作必要缩放/后备。
路线选择依据是已有硬件路径、厂商分工及窗口A原型的实际成本。

最新[PQ独占窗口](bringup/2026-10-30-hdr2-pq-window.md)：M6仍为SDR/444/8bit，EDID已经宣告PQ；
完成5.15/uhd3同源SDR旁路、编码前帧和受限寄存器基线，并补齐配置/已写PQ shadow CRC诊断。
PQ/HLG颜色及切换未实测，需要用户在M6物理开启HDR。独立[HLG候选](hdr2-hlg.md)已合并到本会话内核分支，
合并后的夹具、W=1/sparse通过，尚需完整候选构建和硬件门禁；未改正式配置、未push。
以下源码分析与工期为此前离线可行性研究，不代表上述窗口已经通过全部验收。

## 固定源码与证据记法

- V：VM `~/src/linux-native-hdr-5.15/common_drivers@8648a716befda5ec2837a7764cd61b8493db8d99`，工作树干净。
  这是包含native-hdr分流的源码快照；本轮不宣称已重新核对板上hdrdual6二进制的完整源码锁。
- P：VM `~/src/linux-7.3-hdmi-integration@f71b5c6289cb3254690e57292327e73514f0715f`，正式uhd3。
- 以下V的`vin/...`均相对`drivers/media/vin/tvin/`；`vecm/...`相对`drivers/media/enhancement/amvecm/`。
  P的短文件名均相对`drivers/media/platform/amlogic/t7-hdmirx/`。
- 普通VM `~/src/linux/common_drivers@563cff9d…`与V不同，且其vdin_drv.c有未提交修改；只用于定位，未混作native-hdr依据、未改它。

## 5.15：谁决定输出，谁写HDR2

| 环节 | file:line与行为 |
|---|---|
| RX静态HDR信息 | V `vin/hdmirx/hdmi_rx_drv.c:1551–1587`从已接收DRM包填充EOTF、metadata id、primaries、白点、mastering亮度、MaxCLL/FALL和rawdata；不是从输出显示器猜输入 |
| 信号变化 | V `vin/vdin/vdin_sm.c:271–293`比较hdr flag/EOTF，经计数确认产生SDR↔HDR变化；同文件`:651–695`将HDR_STATE_GET/NULL与EOTF转成vdin_hdr_flag |
| VDIN选处理类型 | V `vin/vdin/vdin_ctl.c:1879–1887`区分SDR/HDR10/HDR10+/HLG；`:1963–1981`分别调用hdr_set(HDR_SDR)、bypass、HLG_SDR。HDR10+此处走静态HDR_SDR，不等于完整动态元数据映射 |
| 配置触发 | V `vin/vdin/vdin_ctl.c:2030`附近的set_matrix路径会配置HDR；V `vin/vdin/vdin_drv.c:3480–3519`在颜色/HDR/范围变化后重配矩阵和写出，丢弃转换帧；`:3472–3477`在帧边界处理用户曲线reload请求 |
| amvecm入口 | V `vecm/set_hdr2_v0.c:4433–4439`的hdr_set调用hdr_func；`:4951–4967`先选时钟/模块，再输入矩阵→EOTF→gamut→OOTF增益→OETF→输出矩阵→chroma gain/hist。不能只拷三张LUT忽略matrix/bit mode |
| PQ表选择 | V `vecm/set_hdr2_v0.c:3295–3312`选eo_y_lut_pq或eo_y_lut_hdr、hdr_sdr_gain、oe_y_lut_sdr；eo_gmt_bit_mode的T7分支在`:3209`附近，移植时锁定该分支而非其他SoC默认值 |
| HLG表选择 | V `vecm/set_hdr2_v0.c:3373–3407`区分普通HLG与CUVA静态模式，选eo_y_lut_hlg/hlg_23、oo_y_lut_hlg_sdr、oe_y_lut_sdr及cgain。不能以PQ表或解析EOTF=3一项替代HLG处理 |
| 用户曲线独立性 | V `vecm/set_hdr2_v0.c:442–453`为VDIN提供独立149点gain，避免全局VPP策略覆盖；这仍是厂商module_param接口，七系不应照搬成新UAPI |

### native-hdr/hdrdual关系

V `vin/vdin/vdin_ctl.c:1890–1922`定义`vdin0_native_hdr`：为1时VDIN0明确调用HDR/HLG bypass并清除hdr_sdr_output，
让本地显示路径保留高位深；共享主HDMI frontend的VDIN1则按**输入RX**分类映射SDR，不依赖TX当前格式。
VDIN1默认VIU回写分支仍存在，不能把任意video71都当HDMI输入。
`vdin1_set_hdr_bypass`只是提前return，不等于主动清除旧HDR2配置；需要显式bypass序列和状态证明。
产品路径为RX→VDIN0原生HDR→VPP/TX，以及同源RX→VDIN1 HDR2→SDR KVM；见[既有双路径交付](bringup/2026-10-25-native-hdr-dual-path.md)。
七系这次目标是**捕获SDR**，不复制native-hdr参数，也不要求先做原始十位DMA导出/GPU tone map。
V `vecm/set_hdr2_v0.c:810–812`的cuva_static_hlg_en源码默认零，但可运行时修改；对照需记录该参数，不能仅凭默认值断言板上实际HLG分支。
若未来同时做原生HDR显示，必须单独设计显示与捕获消费者的所有权及HDR metadata，不能把已映射NV12标成PQ再发TX。

### T7寄存器块与确定值来源

V `vecm/arch/vpp_hdr_regs.h:502–563`给出VDIN0/1 HDR2**字索引**；不是物理字节地址，不能直接加到任意MMIO基址。
P `t7-vdin-test.c:185–198`按设备资源与字索引映射，并拒绝资源外寄存器；继续沿用该边界。

| T7 VDIN0字索引 | 功能 | 来源 |
|---|---|---|
| 0x1280/0x1281 | HDR_CTRL/CLK_GATE | V vpp_hdr_regs.h:502–503 |
| 0x1282–0x128d | 输入矩阵/offset/pre-offset | 同文件:504–515 |
| 0x128e–0x1299 | 输出矩阵/offset | 同文件:516–527 |
| 0x129e/0x129f | EOTF addr/data | 同文件:531–532 |
| 0x12a0/0x12a1 | OETF addr/data | 同文件:533–534 |
| 0x12a6/0x12a7 | OOTF gain addr/data | 同文件:539–540 |
| 0x12a8–0x12af | adaptive scaler参数 | 同文件:541–548 |
| 0x12b0起 | gamut mode/coefficients | 同文件:549起；VDIN1基块0x1380在:563 |

V `include/linux/amlogic/media/amvecm/hdr2_ext.h:80–82`固定EOTF143、OOTF149、OETF149项。
PQ/HLG完整profile必须包含有符号系数、offset、LUT长度、打包位宽/舍入、gamut和enable/bypass位，逐字段注明V源位置与hash。
这些地址只是审查清单，**不是允许逐地址盲扫或整段复制写入的脚本**；T3X等其他SoC有不同银行，禁止套用。

## 正式7.3：已有能力与真实欠账

| 能力 | P源码证据 | 结论 |
|---|---|---|
| DRM infoframe | t7-hdmirx.c:813–836：双读、包型0x87/version1/length26/checksum，EOTF=2、descriptor=0，失锁清状态；:846一秒有效期 | 已有真实PQ包处理；不是无条件把HDR EDID当输入PQ。HLG EOTF=3当前不接纳 |
| AVI/range/位深 | t7-hdmirx.c:839–863、905–952：BT.2020 YUV、GCP与AVI一致性检查；dynamic允许420/422/444，有限PQ路径；RGB2020及HLG拒绝 | PQ limited是现成基线，不能宣称所有RGB/全范围/深色组合通过 |
| 运行时启用 | 主仓packaging/kernel-edge/one-kvm-edge-prepare:34–38启用hdr_probe/hdr_capture及dynamic_modes；:62–65应用曲线 | 内核参数自身是实验默认，但产品prepare已经开启；缺口不是“忘了加载HDR2” |
| 矩阵/HDR2 | t7-vdin-test.c:421–457先清旧矩阵/HDR使能，再按lease调用HDR配置；t7-vdin-hdr.h:100–139写输入/输出/gamut、143点PQ、adaptive参数、enable | 已是真正的硬件映射，不是GPU或八位截断替代 |
| LUT重载 | t7-vdin-hdr.h:70–83写149点gain与OETF（后者右移2位）；t7-vdin-test.c:240–245在AXI完成边界应用并丢过渡帧 | 已有安全边界，保留并补完整profile事务，不在任意活动帧逐点改表 |
| 当前接口 | t7-vdin-test.c:1425–1477：298值验证后置pending，暴露私有hdr_curve sysfs | 现有兼容口需收敛；不复制到新设计作为正式寄存器/LUT UAPI |
| 输出/编码 | t7-vdin-test.c:1049–1069：NV12、32字节行对齐、16行tail容量、709/limited；gst-plugin-venc/wave5/gstvim4wave5enc.c:156只公布NV12 | 可直接走已验证NV12 dma-buf→两平面lease→Wave5；不需要新十位写出接口 |

t7-vdin-hdr.h:7–67已有PQ/gain/sRGB表，:96–98说明PQ2020到SDR域；
但fill_fmt把NV12 transfer统一标709。**sRGB表与709 OETF不是同一曲线**，必须核定信令与像素目标，不能仅改标签宣称一致。
还须检查GStreamer caps→Wave5 VUI→浏览器的传递；若固件信令受限，需提出带像素误差证据的兼容方案，不能在驱动里静默换gamma掩盖问题。
HDR配置调用未以nv12为条件，RGB24请求的最终矩阵/输出字节解释也需单独审查；首个候选只承诺HDR→NV12，不扩展HDR→RGB24。
此外tools/hdr-curve.sh的tables-edge与厂商tables肩部不同：先固定203/1000、选择明确的厂商对齐profile，不能拿不同曲线做逐码通过判断。
当前lease保存HDR分类（t7-hdmirx.c:1982–1992），check_capture刷新DRM并保护活动DMA（:2099–2150）；
仍应专测同分辨率的EOTF/range变化、失效DRM和恢复，不能由“已有函数”推断切换/全格式已验收。

## 上游框架与实现边界

主路径：HDMI RX subdevice的输入色彩/静态HDR快照→VDIN HDR2固定profile→SDR NV12 DMA→现有Wave5，GPU不承担逐像素tone map。
输入域与输出域分别存储；每帧绑定generation，源域BT.2020/PQ或HLG不能污染转换后709 NV12的输出标签。

1. **源描述**：保留AVI/GCP/DRM的有效性、色域、range、EOTF与时戳，PQ/HLG枚举取代单一lease_hdr bool；非法/过期不以SDR猜测继续写帧。
2. **输出协商**：用VIDIOC_TRY/S/G_FMT的colorspace、xfer_func、ycbcr_enc、quantization表达输出域。
   P `include/uapi/linux/videodev2.h:915、935–939`已有SET_CSC及CSC_*能力旗标；只声明真正实现的转换组合，不将这些旗标本身视为硬件tone-map定义。
   应用未指定时保持兼容默认；不支持的请求不得悄悄按PQ处理。格式/颜色改变走V4L2 source-change/reconfigure与有界drain。
3. **参数控制**：首个候选使用固定、版本化的203/1000厂商对齐profile，不增加裸寄存器或任意LUT接口。
   若保留用户white/peak需求，再提出有单位、边界和默认值的通用V4L2控制规范；目前没有可直接套用的通用white/peak tone-map控件。
   固定profile仅是首个候选，不代表允许静默删除现有管理器调参功能；旧兼容口的退场须与应用迁移一并验证，最终方案不能以新厂商私有控件绕过通用接口讨论。
   HDR10 mastering/CLL元数据控件不是映射白点，摄像头WDR控制也不是PQ/HLG选择器，不能滥用。
4. **DRM边界**：借鉴degamma/CTM/gamma分层概念，但VDIN不是CRTC；不借DRM output HDR metadata强行控制capture，也不制造新的厂商ioctl/sysfs。
5. **事务**：profile在进程上下文计算/验证，停流或已审阅AXI完成边界应用；保持既有资源/时钟/复位顺序。
   先准备全部matrix/LUT，最后启用；明确SDR/bypass清理。跨blanking丢弃过渡帧，旧buffer直到GPU/编码器退休才复用；故障不热解绑驱动。

PQ先保持现有有限YUV输入与NV12输出；HLG第二个独立补丁按V的**T7普通HLG分支**选EOTF/gain/gamut/cgain/OETF，
不复用PQ的gamut mode假设、不误用CUVA或g12a的ox2表。RGB2020、full-range HDR、动态HDR及原生HDR显示另列能力，未验收前不在EDID扩大宣传。
静态对照时固定动态clip/hist/VPP策略或记录全部实际应用参数；不能拿可变厂商LUT与固定七系profile计算“同条件误差”。

## 下一步离线计划、工期与验收

| 离线阶段 | 交付与证明 | 估算工程日 |
|---|---|---:|
| 固定来源与差分 | PQ/HLG的T7寄存器/profile来源表、LUT hash/长度/打包、厂商tables与edge曲线差异；保留作者/许可证 | 1–2 |
| PQ规范化 | 现有HDR2拆为纯profile选择＋受限写入器；统一像素/标签合同，去除新路径对私有sysfs的依赖；mock只允许清单写入、测试SDR清旧态 | 1–2 |
| HLG与生命周期 | infoframe EOTF=3、profile选择、generation/source-change、IRQ重载/失败回退；时钟/校验和/超时/切换夹具 | 2–3 |
| 色彩与产品验收 | 5.15同输入数值对照、PQ/HLG/SDR往返及Wave5 4K60/缩放/长期回归 | 2–3 |

**合计6–10工程日（含上述色彩/上板验证）**；若需通用控制设计或RGB/full HDR扩展，另加2–4日本地工作量，上游讨论/等待周期另计。
PQ固定profile的首个离线候选约2–4日；HLG不能因表已存在就按零成本估算。
相比GPU方案8–14日且窗口A仅12.74fps，这条路线复用已存在的硬件和NV12产品链，取消原始十位DMA/GPU外部buffer作为HDR→SDR前置依赖。
这是可行性与工作量判断，本轮没有新增硬件60fps或颜色一致性测试。

上板另开独占RAM候选窗口，每项timeout且≤10分钟，不HID、不音频、不ptrace、不猜电压，不改默认5.15：

- 建立5.15/7.3同源、同EDID、同white/peak基线；优先已有HDMI源图，无须采集卡，也不通过HID切源。PQ与HLG未就绪时明确记未测。
- 驱动内白名单快照只读已上电的CTRL/矩阵/offset/gamut/写出配置，读回mask后与profile逐字段比对。
  LUT先比对待写/已应用shadow的CRC；data port可能自增或不可读，不能把它当普通只读寄存器扫。
  只有确认端口读取语义、指针配置序列及停流保护后，才增加受限LUT读回。
- RX前矩阵具名10bit探针＋已知源色块作为输入参考；CPU模型按确定的定点matrix、LUT插值/截断与范围计算，比较**编码前NV12**。
  模型还需确定非均匀LUT节点间距及硬件浮点/定点规则；资料未闭合时只能给连续数学参考与5.15硬件配对，不能声称已有bit-exact模拟器。
  黑白、近黑、灰阶、203/400/1000nit层次、饱和色及色度位置；厂商硬件配对误差先建固定包，预注册容差，不从主观画面或GPU数学容差直接推导硬件容差。
- PQ↔SDR、HLG↔SDR、PQ↔HLG、同分辨率range变化、断包超时/失锁恢复各有帧generation与PTS证据；过渡帧不交编码，无混用旧HDR2状态。
- 持续4K60采集→Wave5至少60秒，测吞吐、p99、CPU、CMA、完整帧和错误；缩放独立配对。普通性能采样不同时读大量寄存器或执行CPU全帧oracle。
- 颜色门禁不过则停止性能推广；正常重启回5.15，服务/UDC/启动文件SHA一致，释放锁。无面板光度测量就不宣称显示亮度准确。

可行性研究阶段只提交文档；旧GPU shader、DMA适配与实验编译器提交均保留，不继续实现。
该阶段主仓全量unittest：315项、跳过13项、无失败；本轮实施验证见最新窗口记录。
