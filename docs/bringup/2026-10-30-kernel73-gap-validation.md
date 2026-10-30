# 2026-10-30：7.3 差距补齐批量验证

本轮为独占板子的自动验证，源码与产物均未 push。下面分开记录硬件实测与未完成判据，
不能将子项成功理解为整张验收清单通过。原始日志位于主工作区忽略目录
`logs/73-gap-20261030/`，测试程序位于 `build/73-*.{py,mjs,c}`。

## 拓扑与安全边界

- 被控机为 **Mac mini M6**：提供 HDMI 输入并连接板子 USB-C OTG。
  执行端 **Mac mini M4** 仅通过 LAN `ssh vim4` 和 USB-UART 操作板子。
  硬件文档旧图中的 M4 被控机关系不适用于本轮。
- 未操作 M6 分辨率，未发送键鼠报告，未播放或测量声音。
  WebRTC 客户端只加载空白 HTML，仅建立视频 transceiver，不加载产品页面、HID 或音频通道。
- 应用 USB 重建会主动发送全释放 HID 报告。测试期间用临时 systemd DevicePolicy
  拒绝 hidg/input/hidraw 设备访问，日志确认 HID 初始化返回 EPERM。
  因此 USB 实际枚举改走已安装特权助手，应用停止后运行；完整成功 API 链路未据此宣称通过。
- 用户中途纠正拓扑后，不再从 M4 查找 ACM，也不进行主机数据测试。
  USB 只做单次启用/恢复，省略十轮重枚举，以减少对 M6 的打断。
- 编码夹具以 khadas 运行，停止 One-KVM 后检查共享编码器；没有删除活跃锁文件。
  性能采样前已完成编译，没有使用 strace/ptrace。

## 输入与启动证据

| 项目 | 版本或证据 |
|---|---|
| 主仓配置 | `b4893d6`，uhd1.config；没有修改 sources.toml 的旧锁或删除版本保护 |
| One-KVM | `c9f2a7b9`，包 `2.5.1+vim4.20261027.3.dev.13.gc9f2a7b` |
| manager | `c2bd660`，包 `2.5.1+vim4.20261029.102.dev.1.gc2bd660` |
| 原始系统 | `5.15.137-vim4kvm-hdrdual6`；LAN 经 eth0，192.168.50.210 |
| 保留 7.3 | `b1300eb808f43`，build ID `eeddb005df059a850853876d52ef603aa1af192b` |
| 新候选 | `213f271505411845eecb3c6ef10df7565b895ebc`，build ID `7a473adf9353013fd1ab01908d20bbf503a063fb` |

构建只读取 VM `~/src/linux-7.3-hdmi-integration`，使用独立
`~/build/73-gap-20261030` 输出目录。按既有候选流程直接执行 olddefconfig 和
`make O=… ARCH=arm64 Image dtbs modules`，再用 package-final.py 核对完整模块清单。
配置哈希 `4f8f254d60a37b7cdd7842a1ea7e40f0b036491185efa056179de15628e8dfa6`；
完整清单、DTB/MAC、模块归档哈希见 `candidate-manifest.json`。

两个 7.3 均从 U-Boot RAM 的 sysboot 选择，没有 saveenv、刷引导区或 OOWOW。
新候选完整模块在静态 PID 1 校验 build ID 后只读 bind，未覆盖正式模块。
私有 display-once.py 仅将精确基线 ID 改为本板保留的 eeddb005，其他门禁保持原样。

早期串口实测需要 115200，正常复位后改为 921600。两次未识别提示符时没有发送 sysboot；
一次旧内核路径错误时 sysboot 自动 reset 回默认。根分区无法通过 `/boot` 路径访问独立启动分区，
旧 Image/DTB 后改放根分区私有目录。离开旧 7.3 时发生 watchdog reboot，跳过 U-Boot 等待并回到默认 5.15，
随后从 5.15 正常重启选择候选。启动日志保留全部失败尝试，不将自动回基线记为候选启动成功。

## 5.15

| 项目 | 结果 | 数据与日志 |
|---|---|---|
| Vendor 三模式十轮 | 通过 | 30 个视频专用窗口，均推进至少 120 帧；`515-video.log` |
| Vendor 固定 QP | 通过 | NV12/NV21/P010，QP 18/40；夹具逐 slice 断言 PPS 初始 QP + delta 匹配；`515-quality.log` |
| Vendor 无损 | 通过 | 三种格式各 5 帧，解码差异字节均为 0；`515-quality.log` |
| ACM 板侧 | 通过（助手） | 三 HID + ACM 五端点成功、configured、ttyGS0 可打开；`515-usb-helper3.log` |
| 五/六 IN 端点 | 通过（助手） | 五端点成功，六端点拒绝且快照不变；同上 |
| ACM API 完整成功路径 | 未验证 | HID 访问隔离使运行时 reload 无法初始化；backend=none 会按配置约束自动关闭 serial，不能替代该判据；`515-usb.log` |
| ACM 主机描述符/双向数据 | 未验证 | 需 M6 访问；字节数、哈希无实测值 |
| Vendor GPU | 通过 | 7 次采样约 30 秒，厂商 utilization 与 API 均 0；journal 无 gpu-snapshot 调用；`515-gpu.log` |

两个新包的构建与隔离 verify 均通过。board.py deploy 已实际安装成功，末尾通用 check
因原有失败 NAS mount 返回非零，另有网关未认证 GET 401；这不是新二进制安装失败。
初始 `initial.txt` 与两个 `deploy-*.log` 可对照这一既有失败。

## b1300eb

| 项目 | 结果 | 数据与日志 |
|---|---|---|
| 能力 API/控件 | 通过 | fixed QP=false、lossless=true；缺少 HEVC P/B QP；`b1300-capabilities.json`、`b1300-controls.log` |
| 尺寸回退十轮 | 通过 | 30 窗口，900 高回退 AVC，720/原尺寸仍可 HEVC；尺寸 1280×720、1600×900、3840×2160，均推进至少 120 帧；`b1300-sizes.log` |
| 固定 QP 拒绝 | 通过 | PATCH 返回 400，视频配置不变；`b1300-api-negative.log` |
| 无损夹具 | 通过 | 640×384，5 帧，1,843,200 样本，差异 0；slice QP=4，说明不能将 QP=0 当无损判据；`b1300-fixture.log` |
| ACM 拒绝 | 通过 | API 400 明确要求 ACM 配置/模块，API、UDC、configfs 快照不变；助手同样拒绝；`b1300-api-negative.log`、`b1300-helper-usb.log` |
| GPU 负载/恢复 | 通过（基础窗口） | Panfrost Mali-G52 r1；重算中位数空闲 0%、满载 97.762%、半占空比 48.765%，恢复 0%；`b1300-gpu.log` |
| GPU profiling 开销 | 通过（本负载） | 关/开/关各 60 秒，3800/3799/3801 次完成；扫描墙钟中位约 462 ms，最大 554 ms；同上 |

## 213f2715 候选

| 项目 | 结果 | 数据与日志 |
|---|---|---|
| 能力探测 | 通过 | visible_hevc/fixed_qp/lossless 均 true，无探测固件超时；`candidate-capabilities.json`、`candidate-onekvm.log` |
| 720/900/原尺寸十轮 | 失败 | 720 HEVC 推进 120 帧，900 高输出反复 not-negotiated，API 500 超时，未继续十轮；`candidate-sizes.log`、`candidate-sizes-recheck.log` |
| 1366×768、1440×900、1680×1050 NV12 夹具 | 失败（协商） | 三组均在 GStreamer capsfilter 被拒绝，未产生可供验收的 SPS/解码结果；`candidate-fixture.log` |
| 固定 QP 0/30/51 | 通过（夹具） | 每组 5 帧，实际 slice QP 分别全为 0/30/51；slice_type=2/1/2/1/2，覆盖 I/P；`candidate-fixture.log`、`candidate-wave-results/*.trace` |
| 无损 | 通过（夹具） | 640×384，5 帧，1,843,200 样本，差异 0，实际 slice QP=4；同上 |
| ACM 板侧/端点预算 | 通过（助手） | 三 HID + ACM 五端点成功，configured，ttyGS0 可打开；六端点拒绝且快照不变；`candidate-helper-usb.log` |
| ACM 成功 API/主机数据 | 未验证 | 成功 API 受 HID 禁令和测试隔离限制；主机描述符、字节数、哈希需 M6 访问 |
| GPU 负载/恢复 | 通过（基础窗口） | 重算中位数 0%/97.903%/48.778%，API 对应中位数 0%/98.083%/48.903%，恢复 0%；`candidate-gpu.log` |
| GPU profiling 开销 | 通过（本负载） | 关/开/关各 60 秒，3799/3803/3801 次完成；扫描墙钟中位 460 ms，最大 547 ms，CPU 中位 456 ms；`gpu-summary.json` |

两个内核 helper CPU 中位数均约 456 ms，按 5 秒周期约占单核 **9.1%**，
显著高于先前 VM 估算的 1.07%。扫描都低于 2 秒，Panfrost 本负载的 profiling 开关吞吐
变化小于 0.11%，无新增 GPU timeout/reset，候选 taint=0；但低吞吐影响不等于低采样 CPU 成本。
建议后续评估减少进程启动/扫描成本，或合并既有 CPU/GPU 采样，避免把 VM 开销直接用于产品预算。

尺寸失败判断：新驱动接受对齐 RAW 存储加非对齐 CROP，但 GStreamer 管线和本轮简单
appsrc 夹具仍以可见尺寸直接协商 RAW caps。能力探测成功无法证明实际管线已经处理
存储对齐与可见矩形。建议在桥接层补齐 padded storage、真实 stride/UV 偏移和 CROP，
并更新直接 V4L2 夹具；本轮不修改生产代码。三个非对齐尺寸的 SPS 可见矩形、四边内容、
解码帧数仍然未验证，不能将 caps 协商失败归为固件像素错误。

## 未完成判据与最终状态

两个内核的跨用户/复制 fd、预留管理器实例遮蔽来源后的
API null/恢复，没有完成硬件验收；现有客户端更换时留空和重新恢复数据不能覆盖全部边界。
WebRTC/UU/SRT 三路共享 HEVC 的 120 秒并发接收也没有完成，不能用单路浏览器或 UU 在线日志代替。
这项没有运行三路接收测试，并非已经证明服务缺陷。尺寸切换窗口只验证接收推进，
没有补齐逐轮 CMA/fd 漂移判据，不能宣称完整生命周期验收通过。

GPU 数字是最忙引擎近似值，不能解释为精确整 GPU 时间并集。helper 约半秒的扫描耗时
低于 2 秒期限，但不是零开销；5 秒周期下 CPU 成本需按日志中的 CPU 时间评估。
稳定性短窗不代表长期可靠性。

最终恢复 `5.15.137-vim4kvm-hdrdual6` 默认启动。One-KVM、manager、HDMI、gadget 与
音频桥均 active，UDC configured；DevicePolicy=auto，InaccessiblePaths 为空，临时隔离已删除。
收尾视频专用客户端再次跑三种画质，均 HEVC 1280×720、窗口推进 120 帧，恢复原输出配置。
配置 API 与测试前相同；音频仅查看服务和 continuity 日志，没有播放/采样音频。
新应用包保留，已执行的 5.15 子项未出现产品回归；成功 ACM API 和上表未完成判据仍须补验。
workspace.toml 同步两个本地安装提交，并注明它们尚未推送。

五个受保护文件（旧 Image/DTB、extlinux、kernels.json、runtime-build.json）收尾哈希与
进入 b1300eb 前完全相同；候选仅保留在私有目录，不登记为默认运行时。
`final-state.txt`、`protected-final.txt` 和 `final-515-video.log` 为收尾证据。
