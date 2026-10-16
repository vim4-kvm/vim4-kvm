# 2026-10-13：补齐原 NanoKVM 功能缺项

- 最终组件 1.0.3+vim4.20261013.18 来自干净提交（应用 6e05134、编码插件
  7f34fb3、主仓库 492fa09；清单固定提交尚未更新）。开发包 .10–.17 带脏标记，
  仅用于逐项上板。board.py verify 的 hid/audio/video 全部 PASS。
- 防休眠：相对、绝对两种模式实际移动 Mac 光标；重启 NanoKVM 后保持开启，
  关闭后删除配置，不再移动。
- H.264 Direct、H.265 WebRTC/Direct：4K60 静态桌面，各模式解码约 60fps、
  丢帧 0；H.265 协商 video/H265，携带 NACK/PLI/RTX。最后一个查看端离开后释放
  编码器。Direct 依赖 WebCodecs，Chrome 只在安全上下文提供，HTTP 下需 HTTPS。
- 自定义 EDID：hdmirx edid_with_port + EDID_UPDATE_WITH_PORT ioctl 写入 port B；
  Mac 识别到自定义显示器名，并能在 4K60/1080P60 预设间切换。tvserver 开机写入
  厂商 EDID 后由 HDMI 服务恢复所选 EDID，整机重启验证通过；修改采集分辨率重启
  HDMI 服务不会再次拉低 HPD。
- MJPEG/Direct 音频：增加纯音频 WebRTC 会话。复测发现 GetStreamType 与读帧共用
  互斥锁，10fps MJPEG 只收到 3 包/秒；改为原子读取后，四种模式均 50 包/秒，
  补偿 0，能收到 440Hz 测试音。H.264 WebRTC 在低帧率设置下也受益于此修复。
- CBR/VBR：厂商 strict_rc_window 实测会跳过大量帧，也不能把码率压在目标值，
  因此不采用（logs/rc-strict-window-20261013.txt）。VBR 改用 qp-max=36 上限。
  运动画面、3000 Kbps 目标时，浏览器端 CBR 3.99 Mbps、VBR 10.23 Mbps，均为
  60fps 且丢帧 0（logs/rc-browser-20261013.txt）。
- 快照：/api/stream/snapshot 请求 IDR 后软件解码，或直接采集；直播 H.264 期间
  取快照用时 0.25–0.77s，查看端保持 60fps、丢帧 0。
- Tailscale：经官方签名 apt 源安装约 20 秒，状态 notLogin，能取得登录链接，
  停止/启动/卸载正常。没有账号授权，未验证组网。测试后已 purge，恢复原状。
- AI 助手：python3-venv + 应用私有 venv 安装依赖；页面、令牌鉴权、socket、
  桌面预览（快照）正常。经助手函数验证绝对定位到 (0.25,0.25)，相对移动正常。
  未提供模型 API Key，未执行推理任务。
- USB 麦克风：UAC2 仅提供主机输入（48kHz 双声道），开启时替换 NCM；可与虚拟介质
  同时存在（HID×3+存储+UAC2 已枚举，HID 正常）。Chrome 模拟麦克风经原按钮开启后，
  NanoKVM 启动 aplay 并收到 PCM；关闭后恢复 NCM。终端没有 macOS 麦克风权限，
  未验证主机实际录到声音（tools/uac-record-level.swift 待授权后复测）。
- 内核崩溃：USB 功能重新绑定后关闭仍注册在 epoll 中的 /dev/hidg*，触发
  remove_wait_queue list_del corruption（logs/uart-mic-crash.log）。5.15
  f_hid 的 hidg_bind 会重新初始化等待队列。应用改为重新枚举期间关闭 HID 文件，
  复现序列不再崩溃；内核侧根因修复待处理，虚拟介质切换此前也存在同样风险。
- 崩溃损坏：根分区 data=writeback，panic 前两分钟安装的 6 个 NanoKVM sudoers
  文件被清零，特权接口失效。dpkg --verify 确认仅这 6 个 conffile 受影响；
  经授权按包内容恢复并 visudo 校验，此后部署均 sync。
