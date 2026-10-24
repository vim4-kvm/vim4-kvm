# 2026-10-23：M3 视频 MIF、PPS 相位与 VD2 SRAM（离线）

接续 [DMA 边界与剩余合同](2026-10-23-display-m3-dma-contracts.md)。本批新增线性
NV12/NV21 的 MIF 参数生成、逐行 PPS 相位计算，以及 VD2 的两个 SRAM 域。
**这些是尚未接入 KMS 的视频路径组件，VD1/VD2 plane、NV12 零拷贝 scanout 仍未完成。**
当前 M3 对用户态继续只公开线性 RGB OSD；没有访问板子、修改部署版本锁或正式分支。

## 分步实现

| 提交 | 内容 | 明确边界 |
|---|---|---|
| `01155d35f304c` | `meson_t7_video_mif_prepare()` | 仅计算，fetch enable 保持 0，不访问 MMIO |
| `da63d538d34b5` | `meson_t7_video_phase_prepare()` | 1:4 到 4:1 的逐行缩放相位，不包含完整 scaler 寄存器事务 |
| `7da5902235425` | VD2 scaler/FIFO 的 DT binding IDs | 厂商转换得到 86/103，不复用 OSD scaler ID |
| `d05732abbed56` | 在 secure genpd 注册上述 SRAM | 尚无 DT 消费者；未领取的域不改变固件启动状态 |
| `89bcdf07ff624` | 明确 GEN2/GEN3/STRIDE_1 写掩码 | 厂商 block-mode 函数比较 32 组寄存器初值，保留无关位 |

### 线性 MIF

输入描述区分可见 framebuffer 尺寸、整数 crop、每个 plane 的 pitch、DMA 地址和可用
容量；地址已包含 DRM offset。对两平面分别验证完整行容量、32-byte pitch、16-byte
地址、DMA32 全范围。限制偶数尺寸/色度 crop、最大 3840×2160，拒绝其他格式。
单对象与双对象没有不同寄存器路径，只使用调用方交来的 Y/UV 地址，不反推 UV 偏移。
失败时输出结构保持原值，避免出现可被误用的半套取帧参数。

生成 SC2 VD1/VD2 的地址、stride、luma/chroma scope、formatter、GEN 参数，
不使用 canvas。厂商路径有两个容易被“统一”掉的差异：

- `vd1_set_dcu()` 写 `GEN_REG[29]` reset-on-field；`vdx_set_dcu()` 不写该位。
  新代码保留两路差异，没有把 VD1 的整个控制字复制给 VD2。
- `set_vd_mif_linear()` 的 STRIDE_1 调用只写低 16 位，表达式里的 bit16 无效。
  参数只描述这 16 位；未来应用时仍须保留上半字的无关字段。

GEN2/GEN3 同样附带写掩码；mask 之外的位不属于本 profile。厂商 block-mode 函数
另在 stereo 情况更新 `STRIDE_1_F1`，不改变逐行 `STRIDE_1` 的高位；测试以 32 组
初值编译执行该原函数，检查参数合成后与实际 masked writes 一致。

GEN 保留 urgent、8 hold lines、chroma repeat、linear/separate-plane 等参数，
同时明确清除 fetch enable。GEN_REG2 对 NV12 为 2、NV21 为 1。
formatter 为逐行 4:2:0 的水平 2:1、垂直 step=8、initial phase=12 和 line0 repeat；
GEN_REG3 使用 8-bit、linear 和随 luma pitch 选择的 burst。

`test_t7_video.py --vendor /home/deepdream/src/linux/common_drivers` 编译执行当前
C 实现，以及厂商真实 `set_vd_mif_linear()`、`viu_line_stride()`、
`vd_mif_setting()` 的线性 scope 块、两路 DCU 的控制/formatter 块。64 例组合覆盖
720×400、720p、1080p、4K、两路 MIF、NV12/NV21、两档对齐 pitch；额外检查
UV 少一字节、DMA32 越界、奇数 crop、越界 crop、错误格式、短 stride 和失败不改输出。
测试使用 UBSan，不模拟实际 DMA、producer fence 完成或视频退休。

### PPS 相位

保留厂商 `(input << 18) / output` 后再左移 6 的截断顺序。逐行缩小时的垂直初相
来自 `f2v_get_vertical_phase()` 的 P2P 分支：超过 1:1 时输出偏移为四分之一行，
接收/重复控制与 `skip_tab` 对应；精确 4:1 会跨过 skip 边界。

`test_t7_video_phase.py` 编译原厂完整 `f2v_get_vertical_phase()`、位置数组和
`skip_tab`，逐个比较 1:1 两侧、2:1、4:1、1:4 及 4K/1080p/720p 的初相和接收/重复。
范围、零尺寸与 NULL 输出均有拒绝检查。**这不证明滤波系数、PPS 时钟/路由、
scaler 寄存器配置、画质或带宽已经实现。**

### VD2 SRAM

厂商仍固定 `common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49`。
`test_t7_sram.py` 执行厂商 `vpu_mempd_psci_smc()`，对照 top-level domain 数量
52 加 `VPU_VD2_SCALE` / `VPU_VD2_OFIFO`，结果分别为 86 / 103。连同现有项共
13 个 display SRAM ID 均通过对照；既有 35 组 OSD 领取/失败回滚、计数回绕和
无 vsync 拒绝测试通过，secure provider 的 12 组失败/未领取状态测试也通过。
没有将新域加入 M3 显示 DT，因此本批没有视频 SRAM 接管或上电证据。

## 尚未完成的接线与依据

1. **VD1/VD2：** 尚需完整 PPS/系数、时钟、SDR HDR-core 旁路、输入尺寸、
   VPP postblend 端口和 zpos 分组、窄 MMIO claims、视频 SRAM 接管及 atomic plane
   接入。厂商 `postblend_check_state()` 拒绝视频插在 OSD 组中间；不能只按五平面
   normalized_zpos 任意排列。参数组件不能作为可上板的视频候选。
2. **退休：** 厂商 `pipx_toggle_frame()` / `check_dispbuf()` 将正在 RDMA 使用的
   vframe 放入延迟队列，`pipx_late_proc()` 更新 `cur_rdma_buf`；这些是固件驱动的
   vframe 生命周期，尚未完成向当前 atomic 提交、disable、错误 fence 和五层退休的
   移植测试。不能只增加 framebuffer 引用、随后提前发 flip event。
3. **NV12：** 尚未把已验证的 VDIN/Wave5/vdec 布局真正接到 video plane；上一条记录
   的生产者布局证据保持有效。用户态仍需等待显示退休再 QBUF，producer 完成不能
   代表显示已结束。尚无直通或播放的物理/零拷贝证据。
4. **P010：** T7 的 `video_hw.c` 无 `bit16_mode/P010_MODE` 路径；明确的支持在
   `video_hw_s5.c`，不能将 S5 的 GEN_REG3[7] 或 16-bit stride 算法直接移给 T7。
   当前拒绝，不据此断言 T7 硬件绝对不支持；需要 T7 寄存器合同或具体实现依据。
5. **ARM AFBC：** 现有厂商 disable 仅停 surface，未找到 DMA idle 等待；错误检测
   不等于排空。configuration-swapped / surfaces-completed 的代际确认、陈旧 IRQ、
   两 core 的多 surface 原子交换、失败 pinning 与 disable 仍需明确并测试。未实现 modifier。
6. **HDR/10bit/420/Colorspace：** 未实现，仍是 M2 的 8-bit YUV444 BT.709 limited。
   需要一并实现 CSC、formatter、TMDS/pixel 分离、PHY/ACR 和 AVI/DRM infoframe；
   没有添加无法兑现的属性或扩张 mode_valid。

本轮交付为上述五个离线基础提交，不是 M3 功能完成；未把其余移植工作归为“已支持”。

## 构建、推送与清理

在独立源码 worktree 与 `~/build/kernel-display-m3` 中，持 Mac
`/tmp/vim4-heavy.lock` 顺序验证五个提交。每个提交均完整构建 Image、DTB、
2334 个模块，并运行显示、CEC、RX、Wave5 的离线测试和定向 DT schema；五轮均通过，
无编译告警。上述 MIF/PPS、SRAM 以及既有 OSD fence/退休测试均在这些轮次内运行。
五个新增提交分别 strict checkpatch 0 errors / 0 warnings / 0 checks；
最终全分支 25 个提交也均为 0/0/0。日志内累计 115 次是 21+22+23+24+25 的重复检查，
不是 115 个不同提交。

| 提交 | 完整构建 build ID 前缀 |
|---|---|
| `01155d35f304c` | `ab472741895b` |
| `da63d538d34b5` | `5aa9f42afcd1` |
| `7da5902235425` | `a2bbef58dbe7` |
| `d05732abbed56` | `f19b577535a4` |
| `89bcdf07ff624` | `9bcd69c0fe1c` |

最终 build ID `9bcd69c0fe1cdab4059bcedb868f3e2fd8a965b8`；
Image SHA256 `172f4bfac52149fd1ae3bae5da40555a00c911c557d7a30a4c8ce55a3f0a718d`；
M3 DTB SHA256 `8b535ea3b9ed3296a5076d0aa75f538fcbd896780e60e2274d7bf653761faf7e`；
配置 SHA256 `8af98a1fbefdf163c407f9f04bb31372178b8f8d7d6f00f5dff162b930c968bf`。
开发机证据位于 `logs/display/m3/build-video-mif.log` 和
`logs/display/m3/video-parameters-artifacts.json`，不构成板上证据。

`vim4-display-m3` 已正常快进推到 fork `89bcdf07ff624`，远端跟踪哈希一致；
没有合入或推送正式内核分支。主仓 `pull --rebase` 同步 main 后，
全量离线测试 233 项、10 项跳过，整体通过；最后同步并发提交 `537c379` 后，
再次完整运行 234 项、10 项跳过，整体通过。

验证后删除本任务 VM 构建输出和临时 `linux-7.3-display-m3-next` worktree；
删除前 `du -sk` 分别为 7900848 KiB 和 1828804 KiB，不能据此推断共享磁盘净增量。
Mac `build/display-m3` 也清理，配置和重建脚本迁至
`logs/display/m3/rebuild/`，下一次上板须重新构建匹配的 Image/DTB/全模块。
保留 `linux-7.3-display-m3` 源码 worktree 与证据日志；没有清理其他任务的输出，
也没有改动待用户在场时使用的 M2 工具。

## 后续上板

本轮不上板。先完成 [M2 用户在场收尾](2026-10-23-display-m3.md#用户在场时的-m2-收尾)：
RGB 数值、997Hz 物理录音、HPD 插拔以及支持 1440p/4K60 的显示器。
等视频路径真正接通并完成离线生命周期测试后，再 rebase 到当时正式 HEAD，
双锁一次性启动，验证 NV12 的单/双对象、两路视频与 RGB OSD 混合、缩放/zpos、
producer fence、RMFB/disable、独立翻页及 RX 编码/音频共存。电源管理变更执行九类
门禁；结束重启回当时正式基线并冒烟。本记录中的基础参数提交不扩张上板验收范围。
