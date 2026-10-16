# 2026-10-12：WebRTC 网页 KVM

应用仓库为同级 `kvm/`，工作分支 `vim4`。详见其中 `VIM4.md`。
网页地址 **http://192.168.50.210:8080**，本次选择本地免密码模式。
SSH 已恢复，可以直接同步代码和构建；Ubuntu 密码未改。

- `go build -tags vim4` 排除 Rockchip/LVGL，接入 GStreamer appsink。
- 视频路径：vfmcapsrc → amlvenc → h264parse → appsink → WebRTC。
  完整 H.264 帧按 PTS 间隔送入媒体轨道，每个 IDR 重发 SPS/PPS。
- 发现 amlvenc 的 duration 仍为 1/30 秒，即使实际输入为 60fps。
  改用相邻 PTS 后，300 帧媒体时长为 5.017 秒；ffprobe 确认 1080p60。
- 键鼠复用既有 hidg0–2，适配六字节绝对鼠标、四字节相对鼠标。
  应用不改 gadget 和 PD，系统网络、时钟、升级、看门狗仍由 Ubuntu 管理。
- `deploy/vim4/install.sh` 安装 `vim4-kvm.service` 和 HID udev 权限规则。
  服务使用 khadas 用户、video/input 组，配置在 `/var/lib/vim4-kvm/config.json`。
- root 启动编码会崩溃：现有 khadas 所有的 `/tmp/vpu_mutex.map` 在 root
  使用 O_CREAT 打开时返回 EACCES。编码测试和服务统一用 khadas，保留共享 /tmp。

验证：ARM64 `go test -tags vim4 ./...` 全部通过，网页 TypeScript 与构建通过。
Chrome 3 秒解码约 180 帧；通过 WebRTC RPC 和网页实际 Shift 按键分别验证
Mac modifierFlags 0 → 131072 → 0。绝对鼠标到 (960,540)，相对鼠标向右移动。
浏览器刷新可以重新打开编码器并恢复视频。

整机重启后 boot ID 改变，PD/HDMI/gadget/web 四个服务均 active，PD Result=success，
UDC=configured，hidg0–2 权限自动恢复为 root:input 0660。
浏览器再次解码 1080p 视频（3 秒 181 帧，新增丢帧 2），网页 Shift 与两种鼠标再次通过。
此数据不是延迟测量，也不代表零丢帧。
