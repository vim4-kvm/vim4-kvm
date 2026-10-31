# 7.3 原生远程 HDR10 候选与门禁

本分支实现 `VDIN AMLY → Vulkan → P010 → Wave5 Main10 → 用户态 HDR10 SEI`。
尚未通过实板门禁，不能视为P0完成。证据见[离线调查](bringup/2026-10-31-hdr10-remote-offline.md)。

## DMA与模式

AMLY是私有fourcc，不是标准P010/Y210/NV15。唯一C定义在内核
`include/uapi/linux/amlogic-vdin.h`：每两像素五字节，little-endian连续十位槽
Cb/Y0/Cr/Y1，一个内存平面，stride=`ALIGN(width*5/2,32)`。
4K为9600×2160=20,736,000字节。REQBUFS/CREATE_BUFS共用HDR2的192 MiB字节预算，
先扣direct DMA discard frame，再按实际allocation_size计算；4K最多八个用户缓冲。
GPU source使用四个采集缓冲、三个独立P010缓冲。

VDIN状态由空队列S_FMT决定：NV12使用HDR2→BT.709映射，AMLY旁路HDR2保留十位。
切换先停编码、等待租约归还、STREAMOFF、worker退出、REQBUFS(0)，再S_FMT和重启。
忙队列拒绝切换。原生STREAMON只接受有效PQ/YUV/limited，拒绝HLG/RGB/full；
原生期间保留待更新HDR2 LUT，恢复映射后装载。SDR继续八位路径。

私有GStreamer `vim4amlysrc`复用5.15产品的Vulkan compute API与着色器：
`amly-gpu.c`、`amly-to-p010.comp`，缩放用`amly-to-texture.comp`、`texture-to-p010.comp`。
仅dma-buf导入/导出，无像素CPU mapping或转换后备。连续堆依次尝试
heap-codecmm、reserved、linux,cma，不用非连续system heap。
允许Vulkan 1.1 core与1.0 KHR等价查询，以兼容kbase/Panfrost API；仍要求真实Mali-G52、
compute和外部dma-buf能力，不能据此声称两个驱动已实测。
[KHR查询合同](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_external_memory_capabilities.html)
与[dma-buf扩展](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_external_memory_dma_buf.html)
共同约束导入。标准十位VDIN直写只继续查资料，有证据再提议，不盲试寄存器。

GPU输出为标准P010_10LE：16-bit字高十位有效，交错CbCr，两分量共享连续fd。
Wave5 storage为32像素×16行：stride=`ALIGN(width*2,64)`，
UV offset=`stride*ALIGN(height,16)`，容量为offset×3/2。
VideoMeta传递可见尺寸、stride、UV offset与右/下补齐；着色器使用同一storage height。
不得用可见高度或额外尾容量猜UV offset。

## 编码、元数据与能力

P010仅接HEVC十位内部编码，保留固件`support_hevc10bit_enc`检查。
匹配5.15 SDK的`FORMAT_420_P10_16BIT_LSB`使用LEFT_JUSTIFIED/16BIT，legacy source
endian为0xe；r1的0xf已修正。必须以相邻值差一的十位梯度经真实编解码验证。
VUI从V4L2 colorimetry传递：BT.2020/PQ/BT.2020nc/limited，即9/16/9、full_range=0。
SPS同时检查profile=2和Y/UV bit_depth_minus8=2。

VDIN暴露只读volatile标准compound controls：
`V4L2_CID_COLORIMETRY_HDR10_CLL_INFO`和`MASTERING_DISPLAY`。
来源是校验合格的HDMI RX DRM静态infoframe；无包、非PQ或超过一秒返回ENODATA。
保留显式零值；HDMI MaxLum整cd/m²乘10000，MinLum不重复换算。
多次读取尚不承诺与特定DMA帧原子绑定。

没有证据证明Wave521C固件采用Wave4 SEI ABI，不写猜测寄存器，也不注册暗示固件会
插入SEI的空实现控件。One-KVM在编码后AU插入完整Annex B prefix SEI：137为mastering、
144为CLL，大端和emulation prevention；每个IRAP前重复，元数据变化时更新；去除已有HDR
消息但保留同NAL其他SEI。无新鲜源metadata时丢弃原生AU，不编造EDID默认值。
历史保存的5.15样本没有type39/40，不能据此断言当前所有产品流均无SEI；仍需新鲜基线。

One-KVM能力探测不读uname：VDIN AMLY枚举、两类metadata controls大小/可用性；
独立无缓冲编码上下文协商HEVC/Main10/P010、尺寸、stride、容量及PQ/2020nc/limited；
检查私有source和编码器P010 caps。源PQ还要求新鲜metadata。静态检查不能替代固件/像素门禁。

## 应用与阶段门禁

沿用HDR_SDR_ENABLED和UU enable_hdr选项语义：原生请求与HDR源都满足时选AMLY/GPU/P010，
否则选HDR2映射NV12。共享采集所有者串行重建，不为截图临时切换主采集。
源变化、UU断开与接管的恢复仍须实板往返验证。

| 接入方 | 本候选范围 / 未完成项 |
|---|---|
| One-KVM网页 | Wave5原生source、Main10/PQ、SEI和能力探测；接收端HDR 4K60未验 |
| UU | 复用共享编码，沿用独立十位声明、profile2、enable_hdr；未连真实客户端 |
| NanoKVM / JetKVM / PiKVM | 仍需扩展公共vim4h265src的Wave5后端，各网页/Janus独立验收；本轮未改 |
| JPEG / H.264 / 截图 | 映射模式保留；原生Wave5暂无并行SDR分支，截图不可用。需GPU tone map或同源第二VDIN才可宣称双路径/P0 |

| 阶段 | 门禁 | 剩余预计 |
|---|---|---|
| 离线候选 | 同源完整Image/DTB/模块，私有插件/One-KVM构建，宿主生命周期/码流测试，归档及哈希 | 以本轮实际记录为准 |
| 硬件精度与性能 | 真十位DMA、P010低两位、真实SPS/VUI/SEI；先量5.15 Vulkan分辨率/fps/GPU占用，7.3至少对齐；零WARN | 1–2工程日 |
| 产品补齐 | 原生期间并行SDR截图、四应用公共源、UU恢复、浏览器实际HDR解码4K60 | 3–5工程日 |

主要风险是固件P010解释、PanVK/kbase外部内存能力、CMA峰值与UHD60带宽。

## 独占上板清单：最多30分钟

先完成离线构建、提交、push和归档。全部使用主仓main新工具：重负载用
`tools/board-queue run --heavy --who hdr10 --purpose ... -- <cmd>`；上板用
`tools/board-queue run --who hdr10 --purpose ... --max-min 30 -- <window脚本>`。
窗口内使用board-window的boot-candidate/mcp/receiver/collect/return-baseline，
编译不持板票据，不再直接使用lockf。按kbase、HDR(uhd4)、本会话的队列次序，最多等150分钟；
5.15基线优先复用哈希不变的缓存。上板前若正式uhd4已合入，先rebase再出候选。
必须有M6 MCP；新工具的HDR操作实际发送HID，与此前禁止HID约束存在冲突，
得到限定授权前仅截图/检查，不执行HDR点击序列。预备5.15回退与已验证启动工具，禁止刷机。

1. 0–5分钟：截图确认M6空闲，经MCP开HDR；在5.15保存新鲜产品HEVC与Vulkan转换
   分辨率/fps/GPU占用；记录服务、UDC、源状态、固件及产物哈希基线。
2. 5–12分钟：候选工具加载唯一release的Image/DTB/模块；核对release、build ID/BTF、
   源PQ/2020与WARN增量。抓少量AMLY/P010核对真实低两位、UV顺序、stride/storage。
   不把八位左移当十位；任一失败立即收尾，不改未知寄存器。
3. 12–20分钟：解析真实Main10/十位SPS、9/16/9/limited VUI、137/144逐项数值和去重，
   与新鲜5.15对照；网页接收端证明HDR解码4K60，UU短测独立声明；记录GPU性能。
   不以发送fps代替接收显示证据。
4. 20–24分钟：原生→HDR2映射→SDR→原生，核对画面恢复、队列释放、CMA/fd、零WARN。
   原生SDR截图缺口明确记录，不计通过；四应用长测另开窗口。
5. 24–30分钟：MCP关闭M6 HDR并截图；回5.15核验服务、UDC、配置和哈希；保存原始样本、
   码流与接收统计，释放锁。窗口超限立即收尾。

全程不发HID、不测声音、不ptrace视频进程，sudo不与heredoc共用stdin。
