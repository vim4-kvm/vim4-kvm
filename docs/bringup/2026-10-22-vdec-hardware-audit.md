# 2026-10-22：T7 解码硬件、固件与主线差异明细

本页是[可行性调查](2026-10-22-vdec-feasibility.md)的离线证据明细，版本和执行范围见该记录。
后续原始能力值见 [Wave521C 取证](2026-10-22-vdec-wave5-capabilities.md)，
带厂商行号的时序表与离线改动见 [T7 离线准备](2026-10-22-vdec-t7-offline.md)。
结论：T7 有独立 DOS 解码硬件；旧 meson-vdec 不能靠 DT 接入。
新 S4 stateless 是较合适的参考，但须实现 T7 的时钟、DBUS 和固件加载协议。
下述能力来自厂商源码与本轮只读元数据，均不是 7.3 解码实测。

## 厂商 T7 资源

以下路径均相对固定的 common_drivers：

| 资源 | 厂商证据 / 含义 |
|---|---|
| VDEC_1 | `common/chips/decoder_cpu_ver_info.c:237` 的 T7 表；旧格式及 H.264 解码核 |
| HEVC | 同表；HEVC/VP9/AVS2/AV1，front/back 时钟独立；`is_support_dual_core=false` 不表示没有前后端 |
| HCODEC | `mesont7.dtsi:jpegenc`、DOS_HCODEC 域；当前 JPEG 编码使用，不作为 AVC/HEVC 解码捷径 |
| Wave521C | `mesont7.dtsi:aml_enc`，`0xfe310000/0x10000`、IRQ 94/95、DOS_WAVE；与 VDEC 分开 |
| DOS 解码寄存器 | `mesont7.dtsi:codec_io` 的 dosbus 为 `0xfe320000/0x10000` |
| 解码 mailbox | `mesont7.dtsi:vdec` 的 mailbox_0/1/2 为 SPI 91/92/93，edge rising；不能全量申请并干扰 JPEG |
| 电源域 | `mesont7.dtsi:vdec` 分别 attach pwrc-vdec/hcodec/hevc/wave；T7 7.3 binding ID 分别为 4/2/3/5 |
| DOS 总线时钟 | 厂商 CLKID_DOS；7.3 为 CLKID_SYS_DOS，不能用它代替功能时钟 |
| 功能时钟 | 厂商 `drivers/clk/meson/t7.c` 的 vdec_p0/p1/mux、hevcf_p0/p1/mux、hevcb_p0/p1/mux；T7 最大表值各 800MHz |
| canvas | T7 表 `is_vdec_canvas_support=true`；`mesont7.dtsi:canvas` 基址 `0xfe036048`；不是“所有新芯片都无 canvas” |
| 输入机制 | T7 表 `is_hw_parser_support=false`；使用 VLD/HEVC frame-based 输入，不能访问旧 ESPARSER |
| MMU/AXI | `is_support_h264_mmu=true`、`is_support_axi_ctrl=true`；线性 canvas 路径与 MMU 路径须按所选固件分别核对 |

上述解码源码前缀是 `drivers/media_modules/`。
7.3 的 T7 canvas 节点已经存在：`&apb4/video-lut@36048`，大小 0x14，
可用标准 meson_canvas API；本轮未验证 decoder 使用它的输出布局。
厂商 DTS 中 vdin 的“no canvas”注释不是 vdec 能力声明。

厂商时钟寄存器在 `drivers/clk/meson/t7.h`：VDEC_CLK_CTRL 为 0x50×4，
VDEC2 为 0x51×4、VDEC3 为 0x52×4、VDEC4 为 0x53×4。
以 VDEC 为例，p0 使用 VDEC_CLK_CTRL 的 mux [11:9]、div [6:0]、gate bit 8；
p1 使用 VDEC3 同一低半部，最终 mux 在 VDEC3 bit 15。
HCODEC 使用同组寄存器高半部；实现 CCF 时必须使用精确 mask，不能整字覆盖。
HEVC front/back 另有各自的 parent/div/gate 和 mux；不能借用 Wave A/B/C 时钟。

7.3 `drivers/clk/meson/t7-peripherals.c` 和对应 dt-binding 已有 SYS_DOS、HCODEC、
Wave，但没有 VDEC/HEVC 功能时钟 provider。本轮 clk_summary 也未出现 vdec/hevc
功能时钟，只有 `t7_sys_ts_hevc` 温度传感器时钟。按厂商表补 provider 是实际前置工作。
800MHz 是厂商允许的上限，不是要求在首轮使用最大频率；本轮未设置任何频率。

## 格式与上限

T7 `fmt_support_flags = FMT_VDEC_ALL | FMT_HEVC_VP9_AVS2_AV1`。
`FMT_VDEC_ALL` 只包含 MPEG1/2、MPEG4、H.264、MJPEG、VC1、MVC、AVS；
没有 VP8、RealVideo、AVS3。不要把整个驱动目录中的 codec 当作 T7 支持列表。

| 格式 | 厂商功能报告 / 范围 | 固件目录对应项 |
|---|---|---|
| H.264 AVC | `vdec_feature.c` 报 4k30 | h264_multi、h264_multi_mmu |
| H.264 MVC | T7 格式位与固件存在；功能报告未单列可靠上限，不能断言 4K MVC | h264_mvc |
| HEVC | 功能报告列 8k；T7 表 hevc_max_resolution=8K | hevc、hevc_mmu、hevc_mmu_swap |
| VP9、AVS2、AV1 | T7 格式位存在，功能报告泛化列 8k；单格式精确 profile/帧率未从本轮资料确定 | vp9_mmu、avs2_mmu、av1_mmu |
| MPEG1/2 | 1080p60 | mpeg12_multi |
| MPEG4/Xvid | 1080p60 | xvid_multi |
| MJPEG | 1080p60 | mjpeg_multi |
| VC-1 | 1080p60 | vc1 |
| AVS | 1080p60 | avs_multi |

必须区分驱动能力分类与规格/逐格式保证：`decoder_cpu_ver_info.h` 的 4K/8K
常量分别为 **4302×2176、8192×4352 的面积门槛**，不是支持任意该宽高组合的声明。
T7 表同时给 `support_h265_level_idc=IDC_5_1`，与泛化的 8K 报告不足以组成完整规格。
[Khadas VIM4 官方规格](https://dl.khadas.com/products/vim4/specs/new-vim4-specs.pdf)
给出整机最高 8K24 和 4K60+1080p60 多路解码描述，没有逐格式上限表。
因此本轮能够确认上述支持集合和源码上限分类，**不能确认所有现代格式均达到 8K24**，
也不能把工作区 Wave 编码实测 4K60 当作解码上限或解码验收。

## staging meson-vdec 与 T7 对照

7.3 `drivers/staging/media/meson/vdec/vdec_platform.c` 只列 GXBB/GXL/GXLX/GXM/G12A/SM1。
其 codec 实现有 MPEG1/2、H.264、VP9；`vdec_hevc.c` 是 HEVC 硬件引擎管理，
不是 HEVC codec 支持，目录中没有 codec_hevc.c。

| 项目 | staging 实现 | 厂商 T7 / 必须改变 |
|---|---|---|
| DOS | MPSR 0xc04、CPSR 0xc84、AV_SCRATCH_0 0x2700、DOS_SW_RESET0 0xfc00 | 厂商 word 索引分别 0x301/0x321/0x9c0/0x3f00，乘 4 后相同；公共子集可参考，不代表整块兼容 |
| 输入 | esparser.c 配 parser MMIO、parser IRQ、fetch/startcode，再喂 VIFIFO | T7 无该 parser；须改成 vb2/frame-based 输入及对应固件消息协议，绝非补地址 |
| 时钟 | vdec_1/hevc/hevcf 固定命名及旧 revision 分支 | T7 需独立前后端 CCF provider、匹配 DT 时钟和可靠错误回滚 |
| 电源 | vdec_1.c/vdec_hevc.c 直接改旧 AO_RTI_GEN_PWR_SLEEP0/ISO0、DOS_MEM_PD | T7 通过 secure genpd，时钟使能后取 power domain；不能照搬 AO 寄存器 |
| 总线复位 | staging 对旧 DMC/AO 假设 | T7 厂商 vdec_reset_core() 使用 DBUS disable/enable，HEVC 使用 AXI 仲裁；不沿用 S4 的 DMC bit 21 |
| 输出 | meson_canvas_alloc/config，NV12M 等 | T7 确有 canvas；需核对 endian、linear/block 布局、DMA mask、MMU/参考帧协议 |
| 固件 | 各代 raw `.bin`，H.264 还复制固定偏移的扩展段；codec_h264 依赖 AV_SCRATCH 消息 | T7 有 multi/MMU 等不同微码；包 header、secure 加载、请求/DPB 协议与 raw g12a 固件不同，不能改名加载 |

最明确的硬件差异见厂商
`frame_provider/decoder/utils/vdec.c:vdec_reset_core()`：T7 走
`vdec_dbus_ctrl()`，向 word index `VDEC_ASSIST_DBUS_DISABLE=0x46` 写 disable mask
并检查状态，再复位，完成后恢复 DBUS。厂商等待中有无界循环，移植须补有界等待与
失败时 DMA 所有权处理，不能仅照抄。其注释说明 T7 的 VDEC 没有独立 DMC req。
HEVC 的 AXI 路径在同文件 `hevc_arb_ctrl()`；不能把 VDEC 的位写到 HEVC。

`utils/vdec_power_ctrl.c` 的 T7 PM 路径先使能功能时钟，再 runtime get power domain；
`dos_local_config()` 对 T7 不执行 S4 旧驱动那组本地 PD/reset 写操作。
旧 S4 驱动还忽略若干 clock/runtime-PM 失败，不能认为映射成功后即可访问 DOS。

## 板上 video_ucode.bin 的只读目录

从 `/lib/firmware/video/video_ucode.bin` 复制到不入库日志目录，未改板上文件。
389696 字节，SHA256：
`59e242bd63d6372d6462d2a2d6815e7bdea1a2cd12cd29fac093f38e73294e4b`。
依据厂商 `common/firmware/firmware_priv.h` 的结构解读：magic NEWP（字节 PWEN），
version=4、submit_count=129、total=15；所有目录项 CPU=t7，版本
`v0.4.81.If60661d.7f05035`、commit `7f05035`。

| 条目（文件名前缀均为 t7_） | 头部声明的微码字节数 |
|---|---:|
| av1_mmu.bin | 16384 |
| mpeg12_multi.bin | 8192 |
| jpeg_enc.bin（编码，非解码格式） | 16384 |
| xvid_multi.bin | 16384 |
| avs_multi.bin | 16384 |
| h264_mvc.bin | 28672 |
| hevc.bin | 40960 |
| hevc_mmu.bin | 36864 |
| hevc_mmu_swap.bin | 40960 |
| mjpeg_multi.bin | 16384 |
| avs2_mmu.bin | 28672 |
| vc1.bin | 16384 |
| vp9_mmu.bin | 28672 |
| h264_multi_mmu.bin | 4096 |
| h264_multi.bin | 28672 |

15 项的 package_info.length 全为 512，均只装一个 CODE header，没有其声明的完整微码。
元数据结束于偏移 11776，后面尚有 377920 字节，本轮未解码/拆分或将其解释为 raw 微码。
这直接排除了“逐项剥 512-byte header 就能得到 T7 h264_multi.bin”的做法。
固定 Armbian S4 的 load_firmware() 恰恰按 header 后直接 DMA 处理，不能喂这个目录项。

厂商 `utils/amvdec.c` 的 TEE 路径调用 `optee_load_fw()`，按 codec/microcode variant
选择索引，再经 `drivers/tee/tee.c:tee_load_video_fw[_swap]()` 发安全调用；
local loader 是另一条路径。新版社区系列补充 TEE 解包和 SM 加载，仍需核对 T7
现有安全世界接口、固件包和所需 variant，不能假定 S4 签名包与 T7 可互换。
本轮仅记录目录，没有向安全世界提交包，也没有尝试解密或发布固件。

## 共享硬件与首次上板前置条件

只读 pm_genpd_summary 当时显示 DOS_WAVE on、DOS_VDEC off、DOS_HEVC on、
DOS_HCODEC off；HEVC on 不意味着 decoder 已初始化，也不构成安全读 DOS 的保证。
clk_summary 中 Wave A/B/C 均为 666666656Hz，运行视频节点仅 VDIN 与 Wave 编码器。

DOS 的 VDEC、HEVC、HCODEC 寄存器窗口与 mailbox 邻接，当前 JPEG 驱动也使用
fe320000 内的 HCODEC 资源。候选必须核对 resource reservation 和 IRQ 的精确范围，
避免对全 DOS 申请互斥区导致 JPEG probe 失败，或全局复位破坏其他使用者。
Wave 单独使用 fe310000 与 DOS_WAVE 域；不能为了取解码能力复位正在编码的 Wave。
厂商 `/tmp/vpu_mutex.map` 是旧用户态共享锁，不会自动串行化新内核驱动。
现阶段不宣称可与 Wave 编码或 JPEG 并发；先停所有硬件消费者独占验证，再专门审查并发。

进入实际验证前须补齐：T7 功能时钟 provider 与 PM 出错传播、DBUS/AXI 有界停机证明、
匹配固件加载和 Request/DPB 协议、DMA 地址/缓冲生命周期、精确 DT 资源及编码/采集隔离。
首次存在挂总线风险的验证须具备现场 RESET 条件；软件 timeout 不能解除单次 MMIO 总线挂起。
每窗口从安装到恢复均持 board 锁，性能采样还持 heavy 锁，不在失败后反复尝试。
恢复须安装同次匹配整包并核验运行 build ID、服务、UDC 和实际 HID；不借用其他任务模块。
