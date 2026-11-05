# 工具目录

按文件名查入口、影响和用途；参数与限制查头注释或 `--help`。
影响：无＝无板端硬件访问；只读＝观察；独占＝先协调；破坏＝清盘或重启。混合入口标最高影响，命令边界见源码。
约束见[板级工具](board-tools.md)、[占板窗口](board-window.md)。增删工具同步本页。
导航：[构建打包](#工作区构建与打包) · [板操作](#板级操作) · [服务](#板级服务源码由-boardinstallsh-或组件包安装) · [应用回归](#应用回归浏览器) · [诊断测量](#诊断与测量)。

## 浏览器测试的公共前提

见[公共前提](board-tools.md#浏览器测试的公共前提)。

## 工作区、构建与打包

重型构建在Mac侧通过 `tools/board-queue run --heavy --who TASK --purpose PURPOSE -- orb -m vim4-build ...`
排队，由队列协调构建与板端采样；不要直接用legacy lockf绕过队列。构建票不占板票。

| 入口（同族文件） | 影响 | 用途 |
|---|---|---|
| [workspace.py](../tools/workspace.py) | 无 | 工作区管理与构建。 |
| [vm](../tools/vm) | 无；写远端 | Mac 管理 VM 工作树；推送预览列出 origin 尚未包含的提交，来源分支未发布时也可推新任务分支，仍禁止推受保护分支。 |
| [ubuntu-build.py](../tools/ubuntu-build.py)、ubuntu-image.py、[packaging/ubuntu/](../packaging/ubuntu)、[packaging/image/](../packaging/image) | 无 | 组件打包与镜像组装；开发包可指定目标已安装版本下限。 |
| [packaging/kernel/](../packaging/kernel) | 独占 | 内核构建及板端准备。 |
| [build-integration.py](../packaging/kernel/build-integration.py) | 无 | 持heavy票离线构建并封存生产/调试RAM候选；复用同一O=时同步并核对生效配置，保存生成头证据，分别传构建号可指定顺序。 |
| [package-unified.py](../packaging/kernel/package-unified.py)（同目录 package-hdr10.py、package-final.py、package-vdec.py） | 无 | 封存已构建候选包。 |
| [build-integration.py](../packaging/kernel/build-integration.py) | 无；写 VM 构建目录 | 持 heavy 租约后离线构建指定完整 SHA 的生产/调试 RAM 候选，复用同一 O=，封包后清理对象；不排票、不访问板子。 |
| [build-gstreamer.py](../packaging/kernel/build-gstreamer.py)（test_gstreamer_p010.py、test_gstreamer_pq.py、test_gstreamer_visible_crop.py） | 无 | 插件构建及离线协商回放。 |
| [maintain.py](../packaging/kernel/maintain.py) | 无 | 补丁导出与前移。 |
| [vdec-fixtures.py](../packaging/kernel/vdec-fixtures.py) | 无 | 生成 H.264/MPEG-2/MJPEG 运动样本；JPEG 保留全范围参考像素，generate-fields 下载并校验固定场编码样本。离线逐帧比较 I420 并量化平面误差，非逐字节一致仍返回失败。 |
| [vdec-capture.c](../packaging/kernel/vdec-capture.c) | 指定管线 | 用 GStreamer appsink 映射视频元数据，只保存可见 I420 平面，不做范围转换、不写入对齐填充；编译依赖及用法见文件。硬解管线须持板锁。 |
| [build-vdec-gstreamer.py](../packaging/kernel/build-vdec-gstreamer.py)（test_gstreamer_mpeg2.py） | 无 | 按独立源码锁构建私有 stateless 解码插件并回放 MPEG-2 标准控制转换；不覆盖系统插件。 |
| [prepare-vdec-fluster.py](../packaging/kernel/prepare-vdec-fluster.py)、[build-vdec-mpeg2-reference.py](../packaging/kernel/build-vdec-mpeg2-reference.py) | 无 | 宿主按锁准备标准码流、校验并记录离线清单；单独从已取得的 ISO 归档构建私有 MPEG-2 参考解码器。 |
| [hdmi-mode-fixture.py](../packaging/kernel/hdmi-mode-fixture.py)（hdmi-modes.json） | 只读 | 离线准备及板端输入模式验证。 |
| [register-runtime.py](../packaging/kernel/register-runtime.py) | 独占 | 盘点及板端运行时登记、安装。 |
| [assemble-phase2.py](../packaging/hdr10/assemble-phase2.py)（同目录 ram-payload.py、analyze-phase2.py、ffmpeg-vm.py、check-phase2-plugins.py、screen-observe.swift、test-receiver.mjs） | 只读 | HDR10 封装、插件检查及证据分析。 |
| [persistent-r14e.py](../packaging/hdr10/persistent-r14e.py) | 独占 | 安装私有 HDR10 运行时。 |
| [packaging/gpu/](../packaging/gpu) | 独占 | GPU 运行时构建及板端 probe。 |
| [vrr-edid.py](../tools/vrr-edid.py) | 无 | 离线生成实验 EDID。 |
| [mali-runtime.py](../tools/mali-runtime.py) | 独占 | 下载或板端安装私有 GPU 运行时。 |
| [tests/](../tests) | 无 | 离线回归。 |

## 板级操作

| 入口（同族文件） | 影响 | 用途 |
|---|---|---|
| [board-queue](../tools/board-queue) | 无 | 协调主机管理板票与采样；子命令影响由被调用入口决定。 |
| [board-window](../tools/board-window) | 破坏；重启 | RAM 启动、采样与恢复。 |
| [board.py](../tools/board.py) | 破坏；清盘 | check / deploy / verify / provision / enroll / recover / flash。 |
| [install-components.sh](../tools/install-components.sh) | 独占 | 板端组件升级与迁移。 |
| [uart-run.py](../tools/uart-run.py)、uart-log.py | 独占 | Mac 串口执行或抓日志；纯日志只读，发送前核对命令影响。 |
| [oowow-flash.sh](../tools/oowow-flash.sh) | 破坏；清盘 | Mac 驱动 OOWOW 刷写。 |
| [kernel-install.sh](../tools/kernel-install.sh)、rootfs-policy.py、[promote.py](../packaging/kernel/promote.py) | 独占；改默认启动项 | 板端安装内核、根分区策略或登记候选。 |
| [display-once.py](../packaging/kernel/display-once.py)（display-once-init.c） | 独占 | 准备或暂存 RAM 启动候选。 |
| [final-window.py](../packaging/kernel/final-window.py)（final-board.py） | 破坏；重启 | 正式包部署、验证与恢复。 |
| [final-regression.py](../packaging/kernel/final-regression.py)（final-manager-check.mjs） | 独占；断开 USB | 离线快照及部署回归。 |
| [vdec-window.py](../packaging/kernel/vdec-window.py)（vdec-register-dump.c、[vdec-benchmark.c](../packaging/kernel/vdec-benchmark.c)） | 破坏；重启 | 解码候选窗口、compliance、fluster 与性能；默认离线，复用板队列、manifest、watchdog 和基线视频恢复；Fluster 像素失败逐流记录后继续，超时/内核异常停止；见[验收合同](vdec-validation.md)。 |
| [check-wifi-p2p.py](../packaging/kernel/check-wifi-p2p.py) | 独占 | Wi-Fi/P2P 验证。 |
| [phase2-window.py](../packaging/hdr10/phase2-window.py)（m6-gates.py、phase2-board.py、phase2-run） | 破坏；重启 | HDR10 批量验收窗口。 |
| [build.py](../packaging/kbase/build.py)（同目录 package.py、run.py、check-style.py、check-semantics.py、check-heaps.py、clpeak-subset.py、dma-profile.py、default-parity.py、resolve-egl.c、heaps/vim4_kbase_heaps.c、dvfs/governor_vim4.c） | 独占 | kbase 构建、GPU 门禁与调频。 |

## 板级服务源码（由 board/install.sh 或组件包安装）

| 入口（同族文件） | 影响 | 用途 |
|---|---|---|
| [hdmi-setup.sh](../tools/hdmi-setup.sh)、hdr-curve.sh | 独占 | 板端采集路径与 HDR 映射。 |
| [kvm-gadget.sh](../tools/kvm-gadget.sh) | 独占；断开 USB | gadget 生命周期。 |
| [usb-pd-init.c](../tools/usb-pd-init.c) | 独占 | 旧内核的有限 PD 协商；拒绝访问已声明给内核的控制器，包括尚未绑定驱动的设备。 |
| [one-kvm-edge](../packaging/kernel/one-kvm-edge)（one-kvm-edge-prepare、one-kvm-edge.service）、[hdr10-prepare](../packaging/kernel/hdr10-prepare)（hdr10-run） | 独占 | 板端候选视频服务准备与启动。 |
| [vim4-ethernet-generator.py](../board/vim4-ethernet-generator.py) | 只读 | 读取每板 MAC 并生成运行时网络配置。 |
| [vim4-wave5-monitor.py](../board/vim4-wave5-monitor.py) | 只读 | 监视编码器隔离并记日志。 |
| [60-vim4-watchdog.conf](../board/60-vim4-watchdog.conf)、[60-vim4-panic.conf](../board/60-vim4-panic.conf) | 破坏；重启 | 板端看门狗和 panic 策略。 |

## 应用回归（浏览器）

| 入口（同族文件） | 影响 | 用途 |
|---|---|---|
| [video-smoke.mjs](../tools/video-smoke.mjs)、audio-smoke.mjs | 独占 | 视频/音频冒烟。 |
| [mic-smoke.mjs](../tools/mic-smoke.mjs)、usb-switch-check.mjs | 独占；断开 USB | 麦克风及 USB 组合切换。 |
| [media-upload-check.mjs](../tools/media-upload-check.mjs) | 独占；写远端 | 镜像上传与网页终端。 |
| [input-check.mjs](../tools/input-check.mjs) | 独占；发 HID | 键鼠延迟、长按和滚轮。 |
| [nanokvm-board-check.mjs](../tools/nanokvm-board-check.mjs) | 独占 | EDID 往返。 |
| [jetkvm-smoke.mjs](../tools/jetkvm-smoke.mjs) | 独占；可发 HID | JetKVM 视频、RPC 与终端。 |
| [one-kvm-smoke.mjs](../tools/one-kvm-smoke.mjs)、one-kvm-stability-check.mjs、one-kvm-audio-check.mjs、one-kvm-audio-continuity.mjs、one-kvm-av-sync-check.mjs、av-sync-probe.mjs、one-kvm-recording-check.mjs | 独占 | 视频、音频、同步与录屏回归。 |
| [one-kvm-settings-check.mjs](../tools/one-kvm-settings-check.mjs)、one-kvm-board-check.mjs、one-kvm-scaling-check.mjs、one-kvm-features-check.mjs | 独占 | 设置、缩放及扩展往返。 |
| [one-kvm-drive-check.mjs](../tools/one-kvm-drive-check.mjs) | 独占；写盘 | Ventoy 虚拟盘与文件往返。 |
| [one-kvm-usb-check.mjs](../tools/one-kvm-usb-check.mjs) | 独占；发 HID | 主机键鼠及 ISO 挂载。 |
| [one-kvm-usb-profile-check.mjs](../tools/one-kvm-usb-profile-check.mjs)、one-kvm-usb-media-check.mjs、one-kvm-usb-board-check.py | 独占；断开 USB | USB 组合、介质及板端助手。 |
| [one-kvm-usb-network-host.py](../tools/one-kvm-usb-network-host.py) | 独占 | Mac 检查已启用的 USB 网卡。 |
| [one-kvm-uu-ui-check.mjs](../tools/one-kvm-uu-ui-check.mjs) | 无 | 仅一次性容器的 UU 绑定界面，禁止对板子账户运行。 |
| [pikvm-smoke.mjs](../tools/pikvm-smoke.mjs) | 独占；发 HID | PiKVM 功能冒烟。 |
| [kvm-switch-check.mjs](../tools/kvm-switch-check.mjs) | 独占 | 管理器四应用切换。 |
| [kernel-switch-check.mjs](../tools/kernel-switch-check.mjs) | 破坏；重启 | 管理器双内核切换。 |
| [manager-login.mjs](../tools/manager-login.mjs) | 只读 | 浏览器测试共享登录。 |

## 诊断与测量

| 入口（同族文件） | 影响 | 用途 |
|---|---|---|
| [gpu-diagnose.py](../tools/gpu-diagnose.py)、gpu-compare.py、gpu-cl-map.c | 独占 | GPU 诊断与运行时配对。 |
| [mali-dma-probe.c](../tools/mali-dma-probe.c)、mali-dma-probe.comp、mali-cl-probe.c | 独占 | GPU 缓冲导入。 |
| [npu-validate.py](../tools/npu-validate.py)、npu-probe.c、npu-models.json、npu-uapi-probe.c | 独占 | NPU 推理及接口验证。 |
| [memory-bench.py](../tools/memory-bench.py)、memory-bench.c | 独占 | Linux 内存吞吐基准。 |
| [t7-vdin-copy-bench.py](../tools/t7-vdin-copy-bench.py) | 独占 | Linux ARM64 离线编译 SIMD 候选与内核 memcpy 对照；生成程序的 benchmark 模式分配真实 VDIN MMAP 缓冲。 |
| [gbm-scanout-probe.c](../tools/gbm-scanout-probe.c) | 独占 | GBM 扫描输出。 |
| [measure-gpu.py](../packaging/hdr10/measure-gpu.py)、[application-receiver.mjs](../packaging/hdr10/application-receiver.mjs) | 独占 | HDR10 GPU 转换与应用接收取证。 |
| [rtp-udp-bench.c](../tools/rtp-udp-bench.c) | 独占 | Linux/板端 UDP 发送基准。 |
| [encoder-vbv-run.py](../tools/encoder-vbv-run.py)、encoder-vbv-bench.c、encoder-vbv-probe.c | 独占 | VBV 固定输入基准。 |
| [wave5-reproduce-hang.py](../tools/wave5-reproduce-hang.py) | 独占 | Wave5 编码/取消与有界进程取证；默认仅输出计划，执行须独占板窗、停止视频应用并预备恢复。 |
| [encoder-vbv-summary.py](../tools/encoder-vbv-summary.py)、encoder-vbv-quality.py | 无 | VBV 与画质汇总。 |
| [display-color.py](../tools/display-color.py)、display-color.c | 独占 | 离线分析或板端显示颜色校准。 |
| [hdmi-color-check.py](../tools/hdmi-color-check.py)、hdmi-resolution-check.py | 无 | HDMI 颜色与细节分析。 |
| [perf-quick.py](../tools/perf-quick.py)、perf-motion.html | 破坏；重启 | 视频实验采样窗口。 |
| [perf-baseline.py](../tools/perf-baseline.py) | 无 | 离线性能预算与配对汇总。 |
| [perf-sensors.py](../tools/perf-sensors.py)、passthrough-monitor.py、hdmi-control-watch.py | 只读 | 板端遥测与 HDMI 状态观察。 |
| [vendor-boot-plan.py](../tools/vendor-boot-plan.py) | 无 | 离线一次性启动计划。 |
| [hdmi-source-mode.swift](../tools/hdmi-source-mode.swift)、hdmi-resolution-source.swift、latency-source.swift、input-target.swift | 独占 | Mac 信源模式、图样及输入接收窗口。 |
| [latency-receiver.mjs](../tools/latency-receiver.mjs)、board-window-receiver.mjs、board-window-timing.mjs | 独占 | 浏览器帧标记与呈现接收。 |
| [latency-summary.py](../tools/latency-summary.py)、latency-rtp-summary.py、video-timing-summary.py、input-summary.py | 无 | 离线时序汇总。 |
| [key-repeat.html](../tools/key-repeat.html) | 无 | 被控电脑浏览器手动长按对照。 |
| [uu-scroll-probe.swift](../tools/uu-scroll-probe.swift) | 无 | 历史：Mac 滚轮事件调查，见[归档](archive/uu-scroll.md)。 |
| [hdmi-audio-tone.c](../tools/hdmi-audio-tone.c)、uac-record-level.swift | 无 | Mac HDMI 测试音与 UAC2 录音。 |
| [hdmi-capture.sh](../tools/hdmi-capture.sh) | 独占 | 板端单帧 PNG 采集。 |
| [hid-rebind-check.py](../tools/hid-rebind-check.py)、crg-udc-check.py | 独占；断开 USB | HID 重绑定回归。 |
| [crg-composite-host-check.py](../tools/crg-composite-host-check.py) | 独占；发 HID | Mac 配合 CRG 枚举验证。 |
| [hdmirx-resource-check.py](../tools/hdmirx-resource-check.py)、hdmirx-ddc-host-check.py | 独占 | 实验内核 RX 资源与 EDID/DDC 验证。 |
| [hdmirx-stream-check.c](../tools/hdmirx-stream-check.c)、hdmirx-soak.c、hdmirx-encode-check.py、wave5-lifecycle-check.py、vim4-driver-bench.c | 独占 | 板端采集/编码生命周期与基准。 |
| [hdmirx-frame-check.py](../tools/hdmirx-frame-check.py) | 无 | 离线原始帧标记校验。 |
| [edge-jpeg-check.py](../tools/edge-jpeg-check.py)、edge-jpeg-profile.py | 独占 | JPEG 驱动及分段计时。 |
| [mcp-screenshot.py](../packaging/hdr2-pq/mcp-screenshot.py) | 只读 | 持板锁获取 MCP 截图。 |
| [onekvm-local-bench.py](../tools/onekvm-local-bench.py) | 独占；可写远端 | Mac 调度容器或板端 CPU/内存基准；内核参数只记源码身份，驱动验证单独运行。 |
| [test-fan-policy.sh](../tools/test-fan-policy.sh) | 无 | 仅5.15：离线验证厂商风扇曲线函数。 |
| [fan-thermal-check.py](../tools/fan-thermal-check.py) | 独占；休眠 | 外部集成RAM包prepare/compare仅离线；上板校运行身份后做温控/面板/稳定温度检查。不自行申请板窗。 |
