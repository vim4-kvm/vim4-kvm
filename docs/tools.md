# 工具目录

tools/ 与 packaging/ 下每个入口一行。tests/test_docs.py 检查本表与目录一致，
新增或删除脚本时同步修改。命令从主仓库根目录运行；用法以脚本头注释或 --help 为准，
“影响”列决定是否需要先协调板子独占（见 [代码规范](code-standards.md)）。

运行位置：Mac = 开发机；板 = 先 scp 到板上 /tmp 再 ssh 运行；容器/VM = 由上层工具调用。
`hdmi-setup.sh` 的 `HDMI_CAPTURE_FORMAT=YUV444` 只供兼容的采集管线使用；现有应用保留默认 NV21。
影响：无 = 不访问硬件；读 = 只读访问板子；独占 = 停启服务、占用编码器/HID/USB 或改设置，
不能与其他硬件任务并行；破坏 = 清空 eMMC 或重启，须用户明确授权。

## 浏览器测试的公共前提

*.mjs 需要 Node 与 Playwright + Chrome，经 PLAYWRIGHT_MODULE 指向 playwright/index.mjs 的绝对路径
（`mdfind -name index.mjs | grep 'playwright/index.mjs'` 可找到本机已有副本）。
访问网关的浏览器测试经 MANAGER_PASSWORD 和可选 MANAGER_USERNAME（默认 admin）
传入统一账户，由 tools/manager-login.mjs 登录，不打印凭据；无需应用独立密码。
默认地址为 http://192.168.50.210:8080（管理器 :80）。同一应用账户的测试依次运行。
PiKVM smoke 可用 `PIKVM_CDP` 接入专用测试 Chrome；结束时关闭测试 context，
保留外部浏览器。截图检查包含局域网响应时间，拒绝等待 3 秒超时才返回的 JPEG。
视频 smoke 与 `kvm-switch-check.mjs` 可用 `VIM4_TEST_CHROME` 指定固定
浏览器可执行文件的绝对路径；配对测试同时核对每轮实际浏览器版本。

## 工作区、构建与打包

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| tools/memory-bench.c、memory-bench.py | C：Linux ARM64编译；runner：Linux/板 | 独占CPU/内存/tmpfs；无频率写入、部署、HID | 单核强制绑定、逐段实际CPU/每核频率、多尺寸分布与fault，≤3分钟、采温度并恢复亲和 | [内存拷贝审查](memory-copy-audit.md)、[绑核门禁与配置草案](nodebug-performance-gate.md) |
| tools/gpu-diagnose.py、gpu-cl-map.c | 板；CL工具先ARM64编译 | 独占GPU；诊断器可临时锁频/PM/profiling并恢复；不写电压、不ptrace | 自有子进程fdinfo/周期/忙闲估计、trans_stat与CPU；小buffer CL map复现 | [GPU性能复核](gpu-performance-diagnosis.md) |
| packaging/gpu/（含 compiler-compare.sh、corpus-check.sh、corpus-report.py、gpu-probe.c、hdr-check.sh、hdr-check.py、hdr-probe.c、hdr.comp、hdr-vulkan.py、hdr-dmabuf.c/h、hdr-dmabuf-test.c） | Docker ARM64；probe：板 | 构建无；probe占GPU | 固定shader-db、全帧RGBA；HDR参考/GBM负载、候选外部buffer导入与退休，不接生产DMA | [GPU运行时](bringup/2026-10-30-gpu-runtime.md)、[HDR规格](gpu-hdr-pipeline.md) |
| tools/npu-probe.c、npu-validate.py、npu-models.json | 编译：ARM64；run：板；compare：Mac/VM | run 占用 NPU，写新结果目录；无部署、HID、声音 | 固定下载SHA、逐轮完整张量校验、均值/P50/P99/最大值；probe的--timing分段SDK外开销 | [ADLA离线候选](npu-adla.md)、[端到端分段](npu-e2e-timing.md) |
| tools/npu-uapi-probe.c | ARM64编译→板 | 占用NPU兼容接口；无推理、HID或声音 | 初始化MMU上下文后测试ATTACH别名；负向PROFILE_CFG拒绝厂商5.15，须有界运行 | [ADLA候选与验收](npu-adla.md) |
| packaging/kernel-edge/build-gstreamer.py | 容器/VM | 无 | 校验固定源码、应用 V4L2 生命周期补丁并构建私有插件，不改系统库 | [音视频](subsystems/video.md) |
| packaging/kernel-edge/test_gstreamer_visible_crop.py | 容器/VM | 无 | 提取实际 V4L2 caps／padding／crop 函数，以模拟 ioctl 离线回放 Wave5 非对齐尺寸协商 | [音视频](subsystems/video.md) |
| packaging/kernel-edge/maintain.py | Linux ARM64 VM | 无 | inventory 导出按主题存放的保序补丁并证明 tree 一致；forward 在新分支 rebase；verify 汇总 host C/KUnit 入口、strict checkpatch、schema/DTB 与可选完整构建，不自动 fetch、部署 | [补丁清单](archive/kernel-patch-inventory.md) |
| packaging/kernel-edge/register-runtime.py | VM / 板 | inventory 无；register 改启动配置 | 核对完整 Image/模块清单后登记双内核，保留当前默认项；不安装、不重启 | [双内核集成](bringup/2026-10-21-dual-kernel-integration.md) |
| packaging/kernel-edge/package-final.py | VM | 无 | 打包 UHD 完整构建，生成哈希/build ID 清单；--dtb 显式选择 audio-test/display-m0/display-m1；M1 检查驱动与 DT 互斥；不编译 Image、不上板 | [M1 合入](bringup/2026-10-23-display-m2.md) |
| packaging/kernel-edge/display-once.py、display-once-init.c | VM / 板 | prepare 无；stage 独占；串口选择后重启 | 私有归档与静态 PID 1 模块 bind；保留默认启动项；一次性启动、预检失败回退及重启回默认已实测，物理 RESET 未测 | [M1 安全网](bringup/2026-10-23-display-m1-safety.md) |
| packaging/kernel-edge/final-window.py、final-board.py | Mac → 板 | stage/dry-run 无；execute 独占、重启 | 双锁备份、安装与回归；kernel-only 保留用户态；--require-all-checks 任一失败回退，--framebuffer-console 登记 tty0；--ir-keytable 将 ARM64 IR 检查工具保存在 bundle；支持正常重启 pstore 读回，HDMI 恢复最多等 35 秒 | [pstore 部署与回退](bringup/2026-10-22-edge-pstore-deploy.md) |
| packaging/kernel-edge/final-regression.py、final-manager-check.mjs | Mac → 板 | prepare 无；run 独占、改 HDMI/USB 设置后恢复 | 默认19模式，可用 --sample-modes 抽样；--hevc-visible-sizes 仅用于 E02 内核，增加非8对齐HEVC浏览器验收；--gpu-load 快照 ARM64 GPU 负载；音频等待CoreAudio枚举、直接AudioData检查、恢复48k后停音；仅显式 --wifi-scan 扫描并恢复 radio/autoconnect，不操作P2P；run仅由双锁窗口调用 | [正式版部署准备](bringup/2026-10-22-deploy-7-3-final-prep.md) |
| packaging/kernel-edge/package-vdec.py | VM | 无 | 打包干净的独立构建、检查 vermagic/BTF/哈希；默认 vdec5，once 模式为同 release 私有模块，不登记运行时 | [MDEC 远程窗口](bringup/2026-10-23-vdec-mdec-window.md) |
| packaging/kernel-edge/vdec-window.py | Mac → 板 | 默认离线；execute 双锁、加载模块；旧 boot 动作装内核 | snapshot 仅到第八步，保存外部寄存器后下电；解码仍需完整 MDEC 门禁；once 校验看门狗/私有模块/五文件，失败不重试、不强卸载 | [寄存器差分](bringup/2026-10-23-vdec-register-diff.md) |
| packaging/kernel-edge/vdec-register-dump.c | 板 | 双锁、已上电期间只读 MMIO | 先校验完整地址清单；/dev/mem 只读映射，厂商 debugfs 只缓存单地址；拒绝内部 DOS/GCLK，每次读取前输出地址 | [寄存器差分](bringup/2026-10-23-vdec-register-diff.md) |
| packaging/kernel-edge/check-wifi-p2p.py | 板 | 独占、临时接管 Wi-Fi 后恢复 | 已保存 SAE 客户端与 P2P 扫描、监听、双频 GO 启停；不代替真实对端传输 | [Wi-Fi Direct](bringup/2026-10-21-edge-wifi-p2p.md) |
| tools/workspace.py | Mac / CI | 无 | bootstrap/status 子仓库（`--override` 供发布 CI 替换单个仓库提交），build 各目标（kernel 走 OrbStack） | [工作区](workspace.md) |
| tools/mali-runtime.py | fetch：Mac / Linux；install：板（root） | 下载或写私有 GPU 目录，不重启服务 | 固定来源和 SHA 获取 r44p0 用户态驱动，安装前检查 5.15/Mali ABI 与依赖；不注册全局 ICD | [HDR GPU](bringup/2026-10-26-hdr-gpu.md) |
| tools/mali-dma-probe.c、mali-dma-probe.comp | ARM64 容器编译 → 板 | GPU 计算、临时约25MB连续CMA，不操作采集/编码 | Vulkan计算、DMA-buf导入与逐字读回；可选第二参数指定已知连续heap路径，默认codecmm；不是视频吞吐基准 | [HDR GPU](bringup/2026-10-26-hdr-gpu.md) |
| tools/vrr-edid.py | Mac / Linux | 只写指定的新文件，不访问板子 | 显式实验范围生成远程VRR EDID；Forum最小值≤48、显式最大值≥100，拒绝保留值与模式相关上限；本地模式必须提供同协议sink并取交集，不安装预设或触发HPD | [VRR准备](vrr-preparation.md) |
| tools/ubuntu-build.py | Mac / CI → Docker | 无 | package/verify 七组件；支持 platform、capture、encoder、nanokvm、jetkvm、onekvm、manager、pikvm、pikvm-app | [Ubuntu 构建](ubuntu-build.md) |
| tools/ubuntu-image.py | Mac → OrbStack | 无 | 内核包、候选镜像 assemble/verify/export | [候选镜像](ubuntu-image.md) |
| packaging/ubuntu/ | 容器 | 无 | Dockerfile、锁文件、fetch.py、build.sh、package.py、verify.sh；manager-config.py 迁移网关配置；check-audio-startup.py、check-onekvm-update.py 与 pikvm/check-janus.py 为打包门禁 | [Ubuntu 构建](ubuntu-build.md) |
| packaging/kernel/ | VM | 无 | package.sh 构建内核包，vim4.config 为配置 | [内核](kernel.md) |
| packaging/kernel-edge/ | Linux ARM64 VM / 板 | 构建无；准备工具改固件目录；Wi-Fi 转储保存后释放其内核副本 | build.sh 构建实验内核；prepare-wave521c-firmware.py 转换匹配固件；prepare-wifi-firmware.py 建立主线名称链接；save-wifi-coredump.py 由配套 udev 规则保存至私有目录，最多两份、每份 16MiB | [新内核基线](kernel-edge.md)、[Wi-Fi 排查](bringup/2026-10-21-edge-wifi-fps.md) |
| packaging/kernel-edge/one-kvm-edge、one-kvm-edge-prepare、one-kvm-edge.service | 板 | 独占 | 按匹配内核选择独立视频程序；准备器校验固件后加载固定 UHD60 驱动，实验服务另需启动参数显式启用 | [新内核基线](kernel-edge.md) |
| packaging/image/ | VM（root） | 无 | assemble.sh 组装镜像文件，configure.sh 仅由其调用，verify.sh 只读检查 | [候选镜像](ubuntu-image.md) |
| tests/ | Mac | 无 | 离线单元测试：`python3 -m unittest discover -s tests -p 'test_*.py'` | 本页 |

## 板级操作

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| tools/board-queue | Mac / Linux，同一协调主机 | 仅本机锁与票据；run 的影响由命令决定 | FIFO、≤30分钟租约、旧 lockf 兼容、sampling 与 heavy 协调 | [短窗口](board-window.md) |
| tools/board-window | Mac → 板 | collect --readonly 读；baseline/receiver/MCP 截图占采集；MCP HDR 发 HID；boot-candidate/return-baseline 重启 | 哈希校验、候选链式 RAM 启动、每日基线缓存、MCP、接收与证据包 | [短窗口](board-window.md) |
| tools/board-window-receiver.mjs、board-window-timing.mjs | Mac / Node | 接收占用编码器；compare 仅本机图片 | board-window 私有浏览器接收/裁图比较入口与50ms计时；沿用 Playwright、manager-login.mjs | [短窗口](board-window.md) |
| tools/gpu-compare.py | 板 | 独占 | vendor/system/private能力与固定离屏GLES、clpeak；超时、逐进程ICD隔离，不操作服务/HID | [GPU运行时](bringup/2026-10-30-gpu-runtime.md) |
| tools/board.py check | Mac | 读 | 内核、服务、设备节点、8081 后端与 8080 网关状态 | [板级工具](board-tools.md) |
| tools/board.py deploy --exclusive | Mac | 独占 | 校验并安装组件包（委托 install-components.sh） | [板级工具](board-tools.md#增量开发闭环) |
| tools/board.py verify | Mac | 独占 | 部署后 hid/audio/video 实测，写 verify.json | [板级工具](board-tools.md) |
| tools/board.py provision / enroll | Mac | 改板配置 | 公钥与开发用免密 sudo | [板级工具](board-tools.md#操作前约定) |
| tools/board.py recover / flash | Mac | 破坏 | 进入 OOWOW；校验刷写本地镜像 | [板级工具](board-tools.md#本地候选镜像一键刷写) |
| tools/install-components.sh | 板（由 deploy 调用） | 独占 | 板上包校验、APT 模拟、迁移与恢复所选应用 | [板级工具](board-tools.md) |
| tools/uart-run.py | Mac | 取决于命令 | 串口执行命令；超时后命令可能仍在运行 | [部署](subsystems/deployment.md) |
| tools/uart-log.py | Mac | 读（`--send` 除外） | 只读抓串口日志 | [部署](subsystems/deployment.md) |
| tools/oowow-flash.sh | Mac（板在 OOWOW） | 破坏 | 手工 URL 刷写，优先用 board.py flash | [板级工具](board-tools.md) |
| tools/kernel-install.sh | 板（root） | 改启动项 | 安装厂商内核包并保留 Stock；7.x 在解包前拒绝，走独立 edge 窗口 | [内核](kernel.md) |
| packaging/kernel/promote.py | 板（root，双锁） | 改默认；可删除显式淘汰的未登记旧产物 | 将已运行验证的厂商候选登记至标准 vim4boot 和透传资格清单；可备份回退或显式不备份，不重启 | [原生 HDR 交付](bringup/2026-10-25-native-hdr-dual-path.md) |
| tools/passthrough-monitor.py | 板（只读硬件，写指定日志） | 不控制硬件 | 默认十分钟观察 TX 重设、RX 失锁与扫描输出停顿；排除无输入/主动关闭，不代替光学黑屏检测 | [HDR 输出开关](bringup/2026-10-25-passthrough-hdr-switch.md) |
| packaging/kernel-edge/passthrough-preflight.py | 离线 Mac / VM，需 fdtget | 只读内核源码与 DTB | 检查 native/VD1/TX 声卡、simplefb、GPU 互斥和实际 split VCBUS 资源重叠；通过不代表运行支持 | [7.3 透传计划](passthrough-73-plan.md) |
| packaging/passthrough73/service.py | Linux，需设备库 | 独占 V4L2；显式 display 时占 KMS | 实验常驻采集与 SCM_RIGHTS 分发；输出资格未完成时 manager 保持 unsupported；不自动安装启用 | [离线移植](passthrough-73-offline.md) |
| packaging/kernel-edge/build-pt1.py | ARM64 VM | 编译与写指定输出目录，不部署 | uhd4配置派生pt1新release，完整Image/DT/modules与清单封存；须heavy | [pt1封存](passthrough-73-pt1.md) |
| tools/rootfs-policy.py | 板（root，随包安装） | 改启动项 | 根分区 ordered/commit=5，重启生效 | [Ubuntu 构建](ubuntu-build.md) |

## 板级服务源码（由 board/install.sh 或组件包安装）

| 入口 | 安装为 | 用途 | 文档 |
|---|---|---|---|
| tools/hdmi-setup.sh | /usr/local/sbin/hdmi-setup.sh | vdin0 + vfm_cap 配置并打开 HDMI 源 | [音视频](subsystems/video.md) |
| tools/hdr-curve.sh | vim4-hdr-curve | HDR10→SDR 映射表生成与写入；`tables` 为 5.15，`tables-edge` 保留高光，`apply` 自动选择接口；新5.15独立保存VDIN增益，原生模式同时请求VDIN1重载 | [音视频](subsystems/video.md#hdr-输入) |
| tools/kvm-gadget.sh | /usr/local/sbin/kvm-gadget.sh | USB gadget：键盘、绝对/相对鼠标、NCM | [USB](subsystems/usb.md) |
| tools/usb-pd-init.c | /usr/sbin/usb-pd-init | FUSB302B 5V PD 协商；成功调用板级 Python 模块原子保存合同；`--status` 只读 VBUS 状态 | [USB-PD](usb-pd.md) |
| board/vim4-wave5-monitor.py | /usr/libexec/vim4-wave5-monitor | 轮询 Wave5 隔离状态并记 journal；自动重启默认关闭，启用后仍要求应用均已停止且虚拟盘为空 | [音视频](subsystems/video.md#wave5-隔离告警) |
| board/60-vim4-watchdog.conf | /usr/lib/systemd/system.conf.d/60-vim4-watchdog.conf | board/install.sh 与 Ubuntu board 包安装；PID 1 在两种内核共用 30 秒运行、60 秒重启硬件看门狗策略，重启或 daemon-reexec 生效 | [部署](subsystems/deployment.md#一次性启动与硬件看门狗) |
| board/60-vim4-panic.conf | /usr/lib/sysctl.d/60-vim4-panic.conf | board/install.sh、Ubuntu board 包与正式部署窗口安装；两种内核启动时设置 panic_on_oops=1，与 panic=20 和硬件看门狗配合 | [部署](subsystems/deployment.md#一次性启动与硬件看门狗) |

## 应用回归（浏览器）

| 入口 | 应用 | 影响 | 覆盖 | 文档 |
|---|---|---|---|---|
| tools/video-smoke.mjs | NanoKVM | 独占 | WebRTC 实际编码、解码帧数/丢帧/丢包；Direct 首帧尺寸与持续收包（不等于持续呈现） | [板级工具](board-tools.md) |
| tools/audio-smoke.mjs | NanoKVM | 独占 | 音量控件与解码音频；配 hdmi-audio-tone | [功能状态](archive/feature-status.md) |
| tools/mic-smoke.mjs | NanoKVM | 独占，重新枚举 USB | Chrome 合成麦克风到 UAC2 播放 | 脚本头注释 |
| tools/usb-switch-check.mjs | NanoKVM | 独占，断开 USB | 麦克风/镜像组合切换与恢复 | [板级工具](board-tools.md#usb-切换回归) |
| tools/media-upload-check.mjs | NanoKVM | 独占，留下上传文件 | 镜像上传与网页终端 | [板级工具](board-tools.md#工具验证边界) |
| tools/input-check.mjs | NanoKVM | 独占，移动光标 | 键鼠延迟、长按、滚轮；配 input-target.swift、input-summary.py | [输入验证](input-latency.md) |
| tools/jetkvm-smoke.mjs | JetKVM | 独占 | 视频、JSON-RPC、网页终端；`--audio` 要求实际 HDMI 声音波形，测试输出静音 | [JetKVM](../kvm/VIM4.md) |
| tools/one-kvm-smoke.mjs | One-KVM | 独占 | H.264/H.265/MJPEG 解码、缓冲与呈现间隔尾部；`--seconds`/`--warmup` 控制测量窗口，`--audio` 检查波形 | [板级工具](board-tools.md) |
| tools/one-kvm-stability-check.mjs | One-KVM edge | 独占，切编码后恢复 | 4K60 持续解码、同帧标记校验、音画脉冲、温度/CPU/内存；须另启动同步运动源，JSONL 保存每 10 秒窗口 | [音视频](subsystems/video.md) |
| tools/one-kvm-av-sync-check.mjs、tools/av-sync-probe.mjs | Mac / One-KVM edge | 校准无；上板独占、切编码后恢复 | 标签页播放输出回环、逐样本音频脉冲与预计视频显示时间；`--calibrate=FILE --expected-ms=120` 校准已知偏移，板端须同步源 | 脚本头注释 |
| tools/one-kvm-audio-check.mjs | One-KVM | 独占 | Opus WebSocket 音频，静音判失败 | [板级工具](board-tools.md) |
| tools/one-kvm-audio-continuity.mjs | Mac / One-KVM | 上板独占；--calibrate 本地对照 | 440Hz 音频逐样本连续性、直接 AudioData 与可选 Worklet/Opus 对照、同步 getStats；--headed 真实 Chrome，调用者持双锁并管理 HDMI 音源 | 脚本头注释 |
| tools/one-kvm-recording-check.mjs | One-KVM | 独占 | H.264/H.265 带声音录屏、关网页续录、下载、断流与重启；仅清理本次录像 | [板级工具](board-tools.md) |
| tools/one-kvm-settings-check.mjs | One-KVM | 独占，改 EDID/HDR 后恢复 | 视频设置往返 | [One-KVM](../One-KVM/VIM4.md) |
| tools/one-kvm-board-check.mjs | One-KVM | 独占，改 EDID/HDR 后恢复 | 原生板级接口、同一网页的 UHD/FHD 切换与 HDR 曲线；不覆盖自定义 EDID | 脚本头注释 |
| tools/nanokvm-board-check.mjs | NanoKVM | 独占，改 EDID 后恢复 | 原生 EDID 接口与同一网页的 FHD/UHD 恢复；不覆盖自定义 EDID | 脚本头注释 |
| tools/edge-jpeg-check.py | 板（root），7.x | 独占，应用须停止 | VDIN 硬件缩放、JPEG DMA 连续帧、质量、IRQ 与 CMA 回收；需运动 HDMI 源另验内容 | 脚本头注释 |
| tools/edge-jpeg-profile.py | 板（root），7.x | 独占 JPEG，应用须停止；不采集或改时钟 | 用一帧 NV12 拆分命令、等待、完成 ioctl 和输出复制；可跳过复制，保存新报告及 JPEG | 脚本头注释 |
| tools/one-kvm-scaling-check.mjs | One-KVM edge | 独占，改输出尺寸/帧率/质量后恢复；可暂停并恢复空闲 UU | H.264/H.265/MJPEG 往返、完整画面动态标记、输入时序和 DMA 回收；须另启动运动 HDMI 源；--require-hdr 核对 RX，--mjpeg-max-rate 请求 60fps，--mjpeg-only 只测 JPEG，--mjpeg-frames=600 延长每档采样 | 脚本头注释 |
| tools/one-kvm-features-check.mjs | One-KVM | 独占 | 终端、扩展、看门狗；需本地 FRP 17700 | [板级工具](board-tools.md) |
| tools/one-kvm-drive-check.mjs | One-KVM | 独占，可能创建虚拟盘 | Ventoy 虚拟盘与文件往返 | [Ubuntu 构建](ubuntu-build.md) |
| tools/one-kvm-usb-check.mjs | One-KVM | 独占，重新枚举 USB；--hid-only 短暂覆盖桌面并恢复指针 | Mac 主机键鼠、ISO 挂载；--hid-only 使用 input-target 验证实际方向键、两种鼠标、点击和滚轮 | [板级工具](board-tools.md) |
| tools/one-kvm-usb-profile-check.mjs | One-KVM | 独占，改 USB 组合后恢复；录音只选择 USB 输入 | HID/UAC/网卡组合与超限回滚、拒绝内核告警；--audio 原生录音，--browser-audio 指定 USB 设备波形；--output-prefix 保存独立记录 | [板级工具](board-tools.md) |
| tools/one-kvm-usb-media-check.mjs | Mac / One-KVM | 独占，上传专用 EDGEUSB21 FAT 镜像；主机弹出后删除本次文件并恢复配置 | 只读/可写、1MiB 哈希、fsck、五端点与挂载保护；`--service=one-kvm` 验正式入口，`--manager-url=URL` 检查内核/应用切换拒绝 | 脚本头注释 |
| tools/one-kvm-usb-network-host.py | Mac → 板 | 独占，只读当前 USB 网卡配置；临时监听器绑定 USB IP，退出终止，不修改主机网络 | 手动启用一种 USB 网卡后，核对 DHCP ACK 并经指定接口双向传输 1MiB、比较哈希；以 SSH 控制板端 | 脚本头注释 |
| tools/one-kvm-usb-board-check.py | 板（root） | 独占，应用停止 | 板端 USB 助手枚举与恢复 | [板级工具](board-tools.md) |
| tools/one-kvm-uu-ui-check.mjs | 一次性容器实例 | 无（禁止对板子账户运行） | UU 远程绑定界面 | [上板记录](bringup/2026-10-15-uu-output-controls-identity.md) |
| tools/pikvm-smoke.mjs | PiKVM | 独占 | 解码、截图、MJPEG 重连与可选 Mac USB 输入；`--audio --existing-audio` 使用已运行的 HDMI 音源 | [Ubuntu 构建](ubuntu-build.md#pikvm-组件) |
| tools/kvm-switch-check.mjs | 管理器 | 独占，切换应用 | 四应用互斥与解码，恢复原选择；`VIM4_KVM_URL` 可指定 SSH 转发的网关 | [板级工具](board-tools.md#kvm-应用切换回归) |
| tools/kernel-switch-check.mjs | Mac → 板 | 独占、重启两次 | `--exclusive --reboot` 验证面板 7→5→7、配置双向保留及临时镜像哈希；`--switch-apps` 在两边跑四应用循环；结束恢复设置并删除本次文件 | 脚本头注释 |
| tools/manager-login.mjs | 管理器 | 创建登录会话 | 浏览器测试共享统一登录；导出 loginManager(context, managerURL) | 本页 |

## 诊断与测量

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| tools/rtp-udp-bench.c | Linux ARM64 容器 / 板 | 无硬件访问；板端占 CPU，须协调测量窗口 | sendto 与 sendmmsg 8/32/64 的逐帧 loopback 对照，完整包校验、失败保留；不含 SRTP/ICE | [发送基准](bringup/2026-10-25-rtp-send-benchmark.md) |
| tools/encoder-vbv-bench.c、tools/encoder-vbv-probe.c | Linux ARM64 / 板 | bench run 独占编码；fixture/reference 无；probe 仅限私有测试进程 | 固定4K输入、同PTS编码计时、完整AU记录；匹配厂商头文件的VPU_EncOpen探针只改变VBV，0为观察对照，不安装到应用 | [VBV 对照](bringup/2026-10-26-encoder-vbv.md) |
| tools/encoder-vbv-run.py | 板 | 独占；临时停启One-KVM并恢复原active状态 | 24窗口原库/观察/500ms/100ms固定输入对照，其他KVM须已停止；调用者持双锁，失败保留证据 | [VBV 对照](bringup/2026-10-26-encoder-vbv.md) |
| tools/encoder-vbv-summary.py、tools/encoder-vbv-quality.py | 离线；quality需ffmpeg | 不访问硬件；解码需避开性能窗口 | 分场景峰值、编码耗时、固定带宽FIFO模型；选定帧与原始输入的PSNR/SSIM，不代表真实网络或全片画质 | [VBV 对照](bringup/2026-10-26-encoder-vbv.md) |
| tools/display-color.py、tools/display-color.c | 离线 / 板（root） | chart/analyze/diff 无；run 独占显示/采集；snapshot 只读控制和矩阵 | KMS dumb 图案、V4L2 原始 NV12 三帧、≤2 码值色块分析；5.15 同 sink 寄存器对照、TX/RX AVI；调用者持双锁并管理服务/一次性启动 | [颜色校准](display-color-calibration.md) |
| tools/hdmi-color-check.py | 离线，PNG分析需Pillow | 不接触板子 | 按16色块的RX前矩阵10-bit Y/Cb/Cr探针值，计算SDR709或PQ2020→SDR参考并统计解码帧码值误差；不替代显示器测色 | [HDR切换颜色修复](bringup/2026-10-25-native-hdr-color.md) |
| tools/perf-baseline.py | 离线 | 无 | 5.15/7.3命令计划与三组A/B/A单指标门禁；缺失/受干扰不算通过，不执行命令 | [性能基线](performance-baseline.md) |
| tools/perf-sensors.py | 板 | 读；性能窗口内 | 1Hz温度/功率/频率/runtime状态JSONL，不改时钟；缺传感器不记0 | [性能基线](performance-baseline.md) |
| tools/vendor-boot-plan.py | 离线 | 无 | 从启动快照和已解析厂商profile生成一次性配置；不stage、不改默认、不重启 | [厂商对照启动](vendor-boot-baseline.md) |
| tools/latency-source.swift | Mac | 占用 HDMI 画面；可输出 HDMI 音频 | 把帧号画进 HDMI 输出；`--display-link` 可选跟随刷新，默认60Hz Timer；`--motion` 运动网格，`--motion-cycle=运动秒数,周期秒数` 交替滚动/静止背景并记录状态；`--verify-coherence` 三处标记，`--hdr-chart`/`--color-chart` 灰阶/色块，`--no-labels` 禁用字体；仅显式 `--sync-audio=设备名` 输出同步闪块/音调，不改默认音频设备 | [延迟测量](latency.md) |
| tools/hdmi-resolution-source.swift | Mac | 临时覆盖所选 HDMI 桌面 | 原生 UHD 单像素条纹与参考 PNG；不切模式、不注入输入 | [清晰度复核](bringup/2026-10-20-edge-uhd-detail.md) |
| tools/hdmi-resolution-check.py | 离线 | 无 | Pillow 检查原生解码帧的亮度空间细节，拒绝 1080p 放大负例 | [清晰度复核](bringup/2026-10-20-edge-uhd-detail.md) |
| tools/latency-receiver.mjs | Mac | 独占 | 像素帧号、RTP 时间戳、收帧时间与呈现节奏；`--rtp-timeline` 为每次回调保留 RTP 身份与校准墙钟，`--expect-codec` 拒绝非预期编码，`--stats-interval` 记录长测窗口；GPU 裁剪及 `--cpu-readback` 对照 | [延迟测量](latency.md) |
| tools/latency-summary.py | Mac | 无 | 匹配时间戳与呈现节奏；`--window-start`/`--window-seconds` 比较长测首尾，拒绝错误帧号匹配及失准时钟 | [延迟测量](latency.md) |
| tools/latency-rtp-summary.py | 离线 | 无 | 用独立解码验证的 AU→RTP 映射关联所有回调，报告缺失关联及像素回读错帧；拒绝重复映射、SSRC 变化和失准时钟，不通过推算帧周期补帧号 | [延迟测量](latency.md) |
| tools/video-timing-summary.py | Mac | 无 | 汇总 VIM4_VIDEO_TIMING 分段计时 | [延迟测量](latency.md) |
| tools/input-target.swift | Mac | 覆盖显示器 | input-check 的临时接收窗口 | [输入验证](input-latency.md) |
| tools/input-summary.py | Mac | 无 | 汇总 input-check 日志 | [输入验证](input-latency.md) |
| tools/key-repeat.html | 被控电脑浏览器 | 只接收本页面手动输入，不注入键鼠 | Backspace 直连 / KVM 长按频率、首次重复等待、释放事件对照，导出 JSON | [输入验证](input-latency.md#手动对照-backspace-长按) |
| tools/uu-scroll-probe.swift | Mac | 无 | 只测本窗口收到的滚轮事件，不注入输入 | [UU 滚轮](uu-scroll.md) |
| tools/hdmi-audio-tone.c | Mac | 无 | 只向 HDMI 设备播放 440Hz | [功能状态](archive/feature-status.md) |
| tools/uac-record-level.swift | Mac | 无（需麦克风权限） | 录 UAC2 电平与主频 | [板级工具](board-tools.md) |
| tools/hdmi-capture.sh | 板（root） | 独占采集 | 经 vfm_cap 抓一帧 PNG | [内核](kernel.md) |
| tools/hdmi-control-watch.py | 板（root） | 读 | 采样 RX port 1 控制状态 | [HDMI 恢复审查](archive/hdmi-recovery-review.md#控制状态采样工具) |
| tools/hid-rebind-check.py | 板（root） | 独占，应用停止；旧内核会 panic | HID epoll 跨 UDC 重新绑定 | [内核](kernel.md) |
| tools/crg-udc-check.py | 板（root） | 独占，仅 7.3 CRG 测试内核 | 最小 HID 重绑定；`--storage-image` 增加三种 HID＋只读盘，等待主机弹出确认；可保留旧 fd/epoll | [CRG 实测](bringup/2026-10-19-crg-udc.md) |
| tools/crg-composite-host-check.py | Mac → 板 | 独占，移动光标、临时窗口接收按键、枚举测试盘 | 配合 CRG 板端工具，核对键鼠、只读盘文件哈希、安全弹出与重绑定 | [CRG 组合实测](bringup/2026-10-19-crg-composite.md) |
| tools/hdmirx-resource-check.py | 板（root） | 独占，仅 7.3 HDMI RX 测试内核；PHY 模式改变 EDID／HPD | 资源回收与旧 fd；`--phy-firmware` 验证固定频率 PLL，`--reject-firmware` 在所选模式验证失败 probe | [HDMI PHY 实测](bringup/2026-10-19-hdmirx-phy.md) |
| tools/hdmirx-ddc-host-check.py | Mac → 板 | 独占，加载接收模块并改变 EDID／HPD，影响 HDMI 显示连接 | 比较接收器 RAM 与 Mac HDMI 端实际读到的不同 EDID；不验证视频帧 | [HDMI DDC 实测](bringup/2026-10-19-hdmirx-ddc.md) |
| tools/hdmirx-frame-check.py | Mac / Linux | 无 | 离线校验 1080p/4K RGB24、NV12 的三处帧号及推进；--check-colors 增加颜色块，输入来自 coherence source | [4K 与编码](bringup/2026-10-19-wave521-uhd.md) |
| tools/hdmirx-stream-check.c | 板（root） | 独占，仅 7.3 HDMI 实验内核 | 四缓冲运动检查、耗尽恢复及反复开关流；`--dmabuf` 验证导出、队列重建和重映射，`--hold-exports` 等待控制端释放；需先编译 | [HDMI DMA-buf](bringup/2026-10-19-hdmirx-dmabuf.md) |
| tools/hdmirx-soak.c | 板（root） | 独占采集，调用者持双锁并停启应用 | 原生 NV12 逐帧 ERROR/sequence/单调时间；`--count-errors` 继续计数有效帧率但仍报失败，`--markers` 检查三处运动帧号；不改 EDID/HPD | 脚本头注释 |
| tools/hdmirx-encode-check.py | 板（root）/ Linux | capture 独占实验采集；verify 离线 | DMA-buf采集/编码、CPU/pad时间；HDR2退休配check_retirement.py，噪声底配compare_frames.py；packaging/hdr2-pq/video-recovery.mjs仅接收视频，需独占、不发HID/音频；--literal-host-candidates仅改本次Chrome；HDR2_SAMPLE_MS=50细采样，先验4K解码推进 | [4K 与编码](bringup/2026-10-19-wave521-uhd.md)、[恢复门禁](bringup/2026-10-31-hdr2-recovery.md) |
| packaging/hdr2-pq/mcp-screenshot.py | Mac → 板 | 持板锁，只读截图 | 每次RPC使用新的curl连接；读取既有凭据经stdin传递，不暴露键鼠工具、不输出密钥；--output指定不存在的新图片 | [MCP与接收诊断](bringup/2026-10-31-hdr2-mcp-ice-pq.md) |
| tools/wave5-lifecycle-check.py | 板 | 独占编码；停视频应用 | 实验 7.3 的 H.264/H.265 图案编码反复 EOS；检查视频句柄与 CMA 回收，首轮泄漏即停止 | [One-KVM 接入](bringup/2026-10-20-onekvm-wave5.md) |
| tools/onekvm-local-bench.py | Mac → 容器；可选当前内核板子 | 默认无；--board 占 CPU/内存带宽，不停服务 | DMA 平面、压缩缓存与复制基准；可先跑离线所有权、输入状态等待、profile 和逐行刷新回归 | [本地基准](local-video-benchmark.md) |
| tools/vim4-driver-bench.c | 板；需先编译 | 独占采集/编码；调用者停启应用 | 原生纯采集、H.264/H.265/JPEG 驱动基准；CPU、pad 耗时、CMA；支持 7.x/5.15，`--secondary --fps=120`测1080p独立采集；独立录像验证 | [驱动基准](driver-benchmark.md) |
| tools/test-fan-policy.sh | VM | 无 | 编译内核风扇插值函数做断言 | [内核](kernel.md) |
