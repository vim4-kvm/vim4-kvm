# 2026-10-12：NanoKVM 终端、脚本、网络唤醒与镜像管理

沿用原版菜单、弹窗和 API，增加终端、shell/Python 脚本的上传/前后台执行/删除、
Wake-on-LAN、标题和菜单图标设置。终端以 khadas 运行，shell 退出会关闭 WebSocket；
脚本不再通过拼接 shell 命令执行。WOL 使用 UDP 广播，缓存写入串行化。
原版手动串口界面保留，VIM4 不显示 AX630 固定串口预设；已安装 picocom 并加入
dialout 组，没有外接串口硬件，因此不宣称串口通信实测通过。

镜像存储在 `/var/lib/vim4-kvm/images`，沿用原版分块上传、挂载、校验、删除和 URL
下载界面。未完成上传/下载不会成为可挂载镜像；禁止覆盖或删除正在挂载的文件。
固定 root helper 只接受该目录中的普通 IMG/ISO，以已打开的文件描述符交给 configfs。
不导出 Ubuntu 根盘。CD-ROM 强制只读。板端 gadget 创建但默认不连接 mass_storage.disk0。

USB 实测发现两点：

- CRG 驱动把 OUT context 也声明为 IN，导致省略 HID OUT 端点后产生错误分配；
  修正 capabilities，仅声明硬件固定方向。所有 HID 改用 interrupt IN，键盘 LED
  output 通过 control SET_REPORT。模块 build-id `c6056f5befd206c1a05e40c797895b49bd507aa3`，
  已完整更新 initramfs 并重启。
- 三个 HID + NCM + mass storage 同时使用时，第六个 IN（DCI 12）仍 CONFIG_EP 超时。
  当前挂载镜像时切换掉 NCM，弹出后恢复 NCM，保留 HID function 与 PD 供电契约。
  挂载弹窗明确提示使用以太网/Wi-Fi 管理，不能宣称网卡与镜像盘同时可用。
  configfs 重新枚举时留出 500ms 断开时间，不重新运行 PD 协商。

验证：ARM64 Go 全套测试、两种后端目标编译、前端 TypeScript/生产构建、Python
helper 边界测试通过。真实终端命令及退出、shell/Python 脚本、标题/菜单持久化、
WOL API/缓存、分块上传与乱序拒绝、SHA256、URL 下载、挂载删除保护通过。
WOL 包结构由 UDP 接收测试核对，没有让供电的 Mac 睡眠做唤醒测试。

Mac 已枚举并挂载测试 FAT 镜像与 ISO 光盘；镜像挂载期间，Chrome 实测键盘 Shift
以及绝对/相对鼠标通过，4K H.264 和刷新恢复正常。首次文件读取看似卡住，后查明
macOS tccd 在等待 `com.yetone.magpie` 的 `SystemPolicyRemovableVolumes` 权限弹窗。
因此文件级读写尚未验证，不将其记为驱动传输失败或读写成功；等待用户授权后复测。
测试文件 `vim4-media-check.img/.iso` 留在镜像目录，已弹出，供后续验证。

最终 boot-id `a1cd93b8-a8dd-4c1e-bf92-905c2900569f`；NanoKVM、HDMI、gadget、PD
均 active，UDC=configured。USB gadget 重启会经 Requires 关系停止 PD 服务，再启动
NanoKVM 时会重新执行 PD 引导；仅挂载/弹出镜像不应重启 gadget 服务。
