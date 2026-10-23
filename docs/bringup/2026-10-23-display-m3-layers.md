# 2026-10-23：M3 多层退休、SRAM 所有权与 OSD overlay/cursor（离线）

接续 [M3 首批实现](2026-10-23-display-m3.md)。本批完成前置的多层引用退休、
OSD SRAM 接管，以及 OSD2 overlay / OSD3 cursor、可变 zpos 和 OSD 缩放。
**M3 尚未全部实现**：VD1/VD2、NV12/P010、ARM AFBC、HDR/10bit/420 仍未接通。
没有访问板子、安装、重启、读取板上状态或申请板锁；没有修改正式分支及部署锁。
构建使用 Mac `vim4-heavy.lock`，等待其他任务的性能窗口结束，不绕过锁。

## 提交与验证

内核使用独立 worktree `~/src/linux-7.3-display-m3`，输出
`~/build/kernel-display-m3`；后续修复在临时 detached worktree 开发，正在构建的
源码保持不变，构建结束才快进。分支仍为 `vim4-display-m3`，基于已推送的 M2。

| 提交 | 内容 |
|---|---|
| `6cc4907186a98` | 五槽 framebuffer 引用所有权，同次锁存，故障 pinning |
| `bd1dfc1a38462` | M3 SRAM 接管 binding 与电源域编号 |
| `1c33a5ca791b3` | genpd SRAM、固件返回值检查、取数停稳后接管 |
| `779e0f35f8b91` | OSD scaler/path/非连续地址窗口 binding |
| `fcdaabe2b9265` | OSD2 overlay、OSD3 cursor、多层 RDMA、缩放与可变 zpos |
| `8c9617f8de1d4` | 非阻塞 atomic 提交使用所属 state，避免取错后续 framebuffer/event |
| `3be2db350fcec` | 执行 RDMA builder 后验证所有写寄存器的 DT 所有权 |
| `a0c066757d336` | 三层 DIMM 常量颜色控制的独立资源 binding |
| `422479e19b152` | 每次 RDMA 清除遗留 DIMM，防止常量颜色遮住 framebuffer |
| `6dc88fb14bdf0` | 短表保持每 vsync 翻页，长表 drain 后才发可复用旧缓冲的 event |

各功能步骤完整 Image/DTB/modules 构建与离线回归：

已通过的中间 build ID 前缀：多层 `059be29d71f0`、SRAM `a0d12de8647b`、
三层 OSD `c13a0d1f60cc`、提交 state `5f1f337cd949`、DIMM `77ed706f8a4b`。

中间产物不用于上板。最终 `6dc88fb14bdf0` 已推送；Image/DTB/2334 模块、回归与
schema 通过，新增 10 个及全分支 17 个提交 strict checkpatch 均 0/0/0。
build ID `bb62412f54b1e1d1e7d669e8d12ff74cfc14944c`；Image SHA256
`3fb273a89ac144a85613609c4279cb4260fe11aa21d8fcbb7770c63670788b4b`；DTB SHA256
`8b535ea3b9ed3296a5076d0aa75f538fcbd896780e60e2274d7bf653761faf7e`。
开发机日志 `logs/display/m3/build-safe-events.log`，不是板上日志。
同步 main `30a70bf`、保留双方索引后，主仓全量 232 项通过（10 项跳过）。

先移出 docs worktree，检查无进程使用、无嵌套 worktree，再删除本任务旧输出：
Mac M0/M1 和 M2 bundle 共 1.88 GiB；VM 旧 M0/M1/M2 输出及候选 payload
共 3.04 GiB（按 du）。保留当前 M3、历史日志及 M2 抓帧/录音源码；旧窗口脚本含固定
路径/ID，需按新候选重新生成。不删其他任务目录或板盘。
最终代码快进后移除干净的临时源码 worktree，另回收约 1.74 GiB。

可复验入口位于内核源码 `drivers/gpu/drm/meson/test_t7_{scanout,sram,layers,handoff}.py`；
SRAM/layers 测试传 `--vendor ~/src/linux/common_drivers`，layers 另传 `--dtb ...display-m3.dtb`。
厂商基准为 `common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49` 的工作树内容，
以实际 `git rev-parse HEAD` 核对；不依赖网络硬件描述。

## 引用退休与提交时序

每个 atomic 事务有三个 OSD、两个未来视频槽，各层持 framebuffer 引用。
当前只启用三个 OSD。M3 的 active、pending、retiring 分开保存；同一缓冲在多个层
出现时按槽分别持引用，不以地址相等省略引用。表内全部取数引擎共用一次 RDMA 提交。
标准 `drm_gem_plane_helper_prepare_fb()` 获取 producer fence，atomic helper 在提交
硬件前等待。仅持 DRM 引用不代表 V4L2 生产者可立即重用缓冲，未来直通用户态仍须
等待显示退休才重新 QBUF，不能用 page-flip event 直接代替所有生产者的 release fence。

长 RDMA 表可能跨过取数起点。单独多持一代引用只能防止释放，不能阻止合成器在
page-flip event 后重写旧缓冲，故最终修复同时约束事件：完整几何/格式/混合更新
锁存后把旧 active 转入 retiring，再跨一个 vsync、释放旧引用，才发送 event。
普通翻页先比较已成功提交的全部布局/混合状态；一致时只写最多三个地址，比 M2
五对描述符还短，沿用 RDMA 完成 + vsync 边界，维持每 vsync 一个安全完成事件。
RMFB、缩放、alpha/zpos 等变化走完整表及额外 drain，不能冒充单纯地址翻页。
disable 先 blank/drain 再停 ENC2。任一锁存或 drain 超时永久 pin 住相关引用，
error fence 且不发送成功 event，迟到 IRQ 不释放；故障需重启恢复。
未改变 M1/M2 的原退休策略，也未将此规则冒充 AFBC decoder idle 证明。

审查同时发现排队提交问题：后一个非阻塞 atomic 提交可先替换全局 `plane.state` /
`crtc.state`，前一个 worker 若读全局状态，会扫描尚未等待其 fence 的后续缓冲，或
发送错误的 event。flush/enable/disable、mode 和所有层均改为读取本事务的
`drm_atomic_get_new_*_state()`。离线用确定性排队场景把全局 state 替换为另一 fb、
inactive CRTC 和另一 event，确认仍扫描当前事务且发送当前 event。

离线 C harness 执行实际驱动函数，覆盖 60 安全 event / 60 vsync、事件时旧扫描引用
已释放、完整更新两 vsync 后才完成、两种 IRQ 顺序、计数回绕、
单层 RMFB、全层 blank/drain、模式切换、超时 pinning、失败 fence 与排队 state。
这些模拟不构成硬件 60Hz 或 DMA 空闲的实测证据。

## SRAM 接管

厂商 `sec_power_domain.c:t7_pm_domains[]` 有 52 个顶层域；
`vpu_mempd_psci_smc()` 使用 `0x82000093`，编号为 52 加 VPU 模块枚举。
T7 选择安全固件路径，不能直接套 SC2/T5 的 mem_pd 位表。

新 genpd 子域以 `VPU_HDMI` 为父域，增加 OSD1/2/3、scaler、blend34、RDMA 等 SRAM
编号。实际 M3 只持七个已使用域：52、53、97、59、94、101、109；不获取 VDIN、
VD1/VD2 或 AFBC 域。11 个编号由编译执行厂商代码得到并对照，不手算枚举偏移。
SRAM 状态不能用顶层 `PWRC_GET` 查询；注册时建模为尚未领取，首次消费者显式 SET ON。
SET 同时检查 SMC 分发错误与固件 payload，未知/失败不继续启用层。

接管顺序为：确认 OSD2/3 没有外来活动层 → 注册 IRQ → 等固件输出两个 vsync →
关闭三个 OSD fetch、posted read → 再跨两个 vsync → 获取七个 SRAM 引用。
先停稳才能允许后续失败回滚释放域，避免 probe 失败把仍取数的 U-Boot OSD SRAM 关掉。
成功后引用保持到重启；不做系统挂起/休眠测试。`test_t7_sram.py` 覆盖七处获取位置的
NULL/ERR/PM/action 失败与成功，共 35 种获取/回滚场景及计数回绕和无 vsync。
现有电源转换测试保留并扩展；新增 provider 行为未来上线仍须九类完整回归。

## OSD overlay、cursor、缩放与资源

M3 DT 单独启用 managed SRAM profile，注册 OSD1 primary、OSD2 overlay、OSD3 cursor。
三个层接受线性 RGB888、XRGB/XBGR8888、ARGB/ABGR8888，支持全局 alpha、coverage、
None、X/Y reflection 和 zpos 0–2，DRM normalize_zpos 处理相同 zpos。
不公开 90/270 度旋转或 premultiplied blend。cursor 使用真实 OSD3 路径，
不提供绕开 atomic/vsync 退休的 async cursor 更新。

每层 0.25–4 倍缩放，整数 source、裁剪后的 source/destination、上限 3840×2160；
DMA pitch 32 字节对齐、地址 16 字节对齐、全缓冲边界位于 32bit DMA 地址空间。
厂商 `meson_osd_scaler.c` 的双行阈值 1920、bank length、phase、bicubic / bilinear2 /
triangle4 系数完整加入 RDMA 表；无缩放时旁路。三个 OSD 各九种几何，共 27 种，
编译执行厂商函数，逐个比较 14 个 scaler 寄存器及全部 66 个系数。

T7 OSD2 的地址/stride 在 `0x1a65/0x1a66`，unpack 在 `0x1abd`，不与控制窗口连续；
OSD3 使用 `0x3d80`，scaler 使用 `0x5a00/0x5a40/0x5a80`。本批单独 claim 这些窄窗口。
三层格式、scope、alpha、地址、scaler 和 mixer 顺序一张有界 RDMA 表锁存。
OSD3 路由 VPP0，保留同字其他字段，不写 `VPU_WRARB_MODE_L2C1/2`。
DIMM 控制分别为 `0x1adf/0x1acf/0x3da0`，按厂商初始化清零，避免固件遗留的常量
颜色遮住像素取数；三个控制字各自 claim，覆盖非零遗留状态的回归。
实际 builder 发出的 91 个寄存器全部落在编译 DT 的 MMIO claims，claims 与 VDIN
regions 无交集；不申领全 VCBUS，不用 canvas，不接管采集仲裁或全 VPU reset。
尚无多层混合、透明、裁剪、缩放、光标或 SRAM 固件调用的上板证据。

## 剩余依赖与明确缺口

| 项目 | 状态与必须补齐的证据 |
|---|---|
| VD1/VD2 video plane | 未实现。厂商 `video_reg.c:vd_mif_reg_t7_array` 采用 SC2 MIF，须一起移植 progressive linear fetch、chroma formatter、视频 CSC/postblend 与 scaler；仅写地址不足以上屏。需新增窄 MMIO/域所有权与所有层一致的退休边界 |
| NV12 零拷贝 | 未实现。本分支 VDIN 的实际 UV offset 为 `stride * height`，尾部 allocation 才用 `stride * ALIGN(height,16) * 3/2`；不能把分配高度当 plane offset。Wave5/vdec 需分别按实际写地址及 negotiated V4L2 pitch/offset/size 核对；两平面可同一或不同 GEM，分别验证边界、fence、退休，禁止 CPU copy 冒充 scanout |
| P010 | 无 T7 标准布局依据。厂商 DRM 支持列表无 P010，`video_hw.c` 只有 packed 10bit bit_mode；明确 P010 高 10bit unpack 的 `bit16_mode` 在 `video_hw_s5.c`，不能搬到 T7。当前拒绝，不声称硬件绝对不支持 |
| ARM AFBC | 未实现。T7 OSD1/2 属 core1，OSD3 属 core2；需 decoder SRAM、surface/status 资源、header/body/modifier 边界和错误/完成处理。厂商会 poll raw status；尚未建立各 core 禁用后的 decoder idle 与 DMA 安全退休证明。普通 RDMA 完成不能作为 AFBC 完成；不公开 modifier |
| HDR/10bit/420/Colorspace | 未实现。当前仍为 M2 的 8bit YUV444 BT.709 limited，物理颜色尚待用户。需把 OSD/VPP CSC、BT.2020、DRM/AVI metadata、formatter、深色 PLL/PHY/ACR 联动，拆开 pixel/TMDS rate 才能正确处理 420 4K60；不单独加空属性宣称支持 |

布局核对入口：VDIN `t7_vdin_ring_arm()` 与 `VDIN_WR_CHROMA` 写入；Wave5
`wave5_prepare_fb()` 的 linear 分支使用 negotiated width 作为 stride，单平面 UV 在
`stride * dst_fmt.height`，NV12M 则直接取第二 VB2 plane；staging vdec 的 NV12M
`bytesperline=ALIGN(width,32)`，两个 plane 独立分配。Wave5 的内部压缩参考帧
另用 32 对齐 stride/height，不能当作导出的 linear 图像。以上仍需在候选 rebase 后
重核最新 producer 源码；没有把布局检查本身算作 NV12 已上屏。

## 下一次上板清单

先完成 [M2 物理收尾](2026-10-23-display-m3.md#用户在场时的-m2-收尾)：RGB 数值、
997Hz 物理录音、HPD 拔插；1440p/4K60 需相应显示器，用户在场时才做插拔。
M3 先 rebase 当时正式分支、重建并全量离线回归，持双锁一次性启动，保持默认基线。
分层验证 SRAM 接管/失败、OSD2+OSD3+primary 混合、三层独立翻页/缩放/zpos、边缘
裁剪、ARGB alpha、反射、RMFB/disable、GPU PRIME、三层连续 60Hz 与 HDMI-IN 编码/音频。
错误 IRQ 或超时按 pinning 停止验收，不反复操作故障 DMA；重启回默认基线并做冒烟。
CEC 沿首批清单；VD/NV12/AFBC/HDR 需各自完成离线依赖后另排窗口。
