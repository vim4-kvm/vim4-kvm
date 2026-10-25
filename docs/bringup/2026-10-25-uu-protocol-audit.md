# 2026-10-25：One-KVM UU 协议审查与 P1 修复

审查基线：主仓 `c604760`、One-KVM `24d35af8`、参考 `bf7bd50`。已读双方约定、README、许可证及相关文档，扫描最近100提交。原审查只读；审阅后授权修复P1并部署验收。参考差异不自动等于错误。

路径前缀：`R/`＝相邻 `uu-remote-linux/src/`；`U/`＝`One-KVM/src/uu_remote/`；`O/`＝`One-KVM/src/`；`C/`＝`~/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/`。文件:行均为审查基线；优先级P1→P2→P3；人日含离线回归，不含上板验收。

## 错误

E1–E7 已独立修复并推送 `vim4/a168d726`，各有回归；原尺寸4K60稳定600秒通过。后续缩放CMA、最低HEVC码率与G4已在 `vim4/1c1a790d` 修复验收，见[后续记录](2026-10-25-uu-cma-tools.md)。

| 编号/优先级 | 参考；我们 | 影响、建议修复 | 人日 |
|---|---|---|---|
| E1/P1 已修：信令背压 | R/signaling.rs:81,247,515；U/signaling.rs:135,159,295,348 | 满队列阻塞心跳/退出。`196e6c16`：独立看门狗、投递/写入10秒超时，先回收读写再通知断线；测停读、满队列及超时。 | 1–2 |
| E2/P1 已修：码率单位 | R/capture_setting.rs:115,275,517；U/wire.rs:347,482,663；U/peer.rs:1669 | 1 Mbps误夹到60 Mbps、同步单位错。`9374de85`：协议统一bit/s，入口转kbps，兼容旧单位；测请求/同步及溢出边界，新增发送字节计数。 | 1 |
| E3/P1 已修：能力通知 | R/capability.rs:33,40；U/peer.rs:983 | 旧结构影响手机画质/尺寸。`665d7853`：data.type/device_capability嵌套、真实尺寸/编码、sender_para_info；经实际信令出队测viewer分发结构。 | 1 |
| E4/P1 已修：QR 状态机 | R/login.rs:271,304,318,352；U/mod.rs:545,552,564,590；U/cloud.rs:196 | 旧票据、状态3误确认及短超时。`0af2d374`：优先现代票据、无body签名、仅4确认、0/3换码、60秒轮询及退避；本地HTTP测状态/错误/旧票据。 | 1–2 |
| E5/P1 已修：数字会话释放 | R/main.rs:84,117；U/mod.rs:768；U/signaling.rs:91,285 | 数字release误关桌面、leave误过期。`5e4a4843`：规范化ID，区分缺失/非法/未知；测数字终端释放隔离及房间/peer范围。 | 1 |
| E6/P1 已修：旧1120覆盖登录 | R/main.rs:775；U/mod.rs:637,658,402,619 | 旧请求清除新凭据。`f32236ad`：同锁保存/代次核对，失效先撤销内存；屏障测同token重发/新token交错，验证磁盘及终端保留。 | 1 |
| E7/P1 已修：关闭阻塞房间 | R/main.rs:77；U/peer.rs:928；U/mod.rs:813,843 | pc.close无界阻塞offer/status。`a168d726`：任务取消/DropGuard、先松键及清约束，传输关闭限5秒；实peer阻塞Closed回调测锁释放/任务销毁。 | 1–2 |
| E8/P2 设置失败不答RPC | R/capture_setting.rs:5；U/peer.rs:1520；O/video/pipeline/shared/vim4.rs:139 | 配置失败/5秒超时仅return，客户端等不到回答。用核实的CaptureSettingResponse.errors回失败并同步实际值；未知枚举先取证。 | 1 |
| E9/P2 水平滚轮丢弃 | R/viewer/input.rs:87；R/input.rs:119；U/input.rs:273,684；O/hid/types.rs:159 | 收dx/dy却只用dy，HID也仅单轴；纵滚余数已有。贯通AC Pan描述符/事件/OTG和双轴余数，不能把dx合入dy。 | 2–3 |
| E10/P2 音频发送失败不恢复 | R/audio.rs:69,90,103；U/peer.rs:1203,1223 | write_sample失败即退出，started禁止重启媒体；可能持续有图无声。按关闭状态区分永久/暂时故障，增加重订阅/有限重试。 | 1–2 |

## 缺口（按 KVM 用户价值排序）

| 编号/优先级 | 参考；我们 | 适用性、影响与建议 | 人日 |
|---|---|---|---|
| G1/P2 手机文本、正向粘贴 | R/control_protocol.rs:64；R/webrtc.rs:1351；U/input.rs:240；U/peer.rs:752 | 忽略text_input/TEXT，手机IME失效。HID适用已知布局字符；先支持受限字符并报失败，Unicode需输入法约定/串口/SSH。 | 2–4 |
| G2/P2 已修：文件传输 | R/file_trans.rs:495,624；U/files/mod.rs:174 | `5b80d0cd`：FILE回复、限定板子目录/未挂载镜像、取消/续传及跨入口介质互斥；8MiB往返哈希、600秒验收通过。[记录](2026-10-25-uu-files.md)。 | 5–10 |
| G3/P2 端口映射 | R/port_mapping.rs:156；U/mod.rs:830 | 忽略type=9。适用板子可达的SSH/管理端口；显式启用、限定目的地址、独立peer，经FILE Message27转发。 | 3–5 |
| G4/P2 已修：工具连接转桌面 | R/webrtc.rs:1318；R/desktop_control_tests.rs:220；U/peer.rs:1475；U/mod.rs:830 | `1c1a790d`：同peer幂等取得桌面、保留终端、统一接管/清理；双端回归与官方终端→桌面、600秒缩放验收通过。 | 2–4 |
| G5/P2 结束自动锁屏 | R/system_actions.rs:246,269；U/peer.rs:1577；U/wire.rs:166 | 手动HID锁屏已有；可持久化action19的2/1开关，最终断开按Windows/Mac发锁屏键，无法确认目标锁态。 | 1–2 |
| G6/P2 WOL/电源 | R/wol.rs:40,87；R/system_actions.rs:219；U/mod.rs:734；U/peer.rs:1603 | 未接WOL push/电源动作。WOL适用但参考也未实测；目标重启需ATX/明确SSH，不能照搬systemctl重启板子。 | 2–4 |
| G7/P3 访客/分享协助 | R/assist.rs:1；U/cloud.rs:324；U/mod.rs:741 | 缺协助挑战/签名；适用临时授权，需开关、撤销和终端权限。 | 4–7 |
| G8/P3 反向剪贴板 | R/clipboard_protocol.rs:56；R/webrtc.rs:1191；U/wire.rs:166；U/peer.rs:752 | 无桥接，未虚报ff_clipboard。HDMI/HID读不到目标剪贴板，反向需目标代理/SSH。 | 有代理3–5 |
| G9/P3 多屏/真彩 | R/capture_setting.rs:193,233；R/capability.rs:40；U/wire.rs:257,474 | 硬件限制：只能采当前HDMI，编码仅420。未接其他屏不可选；444需新增编码路径。保持单源/420声明。 | 协议3；后端另估 |

已有终端/列表：`R/terminal.rs:421` 对应 `U/terminal/mod.rs:521`、`U/peer.rs:1310`；TERM v1、改名、detach/重挂、16KiB分块、板子/串口/SSH，默认关闭。

## 改进与待证风险

| 编号/优先级 | 参考；我们 | 判断与建议 | 人日 |
|---|---|---|---|
| I1/P2 DataChannel回收 | R/desktop_control_tests.rs:83；U/peer.rs:755,1279,1337 | 回调强Arc捕获自身；依赖close不清handler（C/webrtc-0.17.2/src/data_channel/mod.rs:444），有引用环。改Weak/任务所有权，测三通道关闭释放；参考未协商测试不足以覆盖。 | 1–2 |
| I2/P2 音频时钟/能力 | R/audio.rs:78；U/peer.rs:1222,1395；O/audio/streamer.rs:301；O/audio/encoder.rs:83 | 满队列丢帧，忽略sequence/encoded_at，RTP未体现缺失时长；恢复不重报sound。补序号缺口/重启时钟及能力更新。 | 2–3 |
| I3/P2 弱网/关键帧 | R/webrtc.rs:382；U/peer.rs:1001,1117,1669 | 已有RR/NACK、PLI/FIR；缺帧/反馈各限流，无共享pending。双方Auto均非带宽自适应。先统一IDR请求/完成，再做弱网控制。 | 2–3；自适应另5–10 |
| I4/P2 SCTP上限 | R/webrtc.rs:1626；U/peer.rs:829；U/terminal/frame.rs:18 | 缺max-message-size，接收buffer仅65535（C/webrtc-0.17.2/src/data_channel/mod.rs:33,317）。业务256KiB检查无效；终端16KiB分块安全。扩展前统一协商/分块并测边界。 | 1–2 |
| I5/P2 SRTP回卷待证 | R/../vendor/webrtc-srtp/src/context/rollover_regression_test.rs:16；O/../Cargo.lock:5506 | d6752e7针对0.12.0；我们0.17.2已用半序列空间，状态仍可回退。未复现冻结；补双套件65000→回卷→85→迟到65000/65530→86..1000鉴权测试。 | 1 |
| I6/P3 ICE/解码/并发 | R/session_ice.rs:26；R/main.rs:72；U/ice.rs:16；U/peer.rs:444；U/mod.rs:896 | 已有TURN/force_relay，缺实传/切网测试；未保留decoder尺寸/fps（U/signaling.rs:315），profile需核SPS。双方均替换桌面；多观看需HID所有权/共享编码。 | 测试2–4；多观看5–8 |

## 近期提交逐项核对

“同类”指上述发现；“已有”仅指源码对应，非本轮官方客户端验收。

| 参考提交 | One-KVM 判断 |
|---|---|
| bcde9f9 | E1。 |
| bf7bd50 | viewer修复不适用；纵滚已有，横滚E9。 |
| 287b21a | viewer补边不适用；U/input.rs:548映射正确，补非16:9缩放坐标回归。 |
| 5fdb98b | E4。 |
| 762cfcc | E2。 |
| 0afc602 | E2/E4。 |
| 7fcc674 | E3：嵌套结构。 |
| 1fa346f | E3：尺寸。 |
| f973707 | G4。 |
| d6752e7 | I5：依赖版本不同，待鉴权回归。 |
| 3d4d8d1 | Mac键码已有U/input.rs:422；FFmpeg viewer不适用。 |
| 9622bf4 | 已有U/peer.rs:1286,1310的终端同通道RPC回复。 |
| aeaf818 | U/signaling.rs:154已有；E1仍在。 |
| 3a78491 | U/signaling.rs:340已有；E1可阻塞执行。 |
| fc8c10c | 已有U/signaling.rs:68,213：首次/失败30秒，成功300秒。 |
| c5aa238 | 字符串未知工具 release 已隔离；非字符串 E5。 |
| b5cc5ed | U/input.rs:57已有关闭串行化/迟到拒绝。 |
| be7dba4 | U/terminal/session.rs:267已有分块。 |
| b63bedd | 重绘已有；ABR区别见I3。 |
| 1b7ec0a | 终端RPC已接，缺真实双通道往返测试。 |
| 078ca02 | 重订阅等关键帧已有U/peer.rs:1104；补连续重配回归。 |
| ca49232 | FFmpeg分AU不适用；O/webrtc/h265_payloader.rs:23已保留CRA、拆参数集。 |
| d95053d | KVM缩放已有U/peer.rs:1625；不移植xrandr/会话改EDID。 |
| 69aecf0 | 多屏 G9；不能从 HDMI 枚举目标全部桌面。 |
| 1009bde | 无Wayland wake调用；应测HDMI无信号恢复。 |
| 10166c6 | 缩放取偶数U/peer.rs:1645；原始奇数可见区/补边待验。 |
| 63ebb3e | G1。 |
| 70cb5ad | spare-keycode不能移植USB HID。 |
| 6416f75 | R/auth.rs:125绕过代理，U/cloud.rs:196沿用默认；有代理时明确策略。 |
| 94ff1f1 | viewer修复不适用，见G1/G8。 |
| 73c1d9b | G8。 |
| 8967dfd | SDL窗口复用不适用。 |
| cd6df7f | FFmpeg viewer不适用。 |
| 94fd3c2 | 无polkit调用；未来电源动作按G6区分目标。 |
| d1791ef | 补G2时测列表超限。 |
| 6226e72 | I4。 |
| ebef246 | I4/G3。 |
| a870f7d | I3；不直接复制限流常数。 |

其他NVENC/VAAPI/Portal/X11、GTK及viewer界面修复不适用。参考也无隐私屏、HDR、超级屏、麦克风回传（R/../README.md:103）。目标锁态/遮黑不能用板子状态替代。

## 修复验收与剩余测试

从 `vim4` 新建 `fix/uu-protocol-p1-20261025`，七提交至 `a168d726`。复用Cargo缓存、独立target卷及Ubuntu ARM64 builder，禁网跑 `cargo test --offline --locked --features vim4`：758通过、2忽略。另35项Python助手、DMA分配器、前端锁文件构建、release及deb升级/配置保留/更新API通过。默认Rockchip目标缺RKMPP接口编译失败，未标通过。证据：`logs/uu-protocol-p1/`。

部署/实测范围与失败窗口见[修复验收记录](2026-10-25-uu-p1-validation.md)。扫码云端流程未重新绑定，QR以本地HTTP协议回归覆盖；未测试声音。

用户后续决定：先修复缩放 CMA，再做 G4 capture_desktop 与 G2 限定板子文件传输，实施状态见[后续记录](2026-10-25-uu-cma-tools.md)。G1 手机文本输入/粘贴暂缓，等用户决定。G3 端口映射、G5 结束自动锁屏、G6 WOL/电源、G7 访客协助、G8 反向剪贴板、G9 多屏/真彩均为**用户决定不做**。

其余补测：双端初始化/echo/RPC失败/BINARY、三通道释放、I5鉴权、音频恢复、PLI/NACK重配、TURN实传、弱网/HID；用容量1/屏障协调。本轮不测声音。

## 许可证

参考Cargo.toml:9为GPL-3.0-or-later，One-KVM Cargo.toml:7为AGPL-3.0-only，主仓GPLv3。双方LICENSE第13节允许组合；GPL部分保持GPL，组合须履行AGPL网络源码义务。保留U/NOTICE；本轮独立实现、未复制参考代码。非完整发行合规审计。
