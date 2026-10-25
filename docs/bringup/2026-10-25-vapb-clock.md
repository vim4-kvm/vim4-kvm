# 2026-10-25：厂商 5.15 VAPB 共享时钟需求

当前状态：时钟修复已合入 common_drivers `vim4-kvm-5.15` 并复编；One-KVM
`vim4` 已移除 debugfs 写时钟，仅保留检查与告警。候选上板验证、默认项切换待完成。
用户允许资格元数据同时列出旧、新内核；声音偏好、路由和 EDID 保持原样。
按最新要求，只做启动、4K/1080p 约 60fps、透传视频/声音的基本自动检查后转默认，
其余尺寸和长期使用由用户继续实测，不重复完整长测。

## 根因和时钟树

接续 [UU 缩放调查](2026-10-24-uu-scaled-60fps.md) 与
[生产包复核](2026-10-25-uu-scaling-production.md)。本次审查厂商 Linux
`80a07ad5406d`、common_drivers `746f93e09`；7.3 只读快照为 `c24465df1dd7`。
路径以下均相对 common_drivers，7.3 路径相对其主内核。

- `drivers/media_modules/frame_sink/encoder/multi/vpu_multi.c::vpu_clk_enable()`
  在首次 open 无条件给 DOS 和 APB 都设置 400MHz；`set_clock_freq` 只允许再降低。
  2023 年 Khadas 的 `5ff5cbd3f` 导入时已有此逻辑，2024 年更新及当前版本仍保留。
  没有分辨率判断、400MHz 上限的硬件说明或功耗策略注释。可确认的是通用初始化值
  被当作独占时钟的精确目标；不能把源码没有解释的设计动机断言为省电或时序要求。
  T7 单独调整 Wave A/B/C 核心时钟，却未处理共享 APB 需求，形成消费者间覆盖。
- `arch/arm64/boot/dts/amlogic/mesont7{,c}.dtsi` 中 MultiEnc 和 JPEG 的
  `clk_apb_dos` 都是 `CLKID_VAPB`；GE2D 的 `clk_vapb_0` 也是该 ID。
  JPEG 的 `jpeg_enc_clk_enable()` 也有精确 400MHz 请求。
- `drivers/clk/meson/t7.c`：固定 PLL 分支 → `vapb_0_sel/div/gate` 或
  `vapb_1_sel/div/gate` → `vapb_sel`（`CLKID_VAPB`）→ `ge2d_gate`。
  GE2D gate 使用 `CLK_SET_RATE_PARENT`，没有独立分频器。`vpu` 是另一套 mux/div/gate，
  与 VAPB 共享部分固定 PLL 来源，但不是 VAPB 的父时钟；GE2D 初始化中按 VPU 频率
  限制 VAPB 是驱动策略，不代表二者为父子关系。
- `drivers/media/common/ge2d/ge2d_main.c` 的 T7 表请求名义 667MHz，probe
  根据 VPU 上限调整后，仅调用一次 `clk_set_rate()`。运行时开关 gate/电源不会重新
  提出频率要求，所以编码器后打开即可覆盖它；约 400MHz 与 666.67MHz 都能工作，
  但缩放吞吐不同。原用户态助手不修改 Wave 核心频率。
- VDIN 使用 VPU 的模块门控和内存电源接口，未找到其正常 start 路径精确设置 VAPB
  为 400MHz。VPU 的通用 suspend/resume 代码还支持切换 VAPB 父路径并降至 50MHz，
  但当前 T7/T7C DTS 未提供其要求的 `vapb_clk0/1`，该切换会提前返回。
  此次不改变系统挂起策略，也不声称消费者最低请求能拦截绕过该节点的祖先时钟
  直接改频或父路径切换。

## 内核修复与离线验证

MultiEnc 将共享 APB 的精确设置改为 `clk_set_min_rate()`：首个实例分配内存/IRQ
之前提出最低需求，打开失败或最后关闭时释放；取整/请求失败通过 open 返回。
DOS 与 Wave 核心频率保持原配置，不增加板型判断。

GE2D 将已有 SoC/VPU 策略计算出的目标转换为最低需求，附着在其 managed clock
消费者上，直到驱动释放。T7 在共享 `CLKID_VAPB` 上投票，所以 CCF 取两者最低
需求的最大值；旧 JPEG 精确请求低于 GE2D 下限时被拒绝，不能覆盖已有频率。
先 `clk_round_rate()` 再设置下限，避免把名义 667000000Hz 当作实际可达下限。
这保留 GE2D 原有驱动存续期的频率策略，不新增按帧调频或空闲降频。

`drivers/media_modules/frame_sink/encoder/multi/test_shared_clock.py` 编译真实
GE2D 请求函数及 MultiEnc 请求、开关和 open 函数，覆盖两种初始化顺序、20 次重开、
旧 JPEG 竞争、低编码器参数、取整和请求失败；验证请求失败没有分配/上电，后续
内存或 IRQ 失败也不遗留投票。时钟 mock 只模拟每消费者下限，不能替代真实
CCF/时钟树的上板验证。Mac 和 ARM64 VM 均通过；checkpatch 零错误、零警告。
该回归已接入 common_drivers CI 的内核构建前门禁。

## 7.3 结论

Wave5 的 `drivers/media/platform/chips-media/wave5/wave5-vpu.c` 使用 bulk
prepare/enable，不在 open 时设置共享 APB 为 400MHz。Wave A/B/C 由设备树
assigned clocks 设置。One-KVM 的该后端在 VDIN 写内存前进行 H/V 缩放，不经过
GE2D，解释了当前 UU 无此问题。

仍存在未来集成边界：7.3 `t7-hdmirx/t7-vdin-test.c` 在初始化时按输入宽度精确请求
VAPB 500/250MHz；当前 T7 GE2D 没有使能/验收，不能据此声称所有未来共享消费者
已实现投票。以后接入 GE2D 或统一显示/采集资源时，应一并整理这些最低需求，
见 [厂商对齐](../vendor-parity.md) 的 D01/R02/D07；本次不修改 7.3。

## 构建与基线窗口

音频会话完成后取得 heavy 锁，在 `orb vim4-build` 独立工作树
`~/src/linux-vapb-5.15` 完成 Image、DTB、全部 modules 和外部 vfm_cap 构建。
没有修改音频任务使用的 `~/src/linux` 或其未提交驱动文件。
随后持 board/heavy 双锁进行板端步骤；没有并行编译和性能采样。

候选 Linux `80a07ad5406d`、驱动 `25d2aa57f808815254fa1e8de7703f8df53babdc`，
两个提交为 `3185aa677`（MultiEnc）与 `25d2aa57f`（GE2D、回归/CI），已推送生产分支。
完整构建 release 为 `5.15.137-vim4kvm-vapb1`，build ID
`db19fc96a2df75099a7335c7bde326d85275e316`。
配置与板上原配置仅 LOCALVERSION 不同，SHA256 为
`37cb2ed8b2293ccd7b32e65c245bc01e49bbbd49360ab7d2b9b99a3ec1236095`。
厂商 Makefile 向 worktree 的 `.git/hooks` 安装钩子失败被其标为 ignored，
另有原有 Kconfig choice 警告；编译、链接、模块安装均成功。

默认原内核为 `5.15.137-vim4kvm`、build ID
`389f77352dc8ab21aa80d8cf36819bb9da31d7ee`。旧 Image、initrd、DTB、config、
extlinux、uEnv、kernels.json、运行登记和资格记录备份于
`/var/backups/vapb-kernel-20261025/`；旧模块目录未覆盖。
01:52:49 入场快照曾见透传 off；偏好文件于 01:52:51 由外部状态变更为 on。
本任务没有写透传偏好，正式窗口开始前已核对视频/声音双 running。

仅在 One-KVM 服务挂载命名空间内绑定临时助手，`video-clock` 只读并输出
`test_clock_write_disabled=true`，实际 399999994Hz；不改安装文件或生产源码。
临时暂停 UU 云连接以保持单一浏览器观看者，结束恢复原 enabled 设置。
每档独立预热 15 秒、采样 120 秒，4K60 SDR/YUV444 运动标记及 48kHz 测试音输入，
透传/音频开启；One-KVM 保留已部署的 DMA 缓存、有界队列和编码设置。

| 输出 / 编码 | UTC 测量窗口 | 发送端编码输出 fps | 浏览器解码 fps |
|---|---|---:|---:|
| 3840×2160 / H.265 | 01:54:54–01:56:54 | 59.998 | 60.006 |
| 3200×1800 / H.265 | 01:57:14–01:59:14 | 39.529 | 39.531 |
| 2560×1440 / H.265 | 01:59:34–02:01:34 | 38.711 | 38.706 |
| 1920×1080 / H.265 | 02:01:55–02:03:55 | 43.661 | 43.647 |
| 1280×720 / H.265 | 02:04:16–02:06:16 | 44.578 | 44.581 |
| 1920×1080 / H.264 | 02:06:36–02:08:36 | 43.635 | 43.640 |

发送端以窗口内 `VIM4 capture progress encoded=` 首末计数差/日志时间差计算，
不是配置上限。六窗零浏览器 drop/loss/freeze；各抓三帧，三处帧号一致并推进、
原色块全部通过。音频非静音峰值约 0.103–0.105，透传/音频始终 running。
这仅是旧内核无时钟恢复的对照，不是新内核通过证据。

## 看门狗与启动安全网

原 5.15 的看门狗为 Meson GXBB，PID 1 持有，Runtime 30s / Reboot 60s。
只在 `/run` 暂停 PID 1 喂狗并 reexec，独立程序 SETTIMEOUT(15)、KEEPALIVE 一次，
保持 fd 打开而停止喂狗。02:13:06 UTC armed，随后实际复位，串口确认
`reboot_mode : watchdog_reboot`，回到原默认 5.15、相同 build ID，视频/声音恢复 running。
未测精确复位墙钟延迟，也不把运行时复位等同于全部早期引导/硬件故障覆盖。
临时 Runtime override 随复位消失，PID 1 恢复持有 /dev/watchdog0。

`/boot` 只有约 13MiB 空闲。候选完整模块存放独立 release 目录，启动文件与
完整匹配 initrd 暂存根分区 `/var/lib/vim4-kvm/vapb-clock/candidate/`，未写默认启动项。
新 initrd 使用已启用的 Zstd 解压支持；因尚未放置 `/boot/config-<新release>`，
mkinitramfs 提示无法检查 CONFIG_RD_ZSTD，已与构建配置的 `=y` 单独核对。
候选 DTB 与已装 kvim4n DTB 字节一致；候选尚未启动，不能把暂存当验收。

先以原 Image 的 gzip 副本、原 initrd/DTB，从根分区做一次 RAM sysboot：
U-Boot 实际环境含 kernel_comp_addr_r=0x0d080000、kernel_comp_size=0x2000000，
串口确认读取私有 Image.gz 并解压，约 29.9 秒到登录；原 build ID、透传/声音 running，
默认启动文件与登记哈希未变。此验证只涉及原内核，不是新驱动验收。

随后正常重启再次进入原默认、相同 build ID，临时 panic=20 参数消失，
证明 RAM 选择未持久化。原 Image/initrd/extlinux/uEnv、内核登记、资格文件、
One-KVM/manager 文件哈希均与入场相同，视频/声音 running。
临时服务内禁写视图随重启消失，恢复 UU enabled=true（当前无客户端会话）。
主仓完整离线测试 243 项通过、7 项跳过。旧内核窗口 soc_thermal 为 54.7–60.5°C，
温度随时间缓慢下降，尚无新内核配对对照；未提供整板 power_input，不能给功耗结论。

资格记录采用 `abi:1` 与 `kernels` 数组，同时列出旧、新 release/module note 指纹，
manager `0755278` 保留旧单条记录兼容，严格匹配两项并保留原权限检查。
One-KVM `7fdbf3ed` 只读检查实际总线频率，低频或检查失败只告警并继续出流。
空间方案可使用已验证的压缩 Image 和 Zstd initrd，调试用 System.map 移至根分区并
保留原路径链接；原厂 Stock、7.3 和旧 5.15 回退产物均须保留，尚未执行此空间调整。

## 尚未完成

新内核的一次性启动、五档 60fps、编码/透传/音频共存及温度对照均待执行。
One-KVM/manager 尚待重打包部署；默认内核未替换。
44.1kHz One-KVM 既有变调见[音频交付](2026-10-25-vendor-passthrough-audio.md)，不在本修复范围。
本任务没有创建或修改 `/tmp/codex-kernel/need-user.txt`。
原始证据目录为 `logs/vapb-kernel-20261025/`，包含构建、UART、计数、PNG 和传感器日志。
