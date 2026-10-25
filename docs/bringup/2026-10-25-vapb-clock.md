# 2026-10-25：厂商 5.15 VAPB 共享时钟需求

当前状态：时钟修复已合入 common_drivers `vim4-kvm-5.15` 并复编；One-KVM
`vim4` 已移除 debugfs 写时钟，仅保留检查与告警。候选短测通过并已设为默认。
用户允许资格元数据同时列出旧、新内核；声音偏好、路由和 EDID 保持原样。
按最新要求，只做启动、4K/1080p 约 60fps、透传视频/声音的基本自动检查后转默认，
其余尺寸和长期使用由用户继续实测。

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
保留 GE2D 原有频率策略。

`drivers/media_modules/frame_sink/encoder/multi/test_shared_clock.py` 编译真实
GE2D 请求函数及 MultiEnc 请求、开关和 open 函数，覆盖两种初始化顺序、20 次重开、
旧 JPEG 竞争、低编码器参数、取整和请求失败；验证请求失败没有分配/上电，后续
内存或 IRQ 失败也不遗留投票。时钟 mock 只模拟每消费者下限，不能替代真实
CCF/时钟树的上板验证。Mac 和 ARM64 VM 均通过；checkpatch 零错误、零警告。
回归已接入 CI。

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

在 `orb vim4-build` 独立树 `~/src/linux-vapb-5.15` 构建完整内核/模块及 vfm_cap，
保留音频任务原树。板端持 board/heavy 双锁，没有并行编译和性能采样。

候选 Linux `80a07ad5406d`，驱动 `3185aa677`（MultiEnc）、`25d2aa57f`（GE2D/回归）
均已推送生产分支。
完整构建 release 为 `5.15.137-vim4kvm-vapb1`，build ID
`db19fc96a2df75099a7335c7bde326d85275e316`。
配置与板上原配置仅 LOCALVERSION 不同，SHA256 为
`37cb2ed8b2293ccd7b32e65c245bc01e49bbbd49360ab7d2b9b99a3ec1236095`。
构建有原厂 Kconfig choice 和 worktree `.git/hooks` 警告；编译、链接、模块安装成功。

默认原内核为 `5.15.137-vim4kvm`、build ID
`389f77352dc8ab21aa80d8cf36819bb9da31d7ee`。旧 Image、initrd、DTB、config、
extlinux、uEnv、kernels.json、运行登记和资格记录备份于
`/var/backups/vapb-kernel-20261025/`；旧模块目录未覆盖。
本任务没有写透传偏好，正式窗口开始前已核对视频/声音双 running。

旧基线在服务挂载命名空间绑定临时只读助手，实际 399999994Hz；不改生产安装文件。
暂停 UU 云连接以保持单一观看者，结束恢复原设置。
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

发送端以 `VIM4 capture progress encoded=` 计数差/时间差计算。六窗零浏览器
drop/loss/freeze；18 帧的帧号推进/一致性和原色块通过。音频峰值约 0.103–0.105，
透传双 running。这是旧内核禁恢复对照。

## 看门狗与启动安全网

原 5.15 看门狗为 Meson GXBB，PID 1 持有，Runtime 30s / Reboot 60s。
只在 `/run` 暂停 PID 1 喂狗，独立程序 SETTIMEOUT(15)、KEEPALIVE 一次后停止喂狗。
02:13:06 UTC armed，实际复位，串口确认 `watchdog_reboot`；原默认 build ID 与
透传视频/声音恢复，临时 override 消失。未测精确复位延迟，不代表全部早期故障覆盖。

`/boot` 原仅约 13MiB 空闲。候选完整模块与启动文件先放独立 release/根分区，
完整 initrd 使用配置已有的 CONFIG_RD_ZSTD=y；候选 DTB 与旧 kvim4n 字节一致。
先以旧 Image 的 gzip 副本、原 initrd/DTB 做 RAM sysboot，串口确认解压并约 29.9 秒
到登录；再正常重启回原默认，两次原 build ID、视频/声音均正常。
原启动文件/登记/生产助手哈希不变，临时 panic 参数消失，证明单次选择未持久化。
旧内核窗口 soc_thermal 54.7–60.5°C；没有整板 power_input，不能给功耗结论。

资格记录采用 `abi:1` 与 `kernels` 数组，同时列出旧、新 release/module note 指纹，
manager `0755278` 保留旧单条记录兼容，严格匹配两项并保留原权限检查。
One-KVM `7fdbf3ed` 只读检查实际总线频率，低频或检查失败只告警并继续出流。
空间调整已执行：新旧 Image 使用已验证的 gzip 格式，新完整 initrd 为 Zstd；
调试用 System.map 移至根分区并保留原路径链接。Stock、7.3、旧 5.15 产物均保留。

## 主线构建、短测与交付

common_drivers 生产分支复编得到相同 Image SHA256 与 build ID；完整模块集与
外部 vfm_cap 均匹配此构建。One-KVM `7fdbf3ed`、manager `0755278` 从各自生产
分支构建于固定 ARM64 builder（镜像 `8f0e51877aaf`），没有从板子获取构建输入。
One-KVM 35 项部署测试、DMA 生命周期检查、744 项 Rust 测试通过（2 ignored）；
manager Go 测试通过，Mac 部署测试 198 项通过（12 skipped）。
包为 `2.5.1+vim4.20261025.2`、`.3`，离线核验后部署；manager 网关启动完成后重检
通过，资格读取进程重启后原内核透传双 running。主仓 244 项离线测试通过（7 skipped）。

一次性从根分区启动候选，默认项仍是旧内核；28.741 秒到登录。
运行 release/build ID、aml_media note 指纹均匹配完整构建；taint 12288 与旧内核一致。
GE2D/VAPB 实际 666666656Hz，编码器打开后保持，生产助手仅只读检查。
4K60 SDR/YUV444 运动输入、48kHz 测试音，透传视频/声音开启；每档预热 10 秒、
采样 30 秒，以窗口内发送端 encoded 首末计数/时间差计算吞吐。

| H.265 输出 | 旧内核禁恢复 fps | 新内核发送 fps | 浏览器解码 fps |
|---|---:|---:|---:|
| 3840×2160 | 59.998 | 60.000 | 59.988 |
| 1920×1080 | 43.661 | 59.998 | 60.019 |

新窗口 UTC 为 02:40:36–02:41:06、02:41:25–02:41:55，发送端计数区间约 25.05 秒。
零浏览器 drop/loss/freeze；每档三帧的帧号一致并推进、原色块通过。
WebRTC 音频峰值 0.103/0.102。透传双 running，独立连续音补检 PCM frames
6686976→6831360、peak 3277，证明声音数据非静音且持续推进。
内核没有新增 Oops/panic；采集重连时仍有
`unknown vframe ... passing through` 日志，后续应单独整理，不能宣称日志全零。
新内核结束时 soc_thermal 59.8°C；短窗与旧温区范围重叠，非配对热稳态试验，
没有整板功耗传感器，不能给出温升/功耗差结论。

通过后，`Default` 显式指向新 release 的 Image/initrd/DTB；`VendorPrevious`
保留旧启动字段。`kernels.json` 更新 vendor 的完整产物哈希，mainline 登记不变。
资格记录同时保留两个 release/note；旧模块未覆盖，原 extlinux 和清单备份可恢复。
正常重启 35.686 秒回到新默认和相同 build ID，视频/声音 running；管理器登记可用，
常规检查通过。临时统计移除，UU/输出恢复；声音偏好与 uEnv 哈希未变。

用户可直接用 One-KVM 或 UU 选择 4K、3200、2560、1920、1280 输出测试；本次
按要求仅复验 4K/1080p，未重复其余尺寸、H.264 或长期稳定性测试。
回退脚本 `--check` 已核验旧 gzip Image、initrd、DTB、完整模块与 7.3；永久回旧 5.15：

```sh
ssh vim4 'sudo python3 /var/backups/vapb-kernel-20261025/rollback.py --reboot'
```

也可在串口启动菜单选择 `VendorPrevious` 单次回旧内核。新 One-KVM 在旧内核仅告警，
缩放可能恢复低吞吐；如需完整恢复旧用户态 workaround，旧 `.1` deb 也已备份在同目录。
44.1kHz One-KVM 既有变调见[音频交付](2026-10-25-vendor-passthrough-audio.md)，不在本修复范围。
本任务没有创建或修改 `/tmp/codex-kernel/need-user.txt`。
证据在 `logs/vapb-kernel-20261025/`。
