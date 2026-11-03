# 2026-11-01：USB 端点合并（多媒体键并入绝对鼠标、虚拟盘按挂载计数）部署验收

**原配置保存、端点提示、M6 输入、UAC2 枚举及 stop/start 描述符恢复验收完成。**
consumer 以 Volume Down HUD 证明通过；Sound/Input 的 Capture Inactive / USB
按 docs/board-tools.md:110 的既有名称接受。最终 One-KVM active、mic ON、介质未挂载、UDC configured。
2026-11-01 16:01:21 UTC，`/etc/vim4-kvm/one-kvm-usb.json` 已登记 acceptance=complete。

## 固定来源与最小部署

- One-KVM usb-integrate：`ffc613064165f1afb6685019565c12e90864fe26`。
- vim4-manager usb-endpoints：`0145679b5ad28d90e06433c4ac56afe7741bf175`，只部署 helper。
- 音频 overlay 同一镜像 hdr10-audio-cache:50f0b4d 与 Cargo 缓存，release 构建 2m36s、退出 0；
  现有 web/dist 未重建，21 条 warning 保留。ELF ID `70abc956027126789a3f0544a79bcb2f161935a9`。

| 安装路径 | SHA256 |
|---|---|
| /opt/vim4-kvm/one-kvm-usb-ffc6130/one-kvm | `b2bdf8a7ca5425f37f52c81246327c874a2802701c3af54aa800c051f1719130` |
| /usr/libexec/vim4-onekvm | `ca82b066526252e44f3700f6657e76f808159710bb24e6982810959d76a28cf0` |
| /usr/libexec/vim4-manager-helper | `21510b33e1ec4c43edc88b174b53d58e52ad635c7c31cb0869db6a83140ddb2f` |

封包 SHA256 `710fb7e81e0247d356d6ef5495a803854e296db06d042725b03287c0b5fabe27`。
先安装 helper，只改 launcher 的 uhd6 One-KVM 程序路径；保留 kbase/r14e/5.15 选择。
launcher SHA256 `cda5abcbe961ba26a8f24a59ae5568619d2191b190381c4f2f040b17a66ca905`。
初次部署 restart 一次，最后验收另 stop/start 一次；manager、HDMI、gadget 服务和板子没有重启。
备份 `/var/lib/vim4-kvm/before-onekvm-usb-1793547130383999656` 只含原 launcher/runtime-build。
最终 PID 23945 的 /proc/exe 哈希再次匹配，旧 overlay 保留，未回退。

## 实际结果

| 检查 | 结果 |
|---|---|
| 原配置保存 | keyboard/abs/rel/consumer/UAC2 ON、MSD enabled 保存成功 |
| GET/介质 | media_mounted=false，LUN 空，mic 48000Hz/2ch ON |
| 合并描述符 | 8501 + 原始 bytes + 8502 + consumer collection 精确匹配，长度 7、protocol/subclass 0 |
| 运行链接 | 三 HID + uac2.usb0，无 hid.consumer 链接，UDC configured |
| 网页 | 4/5 正常；仅页面开网卡后 6/5、Save disabled、warning 可见，随后丢弃 |
| M6 鼠标/点击/滚动 | 两点截图符合坐标，Apple 菜单有效；下/上各 2 步，页面恢复 |
| consumer | 总计一次 Up/release、一次 Down/release；以 Down HUD 为证，未重发 |
| 音频输入枚举 | Sound/Input 单个 Capture Inactive / USB；按文档既有名称接受 |
| stop | 原始描述符逐字节匹配、长度 6、原三 HID 链接完全一致 |
| start | 合并描述符/长度 7/三 HID+UAC2/configured/mic ON/MSD enabled unmounted 全通过 |
| 最终 | 四服务 active、uhd6、taint 4096、acceptance complete |

恢复的原始描述符 SHA256 `29971c6463ad5797eae827986835c31fb4f59b6d51132ce49ba6ef56d98e9b61`。
比较来源为用户给定 bytes、部署前 before.json 与 helper baseline journal；恢复链接为
hid.keyboard、hid.mouse_abs、hid.mouse_rel。stop 后即时 UDC 尚未 attached；start 后已轮询 configured。

## 窗口与失败保留

最后票据 `9ce3e007cae84495af19b473138138ae`，15 分钟硬限，实际持板 8.639s；
begin/cycle/collect/accept 均退出 0。仅板端操作，没有 M6 交互。
全部历次票据累计 142.082s、均已释放，完整票据表见 queue-summary.json / result。
每次失败均释放后才离线分析和修改验收脚本；没有持锁读文档、编辑或编译。

历史失败保留：UDC 就绪检查过早、隧道端口冲突、无历史光标位置、菜单 OCR 混入图标、
Python 直连受限、WebSocket consumer 后 MCP 两秒冷却、音频名称条件只接受 One-KVM。
这些不再是未完成项；日志和失败截图仍保留，不把失败轮次改写成成功。

此前限流汇总 `t7_hdmirx_tmds_status: N callbacks suppressed` 是既有基线噪声。
实际历史证据：logs/hdr2-unified/kernel.log:768,844；logs/hdr10r6/post-native-dmesg.log:561,678；
logs/hdr10r11/encode-dmesg.log:535。最终五份 last-gate 均 failures=[]，仍检查 WARNING/BUG/Oops/
call trace、USB 新错误、其他新 hdmirx 消息和未豁免 warning。

## 证据与边界

`logs/usb-endpoints-20261101/` 保存构建、manifest、实际身份、API/configfs、kernel、全部队列和失败快照。
最终证据 last-stopped.json、last-restore-baseline.json、last-cycle-passed.json、last-restarted.json、
last-receipt.json、last-window-result.json。网页 settings-4-of-5.png/settings-6-of-5-blocked.png；
指针 m6-mouse-*.jpg；滚动 remaining-scroll-*.jpg；consumer remaining-volume-down-hud.jpg；
音频 finish-input-9.jpg；关闭 Settings/恢复光标 finish-sound-final.jpg。

Up HUD 截图未捕获，以 Down HUD 为证；Capture Inactive 是文档名称，不能理解为音频故障。
最终窗口没有 M6 交互；前一窗口已关闭 Settings、恢复光标。
未播放/录制测试音频、挂载介质、切换应用、重启板子或向 M4 发 HID。manager 跨应用行为沿用离线审查证据；
不扩大为 5.15、听音质量或全 r14e 文件回归。extlinux/r14e 收据保护校验通过。
