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

## 工作区、构建与打包

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| tools/workspace.py | Mac / CI | 无 | bootstrap/status 子仓库（`--override` 供发布 CI 替换单个仓库提交），build 各目标（kernel 走 OrbStack） | [工作区](workspace.md) |
| tools/ubuntu-build.py | Mac / CI → Docker | 无 | package/verify 七组件；支持 platform、capture、encoder、nanokvm、jetkvm、onekvm、manager、pikvm、pikvm-app | [Ubuntu 构建](ubuntu-build.md) |
| tools/ubuntu-image.py | Mac → OrbStack | 无 | 内核包、候选镜像 assemble/verify/export | [候选镜像](ubuntu-image.md) |
| packaging/ubuntu/ | 容器 | 无 | Dockerfile、锁文件、fetch.py、build.sh、package.py、verify.sh；manager-config.py 迁移网关配置；check-audio-startup.py、check-onekvm-update.py 与 pikvm/check-janus.py 为打包门禁 | [Ubuntu 构建](ubuntu-build.md) |
| packaging/kernel/ | VM | 无 | package.sh 构建内核包，vim4.config 为配置 | [内核](kernel.md) |
| packaging/image/ | VM（root） | 无 | assemble.sh 组装镜像文件，configure.sh 仅由其调用，verify.sh 只读检查 | [候选镜像](ubuntu-image.md) |
| tests/ | Mac | 无 | 离线单元测试：`python3 -m unittest discover -s tests -p 'test_*.py'` | 本页 |

## 板级操作

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| tools/board.py check | Mac | 读 | 内核、服务、设备节点、8081 后端与 8080 网关状态 | [板级工具](board-tools.md) |
| tools/board.py deploy --exclusive | Mac | 独占 | 校验并安装组件包（委托 install-components.sh） | [板级工具](board-tools.md#增量开发闭环) |
| tools/board.py verify | Mac | 独占 | 部署后 hid/audio/video 实测，写 verify.json | [板级工具](board-tools.md) |
| tools/board.py provision / enroll | Mac | 改板配置 | 公钥与开发用免密 sudo | [板级工具](board-tools.md#操作前约定) |
| tools/board.py recover / flash | Mac | 破坏 | 进入 OOWOW；校验刷写本地镜像 | [板级工具](board-tools.md#本地候选镜像一键刷写) |
| tools/install-components.sh | 板（由 deploy 调用） | 独占 | 板上包校验、APT 模拟、迁移与恢复所选应用 | [板级工具](board-tools.md) |
| tools/uart-run.py | Mac | 取决于命令 | 串口执行命令；超时后命令可能仍在运行 | [部署](subsystems/deployment.md) |
| tools/uart-log.py | Mac | 读（`--send` 除外） | 只读抓串口日志 | [部署](subsystems/deployment.md) |
| tools/oowow-flash.sh | Mac（板在 OOWOW） | 破坏 | 手工 URL 刷写，优先用 board.py flash | [板级工具](board-tools.md) |
| tools/kernel-install.sh | 板（root） | 改启动项 | 安装内核包并保留 Stock 启动项 | [内核](kernel.md) |
| tools/rootfs-policy.py | 板（root，随包安装） | 改启动项 | 根分区 ordered/commit=5，重启生效 | [Ubuntu 构建](ubuntu-build.md) |

## 板级服务源码（由 board/install.sh 或组件包安装）

| 入口 | 安装为 | 用途 | 文档 |
|---|---|---|---|
| tools/hdmi-setup.sh | /usr/local/sbin/hdmi-setup.sh | vdin0 + vfm_cap 配置并打开 HDMI 源 | [音视频](subsystems/video.md) |
| tools/hdr-curve.sh | vim4-hdr-curve | HDR10→SDR 映射表生成与写入 | [音视频](subsystems/video.md#hdr-输入) |
| tools/kvm-gadget.sh | /usr/local/sbin/kvm-gadget.sh | USB gadget：键盘、绝对/相对鼠标、NCM | [USB](subsystems/usb.md) |
| tools/usb-pd-init.c | vim4-kvm-pd.service | 开机 FUSB302B 5V PD 协商；`--status` 只读 VBUS 状态 | [USB-PD](usb-pd.md) |

## 应用回归（浏览器）

| 入口 | 应用 | 影响 | 覆盖 | 文档 |
|---|---|---|---|---|
| tools/video-smoke.mjs | NanoKVM | 独占 | WebRTC 实际编码、解码帧数/丢帧/丢包；Direct 首帧尺寸与持续收包（不等于持续呈现） | [板级工具](board-tools.md) |
| tools/audio-smoke.mjs | NanoKVM | 独占 | 音量控件与解码音频；配 hdmi-audio-tone | [功能状态](feature-status.md) |
| tools/mic-smoke.mjs | NanoKVM | 独占，重新枚举 USB | Chrome 合成麦克风到 UAC2 播放 | 脚本头注释 |
| tools/usb-switch-check.mjs | NanoKVM | 独占，断开 USB | 麦克风/镜像组合切换与恢复 | [板级工具](board-tools.md#usb-切换回归) |
| tools/media-upload-check.mjs | NanoKVM | 独占，留下上传文件 | 镜像上传与网页终端 | [板级工具](board-tools.md#工具验证边界) |
| tools/input-check.mjs | NanoKVM | 独占，移动光标 | 键鼠延迟、长按、滚轮；配 input-target.swift、input-summary.py | [输入验证](input-latency.md) |
| tools/jetkvm-smoke.mjs | JetKVM | 独占 | 视频、JSON-RPC 调用、网页终端 | [JetKVM](../kvm/VIM4.md) |
| tools/one-kvm-smoke.mjs | One-KVM | 独占 | H.264/H.265/MJPEG 解码、缓冲与呈现间隔尾部；`--seconds`/`--warmup` 控制测量窗口，`--audio` 检查波形 | [板级工具](board-tools.md) |
| tools/one-kvm-audio-check.mjs | One-KVM | 独占 | Opus WebSocket 音频，静音判失败 | [板级工具](board-tools.md) |
| tools/one-kvm-recording-check.mjs | One-KVM | 独占 | H.264/H.265 带声音录屏、关网页续录、下载、断流与重启；仅清理本次录像 | [板级工具](board-tools.md) |
| tools/one-kvm-settings-check.mjs | One-KVM | 独占，改 EDID/HDR 后恢复 | 视频设置往返 | [One-KVM](../One-KVM/VIM4.md) |
| tools/one-kvm-features-check.mjs | One-KVM | 独占 | 终端、扩展、看门狗；需本地 FRP 17700 | [板级工具](board-tools.md) |
| tools/one-kvm-drive-check.mjs | One-KVM | 独占，可能创建虚拟盘 | Ventoy 虚拟盘与文件往返 | [Ubuntu 构建](ubuntu-build.md) |
| tools/one-kvm-usb-check.mjs | One-KVM | 独占，重新枚举 USB | Mac 主机键鼠、ISO 挂载 | [板级工具](board-tools.md) |
| tools/one-kvm-usb-profile-check.mjs | One-KVM | 独占，改 USB 组合后恢复 | HID/UAC/网卡组合与超限回滚 | [板级工具](board-tools.md) |
| tools/one-kvm-usb-board-check.py | 板（root） | 独占，应用停止 | 板端 USB 助手枚举与恢复 | [板级工具](board-tools.md) |
| tools/one-kvm-uu-ui-check.mjs | 一次性容器实例 | 无（禁止对板子账户运行） | UU 远程绑定界面 | [上板记录](bringup/2026-10-15-uu-output-controls-identity.md) |
| tools/pikvm-smoke.mjs | PiKVM | 独占 | 解码、及时截图、MJPEG 重连与可选 Mac USB 输入 | [Ubuntu 构建](ubuntu-build.md#pikvm-组件) |
| tools/kvm-switch-check.mjs | 管理器 | 独占，切换应用 | 应用互斥切换并恢复原选择 | [板级工具](board-tools.md#kvm-应用切换回归) |
| tools/manager-login.mjs | 管理器 | 创建登录会话 | 浏览器测试共享统一登录；导出 loginManager(context, managerURL) | 本页 |

## 诊断与测量

| 入口 | 运行位置 | 影响 | 用途 | 文档 |
|---|---|---|---|---|
| tools/latency-source.swift | Mac | 占用 HDMI 画面 | 把帧号画进 HDMI 输出，`--motion` 产生运动网格 | [延迟测量](latency.md) |
| tools/latency-receiver.mjs | Mac | 独占 | 解码像素帧号与呈现节奏；统一管理器登录、专用 CDP 浏览器和无像素回读对照 | [延迟测量](latency.md) |
| tools/latency-summary.py | Mac | 无 | 匹配两端时间戳，统计呈现间隔、回调漏采和无更新尾段 | [延迟测量](latency.md) |
| tools/video-timing-summary.py | Mac | 无 | 汇总 VIM4_VIDEO_TIMING 分段计时 | [延迟测量](latency.md) |
| tools/input-target.swift | Mac | 覆盖显示器 | input-check 的临时接收窗口 | [输入验证](input-latency.md) |
| tools/input-summary.py | Mac | 无 | 汇总 input-check 日志 | [输入验证](input-latency.md) |
| tools/uu-scroll-probe.swift | Mac | 无 | 只测本窗口收到的滚轮事件，不注入输入 | [UU 滚轮](uu-scroll.md) |
| tools/hdmi-audio-tone.c | Mac | 无 | 只向 HDMI 设备播放 440Hz | [功能状态](feature-status.md) |
| tools/uac-record-level.swift | Mac | 无（需麦克风权限） | 录 UAC2 电平与主频 | [板级工具](board-tools.md) |
| tools/hdmi-capture.sh | 板（root） | 独占采集 | 经 vfm_cap 抓一帧 PNG | [内核](kernel.md) |
| tools/hdmi-control-watch.py | 板（root） | 读 | 采样 RX port 1 控制状态 | [HDMI 恢复审查](hdmi-recovery-review.md#控制状态采样工具) |
| tools/hid-rebind-check.py | 板（root） | 独占，应用停止；旧内核会 panic | HID epoll 跨 UDC 重新绑定 | [内核](kernel.md) |
| tools/test-fan-policy.sh | VM | 无 | 编译内核风扇插值函数做断言 | [内核](kernel.md) |
