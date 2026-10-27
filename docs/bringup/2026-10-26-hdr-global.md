# 2026-10-26：远程 HDR 全局默认与源端切换

接续 [GPU Main10 60fps](2026-10-26-hdr-gpu-pipeline.md)，增加管理器全局默认，
继续核实真实 HDMI 的 PQ/SDR 切换和官方 UU 客户端。

## 全局设置

管理器「视频输入 → HDR 转 SDR」新增「启用 HDR 转 SDR」。
`POST /api/hdr-mapping` 必须显式提供布尔 `enabled`，缺失、null、字符串均拒绝。
helper 原子保存 `/etc/default/vim4-kvm-hdr` 的 `HDR_SDR_ENABLED=1|0`，
保留曲线及其他内容；保存曲线也保留开关。动作不改 EDID、不脉冲 HPD、不重启 HDMI。

One-KVM 启动及运行时读取该默认值，运行时检查间隔一秒；只修改 HDR 偏好，
保留尺寸、帧率与码率。Main/Main10 切换等待旧管线释放后通知网页重新协商 SDP。
UU 会话的 HDR 偏好临时覆盖运行状态，期间全局开关只修改保存的默认值；
断开或接管时恢复最新全局值。八位客户端在会话内自动使用 SDR。
旧安装未保存开关时保留原应用偏好，管理器首次保存后启用共享默认；
One-KVM 的同名设置随后同步此文件，避免两处默认值互相覆盖。

关闭转换只对支持真 HDR 的 One-KVM H.265 会话生效；H.264、JPEG、截图、
其他应用及当前 7.x 路径继续使用 SDR。HDMI OUT 偏好独立。

## 连续内存与管线生命周期

旧版本真实 PQ→SDR 再次复现编码器连续 200MiB 分配失败。
缩减 SDR 池的第一版候选恢复了约60fps，但实际只分配到三个采集缓冲，
随后截图触发 CREATE_BUFS 失败及应用 SIGSEGV，不能算作通过。
进一步对照发现，GPU P010 双槽和独立 SDR 截图池先分配，会切碎编码器所需区间；
只减少 SDR 队列不足以解决 Main10 启动。

候选在 GPU/VDIN1 分配前打开 `/dev/amvenc_multi`，先由驱动预留公共连续200MiB。
第一张编码帧到达后释放这份启动引用，由 SDK 自己的 fd 保持资源；
最终 SDK 关闭仍能完整释放和复位驱动，避免跨八位/十位 SDK 保留实例池。
采集失败沿用有界重试，不重启 HDMI。
SDR 编码队列从三帧减为一帧；下游分配预算调整后实际申请六个缓冲，
HDR 专用截图路径申请五个，保持截图原始采集尺寸与 VideoMeta。
另一个失败候选在返回 PQ 时 GPU 的约24.9MiB分配失败，回落 CPU 后只有34.7fps。
最终在原生 HDR 模式将主采集池上限设为六帧，当前4K60实际分配五帧，
比原设备树十帧节省约118MiB；VDIN1的显式V4L2申请独立。
`hdmi-setup.sh` 持久化该策略，保留管理员更小的限制，不影响旧采集模式。

## 最终部署与实测

One-KVM `0851e25e`、manager `826dfe47`，均已部署；
内核保持 `5.15.137-vim4kvm-hdrdual6`，本轮无重启。
Mac mini 实体 HDMI 经 RTK UHD HDR 输入3840×2160p60，Chrome解码，
运动夹具提供连续帧号和三行校验。帧率是浏览器解码差分，不代表端到端延迟。

| 场景 | 三段实测 fps | 画面与连接 |
|---|---|---|
| 管理器关闭→开启→关闭转换 | 59.990 / 59.986 / 59.972 | Main10/PQ→Main/709→Main10/PQ；各20个运动帧校验正确 |
| 实体源 PQ→SDR→PQ 第一轮 | 59.982 / 59.928 / 60.009 | 同一个RTC连接；各20个运动帧校验正确；SDR期间三次MCP截图成功 |
| 实体源 PQ→SDR→PQ 第二轮 | 60.008 / 59.936 / 59.995 | 同一个RTC连接；各20个运动帧校验正确；SDR期间再截图成功 |

最终两轮的有界内核日志无CMA分配失败、Oops或新增Warning，
应用PID143903、重启计数0，内核taint12800不变。
官方UU在线时将全局默认从HDR改为SDR，同一会话保持59.995/59.998fps；
断开后网页实际恢复Main/BT.709，59.957fps。H.264另测60.056fps。
独立MJPEG模式因现有UU启用配置限制返回400，不记为通过；不为该回归改变UU配置。

manager Go全套、前端构建、浏览器控件回归通过，helper运行214项、无失败（macOS跳过12项）；
One-KVM VIM4目标785项通过、忽略3项，release构建通过。
另尝试的非VIM4默认cargo check被现有ARM FFmpeg缺少`AV_HWDEVICE_TYPE_RKMPP`阻塞，
未算通过，不影响已验证的VIM4目标。主仓库运行279项离线测试、无失败、跳过7项，
包含新增HDMI启动池预算回归与文档检查。

部署二进制SHA256：

```text
One-KVM 9c9e18ee393ee8251f8b644686035088828c70db6e1be9b3a3983b2db9094bdc
manager 65c7d3efcff50256cdf03a0e529d1abd7eba537200ee63fc6df7c04779ca7ac6
```

最终保留全局转换开启、原曲线203/1000、RTK UHD HDR与4K60 PQ输入。
备份在板端 `/var/backups/vim4-hdr-global-20261026/`，包含旧应用、helper、
配置和HDMI启动脚本；回退应用需同步恢复helper与脚本。
完全恢复旧内存策略还需将`max_buf_num`恢复12并重新分配主采集池。

## 客户端与验证边界

官方 macOS UU 实际协商 H.265 `profile-id=1`，没有提供 Main10，画质菜单也没有 HDR 项。
其 SDR 连接、全局默认为 HDR 时的兼容处理及最新默认值恢复，与真 HDR 客户端开关分别验收。
没有可用 Main10 官方客户端，不将协议单元测试或网页 Main10 当作官方 UU HDR 验收。
源端与接收浏览器同为 Mac mini；UU 桌面会递归捕获自身窗口，只验证连接与兼容行为，
不据此测量端到端延迟或显示器 HDR 光度。无 HDMI OUT 显示器，未测本地透传；未测音频。

## 证据位置

忽略目录 `build/hdr-gpu/` 保存构建与测量原始记录：
`global-switch-bootref.log`、`source-roundtrip-primary6.log`、
`source-roundtrip-primary6-repeat.log`、`roundtrip-primary6-both-kernel.log`、
`uu-global-live-final.log`、`uu-default-restored.log`、`final-codec-smoke.log`、
`final-mjpeg-smoke.log`、`final-board-state.log`。
桌面和移动版截图为`global-manager-desktop.png`、`global-manager-mobile.png`。
