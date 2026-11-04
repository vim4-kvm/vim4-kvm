# 工具目录

本页只索引入口、用途和影响；命令从仓库根运行，参数/默认值/清单以入口源码头注释或 `--help` 为准。
当前操作合同统一见[板级工具](board-tools.md)，登录见[公共前提](board-tools.md#浏览器测试的公共前提)，占板见[短窗口](board-window.md#占板时间最短化)。
导航：[构建](#工作区构建与打包) · [板操作](#板级操作) · [服务](#板级服务源码由-boardinstallsh-或组件包安装) · [应用回归](#应用回归浏览器) · [诊断](#诊断与测量)。
“独占”须先协调；“破坏”涉及清盘/重启，依当前授权执行；“无”表示无硬件访问。构建与实测不能混为通过。
增删工具同步本页；[文档检查](../tests/test_docs.py)检查工具覆盖、链接与字面脚本路径，不验证命令行为或packaging目录完整性。

## 浏览器测试的公共前提

见[唯一公共前提](board-tools.md#浏览器测试的公共前提)。

## 工作区、构建与打包

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| [packaging/kernel/package-unified.py](../packaging/kernel/package-unified.py) | VM | 无 | 主线整包封存 | [主线内核](kernel-mainline.md) |
| [packaging/hdr10/persistent-r14e.py](../packaging/hdr10/persistent-r14e.py) | Mac → 板 | 独占，安装私有运行时；不改默认或重启 | 构建工具 | [HDR10](hdr10-remote-73.md) |
| [packaging/hdr10/assemble-phase2.py、phase2-run](../packaging/hdr10/assemble-phase2.py) | Linux ARM64 / RAM 候选 | 组装无；运行独占 | 构建工具 | [第二阶段记录](bringup/2026-10-31-hdr10-phase2-offline.md) |
| [packaging/hdr10/ram-payload.py](../packaging/hdr10/ram-payload.py) | VM | 无 | RAM载荷封装 | [HDR10](hdr10-remote-73.md) |
| [packaging/kernel/package-hdr10.py](../packaging/kernel/package-hdr10.py) | VM | 无 | HDR候选封包 | [HDR10](hdr10-remote-73.md) |
| [packaging/kernel/test_gstreamer_p010.py、test_gstreamer_pq.py](../packaging/kernel/test_gstreamer_p010.py) | Linux 宿主 | 无 | 构建工具 | [HDR10](hdr10-remote-73.md) |
| [packaging/kernel/hdmi-mode-fixture.py、hdmi-modes.json](../packaging/kernel/hdmi-mode-fixture.py) | 宿主 / 板 | prepare/verify 无；measure/read-edid 需板票，只读 | 输入模式验证 | [主线内核](kernel-mainline.md) |
| [vm](../tools/vm) | Mac → OrbStack VM | 无板子访问；new/rm 改任务工作树，push 写远端 | status 核对 origin/SHA | [工作区](workspace.md#构建) |
| [memory-bench.c、memory-bench.py](../tools/memory-bench.c) | C：Linux ARM64编译；runner：Linux/板 | 独占CPU/内存/tmpfs；无频率写入、部署、HID | 内存吞吐基准 | [内存拷贝审查](memory-copy-audit.md)、[绑核门禁与配置草案](nodebug-performance-gate.md) |
| [gpu-diagnose.py、gpu-cl-map.c](../tools/gpu-diagnose.py) | 板；CL工具先ARM64编译 | 独占GPU；诊断器可临时锁频/PM/profiling并恢复；不写电压、不ptrace | GPU性能诊断 | [GPU性能复核](gpu-performance-diagnosis.md) |
| [packaging/gpu/](../packaging/gpu/) | Docker ARM64；probe：板 | 构建无；probe占GPU | 构建工具 | [GPU运行时](bringup/2026-10-30-gpu-runtime.md)、[HDR规格](gpu-hdr-pipeline.md) |
| [npu-probe.c、npu-validate.py、npu-models.json](../tools/npu-probe.c) | 编译：ARM64；run：板；compare：Mac/VM | run 占用 NPU，写新结果目录；无部署、HID、声音 | NPU推理验证 | [ADLA离线候选](npu-adla.md)、[端到端分段](npu-e2e-timing.md) |
| [npu-uapi-probe.c](../tools/npu-uapi-probe.c) | ARM64编译→板 | 占用NPU兼容接口；无推理、HID或声音 | 初始化MMU上下文后测试ATTACH别名 | [ADLA候选与验收](npu-adla.md) |
| [packaging/kernel/build-gstreamer.py](../packaging/kernel/build-gstreamer.py) | 容器/VM | 无 | 私有视频插件构建 | [音视频](subsystems/video.md) |
| [packaging/kernel/test_gstreamer_visible_crop.py](../packaging/kernel/test_gstreamer_visible_crop.py) | 容器/VM | 无 | 可见尺寸协商回放 | [音视频](subsystems/video.md) |
| [packaging/kernel/maintain.py](../packaging/kernel/maintain.py) | Linux ARM64 VM | 无 | 补丁导出与前移 | [补丁清单](archive/kernel-patch-inventory.md) |
| [packaging/kernel/register-runtime.py](../packaging/kernel/register-runtime.py) | VM / 板 | inventory 无；register 登记；install 安装 | 构建工具 | [正式安装合同](kernel-mainline.md#正式构建与整包升级) |
| [packaging/kernel/package-final.py](../packaging/kernel/package-final.py) | VM | 无 | 构建工具 | [M1 合入](bringup/2026-10-23-display-m2.md) |
| [packaging/kernel/display-once.py、display-once-init.c](../packaging/kernel/display-once.py) | VM / 板 | prepare 无；stage 独占；串口选择后重启 | 构建工具 | [M1 安全网](bringup/2026-10-23-display-m1-safety.md) |
| [packaging/kernel/final-window.py、final-board.py](../packaging/kernel/final-window.py) | Mac → 板 | stage/dry-run 无；execute 独占、重启 | 构建工具 | [pstore 部署与回退](bringup/2026-10-22-edge-pstore-deploy.md) |
| [packaging/kernel/final-regression.py、final-manager-check.mjs](../packaging/kernel/final-regression.py) | Mac → 板 | prepare 无；run 独占、改 HDMI/USB 设置后恢复 | 构建工具 | [正式版部署准备](bringup/2026-10-22-deploy-7-3-final-prep.md) |
| [packaging/kernel/package-vdec.py](../packaging/kernel/package-vdec.py) | VM | 无 | 解码候选封包 | [MDEC 远程窗口](bringup/2026-10-23-vdec-mdec-window.md) |
| [packaging/kernel/vdec-window.py](../packaging/kernel/vdec-window.py) | Mac → 板 | 默认离线；execute 双锁、加载模块；旧 boot 动作装内核 | 构建工具 | [寄存器差分](bringup/2026-10-23-vdec-register-diff.md) |
| [packaging/kernel/vdec-register-dump.c](../packaging/kernel/vdec-register-dump.c) | 板 | 双锁、已上电期间只读 MMIO | 构建工具 | [寄存器差分](bringup/2026-10-23-vdec-register-diff.md) |
| [packaging/kernel/check-wifi-p2p.py](../packaging/kernel/check-wifi-p2p.py) | 板 | 独占、临时接管 Wi-Fi 后恢复 | Wi-Fi与P2P验证 | [Wi-Fi Direct](bringup/2026-10-21-edge-wifi-p2p.md) |
| [workspace.py](../tools/workspace.py) | Mac / CI | 无 | 工作区管理与构建 | [工作区](workspace.md) |
| [mali-runtime.py](../tools/mali-runtime.py) | fetch：Mac / Linux；install：板（root） | 下载或写私有 GPU 目录，不重启服务 | 私有GPU运行时安装 | [HDR GPU](bringup/2026-10-26-hdr-gpu.md) |
| [vrr-edid.py](../tools/vrr-edid.py) | Mac / Linux | 只写指定的新文件，不访问板子 | 显式实验范围生成远程VRR EDID | [VRR准备](vrr-preparation.md) |
| [ubuntu-build.py](../tools/ubuntu-build.py) | Mac / CI → Docker | 无 | package/verify 七组件 | [Ubuntu 构建](ubuntu-build.md) |
| [ubuntu-image.py](../tools/ubuntu-image.py) | Mac → OrbStack | 无 | 候选镜像组装 | [候选镜像](ubuntu-image.md) |
| [packaging/ubuntu/](../packaging/ubuntu/) | 容器 | 无 | 用户态组件打包 | [Ubuntu 构建](ubuntu-build.md) |
| [packaging/kernel/](../packaging/kernel/) | VM | 构建无；准备工具改固件目录；Wi-Fi 转储保存后释放其内核副本 | 构建工具 | [内核](kernel.md) |
| [packaging/kernel/](../packaging/kernel/) | Linux ARM64 VM / 板 | 构建无；准备工具改固件目录；Wi-Fi 转储保存后释放其内核副本 | 构建工具 | [新内核基线](kernel-mainline.md)、[Wi-Fi 排查](bringup/2026-10-21-edge-wifi-fps.md) |
| [packaging/kernel/one-kvm-edge、one-kvm-edge-prepare、one-kvm-edge.service](../packaging/kernel/one-kvm-edge) | 板 | 独占 | 构建工具 | [新内核基线](kernel-mainline.md) |
| [packaging/image/](../packaging/image/) | VM（root） | 无 | 构建工具 | [候选镜像](ubuntu-image.md) |
| tests/ | Mac | 无 | 离线回归 | 本页 |

## 板级操作

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| [packaging/kbase/build.py、package.py、run.py、check-style.py、check-semantics.py、check-heaps.py、clpeak-subset.py、dma-profile.py、default-parity.py、resolve-egl.c、heaps/vim4_kbase_heaps.c、dvfs/governor_vim4.c](../packaging/kbase/build.py) | build/package/check：宿主/ARM64 VM；run/CL/模块：板 | build/package/check/resolve无硬件访问；run/CL占GPU，parity独占GPU并只读温度，profile临时创建具名trace实例/事件，heap占候选CMA，governor调GPU频率 | 外部GPU模块构建与门禁 | [kbase后备候选](gpu-kbase-7x.md)、[MMU与heap合同](gpu-kbase-mmu-heaps.md) |
| [mali-dma-probe.c、mali-dma-probe.comp、mali-cl-probe.c](../tools/mali-dma-probe.c) | ARM64 容器编译 → 板 | GPU计算与临时内存；不操作采集/编码 | GPU缓冲导入校验 | [kbase候选](gpu-kbase-7x.md) |
| [gbm-scanout-probe.c](../tools/gbm-scanout-probe.c) | ARM64容器编译→板 | 独占显示；保持当前mode，恢复原FB，不抢DRM master | GBM扫描输出验证 | [kbase候选](gpu-kbase-7x.md) |
| [packaging/hdr10/phase2-window.py、m6-gates.py、phase2-board.py](../packaging/hdr10/phase2-window.py) | Mac → 板/M6 | 独占、RAM 重启、切换配置及 M6 HDR 后恢复 | HDR批量窗口 | [第二阶段记录](bringup/2026-10-31-hdr10-phase2-offline.md) |
| [packaging/kernel/hdr10-prepare、hdr10-run](../packaging/kernel/hdr10-prepare) | 板，匹配 RAM 候选 | 独占采集/编码及 8081；prepare 加载模块 | 构建工具 | [HDR10](hdr10-remote-73.md) |
| [board-queue](../tools/board-queue) | Mac / Linux，同一协调主机 | 仅本机锁与票据；run 的影响由命令决定 | 板票与采样协调 | [短窗口](board-window.md) |
| [board-window](../tools/board-window) | Mac → 板 | collect --readonly 读；baseline/receiver/MCP 截图占采集；MCP HDR 发 HID；boot-candidate/return-baseline 重启 | RAM链式启动与恢复 | [短窗口](board-window.md) |
| [board-window-receiver.mjs、board-window-timing.mjs](../tools/board-window-receiver.mjs) | Mac / Node | 接收占用编码器；compare 仅本机图片 | RAM链式启动与恢复 | [短窗口](board-window.md) |
| [gpu-compare.py](../tools/gpu-compare.py) | 板 | 独占 | GPU运行时配对 | [GPU运行时](bringup/2026-10-30-gpu-runtime.md) |
| [board.py check](../tools/board.py) | Mac | 读 | 板状态检查 | [板级工具](board-tools.md) |
| [board.py deploy --exclusive](../tools/board.py) | Mac | 独占 | 组件升级 | [板级工具](board-tools.md#增量开发闭环) |
| [board.py verify](../tools/board.py) | Mac | 独占 | 部署后 hid/audio/video 实测 | [板级工具](board-tools.md) |
| [board.py provision / enroll](../tools/board.py) | Mac | 改板配置 | 公钥与开发用免密 sudo | [板级工具](board-tools.md#操作前约定) |
| [board.py recover / flash](../tools/board.py) | Mac | 破坏 | 进入 OOWOW | [板级工具](board-tools.md#本地候选镜像一键刷写) |
| [install-components.sh](../tools/install-components.sh) | 板（由 deploy 调用） | 独占 | 组件安装与迁移 | [板级工具](board-tools.md) |
| [uart-run.py](../tools/uart-run.py) | Mac | 取决于命令 | 串口执行命令 | [部署](subsystems/deployment.md) |
| [uart-log.py](../tools/uart-log.py) | Mac | 读（`--send` 除外） | 只读抓串口日志 | [部署](subsystems/deployment.md) |
| [oowow-flash.sh](../tools/oowow-flash.sh) | Mac（板在 OOWOW） | 破坏 | 手工 URL 刷写 | [板级工具](board-tools.md) |
| [kernel-install.sh](../tools/kernel-install.sh) | 板（root） | 安装内核 | 厂商包安装 | [内核](kernel.md) |
| [packaging/kernel/promote.py](../packaging/kernel/promote.py) | 板（root，双锁） | 改默认；可删除显式淘汰的未登记旧产物 | 厂商候选登记 | [原生 HDR 交付](bringup/2026-10-25-native-hdr-dual-path.md) |
| [passthrough-monitor.py](../tools/passthrough-monitor.py) | 板（只读硬件，写指定日志） | 不控制硬件 | 透传停顿观察 | [HDR 输出开关](bringup/2026-10-25-passthrough-hdr-switch.md) |
| [rootfs-policy.py](../tools/rootfs-policy.py) | 板（root，随包安装） | 改启动项 | 根分区 ordered/commit=5 | [Ubuntu 构建](ubuntu-build.md) |

## 板级服务源码（由 board/install.sh 或组件包安装）


| 入口 | 安装为 | 用途 | 文档 |
|---|---|---|---|
| [board/vim4-ethernet-generator.py](../board/vim4-ethernet-generator.py) | /usr/lib/systemd/system-generators/（随 board 包） | 读取 U-Boot 每板 eFuse MAC 并在 /run 生成 .link | [主线内核](kernel-mainline.md) |
| [hdmi-setup.sh](../tools/hdmi-setup.sh) | /usr/local/sbin/hdmi-setup.sh | vdin0 + vfm_cap 配置并打开 HDMI 源 | [音视频](subsystems/video.md) |
| [hdr-curve.sh](../tools/hdr-curve.sh) | vim4-hdr-curve | HDR10→SDR 映射表生成与写入 | [音视频](subsystems/video.md#hdr-输入) |
| [kvm-gadget.sh](../tools/kvm-gadget.sh) | /usr/local/sbin/kvm-gadget.sh | USB gadget：键盘、绝对/相对鼠标、NCM | [USB](subsystems/usb.md) |
| [usb-pd-init.c](../tools/usb-pd-init.c) | /usr/sbin/usb-pd-init | FUSB302B 5V PD 协商 | [USB-PD](usb-pd.md) |
| [board/vim4-wave5-monitor.py](../board/vim4-wave5-monitor.py) | /usr/libexec/vim4-wave5-monitor | 轮询 Wave5 隔离状态并记 journal | [音视频](subsystems/video.md#wave5-隔离告警) |
| [board/60-vim4-watchdog.conf](../board/60-vim4-watchdog.conf) | /usr/lib/systemd/system.conf.d/60-vim4-watchdog.conf | board/install.sh 与 Ubuntu board 包安装 | [部署](subsystems/deployment.md#一次性启动与硬件看门狗) |
| [board/60-vim4-panic.conf](../board/60-vim4-panic.conf) | /usr/lib/sysctl.d/60-vim4-panic.conf | board/install.sh、Ubuntu board 包与正式部署窗口安装 | [部署](subsystems/deployment.md#一次性启动与硬件看门狗) |

## 应用回归（浏览器）

| 入口 | 应用 | 影响 | 覆盖 | 文档 |
|---|---|---|---|---|
| [video-smoke.mjs](../tools/video-smoke.mjs) | NanoKVM | 独占 | WebRTC 实际编码、解码帧数/丢帧/丢包 | [板级工具](board-tools.md) |
| [audio-smoke.mjs](../tools/audio-smoke.mjs) | NanoKVM | 独占 | 音量控件与解码音频 | [功能状态](archive/feature-status.md) |
| [mic-smoke.mjs](../tools/mic-smoke.mjs) | NanoKVM | 独占，重新枚举 USB | Chrome 合成麦克风到 UAC2 播放 | 脚本头注释 |
| [usb-switch-check.mjs](../tools/usb-switch-check.mjs) | NanoKVM | 独占，断开 USB | 麦克风/镜像组合切换与恢复 | [板级工具](board-tools.md#usb-切换回归) |
| [media-upload-check.mjs](../tools/media-upload-check.mjs) | NanoKVM | 独占，留下上传文件 | 镜像上传与网页终端 | [板级工具](board-tools.md#工具验证边界) |
| [input-check.mjs](../tools/input-check.mjs) | NanoKVM | 独占，移动光标 | 键鼠延迟、长按、滚轮 | [输入验证](input-latency.md) |
| [jetkvm-smoke.mjs](../tools/jetkvm-smoke.mjs) | JetKVM | 独占 | 视频、JSON-RPC、网页终端 | [JetKVM](../kvm/VIM4.md) |
| [one-kvm-smoke.mjs](../tools/one-kvm-smoke.mjs) | One-KVM | 独占 | 视频解码与播放节奏 | [板级工具](board-tools.md) |
| [one-kvm-stability-check.mjs](../tools/one-kvm-stability-check.mjs) | One-KVM edge | 独占，切编码后恢复 | 持续视频与标记验证 | [音视频](subsystems/video.md) |
| [one-kvm-av-sync-check.mjs、tools/av-sync-probe.mjs](../tools/one-kvm-av-sync-check.mjs) | Mac / One-KVM edge | 校准无；上板独占、切编码后恢复 | 音画同步观测 | 脚本头注释 |
| [one-kvm-audio-check.mjs](../tools/one-kvm-audio-check.mjs) | One-KVM | 独占 | Opus WebSocket 音频 | [板级工具](board-tools.md) |
| [one-kvm-audio-continuity.mjs](../tools/one-kvm-audio-continuity.mjs) | Mac / One-KVM | 上板独占；--calibrate 本地对照 | 音频连续性验证 | 脚本头注释 |
| [one-kvm-recording-check.mjs](../tools/one-kvm-recording-check.mjs) | One-KVM | 独占 | 录屏生命周期验证 | [板级工具](board-tools.md) |
| [one-kvm-settings-check.mjs](../tools/one-kvm-settings-check.mjs) | One-KVM | 独占，改 EDID/HDR 后恢复 | 视频设置往返 | [One-KVM](../One-KVM/VIM4.md) |
| [one-kvm-board-check.mjs](../tools/one-kvm-board-check.mjs) | One-KVM | 独占，改 EDID/HDR 后恢复 | 板级设置回归 | 脚本头注释 |
| [nanokvm-board-check.mjs](../tools/nanokvm-board-check.mjs) | NanoKVM | 独占，改 EDID 后恢复 | EDID与模式恢复 | 脚本头注释 |
| [edge-jpeg-check.py](../tools/edge-jpeg-check.py) | 板（root），7.x | 独占，应用须停止 | JPEG驱动验证 | 脚本头注释 |
| [edge-jpeg-profile.py](../tools/edge-jpeg-profile.py) | 板（root），7.x | 独占 JPEG，应用须停止；不采集或改时钟 | JPEG分段计时 | 脚本头注释 |
| [one-kvm-scaling-check.mjs](../tools/one-kvm-scaling-check.mjs) | One-KVM edge | 独占，改输出尺寸/帧率/质量后恢复；可暂停并恢复空闲 UU | 缩放与帧率回归 | 脚本头注释 |
| [one-kvm-features-check.mjs](../tools/one-kvm-features-check.mjs) | One-KVM | 独占 | 终端、扩展、看门狗 | [板级工具](board-tools.md) |
| [one-kvm-drive-check.mjs](../tools/one-kvm-drive-check.mjs) | One-KVM | 独占，可能创建虚拟盘 | Ventoy 虚拟盘与文件往返 | [Ubuntu 构建](ubuntu-build.md) |
| [one-kvm-usb-check.mjs](../tools/one-kvm-usb-check.mjs) | One-KVM | 独占，重新枚举 USB；--hid-only 短暂覆盖桌面并恢复指针 | Mac 主机键鼠、ISO 挂载 | [板级工具](board-tools.md) |
| [one-kvm-usb-profile-check.mjs](../tools/one-kvm-usb-profile-check.mjs) | One-KVM | 独占，改 USB 组合后恢复；录音只选择 USB 输入 | USB组合与回滚 | [板级工具](board-tools.md) |
| [one-kvm-usb-media-check.mjs](../tools/one-kvm-usb-media-check.mjs) | Mac / One-KVM | 独占，上传专用 EDGEUSB21 FAT 镜像；主机弹出后删除本次文件并恢复配置 | USB介质完整性 | 脚本头注释 |
| [one-kvm-usb-network-host.py](../tools/one-kvm-usb-network-host.py) | Mac → 板 | 独占，只读当前 USB 网卡配置；临时监听器绑定 USB IP，退出终止，不修改主机网络 | 手动启用一种 USB 网卡后 | 脚本头注释 |
| [one-kvm-usb-board-check.py](../tools/one-kvm-usb-board-check.py) | 板（root） | 独占，应用停止 | 板端 USB 助手枚举与恢复 | [板级工具](board-tools.md) |
| [one-kvm-uu-ui-check.mjs](../tools/one-kvm-uu-ui-check.mjs) | 一次性容器实例 | 无（禁止对板子账户运行） | UU 远程绑定界面 | [上板记录](bringup/2026-10-15-uu-output-controls-identity.md) |
| [pikvm-smoke.mjs](../tools/pikvm-smoke.mjs) | PiKVM | 独占 | PiKVM功能冒烟 | [Ubuntu 构建](ubuntu-build.md#pikvm-组件) |
| [kvm-switch-check.mjs](../tools/kvm-switch-check.mjs) | 管理器 | 独占，切换应用 | 四应用互斥与解码 | [板级工具](board-tools.md#kvm-应用切换回归) |
| [kernel-switch-check.mjs](../tools/kernel-switch-check.mjs) | Mac → 板 | 独占、重启两次 | 双内核切换回归 | 脚本头注释 |
| [manager-login.mjs](../tools/manager-login.mjs) | 管理器 | 创建登录会话 | 浏览器测试共享统一登录 | [公共前提](board-tools.md#浏览器测试的公共前提) |

## 诊断与测量

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| [hdmi-source-mode.swift](../tools/hdmi-source-mode.swift) | macOS 信源机编译/运行 | set 改信源模式，须独占并保存/恢复原 ID | list/set backing raster | [主线内核](kernel-mainline.md) |
| [packaging/hdr10/application-receiver.mjs、test-receiver.mjs](../packaging/hdr10/application-receiver.mjs) | Mac / Node | 接收需板票和 sampling；自测无板访问、需 heavy | HDR接收取证 | [HDR10](hdr10-remote-73.md) |
| [packaging/hdr10/screen-observe.swift](../packaging/hdr10/screen-observe.swift) | Mac | 无 | 构建工具 | [第二阶段记录](bringup/2026-10-31-hdr10-phase2-offline.md) |
| [packaging/hdr10/analyze-phase2.py、ffmpeg-vm.py、check-phase2-plugins.py](../packaging/hdr10/analyze-phase2.py) | 宿主 / VM | 离线需 heavy；--device-factories 需候选窗口 | 构建工具 | [第二阶段记录](bringup/2026-10-31-hdr10-phase2-offline.md) |
| [packaging/hdr10/measure-gpu.py](../packaging/hdr10/measure-gpu.py) | 板 | --execute 独占 GPU/采集；其他消费者须停止 | 构建工具 | [HDR10](hdr10-remote-73.md) |
| [rtp-udp-bench.c](../tools/rtp-udp-bench.c) | Linux ARM64 容器 / 板 | 无硬件访问；板端占 CPU，须协调测量窗口 | UDP发送基准 | [发送基准](bringup/2026-10-25-rtp-send-benchmark.md) |
| [encoder-vbv-bench.c、tools/encoder-vbv-probe.c](../tools/encoder-vbv-bench.c) | Linux ARM64 / 板 | bench run 独占编码；fixture/reference 无；probe 仅限私有测试进程 | VBV固定输入基准 | [VBV 对照](bringup/2026-10-26-encoder-vbv.md) |
| [encoder-vbv-run.py](../tools/encoder-vbv-run.py) | 板 | 独占；临时停启One-KVM并恢复原active状态 | VBV配对执行 | [VBV 对照](bringup/2026-10-26-encoder-vbv.md) |
| [encoder-vbv-summary.py、tools/encoder-vbv-quality.py](../tools/encoder-vbv-summary.py) | 离线；quality需ffmpeg | 不访问硬件；解码需避开性能窗口 | VBV与画质汇总 | [VBV 对照](bringup/2026-10-26-encoder-vbv.md) |
| [display-color.py、tools/display-color.c](../tools/display-color.py) | 离线 / 板（root） | chart/analyze/diff 无；run 独占显示/采集；snapshot 只读控制和矩阵 | 显示颜色校准 | [颜色校准](display-color-calibration.md) |
| [hdmi-color-check.py](../tools/hdmi-color-check.py) | 离线，PNG分析需Pillow | 不接触板子 | HDMI颜色分析 | [HDR切换颜色修复](bringup/2026-10-25-native-hdr-color.md) |
| [perf-baseline.py](../tools/perf-baseline.py) | 离线 | 无 | 性能预算与配对汇总 | [性能基线](performance-baseline.md) |
| [perf-quick.py、perf-motion.html](../tools/perf-quick.py) | Mac / M6浏览器 / 板 | MCP发送目标机HID；native独占采集编码、暂停并恢复One-KVM；window可RAM启动/恢复 | pm-phase 合并 4K60/空闲 PM 采样 | [快速实验](bringup/2026-10-31-p0-2-performance.md) |
| [perf-sensors.py](../tools/perf-sensors.py) | 板 | 读；性能窗口内 | 1Hz温度/功率/频率/runtime状态JSONL | [性能基线](performance-baseline.md) |
| [vendor-boot-plan.py](../tools/vendor-boot-plan.py) | 离线 | 无 | 厂商一次性启动计划 | [厂商对照启动](vendor-boot-baseline.md) |
| [latency-source.swift](../tools/latency-source.swift) | Mac | 占用 HDMI 画面；可输出 HDMI 音频 | 把帧号画进 HDMI 输出 | [延迟测量](latency.md) |
| [hdmi-resolution-source.swift](../tools/hdmi-resolution-source.swift) | Mac | 临时覆盖所选 HDMI 桌面 | 原生 UHD 单像素条纹与参考 PNG | [清晰度复核](bringup/2026-10-20-edge-uhd-detail.md) |
| [hdmi-resolution-check.py](../tools/hdmi-resolution-check.py) | 离线 | 无 | 原生空间细节分析 | [清晰度复核](bringup/2026-10-20-edge-uhd-detail.md) |
| [latency-receiver.mjs](../tools/latency-receiver.mjs) | Mac | 独占 | 帧标记与呈现接收 | [延迟测量](latency.md) |
| [latency-summary.py](../tools/latency-summary.py) | Mac | 无 | 匹配时间戳与呈现节奏 | [延迟测量](latency.md) |
| [latency-rtp-summary.py](../tools/latency-rtp-summary.py) | 离线 | 无 | AU与RTP关联验证 | [延迟测量](latency.md) |
| [video-timing-summary.py](../tools/video-timing-summary.py) | Mac | 无 | 汇总 VIM4_VIDEO_TIMING 分段计时 | [延迟测量](latency.md) |
| [input-target.swift](../tools/input-target.swift) | Mac | 覆盖显示器 | input-check临时接收窗口 | [输入验证](input-latency.md) |
| [input-summary.py](../tools/input-summary.py) | Mac | 无 | 汇总 input-check 日志 | [输入验证](input-latency.md) |
| [key-repeat.html](../tools/key-repeat.html) | 被控电脑浏览器 | 只接收本页面手动输入，不注入键鼠 | 长按与释放对照 | [输入验证](input-latency.md#手动对照-backspace-长按) |
| [uu-scroll-probe.swift](../tools/uu-scroll-probe.swift) | Mac | 无 | 只测本窗口收到的滚轮事件 | [UU 滚轮](uu-scroll.md) |
| [hdmi-audio-tone.c](../tools/hdmi-audio-tone.c) | Mac | 无 | 只向 HDMI 设备播放 440Hz | [功能状态](archive/feature-status.md) |
| [uac-record-level.swift](../tools/uac-record-level.swift) | Mac | 无（需麦克风权限） | 录 UAC2 电平与主频 | [板级工具](board-tools.md) |
| [hdmi-capture.sh](../tools/hdmi-capture.sh) | 板（root） | 独占采集 | 经 vfm_cap 抓一帧 PNG | [内核](kernel.md) |
| [hdmi-control-watch.py](../tools/hdmi-control-watch.py) | 板（root） | 读 | 采样 RX port 1 控制状态 | [HDMI 恢复审查](archive/hdmi-recovery-review.md#控制状态采样工具) |
| [hid-rebind-check.py](../tools/hid-rebind-check.py) | 板（root） | 独占，应用停止；旧内核会 panic | HID epoll 跨 UDC 重新绑定 | [内核](kernel.md) |
| [crg-udc-check.py](../tools/crg-udc-check.py) | 板（root） | 独占，仅 7.3 CRG 测试内核 | 最小 HID 重绑定 | [CRG 实测](bringup/2026-10-19-crg-udc.md) |
| [crg-composite-host-check.py](../tools/crg-composite-host-check.py) | Mac → 板 | 独占，移动光标、临时窗口接收按键、枚举测试盘 | 配合 CRG 板端工具 | [CRG 组合实测](bringup/2026-10-19-crg-composite.md) |
| [hdmirx-resource-check.py](../tools/hdmirx-resource-check.py) | 板（root） | 独占，仅 7.3 HDMI RX 测试内核；PHY 模式改变 EDID／HPD | 资源回收与旧 fd | [HDMI PHY 实测](bringup/2026-10-19-hdmirx-phy.md) |
| [hdmirx-ddc-host-check.py](../tools/hdmirx-ddc-host-check.py) | Mac → 板 | 独占，加载接收模块并改变 EDID／HPD，影响 HDMI 显示连接 | DDC读回对照 | [HDMI DDC 实测](bringup/2026-10-19-hdmirx-ddc.md) |
| [hdmirx-frame-check.py](../tools/hdmirx-frame-check.py) | Mac / Linux | 无 | 原始帧标记校验 | [4K 与编码](bringup/2026-10-19-wave521-uhd.md) |
| [hdmirx-stream-check.c](../tools/hdmirx-stream-check.c) | 板（root） | 独占，仅 7.3 HDMI 实验内核 | 采集队列生命周期 | [HDMI DMA-buf](bringup/2026-10-19-hdmirx-dmabuf.md) |
| [hdmirx-soak.c](../tools/hdmirx-soak.c) | 板（root） | 独占采集，调用者持双锁并停启应用 | 逐帧采集稳定性 | 脚本头注释 |
| [hdmirx-encode-check.py](../tools/hdmirx-encode-check.py) | 板（root）/ Linux | capture 独占实验采集；verify 离线 | DMA-buf采集/编码、CPU/pad时间 | [4K 与编码](bringup/2026-10-19-wave521-uhd.md)、[恢复门禁](bringup/2026-10-31-hdr2-recovery.md) |
| [packaging/hdr2-pq/mcp-screenshot.py](../packaging/hdr2-pq/mcp-screenshot.py) | Mac → 板 | 持板锁，只读截图 | MCP只读截图 | [MCP与接收诊断](bringup/2026-10-31-hdr2-mcp-ice-pq.md) |
| [wave5-lifecycle-check.py](../tools/wave5-lifecycle-check.py) | 板 | 独占编码；停视频应用 | 编码器生命周期 | [One-KVM 接入](bringup/2026-10-20-onekvm-wave5.md) |
| [onekvm-local-bench.py](../tools/onekvm-local-bench.py) | Mac → 容器；可选当前内核板子 | 默认无；--board 占 CPU/内存带宽，不停服务 | DMA 平面、压缩缓存与复制基准 | [本地基准](local-video-benchmark.md) |
| [vim4-driver-bench.c](../tools/vim4-driver-bench.c) | 板；需先编译 | 独占采集/编码；调用者停启应用 | 采集编码驱动基准 | [驱动基准](driver-benchmark.md) |
| [test-fan-policy.sh](../tools/test-fan-policy.sh) | VM | 无 | 编译内核风扇插值函数做断言 | [内核](kernel.md) |
