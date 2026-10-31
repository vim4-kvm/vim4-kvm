# 7.3 原生远程 HDR10 设计与门禁

当前为离线候选，**尚不能在 7.3 网页或 UU 启用原生 HDR**。P010 输入接线、
格式容量修复和 HDR10 SEI 序列化已有候选；VDIN 十位输出、HDR10 controls 的固件
接线和应用能力协商尚未完成。不能把 HDR2 映射、Main10 枚举或 CPU 测试算作端到端通过。
源码证据、测试结果见[离线调查](bringup/2026-10-31-hdr10-remote-offline.md)。

## 格式与采集

对外目标使用标准 `V4L2_PIX_FMT_P010`：一个连续内存平面，内部 Y 与交错 CbCr
两分量平面，LE 16-bit 字的高十位有效；同一 byte stride，至少 `2*width`、按32字节
补齐，UV 从 `stride*storage_height` 开始，总容量 `stride*storage_height*3/2`。
可见高度、storage height、UV offset 必须分别传递，禁止由可见宽度反推 pitch。
若沿用当前紧密采集，storage height 就是实际采集高度；额外尾部容量不能改变 UV offset。
Wave5 若协商补高，应像现有 NV12 adapter 一样以真实 plane views 显式导入。

5.15 的 AMLY 是 packed 4:2:2（每两像素5字节），并非 P010；早期有16字节反序，
当前 no_swap 模式为连续 little-endian 十位 Cb/Y0/Cr/Y1。不能把它标为 P010、NV15
或 Y210；Y210 的分量顺序、字填充和步长也不同。7.3 首先在**私有 DMA 环**验证原始
十位 MIF 布局，再选择能直接得到标准 P010 的 MIF 模式；若硬件不支持，利用现有
私有环→V4L2 缓冲复制边界完成显式解包/垂直色度过滤，输出才报告 P010。
不把私有 AMLY fourcc 新增为产品接口。CPU 转换只是正确性基线，不能承诺4K60。
GPU 路径需单独核对7.3的DMA导入、缓存一致性和连续内存预算，不能套用5.15通过结果。

原生模式让 HDR2 bypass、保留 PQ/BT.2020 与 limited/full；映射模式继续使用现有
HDR2→NV12/BT.709。不得先映射到八位再扩展为 P010。SDR 源保持八位效率路径。
不能因为 RX 报 ten-bit 就认为输出 DMA 或编码保留十位。

## 编码、元数据与能力

P010 先限定 HEVC/Main10；八位 Main 和 AVC 输入不能误用此布局。
候选将 P010 接到现有 `FORMAT_420_P10_16BIT_LSB`：此处 LSB 指低六个填充位，
寄存器使用 LEFT_JUSTIFIED/16BIT，沿用既有 source endian 设置。其最终字节解释
必须用相邻样本仅差1的十位梯度经真实编码/十位解码确认。
保留驱动的 `support_hevc10bit_enc` 固件能力检查，不以 Wave521C 名称替代它。
 packed 32-bit 的既有寄存器分支不等于标准 NV15，暂不新增其输入格式。

VUI 从 S_FMT 的 colorspace/xfer_func/ycbcr_enc/quantization 生成，PQ 为9/16/9，
禁止管线后段重新强制709。Main10 SPS 必须同时检查 profile 和两项 bit_depth_minus8=2。

后续用 `V4L2_CID_COLORIMETRY_HDR10_CLL_INFO` 和
`V4L2_CID_COLORIMETRY_HDR10_MASTERING_DISPLAY` compound controls，独立存在标志，
显式全零CLL不能变为“无元数据”。SEI payload 137/144 使用大端，亮度单位0.0001 cd/m²；
HDMI DRM 的 MaxLum 整 cd/m²必须转换，MinLum不能重复乘10000。
必须区分 RX 没包、包内零值与上一次信号的缓存。
标准 mastering control 的校验范围可能不接受源端全零 mastering；需以真实
V4L2 core 验证，不能绕过标准验证或编造默认色度/峰值。

当前 serializer 输出完整 Annex B prefix SEI，尚未接入寄存器。下一步先从匹配固件
API确认 prefix info 的长度单位、使能位、NAL/RBSP输入和插入顺序。固定流元数据在
SEQ_INIT前建立私有 coherent DMA，保留到固件停止；复用现有隔离/销毁合同。
streaming期间控制修改先返回EBUSY并重建，避免修改仍被队列引用的SEI。
每个随机访问入口前重复静态元数据，保证后加入的网页/UU订阅者可恢复；AU必须保留SEI。
在接线完成并经码流读回前不注册这些 controls，以免能力探测误报。

GStreamer 要实测标准 video4linux2 对 P010_10LE 的 caps、单内存平面和两分量映射，
以及8/10位切换时 buffer pool 释放；标准 HDR caps/metadata 显式转 compound controls。
不能认为插件会自动设置 metadata controls。保持独立标准插件路径，避开厂商
libamlv4l2src；标准 P010 的插件映射与协商尚待私有插件集成测试。

应用能力探测不读 uname：分别探测采集 ENUM_FMT/TRY_FMT 返回的真实P010布局与色彩、
编码 P010→HEVC/Main10、QUERY_EXT_CTRL 的 compound 类型/大小和插件caps。
缺任一项返回具体不可用原因；不因“已安装.so”或“profile菜单含Main10”开放7.3 HDR。
已有 `wave5_caps.rs` 可承载无缓冲探测，但格式静态探测仍不能代替固件与像素门禁。

## 切换与产品范围

由共享采集所有者串行执行：停止取帧→停编码→等待编码/截图/显示租约归还→STREAMOFF→
释放池→选择原生P010或HDR2映射NV12→协商→重新启流。失败返回明确不可用状态，
不输出标为PQ的709图像。源端HDR/SDR变化走同一状态机，不改EDID、HPD或HDMI服务。
保留全局HDR_SDR_ENABLED和UU会话临时偏好的现有恢复合同。

同一采集的一种模式切换不能假装同时有两种输出。5.15有独立VDIN1 SDR路径；7.3在
原生HDR时的JPEG/H.264/截图须显式分支tone map，或后续增加同源第二VDIN。没有此分支
时不得为截图短暂切换共享主采集；产品门禁包含HDR推流期间独立SDR截图。

| 接入方 | 范围与边界 |
|---|---|
| One-KVM | 独立worktree修改wave5 caps/pipeline、VideoMeta、重建与截图支路；先接通再开放hdr_remote_available |
| UU | 复用共享编码；独立十位解码声明、profile2、enable_hdr请求、源端PQ和显示能力共同决定；保持断开/接管恢复偏好与单NAL VPS/SPS/PPS |
| NanoKVM / JetKVM / PiKVM | 扩展公共vim4h265src的V4L2后端，保留各网页业务；WebRTC/Direct/Janus分别验证SEI、色彩和Main10 |
| H.264 / JPEG / Safari | H.264/JPEG继续SDR；Safari没有现成真HDR验收，不能随Chrome成功扩大支持声明 |

本轮没有修改One-KVM，仍保留Vendor能力门禁。应用改动必须另建其worktree，按VIM4.md
执行Rust、上游目标检查和前端构建。不能只去掉Vendor判断。

## 阶段与工作量

| 阶段 | 预计工程日 | 门禁 |
|---|---|---|
| A：编码器输入 | 1–2 | 实际C宿主回归、模块/完整Image构建；合成P010十位梯度编码、SPS/VUI与逐样本解码；能力位拒绝测试 |
| B：采集与模式 | 2–3 | 原始DMA布局证据、标准P010容量与边界；PQ↔SDR↔PQ三轮、HDR2无退化、sequence/动态标记/租约与CMA稳定 |
| C：controls/SEI/GStreamer | 1–2 | 标准controls校验、缺包/零值、源元数据逐值对照；真实输出137/144读回、晚加入恢复、停止/隔离不早释放DMA |
| D：四应用/UU | 2–3 | Chrome PQ/2020/Main10、UU独立十位声明、尺寸变化、开关/接管恢复、并行SDR截图；原有SDR行为保持 |

合计约6–10工程日（阶段A与C部分重叠），另需独占板子窗口；固件不接受P010或SEI ABI
不兼容时重新估算。当前仅完成A的离线输入候选和C的序列化，不是P0完成。

## 下一次上板清单：最多30分钟

前提：完整Image/模块/BTF匹配已在另一授权窗口验证且候选已经运行；本清单不安装内核、
不重启或刷机。B/C尚未实现时只执行合成编码诊断，不能跳过门禁做网页HDR演示。
取得板锁和heavy锁，确认其他会话释放，预先准备所有工具和私有插件，计时超限立即收尾。

1. 0–3分钟：记录release/commit/固件SHA、服务/配置/源模式/CMA/fd与dmesg基线。
   不发HID、不测声音、不ptrace，不把sudo和heredoc共用stdin。
2. 3–8分钟：停用共享编码消费者后，用自有编码进程输入64/656宽及1080p合成十位梯度，
   同时保留带padding案例；离线解析SPS/VUI/SEI并十位解码。有效低两位、UV顺序或SEI
   任一不符就结束测试，不尝试改源掩盖。
3. 8–14分钟：由MCP在M6开启真实HDR（仅设置显示HDR，不发送HID），读取RX PQ/2020，
   抓原始DMA与P010各少量帧；核对stride/UV offset、灰阶最低位、动态标记与元数据。
4. 14–20分钟：One-KVM网页与UU顺序各短测；检查实际profile2、十位SPS、PQ/2020、
   SEI和内容推进；UU开关往返、断开恢复；不以发送fps代替接收显示证据。
5. 20–25分钟：Nano/Jet/Pi依次短测公共源，HDR期间SDR JPEG；真实HDR→SDR→HDR一次。
   这是冒烟，四应用的缩放、Direct、长稳与光度验收另开窗口，不宣称已全覆盖。
6. 25–30分钟：恢复原源HDR设置、全局偏好、应用选择与服务；比较配置、fd/CMA和dmesg，
   保存原始码流、十位解码、接收端统计与逐阶段失败。复位失败则保留隔离，不强制释放。
