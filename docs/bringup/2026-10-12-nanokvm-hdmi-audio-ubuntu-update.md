# 2026-10-12：NanoKVM HDMI 音频、Ubuntu 管理与应用更新

继续保留原版 NanoKVM 菜单、设置页和 API。Ubuntu 差异放在 VIM4 build tag 与
固定 root helper 中，没有引入另一套管理界面。应用仍监听 8080。

- HDMI RX 音频设备为 `hw:AMLAUGESOUND,0`，48kHz 双声道 S16LE。厂商
  `audioserver.service` 独占该设备，部署时禁用；tvserver/HDMI 服务保留。
  ALSA → Opus 96Kbps/20ms → 原版 WebRTC 音轨，最后一个观看者离开后释放设备。
  Mac 通过 CoreAudio 定向向 AML TV 输出 440Hz，不改变系统默认输出；VIM4
  原始采样测得 440Hz 幅度约 3277。Chrome 原版音量滑块取消默认静音后，在
  4K 画面下收到并解码非静音音频（约 6 秒 278 包、293280 个采样）。
  USB 麦克风注入、MJPEG 音频尚未实现。
- 原版设备设置接入 NetworkManager 的 eth0 DHCP/静态 IPv4、Wi-Fi 扫描/连接/
  断开，以及 Ubuntu SSH、Avahi mDNS、主机名、时区、chrony 同步和重启。
  Wi-Fi 密码经 stdin 传入；失败的 Ethernet reapply 会恢复原 profile。
  板上读取、同值 DHCP/主机名/时区、启用服务、非法输入拒绝通过；单元测试覆盖
  地址边界、SSID 转义和回滚。没有改动现有 IP，没有关闭 SSH；未实际切换网段，
  Wi-Fi 当前未连接且没有凭据，因此不宣称入网成功。
- 原版账户页支持修改 Web 账户，使用 bcrypt 与 0600 原子文件写入，不调用
  Ubuntu passwd。隔离 API 测试验证新账户可校验且没有明文密码。真实账户密码
  未改，认证仍保持用户原先禁用的状态；仅修改 Web 密码不会自动启用登录认证。
- 新增可复现的 `NanoKVM-Pro/deploy/vim4/package.py`，生成 arm64
  `vim4-nanokvm` DEB、原版 tar.gz 更新包和 latest manifest。包含应用、前端、
  helper、sudoers 和服务；保留配置、账户与镜像。依赖既有 VIM4 内核、插件、
  HDMI/gadget/PD 服务，不是完整刷机镜像。拒绝 AX630 固件和其他平台包。
  未配置公开更新源，清除自定义源不会回退到原机 CDN。
- 实际调用原版手动 inspect/confirm 接口安装 `1.0.1+vim4.20261012`，任务
  succeeded 在自动重启服务后保留。通过板上临时 loopback HTTP 更新服务器，
  在线下载校验并安装 `1.0.2+vim4.20261012`，随后清除测试源。最终文案包为
  `1.0.3+vim4.20261012`。更新只重启应用，不重启板子。DEB 安装不是事务回滚，
  发布包应来自可信构建；当前没有公开发布更新服务。

VIM4 与默认目标 Go 测试、两种后端编译、Python helper 测试、前端 TypeScript/
生产构建通过。默认测试以 `LD_LIBRARY_PATH=$PWD/dl_lib` 加载原版 stub，不能代表
AX630 硬件验证。Chrome 原版设备、账户和更新设置无 pageerror/接口 404。
部署源与验证结果均保留在仓库，供后续系统镜像构建使用。
