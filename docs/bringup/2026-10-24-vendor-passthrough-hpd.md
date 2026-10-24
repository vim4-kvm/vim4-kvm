# 2026-10-24：厂商 5.15 透传 OUT 热插拔恢复

接续 [5.15 透传交付](2026-10-24-vendor-passthrough.md)。本次只修用户态 HPD 恢复和
控制台遮挡，不改内核、启动项、编码参数或前端。真实 1080p 测试须另获临时 EDID 授权。
UU 帧率调查持锁期间只读取证，
部署及用户拔插验证等待 `/tmp/vim4-board.lock` 与 `/tmp/vim4-heavy.lock`。

## 只读证据与“报错”内容

用户报告拔插 OUT 显示器后看见 VIM4 控制台/报错，未回到透传。
15:45 UTC 读取时 watch 仍为同一 PID 10742，15:16:51 启动、NRestarts=0，
没有 Python traceback 或服务退出。request.enabled=true；状态已为 running，
TX 2160p60、444,8bit、ready=1、disable_video=0、VD1 global_output=1、layer_state=1，
VFM 仍为 `vdin0 vfm_cap amvideo`。因此不能把最初目视故障写成服务一直挂死。

插拔日志时序：

- 15:41:53 HPD LOW；15:41:58 HPD HIGH；15:41:59 DRM 强制 modeset 为 RGB。
- 同时厂商 RX 收到 `update EDID from HDMITX`，脉冲输入 HPD；VDIN 停止、vfm_cap 失锁并排空。
- 15:42:01 输入重新稳定，VDIN/vfm_cap 恢复 TEE。
- 15:42:03 watch 检出 RGB，重设为 444 并恢复 VD1；没有服务重启。

当时可确认的内核报错为：

```text
[drm:meson_hdmitx_atomic_check] *ERROR* hdmitx_on changed, force modeset.
[drm:meson_hdmitx_update_hdcp] *ERROR* meet stopped hdcp stat
[drm:meson_hdmitx_update_hdcp] *ERROR* No valid hdcp mode exit, maybe hdcp havenot init.
[hdmitx:] *ERROR* Should run disable_mode before enable new mode.
```

启动参数包含 `console=tty0`，活动 VT 为 tty1，这些 DRM/HDCP 消息会写到本地 fb 控制台。
没有原画面照片，不能逐字断言用户看见的是其中哪一条；它们不是 manager 异常或内核 Oops。
消费者关闭附近还有 `[vfm_cap] ERROR: put: unknown vframe idx=..., passing through`，
属于已有共享帧生命周期风险，不把它归结为 Python 退出，也不宣称此次 OSD 修复已消除该驱动问题。
原始证据在 `logs/passthrough-515/hpd-readonly-before.log`。

## 根因与修复

旧实现只向 fb0/fb1 的 blank 写一次，再依据进程内 `self.blanked` 缓存跳过后续操作。
fb0/fb1 实际均为 mesondrmfb；普通 fb blank 仅禁用当次 plane，并不禁止后续 DRM
热插拔/控制台提交重新配置。两路 `osd_permanent_blank` 当时均为 0；该状态也没有进入
旧 provider 的 running 判定。HPD 重设窗口中即使视频已恢复，也缺少持久的控制台遮挡保证。

此外，连接时 EDID 可能暂时无效，或驱动在第一次采样后才重设模式；若丢失 HPD 边沿而
沿用旧 mode_key，上一轮“相同意图不重复 modeset”的保护会阻止纠正这次真正的外部重配。
旧异常处理中的 disable_video 再次失败还可能逃出循环，让服务依赖 systemd 重启。

修复不使用 CRTC 全局 blank（会影响视频），使用厂商已有的逐 OSD 持久接口：
`/sys/class/drm/card0/osd{0,1}/blank`。`meson_plane.c` 在每次 atomic check 中检查
`osd_permanent_blank`，使控制台即使再次提交也不能盖住 VD1。
启用时保存两路原值到 root 管理的 `osd-before.json`，确认并保持 1；关闭时恢复，
watch 重启不重新覆盖原值。显示器断开、坏 EDID、失信号、错误清理期间均不解除屏蔽。

HPD 同时使用内核 `amhdmitx/hdmitx_hpd` uevent 与 sysfs 轮询，压缩到一次轮询间隔内的
0→1 也会使连接代次失效。只接受 kernel sender；其他设备或用户态消息不能触发重配。
连接/sink EDID 变化后先等待两秒稳定，再恢复到输入与 sink 的有效交集及 4448。
保留上一轮刷新率中值/滞回和每意图单次重配，不能借恢复重新引入周期黑屏。
热插拔异常与错误清理的二次异常在单个 watch cycle 内处理，随后重试，不显示控制台或退出。

## 验证与部署

离线覆盖：HPD 0→1、无效 EDID→有效、sink EDID 变化、驱动回退不同模式/RGB、
短 HPD 脉冲、无关/伪造 uevent、持久 OSD 原策略跨重启恢复、缓存与读回不一致、
清理失败仍能处理下一轮。Python 全套 181 项（12 跳过）通过。
现有刷新率抖动/单写入者/只读状态回归保留。

## 19:11 UTC 部署与现场确认

无超时阻塞等待双锁，UU 会话释放后取得板子。OUT 保持拔出，内核仍为
`5.15.137-vim4kvm`，原脚本 SHA256 为
`0f99b055660f1fffafb61a6761a26653183733ef0253c67d1c33c7791c45118f`。
备份脚本、runtime 状态和两路原 OSD 策略至
`/var/backups/vim4-passthrough-hpd-20261024-1911/`，仅替换脚本并重启透传服务。
部署内容为 manager 分支上的 `6e9f063`、`54257a0`、`2b00fc8`；新脚本 SHA256 为
`6866c94464e355f2f95ed8f115f9dcd473e2ccf3c7e964bfc30f531afc8fa165`。

19:11:49 启动后服务 active、PID 77955、NRestarts=0；HPD=0，manager helper
返回 supported=true、enabled=true、state=no-monitor，对应原界面“未连接显示器”。
两路 OSD 持久 blank 均为 1，保存的原策略均为 0；One-KVM 和管理器保持运行，未重启或改编码。
部署后再次运行 Python 全套 181 项（12 跳过）、Go 全套测试及 go vet，均通过。
前端布局与文案没有修改。

已通过共享 need-user 协议合并请求一次物理插回/目视确认和临时 EDID 授权。
插回自动恢复、软件 HPD 重测与真实 1080p→4K 跟随结果待用户回复后补记；此处不预先写通过。
截至 23:20 UTC（部署后约四小时）仍未收到 user-done，HPD=0、state=no-monitor；
透传、One-KVM、manager 均 active，PID 未变、NRestarts=0。
这是持续断开状态的存活检查，不是插回恢复或连接状态长期无黑屏验收。
保留 need-user 请求，结束本轮本机等待进程并释放双锁；恢复验证前须重新取得锁。
临时 EDID 切换没有执行，源仍是原 RTK-CONTROL；硬件验收前不合入或推送 manager 修复。
主仓全套 243 项（7 跳过）通过。

Mac 显示“1080p”不代表线缆上就是 1080p：此前 Mac 报告 1920×1080，但 RX 实测
3840×2160、约 59.98Hz；服务 input=3840×2160、output=2160p60、scaled=false。
这是 Mac 桌面逻辑缩放后仍发送 4K 时序，透传按真实输入跟随的行为正确。
