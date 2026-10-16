# 2026-10-12：NanoKVM-Pro 首阶段部署

应用仓库的 `vim4` 构建目标排除占位 libkvm，接入 vfmcapsrc → amlvenc →
h264parse → appsink。H.264 12Mbps、GOP 30，按输入 PTS 计算媒体时间。
最后一个视频连接退出后释放编码器；修复了旧管线关闭过程中，新连接启动请求
被忽略而造成刷新黑屏的问题。捕获失败后按 1 秒间隔重新尝试。

键鼠复用现有 gadget，调整 hidg1/hidg2 映射；限时写入，设备不存在时不再空指针
崩溃。最后一个输入连接关闭时等待已排队报告完成，然后释放按键及鼠标按钮，
保留绝对坐标。网页保留粘贴、虚拟键盘、快捷键、鼠标模式和全屏。
其他设备专用功能尚未启用；API 同样不注册固件更新、USB 重建等操作。

应用路径 `/opt/vim4-nanokvm`，配置 `/etc/kvm/server.yaml`，服务 `nanokvm`，
仍为 khadas 用户和本地免密码模式。网页 **http://192.168.50.210:8080**。
Ubuntu 密码未修改。旧 `vim4-kvm` 应用服务已禁用，HDMI/gadget/PD 服务保持启用。
构建、安装及回退步骤见 NanoKVM-Pro/VIM4.md，部署文件进入该应用仓库。

验证：ARM64 `go test -tags vim4 ./...`、前端 TypeScript/生产构建通过，
原始非 vim4 目标也成功编译（仅编译占位库，未运行）。Go `-race` 在板上无法启动：
ThreadSanitizer 要求 48 位 VMA，当前内核为 39 位；没有宣称竞争检测通过。

整机重启后 NanoKVM/HDMI/gadget/PD 均 active、UDC=configured，浏览器显示
3840×2160，5 秒新增 301 帧、播放丢帧 12。网页实际 Shift 按下/释放对应
Mac modifierFlags 131072/0；绝对鼠标到 (480,810)，相对鼠标向右移动。
刷新后恢复 4K。该结果不代表零丢帧或长时间压力测试通过。

## 下一步

- HDMI 热插拔、分辨率切换、多浏览器交接的 WebRTC 回归验证
- 音频、虚拟介质、视频设置和错误自动恢复
- NCM 的 IP 通信验证；当前网页走 eth0
- 断电冷启动、Mac 休眠和 USB 热插拔验证
- 必要时扩展编码器码率/帧率控制（后续进展见 [NanoKVM 视频控件](2026-10-12-nanokvm-video-controls-mjpeg-vdin.md)）
