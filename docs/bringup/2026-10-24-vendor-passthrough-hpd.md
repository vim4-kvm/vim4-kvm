# 2026-10-24：厂商 5.15 透传 OUT 热插拔恢复

接续 [5.15 透传交付](2026-10-24-vendor-passthrough.md)。本次只修用户态 HPD 恢复和
控制台遮挡，不改内核、启动项、源 EDID、编码参数或前端。UU 帧率调查持锁期间只读取证，
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

硬件部署、用户一次合并拔插确认与最终提交：待获得 UU 会话释放的锁后填写，不预先写通过。
