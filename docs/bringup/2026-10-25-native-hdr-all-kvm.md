# 2026-10-25：原生 HDR 双路径的四应用采集修复

用户报告：5.15 下只有 One-KVM 有画面，NanoKVM、JetKVM、PiKVM 黑屏。
实际运行 `5.15.137-vim4kvm-hdrdual6`，`vdin0_native_hdr=Y`。
原生 HDR 模式把 VDIN0 直接交给 amvideo，旧 `vfmcapsrc` 无帧；此前仅 One-KVM
H.26x 接入 VDIN1。根因是[双路径](2026-10-25-native-hdr-dual-path.md)的应用适配遗漏，
本次未替换内核，也未重启板子。

## 修复与部署

`gst-plugin-vfmcap` 新增共享 `vim4vdin1src`：标准 V4L2 `/dev/video71` DMA-BUF，
从 RX 读取实际尺寸/帧率，输出 NV21/BT.709，支持等比缩小和快照。
分配查询要求 VideoMeta 及 6–8 个采集缓冲，避免 H.26x、JPEG、快照分支持帧导致饥饿。
仅显式 `VIM4_SECONDARY_HDMI_CAPTURE=1` 允许启动，防止 stock 内核把显示回写当 HDMI 输入。

NanoKVM 的全部采集分支、JetKVM、PiKVM 的 H.26x/JPEG 共用管线及 One-KVM 的
MJPEG 切换到此源；One-KVM 原有 H.26x 路径保留。NanoKVM 原生模式缩放只调整
独立采集尺寸，不写全局 HDMI 配置或重启透传。7.3 Wave5 分支保持优先级。

平台包集中安装私有标准 V4L2 插件，提供 `vim4-vdin1-api-1`，四应用声明依赖。
构建、ELF/插件校验及包升级检查均覆盖此依赖，不替换厂商 `amlv4l2src`。
源码主仓库 `c7a1f94`，相关仓库提交由 `workspace.toml` 固定：

| 仓库 | 提交 |
|---|---|
| gst-plugin-vfmcap | `bf387941` |
| NanoKVM | `32cad184` |
| JetKVM / kvm | `0d980671` |
| ustreamer | `5cc5d4bb` |
| kvmd | `ea67b245` |
| One-KVM | `f037159f` |

均已安装到 `vim4`：

| 包 | 版本 |
|---|---|
| board / vfmcap / amlvenc | `2.5.1+vim4.20261025.10` |
| NanoKVM | `2.5.1+vim4.20261025.11` |
| JetKVM | `2.5.1+vim4.20261025.12` |
| PiKVM | `2.5.1+vim4.20261025.13` |
| One-KVM | `2.5.1+vim4.20261025.14` |

## 验证证据

持有 board/heavy 独占锁。物理 HDMI 动态帧号输入，Chrome `156.0.8078.47`，
浏览器读取真实解码统计及画布内容变化。四应用两轮交错切换共 8 次，
每次采样 10 秒，均为 3840×2160、59.98–60.69 解码 fps，drop/lost 增量均 0。
切换请求到首个解码帧为 5.6–13.4 秒；不是长期稳态或端到端延迟结论。

NanoKVM H.264/H.265 的 WebRTC、Direct 均通过，MJPEG 和动态画面通过；
JetKVM H.265 解码及动态画面通过，编码偏好恢复 auto。
PiKVM H.264/H.265、MJPEG、动态画面及 JPEG 快照通过，快照约 64ms。
One-KVM H.264/H.265 各 5 秒解码约 59.97fps，drop/lost/freeze 增量均 0；
MJPEG 实收三帧 3840×2160，恢复 WebRTC 后动态画面通过。
原配置启用了 UU，按既有编码约束 API 正确拒绝 MJPEG；补测时临时关闭 UU，
完成后恢复启用及原编码设置，不撤销这项共用编码器约束。
NanoKVM 经真实 API 依次切换 1920×1080、1280×720、恢复 3840×2160，
各尺寸实际解码超过 30 帧且取得 JPEG，主 HDMI PID、启动时间及配置哈希不变。

低层源同时跑 4K H.264 + JPEG、独立 1080p H.265 均正常 EOS。
主透传 `vim4-kvm-hdmi` PID 始终 1096、启动时间单调值 10754764。
验收结束恢复 PiKVM，PiKVM、manager、HDMI 服务 active，failed units 为 0。
13:50 UTC 后验收窗口内无新增 Oops/BUG/WARNING/Call trace，taint 保持已有 12800；
较早日志存在 PDM 音频时钟关闭 warning，不能把本次视频验收表述为整个启动日志无告警。
当前 RX 为真实 SDR 输入；本轮验证原生 HDR 模式下的 KVM 共存，不重新声称完成
HDR 色彩/光学验证，颜色与 HDR 跟随证据见[已有记录](2026-10-25-native-hdr-color.md)。

主仓库离线测试 259 项（7 跳过）；插件 Meson 两组测试通过；Nano/Jet 的 Go、
前端及 PiKVM 的 C/Python/Node 检查通过。One-KVM Rust 774 通过、2 忽略，
35 项板级辅助测试及分配器测试通过。所有正式包通过对应 `ubuntu-build.py verify`。
初始 Docker 默认桥网络导致 3 项 UU ICE 收集测试失败，改用现有隔离网络
`onekvm-uu-test` 后全量通过，未修改产品逻辑绕过测试。

浏览器初始测试受 Node 本地网络权限、mDNS ICE 地址解析影响；使用 SSH 转发访问 HTTP，
仅测试 Chrome 进程关闭 mDNS 地址隐藏和 LocalNetworkAccessChecks 后验收。
没有修改产品网络策略。PiKVM 补测首次因测试点击隐藏菜单超时，改用已有 smoke 工具
相同的 DOM 单选触发方式，仅继续未完成项目。切换工具也改为等待真实解码帧，避免
One-KVM 预览尺寸提前出现导致误判 WebRTC 已就绪。

原始证据位于本地忽略目录 `logs/vdin1-*`：`switch-mdns.log`、`modes.log`、
`modes-remaining.log`、`one-mjpeg.log`、`scaling.log`、`board-final.log`、
`final-root-tests.log`、`final-build-*`、`final-verify-*`、`deploy-*`。
失败的早期浏览器日志不作为通过证据。7.3 与 stock 后端隔离已离线验证，未重启上板复测。
