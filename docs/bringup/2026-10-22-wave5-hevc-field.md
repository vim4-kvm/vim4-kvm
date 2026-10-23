# 2026-10-22：Wave5 HEVC 防护候选现场验证与恢复

候选本轮没有挂死，但**没有证明支持 1366×768 HEVC，也没有证明固件挂住后能够恢复**。
驱动拒绝非 8 对齐 crop 后，GStreamer 忽略错误，实际编码 **1376×768**。
已修正取证脚本，尺寸不符返回失败。应用 HEVC step 8 和 H.264 回退保持不变。
候选未正式部署，已恢复原模块并正常重启，双锁已释放，无需物理 RESET。

## 版本与构建

承接[离线分析](2026-10-22-wave5-hevc-hang-analysis.md)，基线为
[pstore 正式部署](2026-10-22-edge-pstore-deploy.md)：
`vim4-kvm-7.3` / `1262da082ba528be27c17adc62a92d90ed18b158`，
内核 `7.3.0-vim4kvm-uhd1+`，Image build ID
`f283ab1f8a001a19bab5247afc4f9b0c00c1da99`。
未改 Image、DTB、U-Boot（用户报告 pd-handoff `0d5a3d78`），未操作 Wi-Fi/P2P。

VM 独立 worktree `/home/deepdream/src/linux-7.3-wave5`，分支 `vim4-wave5-hang`：

| 提交 | 内容 |
|---|---|
| `2df3c915a8de02315ac68704a5be643e9e0df756` | 原 a64f5e574234b rebase；尺寸校验、release 保留 IRQ 分发、C 仿真 |
| `537ad90f65620c8e7bf74f3ccf16d6544b0fc916` | 原 60b16c739a45a rebase；有界取证脚本 |
| `0196fe22ecf0104d96b7ef0fa497ca2317bd20bb` | 本轮新增 ffprobe 输出尺寸/帧数核验及回归测试 |

主工作树仍为 1262da082ba5；候选分支干净，未推送、未合入。
初次 rebase 因 VM 无身份失败，在自己的 worktree abort 后用指定作者环境变量重做。

从部署 O 目录 `/home/deepdream/build/kernel-p2-pstore` 用
`cp -a --reflink=always` 复制完整目录为 `kernel-wave5-field`。
olddefconfig 后配置逐字节一致，SHA256
`86746fde4d0e6d377264466262a27b4953206ce5e07441c8b870eee5ca05957f`。
只构建 in-tree 模块，没有 `M=`：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build \
  make -C /home/deepdream/src/linux-7.3-wave5 \
  O=/home/deepdream/build/kernel-wave5-field ARCH=arm64 -j8 \
  drivers/media/platform/chips-media/wave5/wave5.ko
```

实际 `MODPOST`、`LD [M] .../wave5.ko`、`BTF [M] .../wave5.ko` 完成，退出 0。
`intree=Y`，vermagic：`7.3.0-vim4kvm-uhd1+ SMP preempt mod_unload aarch64`。
候选未压缩模块 SHA256
`6e7934b8d8c0d60ee846be2c5e6ee6295da26f13bc65181690f92a96a122acca`，
build ID `54b6f490bba202d77ca642fa0fc4eeb52bae9156`。
第三提交只改脚本及测试，未改变被测模块。

## 双锁、备份与安装

Mac 持续持有 board/heavy 双锁，从停服务、备份、安装、编码/HID 测试直到恢复、
重启及最终检查结束。锁宿主 PID 86183，最终输出 `WAVE5_DOUBLE_LOCKS_RELEASED`。
窗口入口：

```sh
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u -c 'import os,sys; print("WAVE5_DOUBLE_LOCKS_ACQUIRED pid="+str(os.getpid()), flush=True); sys.stdin.readline(); print("WAVE5_DOUBLE_LOCKS_RELEASED", flush=True)'
```

串口只读记录 `/dev/cu.usbserial-100`，板端操作通过 SSH。
原模块及 pstore 备份在 `/var/backups/vim4-wave5-field-20261022/`，本机另有 tar 副本。
模块路径：
`/lib/modules/7.3.0-vim4kvm-uhd1+/kernel/drivers/media/platform/chips-media/wave5/wave5.ko.xz`。
原压缩模块 SHA256
`686b455d458043e267fced254e694bdcb0ae5982a3bde4f7e5a4260d841c99ef`，
原加载 build ID `5545f3a76ceb5caaff2c23391e00ebc6290da563`。

窗口内 `sudo systemctl stop one-kvm`，备份后 `sudo modprobe -r wave5`，
用临时文件/mv 安装 xz 候选，再 `sudo modprobe wave5`。
安装后 `intree=Y`、`taint=0`，T7 product `0x521c`，firmware revision `214414`。
编码器 `/dev/video1`；专用插件路径 `/usr/lib/vim4-kvm/mainline-gstreamer-1.0`，
gst-inspect 为 1.24.2。

## 编码与退出证据

C ioctl 探针只设置格式/crop，不分配缓冲、不 STREAMON。
原模块接受下表四个尺寸；候选实际输出：

```text
HEVC crop 1366x768 ret=-1 errno=22 actual=1920x1088
HEVC crop 1440x900 ret=-1 errno=22 actual=1920x1088
HEVC crop 1680x1050 ret=-1 errno=22 actual=1920x1088
HEVC crop 1368x768 ret=0 errno=0 actual=1368x768
```

失败保持原 crop；非对齐尺寸不能再从 S_SELECTION 绕过 step 8。
随后用 videotestsrc 在编码输入端直接产生目标尺寸：180 帧、NV12、30fps。
没有为小尺寸切物理 HDMI EDID，未覆盖完整 HDMI 1366 输入链。
双锁窗口内板端命令示例：

```sh
sudo python3 /tmp/reproduce_hang.py --execute --device /dev/video1 \
  --plugin-path /usr/lib/vim4-kvm/mainline-gstreamer-1.0 \
  --output /var/tmp/wave5-field-hevc1366-checked \
  --codec h265 --width 1366 --height 768 --timeout 45
```

| 请求/试验 | gst 返回 | ffprobe 实际输出 | 观察器结果 |
|---|---|---|---|
| 1366×768 HEVC，初次 | 0 | **1376×768，180 帧** | 旧脚本误报成功 |
| 1366×768 HEVC，加核验后重跑 | 0 | **1376×768，180 帧** | **1，尺寸错误** |
| 1368×768 HEVC | 0 | 1368×768，180 帧 | 0 |
| 1366×768 H.264 | 0 | 1366×768，180 帧 | 0 |
| 1368×768 HEVC，长流 3 秒后 TERM | -15 | 中断流，不作完整帧数验收 | 0，无残留任务 |

所有试验 `timed_out=false`、`remaining_tasks=[]`，未触发 KILL 或 NEED_RESET。
TERM 试验采集 before-term/final 线程栈等信息，正常试验有 final 快照。
三份完整码流经 `ffmpeg -v error -i ... -f null -` 软件解码均返回 0；
这不改变第一份实际为 1376 宽的事实。

GStreamer 报 `Failed to set crop rectangle with VIDIOC_S_SELECTION: Invalid argument`，
却继续使用 RAW 对齐宽度 1376。新脚本实际失败信息：

```text
encoded geometry/frame count (1376, 768, '180'), expected (1366, 768, '180')
```

不能把 gst 返回 0 当作请求成功。本轮防护阻断危险尺寸提交，**没有让固件实际处理
1366 宽，无法评价已经挂住的固件能否恢复**。正常流 TERM 只覆盖正常 IRQ 完成/关闭，
不能替代丢 IRQ、GET_RESULT 失败及复位的故障注入；通用 watchdog/job_abort 恢复仍未实现。
固件卡住根因仍按离线分析保留为未知。

Mac 包装器另设 85 秒 SSH 总截止时间；无响应或观察器返回 125 时输出 NEED_RESET，
每 15 秒探测、最多 600 秒，要求 boot ID 改变后采两处 pstore 和上一启动 journal。
本轮没有进入该分支，不能宣称验证了故障 RESET 后的取证流程。

## 候选回归与保留决定

One-KVM 物理 HDMI 运动源、EDID fixture 18（UHD60）、Chrome 156，
每 codec 预热 3 秒、采样 15 秒，独占复测：

| 候选 3840×2160 | 浏览器接收 fps | dropped/lost/freezes/PLI 增量 |
|---|---:|---|
| H.264 | 60.0471 | 全 0 |
| H.265 | 59.9772 | 全 0 |

第一轮可能与 HID 重叠，已作废，采用随后完全串行的上述复测。
EDID 恢复原值并读回，SHA256
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`，
codec 设置由工具恢复。未测长期稳定性或端到端延迟。

`one-kvm-usb-check.mjs --exclusive --hid-only` 实际 Mac 窗口验证：
keyboardDown=1、keyboardUp=1、absoluteMouse=true、相对鼠标有移动、click=true、wheel=true。
候选和恢复后各运行一次，均退出 0。

尽管回归通过，候选只证明入口保护和正常关闭；1366 请求还有静默错误尺寸，
不足以判定通用挂死已解决。本轮恢复，未合入、推送或改 sources.toml，未放开应用 step 8。

## 恢复、重启与 pstore

双锁内停 One-KVM、卸载候选，用备份原子恢复原模块，加载并启服务，
核对哈希/build ID 后 `sudo reboot`。
初始 boot ID `9e16883b-ac94-4c6a-b593-65f4a70c4ff0`，
重启后 `0edc116f-b44e-4b93-9a6f-52ed63a5644e`，第二次探测成功，含连接超时共 34 秒。
串口有 `reboot: Restarting system` 和重新登录提示，无 RESET 或关机阻塞。
最终实际输出：

```text
/sys/kernel/notes f283ab1f8a001a19bab5247afc4f9b0c00c1da99
/sys/module/wave5/notes/.note.gnu.build-id 5545f3a76ceb5caaff2c23391e00ebc6290da563
686b455d458043e267fced254e694bdcb0ae5982a3bde4f7e5a4260d841c99ef  .../wave5.ko.xz
intree=Y
taint=0
vim4-manager=active
one-kvm=active
UDC=configured
```

无 failed unit、无残留 gst-launch。恢复前误查不存在的 `vim4-kvm-manager` 得到 inactive，
随即核查真实服务 `vim4-manager` 为 active，最终检查使用正确名称；未改管理服务。
重启后 UDC 已 configured，无需 usb-pd-init。

两处 pstore 已前后采集。重启后 sysfs 已由 systemd-pstore 清空归档；
`/var/lib/systemd/pstore/console-ramoops-0` 31204 字节，含本次正常关机的
`[901.725890] reboot: Restarting system`，无新 panic/oops。
`dmesg-ramoops-0` 189366 字节，时间仍为 2026-10-20，不能当本轮故障证据。
恢复标记 `WAVE5_FIELD_BASELINE_RESTORED_9e16883b` 在上一启动 journal，console 未出现；
不能据此宣称所有 printk 均进入 console pstore。

## 测试与证据位置

本轮 C ASan/UBSan：20 组尺寸/固件参数、8 组关闭/IRQ 顺序通过；
观察器 3 项单测通过，新增错误输出尺寸/帧数拒绝测试。仿真仍假定 IRQ 可达。
主仓执行 `python3 -m unittest discover -s tests -p 'test_*.py'`：178 项、5 skipped，
1 项失败。失败是并行 U-Boot 文档的四处链接指向尚不存在的
`2026-10-22-uboot-sd-recovery.md`；未修改对方文件或移除其链接。
本轮新记录另行检查大小、索引和相对链接（包含未跟踪文件），均通过。

本机 `logs/kernel-edge/wave5-field/` 保存构建、安装前后 ioctl、run.json/gst.log/
线程栈、ffprobe、完整解码、4K 独占复测、HID、UART、恢复及最终健康日志，
以及 `artifacts-before-restore.tar`、`pstore-after-reboot.tar`、`previous-kernel.log`。
普通用户 scp root 的 registry.bin 曾拒绝，后用 sudo tar 排除该缓存归档全部取证内容。
本机辅助探针/SSH 包装器在忽略目录 `build/kernel-edge/wave5-field/`；
可复用板端观察器及测试已提交在上述内核分支。

后续仍需实现并验证有界恢复状态机。正确非对齐 HEVC 参数需要厂商证据或独立受控实验，
不能通过放开保护来声称修复。本轮未再发起原驱动的危险编码。
