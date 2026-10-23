# 2026-10-23：M1 第七窗口——一次性启动、RMFB、翻页与 Panfrost

本轮按[内核开发门禁](../subsystems/deployment.md#内核开发流程与部署门禁)做短窗口，
没有正式部署。M1 固定模式设置/关闭、disable、物理图案、page flip 与采集共存通过；
HDMI-OUT 拔插因未收到手动完成确认而跳过。此前事故见 [M1 记录](2026-10-23-display-m1.md)。

## 版本、锁与一次性回退

主仓工作树 `build/display-m1/main-docs` 先拉到 `d0e8f98`。远端正式内核仍为
`aa2f875bec2fc`，因此沿用实验分支 `vim4-display-m1` 的 `c1315a95691e`，
没有额外 rebase 或重建内核；build ID 为 `844bfec2f4240d42447e3dc35d2eee69cf2a0c8f`。
恢复目标保持 `7b8372b894c98ffae12e636a325c86f2b6c85e00`。

首次尝试 heavy 锁被另一任务占用，未改变板子状态；两把锁均取得后才暂存和重启。
全程持 Mac `vim4-board.lock`、`vim4-heavy.lock`，性能采样没有并行重型构建。
保留默认 extlinux、基线 Image/DTB、模块原件与运行时登记文件，未写 U-Boot 环境或引导区。

先复制已校验基线到根分区私有 `baseline-check-7/`，在 U-Boot RAM 中执行：

```text
sysboot mmc 1:2 any ${pxefile_addr_r} /var/lib/vim4-kvm/display-m1/baseline-check-7/extlinux.conf; reset
```

串口成功读取根 ext4 的配置、Image、DTB；Linux cmdline 出现
`vim4.display_baseline_once=7`。随后正常重启，实际 GNU build ID 回到 `7b8372b8…`，
一次性标记消失，五个受保护文件哈希全部相同。实际使用的是重启，不是物理按 RESET；
本轮没有故意制造硬锁或专门验证看门狗超时。

## PID 1 现场修正与失败回退证据

候选先经历两次预检失败，均由静态 PID 1 请求复位，自动回到默认基线；没有进入候选
systemd，也没有 oops。第二次补充检查阶段诊断后明确记录：

```text
DISPLAY_ONCE: module directories failed (Success); reboot to the retained baseline
755 501 501 /lib/modules/7.3.0-vim4kvm-uhd1+
555 0 0 /var/lib/vim4-kvm/display-m1/844bfec2f4240d42447e3dc35d2eee69cf2a0c8f/modules/7.3.0-vim4kvm-uhd1+
```

基线模块目录保留打包机 UID/GID 501，原预检过度要求挂载点也归 root 所有。
修正 [display-once-init.c](../../packaging/kernel-edge/display-once-init.c)：候选源目录仍须
root 所有且 group/other 不可写；目标须为存在的独立目录，不以其旧所有者作为拒绝理由。
没有 chown 或修改基线模块。失败日志新增阶段和 errno；离线真实 C harness 加入
UID 501 挂载点成功、非目录目标失败，并继续拒绝不可信源和源/目标别名。

只更新私有候选 init 及其 trial.json 哈希，内核仍为 `c1315a95`。修正后同一 RAM sysboot
成功，串口输出 `DISPLAY_ONCE: matching modules mounted; starting systemd`。
实测 build ID 为 `844bfec2…`；findmnt 确认私有完整模块以只读 bind 显示在正常模块路径，
五个基线文件哈希仍相同，三服务 active、UDC configured、isolated=0、taint=0。
旧离线归档的 init 仍有目标 UID 限制，不能直接复用；后续须用已修正源码重新 prepare。

## 针对性显示与采集测试

主要命令（modetest 为此前构建的 libdrm 2.4.125 工具）：

```sh
sudo /var/tmp/vim4-display-m1/modetest -M meson-t7-handoff -s 39@37:1920x1080@RG24 -F smpte
sudo /var/tmp/vim4-display-m1/modetest -M meson-t7-handoff -a -w 37:ACTIVE:0
sudo /var/tmp/vim4-display-m1/modetest -M meson-t7-handoff -s 39@37:1920x1080@RG24 -F smpte -v
```

| 项目 | 实际结果 |
|---|---|
| 设置/关闭与 RMFB | 连续 10 轮退出成功，没有第五窗口的 NULL fb oops |
| CRTC disable | atomic ACTIVE=0 成功，debugfs state 确认 `active=0`；随后再次设置成功 |
| 物理输出 | 已授权普通 Chrome + HDMI-OUT 采集卡抓到 1920×1080 SMPTE；不是内存截图 |
| Page flip | 初次及采集共存后复查均看到两个缓冲交替，图像差值 98.01；modetest 持续 29.97Hz |
| 采集同时工作 | 显示翻页保持运行，One-KVM 浏览器解码 3840×2160 H.265，15 秒采样 60.05fps，丢帧/丢包/冻结均为 0 |
| HDMI-OUT 拔插 | 输出 NEED_USER 后约两分钟未收到完成确认，跳过；不宣称真实 HPD 或拔插恢复通过 |

输出模式刷新率为 60Hz；当前实现等待两次 vsync 退休缓冲，因此本次 page flip 是约 30Hz。
采集共存短测不是全量编码/音频/长稳验收，音频没有额外测试信号，不能据此声称音频通过。

收尾第一次物理复查因采集页面的固定 15 分钟上传期限而超时；此时 modetest 仍持续
29.97Hz、板子 taint=0。重新打开采集页后复查通过，不能把这次采集工具超时记成驱动挂起。
另有一次状态查询因 sudo 前 shell 无权展开 debugfs 通配符而失败，改为 root shell 查询后通过。

## GPU：Panfrost 离屏渲染

从 Ubuntu 包提取 glmark2 2023.01 到私有目录，不安装系统包。renderD128 直接作为 DRM
窗口设备会因没有 KMS resources 失败；实际采用显示 card0 加 `DRI_PRIME=1` 选择 Panfrost：

```sh
sudo env DRI_PRIME=1 /var/tmp/display-m1-window-7/gpu-root/usr/bin/glmark2-es2-drm \
  --off-screen --winsys-options drm-device=/dev/dri/card0 \
  --data-path /var/tmp/display-m1-window-7/gpu-root/usr/share/glmark2 \
  --size 800x600 -b :duration=2
```

实际输出：

```text
GL_VENDOR: Mesa
GL_RENDERER: Mali-G52 r1 (Panfrost)
GL_VERSION: OpenGL ES 3.1 Mesa 25.2.8-0ubuntu0.24.04.4
Surface Size: 1920x1080 fullscreen
glmark2 Score: 925
[build] use-vbo=true: Validation: Success
```

DRM flavor 实际报告 1920×1080，不能按命令中的 800×600 记录。每场景 2 秒，分数不与
默认时长的完整性能基线混比。测试后一次 GPU 频率读数为 500MHz，未改电压/频率配置。
`--validate -b build:use-vbo=true` 单独验证成功，渲染器不是 llvmpipe。

日志同时有 `DRM_IOCTL_MODE_CREATE_DUMB failed: Invalid argument` / scanout resource
创建失败：Mesa 尝试 32 位 scanout，而 M1 dumb buffer 仅支持固定 RGB888；离屏场景仍完成。
退出时恢复原 CRTC 返回 -13（modetest 持有 master）；随后物理翻页复查通过。
因此本结果证明硬件离屏渲染，不证明 32 位 GBM GPU 缓冲直接显示或桌面合成已经可用。

## 恢复与证据位置

测试结束关闭 modetest，正常重启回默认项；不运行覆盖式 restore。
最终运行超过 6 分钟，build ID 为 `7b8372b894c98ffae12e636a325c86f2b6c85e00`，
一次性 cmdline 消失、私有模块 bind 消失，五个受保护文件哈希全部保持一致。
`one-kvm`、`vim4-manager`、`vim4-wave5-monitor` 均 active，UDC configured，
isolated=0、taint=0，没有新增 oops。dmesg 只有既有启动告警，未出现此前 CIFS 超时。
HDMI-OUT 采集卡抓到正常 tty 登录画面；20 秒浏览器 H.264 3840×2160 采样为
60.02fps，丢帧/丢包/冻结为 0。原生 HID 实测 keyboardDown=1、keyboardUp=1，
绝对/相对鼠标、click、wheel 全部通过。

已删除本次基线副本、候选私有目录、上传包与私有 GPU 工具；保留历史备份。
清理后再次检查基线哈希和健康状态通过，随后释放两把锁。没有正式部署。
离线验证：修正后的静态 ARM64 init 编译通过；主仓完整离线测试 221 项通过
（10 项按平台条件跳过），Linux VM 中启动安全网 6 项、恢复逻辑 10 项均通过。

本地证据目录 `logs/display/m1/window-7/`：`baseline-once-uart.log`、
`baseline-default-health.json`、三次 `candidate*-uart.log`、`candidate-fixed-start.log`、
`rmfb-0.log` 至 `rmfb-9.log`、`disable-state.log`、`modetest-smpte.png`、
`before-kvm-flip.json`、`after-coexistence-recheck-flip.json`、`candidate-kvm-smoke.log`、
`gpu-glmark2-card0.log`、`gpu-validate.log`、`candidate-after-close.log`、
`final-baseline-health.log`、`final-baseline-encoding.log`、`final-baseline-hid.log`、
`final-baseline-hdmi-out.png`、`cleanup.log`、`tested-trial.json`。
日志和图像不入 Git；候选仍为实验分支，模式切换、真实 HPD、HDMI-OUT 音频和直通继续后续开发。
