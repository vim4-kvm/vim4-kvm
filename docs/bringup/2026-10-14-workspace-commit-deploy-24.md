# 2026-10-14：提交工作区积累改动并部署 .24

将各仓库未提交源码分别提交：NanoKVM `28eafd8`（切换回来时恢复 EDID）、
JetKVM `7040219`（重新连接 HDMI 与共享 EDID 标记）、One-KVM `a2c450a1`
（Tight JPEG 不再要求客户端显式报告质量编码）。管理器 main 的趋势图 `dd37838`
与 onekvm 的三应用选择、HDR 控件合并为 `be7f4f0`，同时保留 Wi-Fi 开关。
工作区清单更新到上述提交，manager 开发分支统一为 main。未推送远端。

从干净源码（主仓库 `1fbf80e`）构建 `2.5.1+vim4.20261014.24`，七包 package、
隔离 verify、board.py deploy 均通过，从 .23 升级并保持 NanoKVM 启用。
构建覆盖 VIM4/默认 NanoKVM Go 测试、JetKVM 内部包测试、One-KVM 561 项 Rust
测试与管理器测试；One-KVM 助手 15 项在 root Ubuntu ARM64 环境通过，其 Mac
宿主测试因临时目录非 root 所有而失败，未将宿主结果计为通过。

板上浏览器确认三应用、趋势图、HDR 和 Wi-Fi 开关均存在。经有线管理连接实测
Wi-Fi 关闭/开启，并恢复开启；随后 NanoKVM 扫描返回 16 个热点。
board.py verify 的 HID 通过，视频为 3840×2160、约 60fps、零丢帧/丢包。
PCM 被 NanoKVM 音频会话占用，独立录音跳过；修正脚本管道末端返回 0 时把 busy
误判为零帧失败的问题。audio-smoke 经真实音量控件收取 6 秒 288480 个采样、
零丢包和补偿采样，能量为 0（信源静音）；不代表已验证有声输出。
最后主机工具 43 项测试通过。未测实际 Wi-Fi 关联、HDMI 重连按钮和 VNC 客户端实机。

证据：`logs/wifi-release/`；部署日志 `logs/board-20261014-211909-d8d81b/`。
