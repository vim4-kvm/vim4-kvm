# 2026-10-23：M3 DMA 边界修复与剩余视频路径合同（离线）

接续 [多层与 SRAM](2026-10-23-display-m3-layers.md)。中断状态核对后，已推送的
`6dc88fb14bdf0` 没有重复开发；其主仓记录 `85f695d` 已推 main。本批继续审查视频层
依赖，补两个实际防护。**没有完成 VD1/VD2、NV12 scanout、AFBC 或 HDR 输出**，
不能把下述 NV12 内存布局测试当作已实现 video plane。没有访问板子或占用板锁，
没有修改正式内核分支、部署文件或版本锁。

## 两个修复

| 提交 | 改动与边界 |
|---|---|
| `b3d3c42c6d0ad` | 在 M3 atomic plane check 核对完整对齐行的 GEM 容量、各对象 offset 和 DMA32 范围；覆盖 RGB 当前消费者和 NV12 布局准备 |
| `64b99f269270f` | 启动取帧合同检查提前至 RDMA 通道配置之前；拒绝 AFBC fetch/unpack，避免线性 OSD profile 接管外部解码 DMA |
| `e4d19b428a947` | 执行真实 VDIN/Wave5 生产地址配置，接入 framebuffer 边界检查，避免布局测试只复述预期常量 |

通用 `drm_gem_fb_create()` 的容量下限允许最后一行只包含可见像素；MIF 按完整
对齐行取数，故现有 M3 检查 32bit DMA 范围还不够。新 `meson_t7_fb_check()` 对每个
对象验证 `offset + pitch * plane_height <= GEM size`，加法前核对对象边界和 DMA32
余量，再检查地址/stride 对齐。分别取每个 plane 的 GEM，UV 使用 framebuffer
声明的 offset，不从分配大小反推。当前接入的仍只有三个线性 RGB OSD。

`test_t7_fb.py` 执行实际 C helper，覆盖：最后一行缺 padding、恰好够大、非零 offset、
不对齐、64bit 地址、32bit aperture 最末一行、越界、UV 缺一字节、第二对象缺失、
第二对象单独越界、pitch 太小/太大、非线性 modifier；另覆盖 VDIN 单对象及
Wave5/vdec 两对象 NV12。`test_t7_handoff.py` 在实际 atomic check 注入短 RGB import，
确认返回 `-ERANGE`、无硬件写入和引用增加；补齐后正常通过。

`test_t7_producer_layouts.py` 另编译执行当前源码的 `t7_vdin_ring_arm()` 和
`wave5_prepare_fb()` linear loop，在 720×400、720p、1080p、4K 几何下覆盖 VDIN
ring/direct 各四例、Wave5 单对象 NV12/双对象 NV12M 各四例，共 16 例；用实际写出的
Y/UV 地址形成 framebuffer，并对每例注入色度对象少一字节。无硬件执行或 DMA 完成
模拟，不把生产者开始写入时的地址计算当作可提前显示/重新 QBUF 的同步证据。

接管检查原先位于 RDMA channel 初始化之后，检查失败也已修改通道。现在先只读
验证 boot frame、stride、scope、ENC2 totals 和 enable，再允许 RDMA 配置。
厂商 `t7_osd_afbc_set_state()` 用 `BLK0_CFG_W0[30]` 选 Mali fetch、
`MALI_UNPACK_CTRL[31]` 选解包；本 profile 未领取 AFBC SRAM，也未建立 decoder
退休合同，任一位存在即返回 `-EBUSY`，不尝试清零强行接管。
`test_t7_boot.py` 执行实际检查函数，覆盖有效固件状态、两个独立选择位，以及九种
fetch/timing 不匹配；确认函数不改寄存器。位置检查确保拒绝早于 probe 首个 RDMA 写。
既有 `bool` Kconfig、内置注册及 `suppress_bind_attrs=true` 生命周期保持不变；
补测试约束，避免今后误开放手动解绑而破坏持有到重启的 DMA/SRAM 合同。

## VD1/VD2：已核对的参数与尚缺的实现

厂商源码基准仍为 `common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49`，
本地读取 `/home/deepdream/src/linux/common_drivers`，`git status --short` 为空；
以下没有依赖板上读取值。

| 路径 | 厂商入口 / 确定事实 |
|---|---|
| T7 MIF | `video_reg.c:vd_mif_reg_t7_array`；VD1/2 为 SC2 `0x4800/0x4880`，不能复用主线 G12 `0x3200/0x3220` |
| 线性地址 | `set_vd_mif_linear()`；Y/CB/CR 分别位于 `0x4820..22`、`0x48a0..a2`，地址右移 4；不需要 canvas |
| NV12 | `vd1_set_mif()`；GEN_REG2 low2=2，NV21=1；8bit bit_mode=0；GEN_REG3 bit0=0 为 linear |
| stride | 32 字节对齐时 burst 随 `%64` 选择 1/2；Y/CB stride 合在 STRIDE_0；STRIDE_1 使用 masked 16bit 写，不可直接把表达式中的 bit16 当成有效写入 |
| formatter | progressive NV12 使用水平 2:1 和垂直 2:1 formatter，顶部 chroma phase/repeat 也须配置；不能只写 Y/UV 地址 |
| PPS | `pps_reg_t7_array`：VD1 使用 VPP PPS，VD2 使用独立 `VD2_*_T7` PPS；OSD scaler 的 `0x5a00` 表不能替代视频 PPS |
| 混合 | `vpp_blend_update_t7()`、`vpp_zorder_check_t7()` 和 DRM `postblend_check_state()`；视频在 OSD 组上/下可变，夹在 OSD 组内部的 zpos 被厂商明确拒绝 |
| SRAM | 先前加入的 VD1/VD2/VD1_SCALE 编号已做厂商枚举对照，但当前 DT 没有领取，不能先开 fetch 再补所有权 |

视频层完整接入仍缺：MIF/AFBCD linear 路由、两个 PPS、HDR/CSC SDR 旁路、postblend
端口与分组 zpos 检查、额外窄 MMIO claims 和 SRAM 接管。厂商 VFM/video_composer
wrapper 不是标准 DRM framebuffer scanout，不能连上私有 vframe 返回路径即宣称
完成主线 DMA-buf 接口。需以真实厂商函数生成参数对照，并把两视频层与三 OSD 置于
同一 RDMA 事务；短地址表预算、完整更新 drain、RMFB/error fence 都须扩展执行测试。

生命周期审查入口是 `video.c` 的 `cur_rdma_buf`、`dispbuf_to_put` 与 `amvideo_vf_put()`；
不能从通用 `VDIF_BUSY` 名称推断 T7 AXI 排空语义。当前没有把 OSD 的一/两 vsync
边界直接扩展成视频/AFBC 的 DMA idle 保证。这是尚未完成的移植工作，不是已经证明
T7 不支持 NV12，也不是通过内存边界测试便可上板的候选。

### 生产者布局

- VDIN `t7_vdin_ring_arm()`：UV 实际写地址 `Y + stride * height`；
  `stride * ALIGN(height,16) * 3/2` 只是尾部容量。1080 高不能把 UV 移到 1088 高。
- Wave5 `wave5_prepare_fb()` linear：按 negotiated width/height 形成 stride/offset；
  NV12 单对象 UV 跟随 luma，NV12M 直接使用第二个 VB2 对象。内部压缩参考帧的
  32 对齐布局不是可直接显示的 linear 输出。
- staging meson-vdec NV12M：两对象，`bytesperline=ALIGN(width,32)`；按协商 pitch
  和真实 plane size 导入，不把两个对象假定为物理连续。
- `drm_gem_plane_helper_prepare_fb()` 已遍历所有 plane 的 reservation fence；直通
  用户态仍需在显示退休后 QBUF，不能仅因 producer 完成便归还正在扫描的缓冲。
- P010：T7 厂商 DRM format list 无 P010；明确的 `P010_MODE/bit16_mode` 出现在
  `video_hw_s5.c`。T7 `video_hw.c` 的 packed10 bit_mode 不能证明支持高 10bit 的
  16bit 标准 P010 布局；保持拒绝，需 T7 寄存器合同或明确实现依据。

## AFBC 与 HDR 的启用边界

ARM AFBC 的 T7 core1 负责 OSD1/2，core2 负责 OSD3。厂商
`t7_osd_afbc_hw_disable()` 只清 surface enable，`arm_fbc_check_error()` 仅检查
raw status 的 error 位；该函数不等待 decoder DMA 排空。上游 G12A 路径 reset 会写
共享 `VIU_SW_RESET`，不能将整个字直接搬到与 VDIN 共存的 T7。

标准寄存器名区分 surfaces-completed（bit0）与 configuration-swapped（bit1）；
完成位若在新配置锁存前由旧帧留下，不能用于退休新旧两代缓冲。仍需建立每 core
配置交换、完成确认、错误 pinning 和 disable 的有序合同，覆盖迟到/陈旧 IRQ，再接
header/body 最小容量、modifier 组合、decoder SRAM、窄资源 claim 与多 surface 事务。
缺这一合同前不公开 ARM AFBC modifier，不用无限持引用掩盖退休问题。

HDR/10bit/420/Colorspace 仍未实现。当前链路是 8bit YUV444 BT.709 limited，
`meson_hdmitx21_bridge_mode_valid()` 也据此检查 sink；没有可用的 BT.2020/深色链路。
必须一起实现 VPP/OSD CSC、HDR metadata infoframe、AVI 色度/范围、formatter、
pixel/TMDS 分频、PHY 与音频 ACR；只挂 `HDR_OUTPUT_METADATA` 属性不能构成 HDR。
420 4K60 的 TMDS 不能继续直接等同于当前 pixel clock，须分别计算并验证。

## 验证与后续上板

持 Mac `/tmp/vim4-heavy.lock`，在独立 `~/build/kernel-display-m3` 顺序构建三个
提交的 Image/DTB/2334 模块。等待其他任务验收释放锁后才开始，没有绕过锁。
三次完整构建、显示/RX/Wave5/CEC 离线回归与定向 schema 均通过，无编译告警。
三个新增提交逐个 strict checkpatch 均 0/0/0；全分支最终 20 个提交也均 0/0/0，
日志中累计 57 次检查是 18+19+20 个提交的三轮检查，不是 57 个不同提交。

中间 build ID 前缀为 `7eb9748d91ab`（边界检查）、`fd451dda586f`（启动检查）。
最终 `e4d19b428a947`：build ID `ecc343cedffaea401a2b91d125c7020000298b1e`；
Image SHA256 `09bfb076724d5c2443e016e01f299ec16115465936d5d65634b27797638bfe69`；
M3 DTB SHA256 `8b535ea3b9ed3296a5076d0aa75f538fcbd896780e60e2274d7bf653761faf7e`；
配置 SHA256 `8af98a1fbefdf163c407f9f04bb31372178b8f8d7d6f00f5dff162b930c968bf`。
开发机日志 `logs/display/m3/build-import-bounds.log`，不构成板上证据。
配置快照另存 Mac `build/display-m3/config`，后续重建不依赖已删除的 M2 输出。

内核分支仍为 `vim4-display-m3`，只推到 fork，未合入正式分支。主仓同步 main
后全量离线测试 233 项、10 项跳过，整体通过。保留当前 M3 输出、配置和日志；
清理临时源码 worktree，旧 M0/M1/M2 输出清理见前一条记录，不重复计算回收量。

下次仍需先完成 [M2 用户在场收尾](2026-10-23-display-m3.md#用户在场时的-m2-收尾)：
RGB 数值、997Hz 物理录音、HPD 拔插；1440p/4K60 需对应显示器。本轮不请求用户插拔。
M3 按当时正式 HEAD rebase、匹配 Image/DTB/全模块、双锁一次性启动，先验现有 OSD
多层/缩放/zpos/alpha/反射/独立翻页、RMFB/disable、PRIME 和 RX 编码/音频共存；
SRAM provider 修改按部署门禁做九类全量回归。VD/NV12/AFBC/HDR 不能列为已可验项目。
任一超时/error fence 停止后续 DMA 操作，重启回默认基线并冒烟，不正式部署本分支。
