# 2026-10-22：T7 解码候选现场分级验证

本轮在 probe 阶段失败：注册 video 节点后，udev 的 `v4l_id` 自动 open，
触发 DOS 上电路径的异步 SError/panic。板子随后重启回预置的 pstore 基线，
实际 HID 与 HDMI→Wave5 H.264→浏览器短测通过。按
[候选清单](2026-10-22-vdec-candidate.md) 停止后续步骤，未正式部署解码器。

## 版本与恢复目标

内核独立 worktree `vim4-build:~/src/linux-7.3-vdec`、分支 `vim4-vdec`，
原八个候选提交 rebase 到 `1262da082ba528be27c17adc62a92d90ed18b158`，
新头 `5bf7d6359df9ff68d8746851cf45de40611988a1`，已推送 fork 的 `vim4-vdec`；
使用明确旧值的 `--force-with-lease` 更新 rebase 后的分支。独立
`O=~/build/kernel-vim4-vdec-field` 完整构建，
由 `package-vdec.py` 校验干净源码、构建 stamp、模块 vermagic/BTF 后打包。

恢复目标为 `7.3.0-vim4kvm-uhd1+`，内核 build ID
`f283ab1f8a001a19bab5247afc4f9b0c00c1da99`；
Image SHA256 `855f0fa8caa49fdb9973bd7cd1cbbfaa2c5f62138574862e651e16eb0fda42b5`，
DTB `d2333e962326d0710300b71e758440a94b177eb273921f70e5ba12eb5f640cf6`。
Wave5 原模块 SHA256
`686b455d458043e267fced254e694bdcb0ae5982a3bde4f7e5a4260d841c99ef`，
已加载 build ID `5545f3a76ceb5caaff2c23391e00ebc6290da563`。
初始 boot ID `0edc116f-b44e-4b93-9a6f-52ed63a5644e`，服务均 active、UDC configured、taint=0。

现场脚本的恢复校验从历史 `3ed254bf…` 更新到本轮 `f283ab1f…`；
诊断工具使用临时 payload 中的 Ubuntu v4l-utils 1.26.1-4build3，不安装系统包。

## 构建与产物

2026-10-23 00:56–01:22 UTC（Mac 为10月22日）完成构建及板上窗口。
构建持 Mac heavy 锁，现场安装、启动、测试和恢复验收全程持 board/heavy 双锁，
结束均已释放。源码与 VM 主工作树干净，主工作树仍为 `1262da082ba5`。
候选配置相对 `uhd1.config` 只修改 localversion、增加 `CONFIG_VIDEO_MESON_T7_DOS=m`。

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build make \
  -C /home/deepdream/src/linux-7.3-vdec \
  O=/home/deepdream/build/kernel-vim4-vdec-field ARCH=arm64 -j8 \
  Image amlogic/amlogic-t7-a311d2-khadas-vim4-vdec-test.dtb \
  amlogic/amlogic-t7-a311d2-khadas-vim4-audio-test.dtb modules
# 同一 heavy 窗口生成 vdec-build.json，再运行：
python3 packaging/kernel-edge/package-vdec.py /home/deepdream/src/linux-7.3-vdec \
  /home/deepdream/build/kernel-vim4-vdec-field \
  /home/deepdream/build/vim4-vdec-field-bundle --mac c8:63:14:74:70:0d
```

候选 release `7.3.0-vim4kvm-vdec3+`，build ID
`1ca661edb9a6e76a88d78af1fa852b47d647e5b7`，2336 个同次构建模块。
打包校验完整构建 stamp、模块清单，及 VDEC/DOS/JPEG/Wave5 的 vermagic、split BTF。
VM bundle 为 `~/build/vim4-vdec-field-bundle`，Mac 副本 `build/vdec-field/bundle`。

| 产物 | SHA256 |
|---|---|
| Image | `6acfa3a5b7b5bb7013e6bf227874f2b9ad41afea94ca272adb47cb7ae59e173a` |
| vdec-test DTB（包内 vim4.dtb） | `04cc3d480cdb8ee462f5263508114ddec449331f9216db93f286ca02407ed540` |
| modules.tar.gz | `ee25bd6231f24aa37091db77cefab610ff6181b9598582095113a4ab0366087e` |
| config | `7783861c2d4bd9ef4ac2ee960b8cdfbaf457bca34a15bbb5b8d0294ad873c85f` |

## 分级实测：第一步失败即停止

临时 payload `/var/tmp/vim4-vdec-field`，fixtures `/var/tmp/vim4-vdec-field-fixtures`，
新备份 `/var/backups/vim4-vdec-field-20261022`。基线模块目录未替换，
候选模块独立保存在其 release 目录，恢复后没有加载 VDEC/DOS 模块。
未改应用、运行时白名单、部署版本锁或 U-Boot。

锁内逐条调用如下；`ACTION` 实际依次为 `boot-install`、`arm-baseline`、`probe`，
panic 回到基线后仅执行 `verify-baseline` 和恢复验收，未继续 codec 测试。

```sh
python3 packaging/kernel-edge/vdec-window.py ACTION --locked --execute --at-board \
  --manifest build/vdec-field/bundle/manifest.json \
  --payload /var/tmp/vim4-vdec-field \
  --backup /var/backups/vim4-vdec-field-20261022 \
  --fixtures /var/tmp/vim4-vdec-field-fixtures
```

| 步骤 | 实际结果 |
|---|---|
| 安装、一次候选启动 | 成功；候选 boot ID `5f6d41b0-6624-4a4c-9c69-c0edadc6301f`，固件预加载服务 `ExecMainStatus=0, SubState=exited` |
| arm-baseline | 成功，原 Image/DTB 写回并 sync、校验 SHA；下一次启动回基线 |
| probe | **失败**：先输出 `PROBE_REGISTERED /dev/video0`，随后自动 open 触发 panic；未完成健康卸载，不算通过 |
| 显式上电/下电、v4l2-compliance | 未执行；自动 open 已越过原先设想的无上电 probe 边界 |
| 小尺寸 H.264、1080p 对比/性能、Wave521C 解码 | 均未执行；没有硬件解码输出、MD5/PSNR、速度或 CPU 结论 |

实际串口及新 pstore 共同保存：

```text
[82.022008] SError Interrupt on CPU6, code 0x00000000bf000002 -- SError
CPU: 6 UID: 0 PID: 1481 Comm: v4l_id ... 7.3.0-vim4kvm-vdec3+
Kernel panic - not syncing: Asynchronous SError Interrupt
regmap_write → dos_enable+0x4c/0x88 [aml_vdec_drv]
→ vdec_enable → aml_vdec_runtime_resume → pm runtime resume
→ fops_vcodec_open → v4l2_open → openat
```

板上 `/usr/lib/udev/rules.d/60-persistent-v4l.rules` 有
`IMPORT{program}="v4l_id $devnode"`。脚本自己没有 open 并不能阻止系统的自动探测。
离线 objdump 将 `dos_enable+0x4c` 对应到 `aml_vdec_hw.c:49` 的
`GCLK_EN` 写返回位置（DOS 字节偏移 `0x260c`，值 `0x3ff`）；
前面还有 `DOS_GCLK_EN0` 访问。SError 是异步异常，不能据此断言唯一故障寄存器或根因。
需继续对照厂商核对映射、时钟、secure genpd 和隔离时序；未在线读写寄存器重试。
此次异常早于固件加载和提交解码任务，secure H.264 加载、DMA 超时隔离均未得到硬件验证。

出现失联后已在用户输出打印复位提示。串口随后显示新的 U-Boot 启动与
`reboot_mode : watchdog_reboot`，SSH 返回基线；未再发送重启命令或重试候选。
未要求用户继续等待10分钟；日志本身不能区分硬件复位源与现场 RESET 操作。
旧 SSH 已确认属于消失的候选启动后才终止本地等待进程。

## pstore 与恢复证据

两处目录前后均已采集。恢复后 `/sys/fs/pstore` 为空，systemd 已归档到
`/var/lib/systemd/pstore`：新 `dmesg-ramoops-0` 为42641字节，SHA256
`908ad8443c8cec21eaf715442a5fa78a7a4b8b072cbcecee80882de262bdeaff`；
`console-ramoops-0` 为3972字节，SHA256
`c0b36387d659d4e66b6b6f91d6434861fcb2f496acbd2c80353a58474cbc3679`。
前者明确包含本次 `v4l_id`/SError 栈；与初始10月20日的189366字节旧 dmesg 记录不同。

```text
BASELINE_BOOT_SERVICES_UDC_OK f283ab1f8a001a19bab5247afc4f9b0c00c1da99
boot ID: 053b91d2-de73-43cf-aa5f-23abfcedcbfc
one-kvm=active
vim4-manager=active
UDC=configured
taint=0
0 loaded failed units
```

Image/DTB、原 Wave5 文件 SHA 和已加载 build ID 均与开头恢复目标一致，
无残留 gst-launch。UDC 自行 configured，未运行 usb-pd-init。
双锁内实际执行：

```sh
python3 build/pstore-deploy/regression/video/run-tool.py \
  tools/one-kvm-usb-check.mjs --exclusive --hid-only
python3 build/pstore-deploy/regression/video/run-tool.py \
  tools/one-kvm-smoke.mjs --exclusive --mode=h264 --seconds=5 --warmup=2
```

实际 HID 输出 `keyboardDown=1, keyboardUp=1, absoluteMouse=true, click=true, wheel=true`，
relative 指针从 `[0.6999959,0.5999891]` 移至 `[0.7099040,0.6117332]`。
恢复后 HDMI→原 Wave5 编码→Chrome H.264 解码3840×2160，5秒采样约60.125fps，
呈现约60.004fps；dropped/lost/freezes/PLI 增量均0。它只是基线恢复短测，
不属于候选硬件解码性能，也没有覆盖像素正确性、音频或长期稳定性。

## 防重试、检查与下一步

`vdec-window.py` 现在在 SSH/拿锁之前拒绝安装或测试上述已失败源提交，
仍允许 `arm-baseline/verify-baseline` 恢复；默认离线计划不受影响。
执行时的原脚本副本为 `logs/kernel-edge/vdec-field/window-executed.py`，SHA256
`c286ce4a2b6e23892bf431eb81e8d1259cd44d6d4e4f4b5fc3628387203e770f`。
另外增加关闭后 runtime suspended 校验，失败保留恢复标记、不卸载模块。

离线 C 生命周期测试6项通过；现场工具测试新增了未 suspend 和已知 panic 候选拒绝边界。
完整构建成功，无编译 warning/error；八个历史提交的严格 checkpatch 仍有提交正文、
Signed-off-by、MAINTAINERS 提示，不能宣称整组 checkpatch 干净。
主仓执行 `python3 -m unittest discover -s tests -p 'test_*.py'`：180项通过，5 skipped。
完整日志在 `logs/kernel-edge/vdec-field/`，不入库。

下次先离线增加驱动内独立的“允许上电”开关，默认阻止包括 udev 在内的自动 open，
确保 probe 真正不访问 DOS；再核对首次 DOS MMIO 前的完整厂商上下电顺序并修正。
重新构建后仍需用户在板边，从无上电 probe 开始，不直接解码。
上电/下电、compliance、小码流、1080p正确帧与性能逐级通过后，才尝试最后的
Wave521C 小尺寸单实例解码。本轮不据剩余现场时间越过已失败步骤。
