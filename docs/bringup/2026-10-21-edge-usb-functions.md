# 2026-10-21：7.x USB 功能接入与主机传输

摘要：实验 One-KVM 已接入消费者 HID、虚拟盘、NCM/ECM/RNDIS 配置和 UAC2。
实际键盘、绝对/相对鼠标、点击/滚轮、只读及可写 FAT 盘、NCM/ECM 双向数据已验证。
UAC2 目前只完成接口/声卡及组合配置验证，主机实际录音未通过：原生录音器缺少
macOS 麦克风权限，浏览器指定 USB 输入的 getUserMedia 获取流超时，不能记成声音通过。
RNDIS 配置及枚举通过，但本次 Mac 未取得 IPv4 地址，Windows 数据通信尚未验证。
本记录不代表全部 USB 主机和物理拔插/整机睡眠场景通过。

## 版本与隔离

Linux `694ea2b5ce0ddf9a816c929a75863e42118b4b36`；One-KVM 最终版本及 ELF 哈希见
[sources.toml](../../packaging/kernel-edge/sources.toml)。DTB 未替换，运行
`7.3.0-rc7-vim4kvm-uhd1+`，内核 build ID
`a01ed3a5c479be77cfa39caa3decf4f061155db2`；安装同次正常 in-tree 构建的完整 Image
及 2334 模块集，保留 split BTF。模块包 SHA-256：
`303b7eb904e362ff34577fcd5d84bc1530beec449e46af101d165ff50a71b045`。

| 模块 | 压缩文件 SHA-256 |
|---|---|
| crg_udc | `ea6ba19ff30032fd102a37ca902d2855c400beef847622b0ca9140ae2f83d39c` |
| usb_f_uac2 | `1ae61d715f372f81bd087dc60ad89f9914e86bcccebf52b52cc7625963b8c374` |
| u_audio | `6887506aa7bf78ccef138265548b7223453f1a786877506f4a48d132f0df27f1` |
| usb_f_hid | `56cbf099b76ba2fe80759afac0df06244377f8e0143de51978621f8382a83cdf` |

只替换 `/opt/vim4-onekvm-edge/one-kvm` ELF，启动包装器保留。
5.15 Image、默认启动项、生产 ELF、生产 USB 助手/服务和系统 JPEG 插件保持原样。
本轮备份位于板上 `/var/backups/vim4-onekvm-edge-20261021-usb`，含修改前 ELF、服务、
准备器、完整实验数据目录、部署清单及旧 USB 模块。完整内核备份在
`/var/backups/vim4-onekvm-edge-20261021-usb-full`；保留原 Image、DTB 和匹配旧 Image
的模块集。重启均由串口单次选择 OneKvmTest，默认启动仍为 5.15。

应用使用独立 `/usr/libexec/vim4-onekvm-edge`。它与普通助手来自相同源码，但按安装
文件名选择固定的 `/var/lib/one-kvm-edge/msd` 和 `/run/vim4-onekvm-edge-usb`，并拒绝
在 5.x 运行；不接受调用者传入任意媒体根目录。`vim4media` 的路径校验、共享介质锁、
外部介质只读规则继续生效；生产媒体与运行时 journal 保持独立。

准备器补建未链接的 NCM、UAC2，重复运行不重建 HID、不解绑、不清空已挂载 LUN。
NCM MAC 从本板 Ethernet 唯一地址派生；UAC2 仅启用 gadget playback → 主机麦克风，
48kHz、双声道 S16LE，禁用反向流及音量/静音中断端点。
默认仍为三个 HID，其余功能按需开启；串口所需 CONFIG_USB_CONFIGFS_ACM 未启用。

安装顺序：先备份，再安装源码助手到独立路径和
`packaging/kernel-edge/one-kvm-edge-usb.sudoers`，通过 visudo 校验后安装准备器、
实验 ELF 和服务。新的 ExecStopPost 只调用独立助手恢复；不要覆盖生产助手或把 ELF
写到同名启动包装器。配置、源码锁和硬件证据必须与最终部署清单一致。

## 上板发现的内核问题

1. UAC2 GET_CUR 同时查询播放、采集采样率，即使 capture 被禁用，其运行时锁也未
   初始化。改为只访问请求指向且已启用的方向，未启用的 clock 返回 EOPNOTSUPP。
2. disconnect 总会调用两个 stop 路径；只修 GET_CUR 后，stop_capture 仍报告未初始化
   锁。因此两个 runtime 的锁与 owner 都在 g_audio_setup 无条件初始化，缓冲分配仍
   按启用方向进行。前一次失败重启记录保留，不能只看 taint=0 忽略 lockdep INFO。
3. CRG 原来等 udc_stop 才完成排队请求，此时 composite 已解绑并释放完成上下文。
   UAC2 类请求不一定设置 composite.setup_pending，导致 unknown request 警告。
   现在 disconnect 先禁止新提交/SETUP，停止 DMA，再在函数仍存在时完成所有请求；
   停止失败时保留请求，不提前释放 DMA。
4. 连续组合切换耗尽 CRG 的 200 个请求池。实际泄漏在 f_hid：每次 bind 分配
   GET_REPORT 请求，disable 只释放等待用户回复的请求，unbind 遗漏空闲请求。
   现在排空工作队列后释放剩余请求，字符串分配失败也走释放路径。离线用实际
   unbind 函数循环 500 次，检查每次释放且不重复释放。

第四项首次仅换 HID 模块时触发 BTF Invalid name：构建已重新链接 vmlinux，旧 Image
仍在运行。没有删除 BTF 或关闭校验；改装同次完整 Image/模块集，再重启验收。

第一项与上游对单方向运行时的
[邮件讨论](https://lists.openwall.net/linux-kernel/2026/08/21/1010) 有关；本板实际触发
capture getter，随后还触发 stop_capture，不能只套用 playback getter 的保护即宣布修复。
最终针对实际请求和生命周期修正，没有关闭 lockdep 或清除 taint 掩盖问题。

离线 `test_uac2_controls.py` 用实际 GET_CUR 函数检查单方向/关闭 clock、正确采样率、
短回复和越界写入，启用 ASan/UBSan。CRG 实际函数回归检查成功停止后的完成顺序、
停止超时保留请求、EP0 reset/SETUP/解绑与分配失败；checkpatch 无错误或警告。

## 应用及介质生命周期

移除原先只允许三种 HID 的笼统限制，保留五个 IN 端点预算：HID、盘和 UAC2 各一个，
网卡两个；API 在关闭 HID 前预留已开启虚拟盘的容量，拒绝超限和未支持的串口。
组合用纯函数检查，覆盖两种后端共 512 种开关组合。

挂载期间修改 USB 配置先返回 400，root 助手在介质锁内再次检查，避免解绑正在使用的
磁盘。第一次硬件负例虽被助手阻止，但应用包装为 500 且重载 HID；前移校验后重测。
应用退出及 ExecStopPost 必须保留主机介质和当前 USB 配置，直到主机 SCSI eject。
初次应用重启实测发现 MSD shutdown 仍主动 detach；已补齐进程退出策略，并在助手
中拒绝非主机确认的强制 detach。随后发现 systemd 私有 StateDirectory 的挂载点在
进程退出后消失，LUN 路径从完整路径缩短为 /msd/images/...，文件并非已关闭。
独立 root 助手现在通过 Python 3.12 os.setns 进入 PID 1 挂载命名空间后打开镜像。
重启回归确认原 LUN、主机磁盘节点及写入哈希不变。测试只使用专用镜像。

## 已验证的主机效果

Mac 同时为 USB 被控机和浏览器客户端，控制经有线 SSH/独立登录网关。
键鼠测试只向临时原生窗口发事件，结束恢复前台应用和指针：

- 右方向键一按一放，主机分别收到 keyCode 124；绝对鼠标两处坐标误差小于 2%。
- 相对鼠标 X=24/Y=16 后，主机指针沿预期方向移动；点击按下/释放与滚轮均被接收。
- 消费者 HID 配置/枚举、单鼠标、单键盘、禁用/重新启用 HID 及 UI 保存由组合工具覆盖；
  没有注入改变系统音量的媒体键来宣称全部 consumer usage 已验证。

匹配完整内核启动后，80 次真实 UDC 重新绑定全部通过；每次保留三个 HID 文件描述符
注册在 epoll 中跨过重绑，再分别注销和关闭。该轮停止应用，结束自动启动；随后
重复实际键鼠输入及功能组合/UI 回归，确认没有新 WARNING/BUG/lockdep INFO。

专用 32MiB FAT16 镜像、卷标 EDGEUSB21，带固定 marker.txt；每轮上传生成独立 ID，
主机确认 BusProtocol=USB、只读属性和 marker。可写轮同时链接三个 HID、盘和 UAC2，
达到五个 IN 端点；写入 1MiB written.bin，主机读回及安全弹出后板端 mtype 读回 SHA-256
均为 `bd8a5183fdafb052402b7f52480145004a781b927f0d376e4fbd922da44f6926`，
fsck.vfat -n 通过。只有 host SCSI eject 将 LUN 清空后才删除测试镜像或恢复配置。
回归还要求挂载期间配置拒绝保持原 LUN，以及应用重启保留原磁盘节点与内容。
UAC2 在该组合中仅验证接口共存，未将其视为并发声音验收。

NCM/ECM 各自取得 DHCP ACK，Mac en10、板端 usb0/usb1，USB 网段 10.42.0.0/24。
临时 HTTP 服务只绑定 USB 地址 10.42.0.1，并限制测试载荷大小和存活时间。
主机 curl 显式绑定 USB 接口，分别下载/上传 1048576 字节；两个方向 SHA-256 均为
`fbbab289f7f94b25736c58be46a994c441fd02552cc6022352e3d86d2fab7c83`。
这验证通信，不是吞吐率或 NAT 上网性能验收。RNDIS 只完成配置/枚举，没有本机通信证明。
最终完整内核再次通过 NCM/ECM 同样传输，记录在 `usb-final-network-ncm-data.jsonl`
及 `usb-final-network-ecm-data.jsonl`；测试后恢复三个 HID，介质和 USB 网络均关闭。

测试初版按 MAC 匹配超时：本机从 Python/Node 启动的 ifconfig 返回占位 MAC，独立
shell 检查却能读到实际地址。主机工具改按 USB 子网、DHCP ACK 及指定发送接口验证，
不修改 macOS 网络配置或关闭隐私保护。登录控制在本机直连请求失败时使用既有 SSH
网关转发；数据载荷始终经真实 USB 网卡，未用 SSH 文件传输冒充 USB 通信。

## 工具、复测与边界

- `one-kvm-usb-check.mjs --exclusive --hid-only`，先编译 `/tmp/vim4-input-target`。
- `one-kvm-usb-media-check.mjs --exclusive --image=专用.img`，镜像必须是上述测试卷和 marker；
  禁止使用真实用户盘。遇到弹出失败不强制解绑，也不删除仍挂载的镜像。
- `one-kvm-usb-network-host.py --exclusive`，先从网页选择一种网卡；验证当前接口，不改配置。
- `one-kvm-usb-profile-check.mjs --exclusive --output-prefix=新路径` 验证组合和 UI，退出后拒绝
  新 kernel WARNING/lockdep INFO；`--audio` 用已授权的原生录音器，`--browser-audio` 只打开
  唯一匹配的 USB 输入，排除 default/communications 别名，超时退出并恢复。

原始证据在不入库的 `logs/kernel-edge/`：`usb-edge-hid-final.jsonl`、
`usb-edge-profile-clean.jsonl`、`usb-edge-hid-80-rebind.log`、
`usb-edge-media-namespace.jsonl`（盘写回及重启）、`usb-native-data2-ncm.jsonl`、
`usb-native-data3-ecm.jsonl`、`usb-native-data3-rndis.stderr`。
`usb-edge-uart.log` 保留最初两处告警，`usb-edge-reboot-uart.log` 是仅修 GET_CUR 的
中间版本，`usb-edge-reboot2-uart.log` 为补齐两个 stop runtime 后的启动及后续测试，
`usb-edge-reboot3-uart.log` 保留 BTF 拒绝，`usb-edge-reboot4-uart.log` 为匹配完整内核。
`usb-edge-modules-final.json` 核对运行内核 build ID 和全部 2334 模块压缩文件哈希。
`usb-edge-profile*.stderr` 包含录音权限、getUserMedia 超时和测试工具失败，不统称通过。

最终匹配内核的盘回归为 `usb-edge-media-matched.jsonl`。音视频短测用物理 HDMI
运动源：`usb-final-video-h264.jsonl` / `usb-final-video-h265.jsonl` 分别约 60.06 / 59.96fps，
均为 3840×2160、零 freeze/drop/loss，WebRTC 音频解码峰值约 0.107 / 0.106。
MJPEG 首次被既有 UU 编码限制拒绝；仅在确认 UU 无连接后暂时关闭并恢复，
`usb-final-mjpeg.jsonl` 验证三处一致且推进的运动标记：1080p/720p 约 60fps，
4K q80 约 51.78fps，关闭后 DMA 为零。这是 USB 修复后的短回归，不替代长测。
主仓库离线 136 项（5 项按环境跳过）、One-KVM Rust 724 项（2 项忽略）、Linux
root 助手 29 项及四个内核回归脚本通过。5.15 六个受保护文件哈希未变。
通用 desktop 测试被容器 FFmpeg 缺少 AV_HWDEVICE_TYPE_RKMPP 枚举阻止，未进入 Rust
测试，见 `usb-edge-generic-tests.log`；不将该目标计为通过。

尚未完成：主机 UAC2 实际录音、Windows/RNDIS 数据、键盘 LED 的实际主机反馈、
真实 USB 物理拔插/整机睡眠及长时间并发压力。默认 5.15 保留，不能据短测提升为发布版。
