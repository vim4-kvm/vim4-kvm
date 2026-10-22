# 2026-10-22：7.3 T7 标准硬件解码可行性调查

第二轮进展见 [Wave521C 实机取证](2026-10-22-vdec-wave5-capabilities.md)和
[T7 离线准备](2026-10-22-vdec-t7-offline.md)；以下保留第一轮调查范围。

阶段 1 调查已记录；阶段 2 的正确帧里程碑未实现，阶段 3 未开始。
推荐以 Amlogic 新 S4 stateless H.264 驱动为基础适配 T7，先限制 8-bit、逐行、1080p。
固定 Armbian 集合已经包含该驱动的旧版，但没有 T7 支持；不能只增加 compatible。
旧 staging meson-vdec 依赖 T7 已移除的 ESPARSER，不适合作为最快路线。
Wave521C 通用 IP 具备 AVC/HEVC 解码能力，**本板 T7 实例及当前编码固件的解码能力仍未证实**，
不能下结论说硬件不支持，也不能强制注册解码节点。

本轮停在实现前：T7 功能时钟缺失、S4/T7 总线隔离协议不同、现有微码包不能直接提供
旧 S4 loader 所需的原始微码；还没有可确认 DMA 停止的失败恢复路径。
这些缺口涉及可能挂总线的寄存器操作，用户不在板边，本轮没有试启解码硬件。
硬件逐项对照、格式上限和固件目录见 [调查明细](2026-10-22-vdec-hardware-audit.md)。

## 源码、分支与证据

| 对象 | 本轮实际版本 / 位置 |
|---|---|
| 7.3 基线 | `e0346697f25035c7eaa77fa44641a54d6e31e327`，VM `~/src/linux-7.3` |
| 独立 worktree | VM `~/src/linux-7.3-vdec`，分支 `vim4-vdec`，HEAD 仍为上述基线，干净 |
| 厂商内核 | VM `~/src/linux`，`80a07ad5406d57855c996285ae75a50a1b9147ae` |
| 厂商 common_drivers | VM `~/src/linux/common_drivers`，`4cfb128d36f8511b2db1bd13c08d5704347ded49` |
| 固定 Armbian | VM `~/src/armbian-build-7.3`，`ecc676bf89af37788f972db9a7ff3f92844a43eb` |
| 本机证据 | `logs/kernel-edge/vdec-audit/`，不入 Git；含源码快照、固件元数据、社区原文、板端只读输出 |

执行过：

```sh
orb -m vim4-build git -C /home/deepdream/src/linux-7.3 worktree add \
  -b vim4-vdec /home/deepdream/src/linux-7.3-vdec \
  e0346697f25035c7eaa77fa44641a54d6e31e327
```

实际输出 `HEAD is now at e0346697f2503`。没有修改、切换其他内核工作树；
没有驱动代码改动、新内核提交、构建或候选产物，未创建 O= 构建目录。
将来实现须使用独立 `O=/home/deepdream/build/kernel-vim4-vdec`。
主仓仅新增本轮两份记录和索引，不提交、不推送，也不改部署锁。

## 三条路线的结论

| 路线 | 已有条件 | 必须补齐 | 判断 |
|---|---|---|---|
| Wave5 stateful | T7 Wave521C 已探测；主线有解码器；电源、IRQ、DMA 和编码固件已有适配 | T7 实例/固件解码能力的可信报告、固件解码命令协议、与当前编码的兼容性 | 条件成立时可能最快；当前不能安全直接启用 |
| 新 S4 stateless H.264 | Request API、直接 vb2 输入、NV12/NV21、I/P/B；T7 厂商有 frame-based H.264 实现可对照 | T7 CCF 时钟、DBUS 隔离、固件安全加载、T7 平台数据、错误与关闭生命周期 | 推荐的独立解码路线；先 1080p |
| staging meson-vdec stateful | GXBB–SM1 的 MPEG1/2、H.264、VP9，部分 DOS/canvas 代码可参考 | 移除 ESPARSER 依赖、输入/固件协议、电源/复位重做；没有 HEVC codec 实现 | 工程量更大，不建议为 T7 继续扩展旧架构 |

Wave5 与 DOS VDEC 是两个 MMIO/电源域独立的模块，并非把 Wave 编码器换成解码器即可。
AVC/HEVC 的标准接口选择取决于可用硬件和固件协议；不需要实现 amstream/amvideo。
若最终选择 stateless，应使用 GStreamer `v4l2codecs` 的 `v4l2slh264dec`；
ffmpeg 的 `h264_v4l2m2m` 是 stateful 路径，不能用它判定 Request API 驱动失败。
ffmpeg 验证须使用确实支持该 stateless API 的版本/构建，否则只承担软件参考解码。

## Wave521C：哪些证据成立

[Chips&Media 官方 WAVE5 产品页](https://chipsnmedia.com/products/video-2) 将 WAVE521C 列为
支持 AVC/HEVC 的 codec，WAVE521 则列为 encoder；产品名和产品码是调查线索。
它们不能证明 T7 的综合选项和随附固件完整实现解码。

本轮板端 dmesg 只读输出：

```text
T7 product 0x521c, previous PC 0x0
Added wave5 driver with caps: 'ENCODE'
Product Code:      0x521c
Firmware Revision: 214414
```

`ENCODE` 来自 `wave5-vpu.c` 的 T7 match flags，不是硬件能力测试；TI match 才设置 ENC|DEC。
`wave5-hw.c:setup_wave5_properties()` 在 GET_VPU_INFO 后解读 STD_DEF1 的 bit 3/2
作为 AVC/HEVC decoder，bit 1/0 作为 encoder。但 T7 老固件的编码能力已经需要
`encoder_mask` 覆盖，因此不能无条件用新版位定义解释旧固件。

本机已有厂商库 `build/jpeg-libs/multiEnc/vpuapi/enc_driver.c:SetupVp5Properties()`
读取 DEF0/DEF1/FEATURE 后，另按产品系列硬编码 `supportDecoders`；PRODUCT_ID_521
包含 AVC/HEVC。`VpVpuGetProductId()` 又把 VP521 和 VP521C 合并到 PRODUCT_ID_521。
**此库的 supportDecoders 不是本板能力位读数，也不是解码命令成功证据。**
厂商内核 `frame_sink/encoder/multi/vpu_multi.c` 提供编码基础设施，未给出标准解码验证。
没有替换或重新分发受限库/固件。

本轮未读取能力返回寄存器：0x124/0x128/0x12c 是 GET_VPU_INFO 的返回窗口，
与其他命令返回值复用；直接 devmem 不能保证其含义。发送 GET_VPU_INFO 会写入命令，
还需要驱动内部 hw_lock 与当前编码实例串行化，不能当作“只读查询”旁路执行。
当前驱动没有公开缓存的 attr/原始 DEF 报告，板上也没有 `/proc/kcore`。

继续 Wave 路线的最小证据应是在现有 probe 的 GET_VPU_INFO 完成处保存原始
DEF0/DEF1/FEATURE、product/version/revision 和解读后的 attr；通过临时匹配整包启动
读取一次报告，恢复基线。若厂家能确认当前固件含解码，再审查解码命令差异；
仅有掩码或产品名仍不足以启动未知固件命令。不要拿 TI 固件替换 T7 固件碰运气。

## Armbian 与社区现状

固定集合的 `0051` binding、`0052` 驱动、`0053` S4 DTS、`0056` 构建修正及
`0145` module table 已进入本地 7.3 树。`0052` 补丁日期 2026-02-13，约 4849 行新增，
目标为 S4/S805X2、8-bit 逐行 H.264；文件名带 s4t7 不等于支持 T7。
路径是 `drivers/media/platform/amlogic/vdec/`，与 staging meson-vdec 分开。
该驱动 TODO 明确包括 T7/S7、HEVC/VP9/AV1/MPEG2、10-bit 和隔行。
当前配置 `CONFIG_VIDEO_AMLOGIC_VDEC=m` 已启用，T7 没有接入其 DT 节点。

本轮联网找到作者 2026-10-12 的
[v11 cover letter](https://lists.openwall.net/linux-kernel/2026/10/12/435) 和
[v11 驱动原文](https://lists.openwall.net/linux-kernel/2026/10/12/439)，已另存 HTML。
它仍只匹配 S4，TODO 仍列 T7；作者报告 S805X2 上 1920×1088、GStreamer 和
v4l2-compliance 验证，不能算作本板证据。相较固定 Armbian 旧版，系列增加 signed
firmware 的 TEE/SMC 加载，并修复码流验证、DPB、资源及并发错误路径；v11 特别修正
clock/power 失败后仍访问寄存器和实例重新初始化问题。故不应原样启用旧 Armbian 驱动。
较新系列的 reset 仍操作 DMC bit 21，不能直接套到 T7。
本轮检索未找到已完成 T7 标准解码和正确帧验收的补丁；这不是不存在其他工作的证明。

## 推荐顺序、投入与第一里程碑

先完成 Wave 的能力/固件证据判断；若不能证明现有固件可解码，按新 S4 stateless
路线推进。基线中的旧 S4 代码应先审查并更新错误处理；完整引入 v11 涉及
TEE/SMC 依赖，不应只拷贝 h264.c 或用假 S4 compatible 绕过平台核对。

第一里程碑明确为：T7 专用、默认关闭的测试节点；8-bit progressive H.264、单实例；
先 640×480 I/P，再 1920×1080 含 B 帧，NV12 输出逐帧比对软件解码。
完成 v4l2-compliance、EOS、STREAMOFF/close、超时注入和 DMA 停止证明后，
才把节点视为可用；4K 是后续验证项，不能从硬件规格推导通过。

估算为熟悉媒体驱动的一人净工作日，非交付承诺：

| 工作 | 估计 / 前提 |
|---|---|
| Wave 能力报告与固件协议确认 | 1–3 日；依赖可解释的报告或厂家固件资料，等待时间另计 |
| T7 VDEC 时钟、genpd、DBUS 复位及错误退出 | 2–4 日；先离线 review/构建，补有界状态检查 |
| T7 signed firmware 加载与 H.264 协议核验 | 3–7 日；依赖匹配固件和现有安全世界接口 |
| Request/DPB/输出正确性、1080p 首帧及回归 | 5–10 日；首次有风险的硬件验证须具备 RESET 条件 |
| 稳定性、4K、多实例和共享资源回归 | 另 5–10 日起；HEVC 属于新增 codec，不是小开关 |

据此，推荐路线到经验证的 1080p 单格式里程碑约 2–4 周；缺少可用固件时无法排期。
若 Wave 条件全部成立，可少做 DOS 移植，仍须单独验证固件 ABI、关闭和编码兼容性。

## 板端操作、基线与未验收项

本轮仅 SSH 读 uname、dmesg、sysfs/debugfs、运行二进制及固件文件；未打开视频队列、
加载/卸载模块、发固件命令、读写裸 MMIO、停服务、安装或重启。没有性能采样、重型构建，
无需占用 board/heavy 锁；没有修改板子，因此没有候选回退操作。
只读命令包括：

```sh
ssh vim4 'uname -r; systemctl is-active one-kvm vim4-manager; cat /sys/class/udc/*/state'
ssh vim4 'sudo dmesg | grep -A3 -B1 "Added wave5"'
ssh vim4 'sudo cat /sys/kernel/debug/clk/clk_summary'
ssh vim4 'sudo cat /sys/kernel/debug/pm_genpd/pm_genpd_summary'
scp vim4:/lib/firmware/video/video_ucode.bin logs/kernel-edge/vdec-audit/video_ucode.bin
```

最后用 Python 按 ELF note 格式解析 `/sys/kernel/notes`，并哈希 `/proc/PID/exe`，
实际输出保存在 `board-health-final.txt`：

```text
7.3.0-vim4kvm-uhd1+
running_build_id 3ed254bfa838ab50732fdce1c5134400a1663fd5
one-kvm active
vim4-manager active
udc configured
HID node hidg0
HID node hidg1
HID node hidg2
HID node hidg3
video0 t7-vdin-test
video1 C&M Wave5 VPU encoder
taint 0
```

One-KVM 运行二进制 SHA256 为 `72db30c07aa2351a27499e06d2ac28ccde3a74e1cb18d0927766a7ba35d37b0d`，
manager 为 `ad7b8aa3e068cb4f5e4ef8e8c2fb6df623c791a1c4ed82949e616cd6fd01f67c`，
与[保留基线](2026-10-22-edge-7-3-final-retained.md)一致。
本轮只核对 HID 节点和 UDC configured，没有注入键鼠或重新做 HDMI/编码功能回归。

未运行 v4l2-compliance、硬件解码、md5/PSNR、1080p/4K 速度或 CPU 测量；
不存在本轮正确帧、性能、错误码流、多实例或关闭释放通过证据。
主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：167 tests，5 skipped，OK，
完整输出 `logs/kernel-edge/vdec-audit/root-tests.log`。两份新记录保持 untracked，
另显式检查本地链接、锚点、索引及每篇不超过 12000 字节；`git diff --check` 通过。
不把调查完成写成硬件解码完成。
