# 2026-10-21：7.3 GPU/IR 合并内核正式部署

合并后的 `51307a1cf3a60` 已正式留在板上，未恢复旧候选。Image、audio-test DTB 和
2335 个模块来自同次构建，保留 BTF；启动、网络、GPU devfreq、IR/按键注册、
HDMI/Wave5 和 CRG HID/虚拟盘短回归通过。原 #12 整包及启动清单保留，可回退。
本轮不是完整长期验收；未验证项见末节。

## 源码、配置和构建

VM `/home/deepdream/src/linux-7.3`、分支 `vim4-kvm-7.3`，HEAD
`51307a1cf3a60ea1a9cfc1cd35f159c5373d8f1d`，tree
`a949e4e664ce9ec1050c95cf6399444483ad80fb`。三个新增提交为 Panfrost 纯调频 OPP、
VIM4 GPU devfreq 和 IR/按键/禁用 SPIFC 节点；本轮未改源码、未提交内核仓库。
构建前后 git status 均为空；两个临时内核工作树已由用户删除。

配置直接使用 `packaging/kernel-edge/uhd1.config`，按原 #12 的流程复制到新空 O=，
再 olddefconfig。与部署前 `/proc/config.gz` 对比，最终差异严格只有：

```diff
-CONFIG_IR_MESON=y
+CONFIG_IR_MESON=m
```

原配置 SHA256 `610ff17daf5bb40085ca657f40a7436c1ff257c57aabb65367fb2aa3a4709ae9`；
最终配置 `b67c0feeb849506467984d27fa75c9484d5dbe46073bb33b22bbfd6418d0c298`。
通用 edge 配置也在本次 HEAD 单独 olddefconfig，最终为
`ea60195c2dcdad4211146db782ee2c6f5b38f450edecbd13c2a770879e23bc71`。
两者均保留 IR_MESON_TX=y、RC_MAP=m、IR_NEC_DECODER=m；模块化取舍见
[自动键表记录](2026-10-21-edge-ir-autoload.md)。

更新本地主仓库 sources.toml 的源码锁后，将 build.sh、配置与锁复制到 VM 临时配方目录，
使用已有构建入口；GCC `13.3.0-6ubuntu2~24.04.1`、8 jobs：

```sh
JOBS=8 bash /home/deepdream/build/gpu-ir-deploy-recipe/build.sh \
  /home/deepdream/src/linux-7.3 /home/deepdream/build/kernel-gpu-ir-deploy \
  /home/deepdream/build/gpu-ir-deploy-recipe/uhd1.config
make -C /home/deepdream/src/linux-7.3 O=/home/deepdream/build/kernel-gpu-ir-deploy \
  ARCH=arm64 -j8 modules_install INSTALL_MOD_STRIP=1 \
  INSTALL_MOD_PATH=/home/deepdream/build/kernel-gpu-ir-deploy-stage
depmod -b /home/deepdream/build/kernel-gpu-ir-deploy-stage 7.3.0-rc7-vim4kvm-uhd1+
```

入口执行同次 `Image dtbs modules`；构建成功，内核编译日志未检出 warning/error。
完整模块集为 2335 个 `.ko.xz`，保留分离 BTF，不覆盖几个单独模块。
DTB 取同次构建的 `amlogic-t7-a311d2-khadas-vim4-audio-test.dtb`，仅用 fdtput 保留原
以太网 `mac-address`/`local-mac-address` 为 `c8:63:14:74:70:0d`。
GPU OPP、IR、按键均随源码继承，SPIFC 继续 disabled，不抢占 8-bit eMMC 引脚。

| 正式产物 | SHA256 |
|---|---|
| Image | `7b8607b2c24b7a1f41a2670770dea07a813a2773c36902e9527dcd4c131bc784` |
| vim4.dtb | `e0ebe345dba968f811136de69412cc58846814775ce4d4f3ac440ee5d32961c5` |
| 完整 modules.tar.gz | `ab5e1464d715d2aa45b4e1bae8be527a033d78df54a94102fdb7169344ab7b6e` |

## 安装和备份

Mac 整个备份、安装、重启、验证窗口持共享锁：

```sh
/usr/bin/lockf -t 600 /tmp/vim4-board.lock \
  python3 -u build/kernel-edge/gpu-ir-deploy/board-window.py
```

备份位置：板上 `/var/backups/vim4-gpu-ir-deploy-20261021`，包含原 Image、DTB、
extlinux、完整 `modules.tar`、原配置、dmesg、逐文件清单、kernels.json 和
runtime-build.json。原完整模块目录另保留为 `modules-before`，未重新 depmod。
原 Image SHA256 `25241ef8c402619e6917e6826129ba301c4b4dfacc4665db365620e9489faa48`，
原 DTB `471fc2881ed6c83726ac1db85277aaeadbb63eb6b608d821f2e0bc177d96a567`，
原运行 build ID `7aa593508a6e987e754de0e343498dbbc8c2edd7`。

候选模块解到暂存目录，使用 `tar --keep-directory-symlink`，校验全部文件后切换完整
release 目录。`/boot` 仅余约 13MiB，先将旧 Image 备份至根分区，再移除并复制新 Image。
`/lib -> usr/lib`、5.15 Image/DTB/initrd 链接、Stock/Default 启动项和全部原启动参数不变。
FullKvm 仍显式使用 `/edge/Image`、`FDT /edge/vim4.dtb`，无 INITRD。

使用现有 `register-runtime.py inventory` 生成完整证明，安装后 register 全量校验：

```text
{"default":"FullKvm","registered":[
  {"id":"vendor","release":"5.15.137-vim4kvm","artifacts":1535},
  {"id":"mainline","release":"7.3.0-rc7-vim4kvm-uhd1+","artifacts":2350}]}
```

成功后同步 `/etc/vim4-kvm/runtime-build.json` 的内核来源、build ID、Image/DTB/模块包
哈希及本轮部署条目。其余包/应用历史字段保留，没有重新宣称全部应用版本验收。
本地主仓库 sources.toml 的 kernel/tested_build 同步本次已部署产物；未提交或推送。

## 启动、GPU、IR、按键和日志

候选重启后 boot_id 为 `5b7de35f-194b-4d05-9135-f2e53f50afbb`，systemd 为 running，
SSH 网络返回。`uname -a` 与 `/sys/kernel/notes` 的实际输出：

```text
Linux Khadas 7.3.0-rc7-vim4kvm-uhd1+ #1 SMP PREEMPT Thu Oct 22 05:06:44 UTC 2026 aarch64 aarch64 aarch64 GNU/Linux
kernel_build_id: 52d5e46fb006230785110a1fa5ba0dd1383b732f
```

运行配置 SHA 与最终 .config 一致，Image/DTB 和完整模块逐文件哈希匹配。已加载
`/sys/module/NAME/notes/.note.gnu.build-id` 与同次模块包逐一比对：

| 模块 | 实际已加载 GNU build ID |
|---|---|
| dwmac_meson8b | `b1abdb06a66968cffc02a86c7fb96ed030f847dc` |
| panfrost | `e67e139e7cec34e7af3c660960d51174cccdbfb3` |
| wave5 | `ccf41f01d1b624738912ca6e55a8b47d72156fe4` |
| t7_hdmirx | `4acd39b5bd849a03382f78ba917ec962bcfbafed` |
| t7_vdin_test | `b8cbea260ce5108b216d5cee75091015a73cfb27` |
| crg_udc | `605b4bc23e6b7fc1b48fa4343817c52794f77e18` |
| meson_ir | `585e3c8d61dfc1715e01c990cc575a7063908482` |
| rc_khadas | `72d76d0463d041ae024c9c7a122c489eab50790a` |
| ir_nec_decoder | `65f0685f8d53b28a5aee9e573e8dd93ba11078ca` |

读取 GPU sysfs、input、无参数 ir-keytable 和服务状态，实际输出：

```text
GPU available_frequencies: 250000000 400000000 500000000 666666666 800000000
GPU governor: simple_ondemand
N: Name="adc-keys"
N: Name="polled-keys"
Default keymap: rc-khadas
Enabled kernel protocols: lirc nec
vim4-manager: active
one-kvm: active
taint: 0
```

ir-keytable 前已读取 sysfs 协议为 `[nec]`、`[lirc]`，并确认三个 IR 模块已自动加载；
没有手动 modprobe 或执行 `ir-keytable -c/-w/-p`。GPU 本轮仅复核五档与 governor，
不重复声称完成[此前的渲染负载专项](2026-10-21-edge-gpu-devfreq.md)。

部署前保存完整 dmesg 和 err/warn 子集，回归前后按去时间戳后的文本与已知模式比较。
SCMI malformed reply、PCIe IRQ index 1、optee/RPMB、eth_wake_irq/sfty、fan 首次
读温告警、mmc descriptor DMA 和 CRG get state 属于已知基线；原 mali regulator
两条警告已消失。现有 brcm 固件/txcap、iwconfig 弃用和 CIFS 默认协议提示仍在。
USB 组合切换新增的 get state 0/1 属同一已知模式。回归前后均输出：

```text
New unexplained warnings: []
HEALTH VERIFIED
```

## HDMI、Wave5 与 CRG 短回归

只用现有工具依次执行，没有并行性能采样、没有暂停 UU 或停止 manager。
Mac 的现有 HDMI 运动夹具临时覆盖 RTK 物理桌面；网关经 SSH 转发到本机 19180，
MANAGER_PASSWORD 仅从现有开发账户文档读入子进程环境，不写命令行或日志。

```sh
VIM4_HDMI_DISPLAY=RTK build/kernel-edge/gpu-ir-deploy/latency-source \
  180 --motion --verify-coherence --no-labels
# 以下依次执行；运动夹具只在视频阶段运行
node tools/one-kvm-smoke.mjs http://127.0.0.1:19180 --exclusive --mode=h264 --seconds=15 --warmup=3
node tools/one-kvm-smoke.mjs http://127.0.0.1:19180 --exclusive --mode=h265 --seconds=15 --warmup=3
node tools/one-kvm-usb-check.mjs --exclusive --hid-only
node tools/one-kvm-usb-media-check.mjs --exclusive --service=one-kvm \
  --image=build/kernel-edge/usb-edge-transfer.img
```

PLAYWRIGHT_MODULE 指向已有运行时，ONEKVM_URL 为该转发地址；运行后恢复原编码模式、
USB 配置、指针及临时接收窗口，主机安全弹出并删除本轮上传的测试盘副本。

| 验证项 | 本轮实际输出 |
|---|---|
| HDMI | `core_active: 1`、`link_ready: 1`、`phy_pll_locked: 1`、`width: 3840`、`height: 2160`；VDIN `faulted: 0`、`stream_error: 0` |
| 编码后端 | 正式进程环境 `VIM4_VIDEO_BACKEND=wave5`，`GST_PLUGIN_PATH=/usr/lib/vim4-kvm/mainline-gstreamer-1.0` |
| H.264 | `video/H264`，3840×2160，`fps: 59.9751099389124`，15 秒窗口 freezes/dropped/lost 均 0 |
| H.265 | `video/H265`，3840×2160，`fps: 59.971130108801624`，15 秒窗口 freezes/dropped/lost 均 0 |
| 原生 HID | `keyboardDown:1`、`keyboardUp:1`、`absoluteMouse:true`、`click:true`、`wheel:true`；相对鼠标由 `[0.6999959,0.5999891]` 移到 `[0.7099040,0.6117332]` |
| 只读盘 | `readonly:true`、`hostUsb:true`、`hostEjectClearedLun:true`，主机读取专用标记成功 |
| 可写盘 | `writtenBytes:1048576`、`applicationRestartPreservedMedia:true`、`hostEjectClearedLun:true`；写回 SHA256 为 `bd8a5183fdafb052402b7f52480145004a781b927f0d376e4fbd922da44f6926`，fsck 通过 |
| 结束状态 | 脚本 `{"kind":"complete","restored":true}` 指 USB 设置恢复；内核保留新版本。LUN 为空，空闲 `Total 0 objects, 0 bytes` |

回归前风扇为 `speed_percent:16, temperature_millic:50900, sensor_fault:0`；
回归后为 `22, 53600, 0`。结束即刻六温区分别 53000、50100、50100、50100、49900、
50000 m°C，taint 仍为 0。风扇温度是最近采样值，百分比是控制输出，不是 RPM。

## 结果与边界

全窗口成功结束：`DEPLOYED: matched runtime inventory registered; Stock/5.15 and boot links preserved`、
`SUCCESS: new merged kernel remains deployed`。未触发关键失败回退，没有把板子恢复到 #12。
备份仍在上述路径；若需回退，持同一 Mac 锁，使用板上临时 board-helper.py 的 restore
恢复 Image/DTB/完整模块和两份清单，再重启并 verify-restore，不能只复制旧 Image。

本轮只对正式 One-KVM 做短视频/USB 回归，没有重跑四应用/双内核往返、HDR 色彩、
音频波形、UAC2 录音、物理 IR/按键动作或唤醒、断电冷启动、GPU 长负载和长期稳定性。
运动源已运行，但本次 smoke 不解析帧内标记，不能据此宣称像素一致性或端到端延迟通过。
SPI NOR 继续禁用，没有读写、擦除或实装容量验收。Wi-Fi/P2P 代码和服务未操作。

本机原始证据在 `logs/kernel-edge/gpu-ir-deploy/`：board-window.log、构建/打包日志、
部署前后 dmesg/warnings、backend.txt 和 runtime-build.json。产物、最终配置和逐文件
manifest 在 `build/kernel-edge/gpu-ir-deploy/`；VM 独立 O= 和 stage 保留。

主仓库 `python3 -m unittest discover -s tests -p 'test_*.py'`：
`Ran 147 tests`、`OK (skipped=5)`，`git diff --check` 通过。未提交主仓库、未推送，
保留此前 GPU/IR 记录和其余未提交改动。
