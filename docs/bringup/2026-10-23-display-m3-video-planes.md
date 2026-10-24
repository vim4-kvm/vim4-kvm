# 2026-10-23：M3 VD1/VD2、PPS 与 NV12 atomic scanout（离线）

接续 [视频参数组件](2026-10-23-display-m3-video-parameters.md)。本批将 VD1/VD2
接入独立的实验 DT：完整逐行 PPS、VPP 混合、五层缓冲退休和线性 NV12/NV21
dma-buf scanout 已有内核实现。**仅完成离线验证，尚无视频层上板证据。**
HDR_OUTPUT_METADATA、10-bit HDMI、YUV420 输出和 connector Colorspace 尚未完成；
P010 与 ARM AFBC 继续拒绝，具体依据与缺口见下文。本轮没有访问板子，没有改变
正式内核分支、应用、部署锁或 U-Boot。

## 提交与候选边界

| 提交 | 内容 |
|---|---|
| `c7b031347140a` | 两路逐行 PPS 完整 RDMA 事务及厂商参数测试 |
| `4627ae356566f` | 可选 video profile 的窄 MMIO、SRAM 和启动合同 binding |
| `2dff95d9be8c9` | VD1/VD2 atomic planes、NV12/NV21、混合及两阶段安全退休 |
| `e257249ee0997` | 按 VPU 实际时钟限制 PPS 吞吐，拒绝尚未实现的 vskip 组合 |

内核分支仍为 `vim4-display-m3`。新增
`amlogic-t7-a311d2-khadas-vim4-display-m3-video.dtb`，原 M3 OSD-only DT 保留。
新候选通过 `amlogic,video-planes` 显式启用视频路径，不改变默认部署选择。

| 能力 | 本候选范围 |
|---|---|
| VD1/VD2 | 两个标准 DRM overlay plane，linear NV12/NV21，逐行 |
| 缩放 | 双轴 1:4 到 4:1，最大输入/输出 3840×2160，整数且偶数色度 crop |
| PPS | 每轴 33 相 bicubic、4 taps、8-bit 系数；不启用 pre-H/pre-V 或 SR |
| 带宽限制 | 原生 4K60 / 4K30 缩小可检查通过；4K 输入缩到小于 2048 行且输出超过 30Hz 时拒绝 |
| 混合 | 与三路 RGB OSD 共用 normalized zpos 0..4；视频不可插在 OSD 组内部 |
| 层序限制 | 最多一层视频置于整个 OSD 组之上；两层均在组下可交换顺序 |
| 输入色彩 | video plane 仅公开 BT.709 / limited；alpha 固定不透明，无旋转属性 |
| 同步 | GEM `prepare_fb`、implicit reservation fences / IN_FENCE_FD、vsync RDMA |
| NV12 更新 | 同布局仅改 Y/UV 地址；几何/格式/层序改变才断开并重新配置 |
| 性能边界 | 视频路径保留额外扫描周期，1080p60 下地址更新理论上限约 30 次/秒，未实测 |

没有把此处的视频路径等同于已有应用直通。用户态仍需将 producer 导出的 fd、
各 plane pitch/offset 交给 PRIME/ADDFB2，再做 atomic commit；不得在显示释放旧帧前
把该帧 QBUF 回采集/解码器。VDIN 的 DQBUF 或对应显式 producer fence 表示生产完成，
不能替代显示退休。若 producer 没有向 dma_resv 发布 fence，使用方必须等待生产完成，
不能期待 KMS 推断 V4L2 队列状态。

## 硬件来源与所有权

厂商源码固定 `common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49`。
对照位置为 `video_reg.c` 的 `pps_reg_t7_array` / T7 MIF/AFBC 表，
`video_hw.c` 的两路 DCU/scaler、`vd_blend_setting()`、`vpp_blend_update_t7()`，
以及 `meson_vpu_postblend.c:postblend_check_state()`。

VD1 使用 SC2 MIF 0x4800，VD2 为 0x4880；PPS 为 VD1 0x1d03 等旧 bank 和 VD2
0x3933 等 T7 bank，保留 VD1 0x1d0f 的空洞。完整事务清掉旧 nonlinear slopes、
repeat/pattern/select，更新 phase、33 相系数、输入尺寸、pre/post scopes 和
VDTOP linear 选择。仅旁路这两路的 HDR input core 和 matrix；T7 DSC ECO 置
bit4、清 bit5，绕过视频输入 Dolby，保留无关字段，不重置其他 pipeline。

VPP 的视频端口依次为 VD1/VD2/VD3/OSD2 source registers，第四端口可放一层
高于 OSD 组的视频；OSD1 固定来源保持由现有 OSD builder 管理。T7 的 VD2 alpha
使用 VPP_MISC[26:18]，没有套用其他芯片的 independent-alpha 位；同时保留
VPP_MISC[11:9] 等无关字段。任意五层交错的 zpos 不受支持，在 atomic check 拒绝。

新 DT 共 42 个 display resource、15 个 power domain。新增视频 SRAM 为
VD1=54、VD2=55、VD1_SCALE=100、VD2_SCALE=86、VD2_OFIFO=103，均按厂商 SMC
转换核对。已有 OSD 启动 fetch 先停、跨两个 vsync 排空，再领取 SRAM。SRAM 在
成功 probe 后持有至重启，包括发生 DMA 故障之后。

视频启动合同在首次 RDMA 写入之前检查：VD1/VD2/VD3 GEN fetch 和 AFBC enable
必须关闭，SR 必须关闭；固件已将 VD1/VD2 路由到 VPP0，VD_PATH_MISC_CTRL 低字节
须为 0x21、PATH_START_SEL 低字节须为 0。当前不强行重设这些共享路由。
不匹配返回 EBUSY；**这个新合同尚未在板上读回确认，可能导致候选拒绝 probe。**
不写 VDIN 的 0x27a2/0x27a3、canvas、全局 arbitration、RX 时钟或 reset。

`vpp.c:vpp_process_speed_check()` 对未压缩 4K 缩小且输出超过 30Hz 使用 vskip。
本 profile 保持完整帧，不实现跳行，因此在 atomic check 拒绝该组合。PPS 吞吐另按
厂商 0x110/256 系数与实际 VPU 时钟校验，upscale 保守计入扫描周期余量；只读时钟，
不调整 VPU 频率。双路 4K 与 VDIN 共存的实际内存带宽仍需硬件验证。

## 缓冲退休与错误路径

完整重配置分两次 RDMA，沿用厂商 ON_REQ → ON_PENDING 的顺序：

1. 先取得五层新 framebuffer 的引用，断开 VD fetch，提交 PPS/MIF/scopes 和空视频来源。
2. 等待本代 RDMA 完成和 vsync，再等一个完整扫描周期，才退休上一代引用。
3. 保持新帧引用，在后续 RDMA/vsync 开启 VD fetch 和视频 blend source；完成后才发 event。

布局、crop、dst、格式、pitch 和 normalized zpos 不变时，只写两路地址，不重复装载
系数或制造视频 blank；该路径也延后一个扫描周期退休。仅 OSD 的短地址更新继续使用
已有每 vblank 一次的路径。第一次配置、disable、RMFB、空 FB 都经过显式空层处理。

每个 latch/drain 等待均为 100ms。任一阶段超时会设置 faulted、返回错误 fence，
停止后续提交，并固定 active/pending/retiring 引用至重启；迟到 IRQ 不释放引用。
额外 vsync 是逐行 MIF 的保守退休边界，**没有据此推导 AFBC decoder idle 合同**。

## 离线验证

`test_t7_video_pps.py --vendor ...` 编译实际厂商 PPS register table、六个 region
写入表达式和 bicubic 系数，与实际 C builder 对照。覆盖两路、4K/1080p/720p、
unity/up/down scale、1:4/4:1 边界、容量不足和失败不修改输出。

`test_t7_video_kms.py --vendor ... --dtb ...display-m3-video.dtb` 编译实际 video C，
覆盖两个独立 GEM、完整 UV 行容量、DMA offset、错误格式、faulted check、两路缩放、
地址更新与重配分流、OSD 分组限制、RMFB 和空 FB。执行厂商原始 postblend port
构造块，比较两层在下、单层在上的 source words；DT 校验 42 个 resource 与实际
VDIN split claims 不相交，并检查 15 个 domain 和新增 SRAM ID。
补充 4K→1080p30 可接受、4K→1080p60 拒绝、原生 4K60 与 VPU 过慢的边界。

`test_t7_handoff.py` 受控投递两种 IRQ 次序，新增两路视频的两阶段 latch/drain、
新旧引用计数、detach 和第二阶段超时固定引用测试。已有 OSD 60/60 与 RMFB 回归保留。
`test_t7_sram.py` 扩充为 OSD/video 两种 profile 的 95 个领取/失败回滚案例，另核对
13 个厂商 SMC ID；既有 producer layout 测试继续执行实际 VDIN/Wave5 布局代码。
这些测试没有运行真实 DMA、ALSA、producer fence 信号或显示器。

四个提交分别持 Mac `/tmp/vim4-heavy.lock`，在独立源码与 O= 目录完整构建
Image、DTB、2334 个模块，运行显示/CEC/RX/Wave5 的离线测试和定向 DT schema，
均通过。视频模块首次编译因缺少 `linux/property.h` 中止，补齐后重新完整构建通过；
失败半成品未推送。最终 29 个 M3 提交 strict checkpatch 均为 0 errors / 0 warnings /
0 checks，没有 ignore 参数，最终构建无编译告警。

| 提交 | 完整构建 build ID |
|---|---|
| `c7b031347140a` | `ee40da0bb05533f2b690579f467244689589e96e` |
| `4627ae356566f` | `40e8a5266d25a1a27330c5b0beba36450a6456ba` |
| `2dff95d9be8c9` | `6e5bf9f4b35e8075c126a1cebc5ce16eb227e8d1` |
| `e257249ee0997` | `8827f7a1d709c6fc57cf25b26fae1bc91f301d87` |

最终 Image SHA256 `a129a64d62575c2e5bd769ae2556d68028cc7320afea390f61cbd1e8b6c77728`；
video DTB SHA256 `6170b1774404958a46e80a35c98c0b0ae0d3a03fe3ed9912ef089d98dd9cf7fc`；
配置 SHA256 `8af98a1fbefdf163c407f9f04bb31372178b8f8d7d6f00f5dff162b930c968bf`。
既有 OSD-only M3 DTB 哈希保持 `8b535ea3b9ed3296a5076d0aa75f538fcbd896780e60e2274d7bf653761faf7e`。
开发机证据为 `logs/display/m3/build-video-pps.log`、`build-video-kms.log`、
`build-video-kms-fixed.log`、`build-video-bandwidth.log` 和 `video-planes-artifacts.json`。

`vim4-display-m3` 已正常快进推至 fork `e257249ee09971e3a9884f8a165959843d0f3263`，
远端跟踪哈希一致；没有推正式内核分支。主仓 rebase 到并发更新 `967b0ec` 后，
全量离线测试 234 项、10 项跳过，通过；主仓只提交本记录和 README 索引。

完成后删除 VM `~/build/kernel-display-m3` 和临时
`~/src/linux-7.3-display-m3-next` worktree，Mac `build/display-m3` 已不存在。
保留分支源码、配置、重建脚本、日志与哈希清单；未删除 M2 用户在场收尾工具或其他
任务构建目录。下次上板须重新构建同次 Image、对应 DTB 和完整模块。

## HDR、P010 与 AFBC 剩余项

HDR/10-bit/420/connector Colorspace **尚未实现，不能宣称 M3 已全部完成**。
厂商 T7 有对应能力；缺的是当前驱动的完整联动移植，不是已经证明硬件不支持：

- `hdmi_tx_hw.c:config_hdmi21_tx()` 根据位深配置 P2T_CTRL、VP_INPUT_MASK 和 packetizer；
  现代码仍固定 8-bit。10-bit 还须覆盖线性 OSD 的 1010102 colormat 与 endian 特例。
- `hw_clk.c:hdmitx21_set_clk()` 的 T7 深色和 420 分支改变 VCO、VID PLL divider、
  ENC/pixel/TMDS 分频；不能把 pixel clock 直接拿去设置 PHY、SCDC 和 audio ACR。
- HDR metadata、BT.2020、OSD/VPP matrix 与 AVI/DRM infoframe 必须在同一 atomic
  state 决定，颜色空间变化须触发完整 modeset。还需校验 EDID 的 HDR/deep-color/420
  能力、清除旧 metadata、SDR 往返及不支持组合的拒绝。没有添加可设置却不生效的属性。
- P010：T7 `video_hw.c` 没有 `bit16_mode/P010_MODE`；明确的 bit7/unpack 实现在
  `video_hw_s5.c`，不能复制给 T7。需 T7 MIF 高 10-bit/低填充、endian、16-bit stride
  的寄存器依据和已知 producer layout 对照，当前只接受 NV12/NV21。
- ARM AFBC：厂商 disable 清 surface enable，raw error status 不代表排空；需要
  configuration-swapped/surfaces-completed 的代际、陈旧 IRQ、多 surface、两个 core、
  disable 和故障 pinning 合同。普通 MIF 的额外 vsync 不能用于证明 AFBC 安全退休。

## 后续一次性启动计划

本轮不上板。M2 物理颜色 RGB 数值、997Hz 出声、HPD 拔插和 1440p/4K60 显示器
仍按 [用户在场清单](2026-10-23-display-m3.md#用户在场时的-m2-收尾) 收尾。
新视频 SRAM profile 未通过硬件门禁，不能合入正式分支部署。

之后 rebase 到当时正式内核，重建 Image/DTB/完整模块；双锁一次性启动视频候选，
先确认上述 boot contract 与 15 个 domain 领取，再分别验单 VD、双 VD 和 OSD 混合，
NV12 单/双对象、VDIN/Wave5 实际 stride/offset、fence 延迟生产、缩放、zpos、地址更新、
RMFB/disable、模式切换和 timeout event。采集帧不能提早 QBUF；另核对 RX 4K60 编码、
音频连续性、HID/UDC、oops/taint。电源所有权变化按部署文档执行九类门禁。
结束重启回当时默认正式基线，确认隔离监控及 KVM 服务、画面/编码/HID 后清理并释放锁。
