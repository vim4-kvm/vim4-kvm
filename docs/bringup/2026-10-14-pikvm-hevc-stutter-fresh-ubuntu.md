# 2026-10-14：PiKVM HEVC、卡顿定位与全新 Ubuntu 组装

正式包 `2.5.1+vim4.20261014.39` 使用 kvmd `009975fd`、uStreamer `04e2756`、
管理器 `de596ac`。ARM64 构建、隔离验证与 board.py 部署通过。HEVC 使用硬件编码、
RFC 7798 RTP 分片和 Janus SDP；H.264 仍为默认，服务配置可选择 H.265，保留 MJPEG。
RTP 测试覆盖两种编码的单包、MTU 边界和多包重组；默认非 VIM4 构建也通过。
kvmd 验证器 673 项通过。浏览器测试现在通过登录表单进入应用，而非绕过登录流程；
新建无缓存浏览器上下文可正常登录，未修改登录跳转逻辑。

`.39` 板上 Chrome 实际协商 `video/H265`，3840×2160 解码、8 个不同运动图像哈希、
HDMI 音频峰值 0.15936、键鼠、ISO 主机读取与 eject、MJPEG/WebRTC 切换、参数保存
和刷新均通过。开发板保留 PiKVM active/enabled 和 H.265，未恢复 NanoKVM 挂盘。
证据：`build/pikvm-package-39.log`、`build/pikvm-verify-39.log`、
`logs/pikvm/deploy-39/`、`logs/pikvm/hevc-full-39.log`。

卡顿不是单纯缓存问题。稳定 60Hz 输入的 300 次 sysfs 采样出现 5987–5999 centi-Hz，
原 10 centi-Hz 阈值导致误重建，离线等待进一步产生秒级空窗。改为超过 1Hz、连续
两次稳定变化才重建，仍保留 3 秒无帧看门狗；默认 GOP 改为 30，避免没有周期关键帧。
修正前 H.265 五分钟测试最大浏览器回调间隔 1.8 秒、8 次 freeze；修正后没有编码器
重建，但同样五分钟仍报告 6 次 freeze、合计 2.609 秒，不能宣称卡顿已全部解决。

进一步同步测量：145 秒板端共享内存收到 8596 帧，P99 间隔 22.69ms，唯一超过
100ms 的间隔是连接建立时的 1.437 秒；随后编码输出连续。同期无缓存浏览器 120 秒
观察窗仍有 4 次 freeze、17 个丢包、最大画面回调间隔 583ms。剩余停顿发生在共享
内存输出之后，尚未区分 Janus 传输、网络与客户端调度。宿主仍有其他 Chrome 与
系统后台负载；这些是局域网桌面场景观测，不能代替独立机器持续运动或 WAN 验证。
证据：`logs/pikvm/hdmi-rate-observation.json`、`hevc-soak-final-37.log`、
`hevc-soak-debounce.log`、`hevc-arrival.json`、`hevc-soak-arrival.log`（后四项同目录）。

全新系统使用锁定的官方 Khadas Ubuntu 24.04/Fenix 1.7.5 基础镜像，加入 `.24`
六个基础组件及 `.39` PiKVM/管理器，内核 `b86c7e5bd`、驱动 `305ab27e9`。
八个额外 Ubuntu 运行依赖固定版本和 SHA256，先验证离线依赖闭包，再本地安装；
不依赖开发板的手工状态。修复 PiKVM 冷启动对 PD 服务的 Requires/After 顺序，
验证私有 Python 扩展、四应用动态库、默认服务唯一性、内核与设备身份初始化。
`vim4-kvm-ubuntu-pikvm39` 组装和只读离线验证通过；目前未刷写、未完成首次启动验证。
当前板子的 `/etc`、khadas 家目录和四应用数据已备份到
`build/backups/pikvm-before-image/config-and-data.tar.gz` 并检查 gzip 与 SHA256；
这是配置与数据备份，不是完整 eMMC 快照。刷写仍需明确清空 eMMC 授权。
