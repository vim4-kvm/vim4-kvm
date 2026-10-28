# 2026-10-14：One-KVM 本地扩展、看门狗与包更新

One-KVM `0989e476`，最终安装 `vim4-onekvm 2.5.1+vim4.20261014.8`。
主仓库 `709f0f0` 是包的源码记录；更新验证脚本随后在 `7e427a8` 修正重启后的重新登录。
保留其他 KVM 和管理器原版本，仅新增终端所需的 libwebsockets 运行库。
中间 `.7` 包引入 Ubuntu ttyd 守护包；发现其默认启动独立服务后，`.8` 改为
包内私有终端程序，移除本轮安装的 ttyd 包。不会额外启动独立终端服务。

新增运行目录和终端就绪等待，解决 spawn 后立即连接 Unix socket 的竞态。
Gostc 2.0.9、EasyTier 2.4.5、FRP 0.71.0 的 ARM64 制品与许可证随包安装，
下载 SHA256 固定在 `packaging/ubuntu/extensions.lock.json`。仅 EasyTier 程序具有
cap_net_admin。硬件看门狗通过服务的专用附加组访问，不放宽为全局可写。

网页更新使用 VIM4 专属平台标识和包版本；下载大小/SHA256、deb 包名/架构/版本、
APT 依赖计划、安装文件校验和重启流程均已接通。构建生成两个更新清单；
公网 Release 尚未发布，不能将本地流程通过写成公网通道已上线。

验证：

- 前端构建、VIM4 release 构建、558 项 Rust 测试、7 项助手测试、42 项工作区测试通过。
- 七组件包校验通过；隔离容器实际验证 deb 升级、保留数据、拒绝重复版本和降级。
  同一容器还运行生产程序，验证认证 API → 清单 → 下载校验 → 安装 → exec 重启 → 重新登录。
- 最终包网页终端实际执行 `id -un` 返回 khadas；Gostc 可启停；EasyTier 创建 TUN
  并在停止后清理；FRP 经仅监听 loopback 的临时 frps 转发 One-KVM HTTP 成功。
- 看门狗开启、初始喂狗及运行检查、安全关闭通过；结束时 sysfs state 为 inactive。
  未进行强杀应用或等待超时导致整机复位的破坏性测试。
- 最终包 WebRTC 视频 3840×2160、59.97 fps，采样中无丢帧/丢包；输入 HDMI 测试音后，
  Web Audio 从真实 WebRTC 轨道采样峰值 0.620，证实解码得到非零音频。
  totalAudioEnergy 仍为 0；单靠此统计判定静音会误判。

用户选择先完成本地适配，公网服务器稍后配置。测试结束恢复各扩展原配置并关闭，
检查脚本显式还原 GET 隐去的空密钥和空完整配置，并比对还原结果；临时 frps、
测试配置及 TUN 均清理。安全弹出后恢复原 256 MiB 虚拟盘，未重建盘或删除用户文件。
One-KVM 和管理器 active，`dpkg --verify vim4-onekvm`、`dpkg --audit` 无输出。
HDMI InvocationID 始终为 `5adb6d1c9b494584996befd0f64d2877`。

普通 ARM 默认目标的额外编译检查被 Ubuntu FFmpeg 缺少 AV_HWDEVICE_TYPE_RKMPP
阻塞；VIM4 feature 构建与测试通过，未将该通用目标检查报告为通过。
日志位于 `logs/one-kvm/features-*.log`。其余未接硬件和未验收功能见
[功能复核](../archive/one-kvm-audit.md)。
