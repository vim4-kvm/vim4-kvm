# 2026-11-02：HDMI-RX COR 复位锁部署与 Wi-Fi 有界流量

结论：COR 锁修复单模块已安装为默认 uhd6 运行时，正常重启后实际加载身份匹配；
三次 N/Q 条件撤回、720p60→4K60 重锁和 600 秒 4K60 解码通过。
Wi-Fi unavailable 是软件关闭；保存的 5GHz AP 上完成 600 秒 TCP 上传，无固件崩溃或断线，
但出现 23 条 unexpected txstatus，不能称历史固件问题已修复。测试后恢复 Wi-Fi 关闭。

## 部署身份与登记

Image 保持正式 `f951e2d24d32d5df0e701e7c355b3db4c91eaf74`，GNU ID
`48106f6f9fb09b12d1eaf6a5fe91953dba53d9cb`；默认 FullKvm、kbase、r14e 用户态及后续 overlay。
修复源码 `f2e8424261af18690ee1fbf2c032365da9185568`，VM 独立工作树由
`tools/vm worktree new board-cor-lock --from origin/fix/hdmirx-cor-reset-lock` 创建。

持 heavy 票，在正式输出树 `~/build/p0-1-uhd6-formal-f951e2d24d32/out` 仅构建
`drivers/media/platform/amlogic/t7-hdmirx/t7-hdmirx.ko`，全部 20 个接收器宿主测试通过。
有效 make 参数为 `ARCH=arm64 LOCALVERSION=+ KBUILD_BUILD_VERSION=1
KBUILD_BUILD_USER=vim4-kvm KBUILD_BUILD_HOST=vim4-build -j8`。
`strip --strip-debug` 后仍有 `.BTF`，以 xz 压缩安装；vermagic 为
`7.3.0-vim4kvm-uhd6+ SMP preempt mod_unload aarch64`。

| 项目 | 实际值 |
|---|---|
| 模块 GNU ID（磁盘与 `/sys/module/t7_hdmirx/notes/.note.gnu.build-id`） | `9b08acc2f8ce6ec746a59a4af4bf37565c8ed25d` |
| 安装 `.ko.xz` SHA256 | `15f0f9c08ad52655ddf1181a9e58475a15c36e064f291d2fbbcf1b75c69c0c03` |
| 未 strip `.ko` SHA256 | `0e410abf36114c574b38f8658d3194aa3098ae4f8c8962b13845611d75ed6330` |
| 正常重启后 boot ID | `e2c35bc3-8b5b-4b50-9239-2fb93153dfaa` |
| 最终 release / taint | `7.3.0-vim4kvm-uhd6+` / `4096`（既有外部模块位） |

安装路径是 `/lib/modules/7.3.0-vim4kvm-uhd6+/kernel/drivers/media/platform/amlogic/t7-hdmirx/t7-hdmirx.ko.xz`。
执行 depmod；同步 `/boot/edge/manifest.json` 的 modules/module_build_ids、
`/opt/vim4-kvm/hdr10-r14e/manifest.json` 与 `/etc/vim4-kvm/hdr10-r14e.json` 的 modules/boot_files，
并在三份清单登记 module_overlays，保留真实 Image 来源及原归档身份。
`/etc/vim4-kvm/kernels.json` 更新实际 artifacts，`runtime-build.json` 更新哈希与模块 ID/overlay。
board-runtime 与 kvm-run 已支持此 release，无需改脚本。
最终在板上调用 `vim4boot.validate_entry(..., hashes=True)` 验证两项登记的全部产物，
输出 `ALL_REGISTERED_BOOT_ARTIFACTS_VALID`，默认仍为 FullKvm。
[部署收据](../../packaging/kernel-edge/uhd6-cor-lock-deployment.json) 固定新登记哈希。
不覆写原正式归档清单，不把新模块称作原正式包内容；本轮无 push、无额外板上备份或回退脚本。

## HDMI 验证与边界

正常重启后 one-kvm、vim4-manager、vim4-kvm-hdmi、vim4-kvm-gadget 均 active，
UDC configured；ALSA 有 VIM4HDMIRX、UAC2Gadget，不测声音、不录音。
初次没有输入：5V/HPD=1、TMDS=0、link_ready=0，QUERY_DV_TIMINGS 返回 ENOLINK。
仅向板上 One-KVM MCP 所接 M6 发送一次 `key {"text":"ctrl"}` 后恢复锁定并截图确认，未向 M4 发 HID。
没有切换前台应用；稳定性源是当时 M6 的静态桌面，不代表运动内容正确性或光学延迟测试。

每次停 One-KVM，读取具名 RX status 确认 capture_users=0；
VIDIOC_S_EDID(blocks=0)、G_EDID 查询零块、保持 2 秒、重新发布原 384 字节 EDID，
G_EDID 字节一致，QUERY_DV_TIMINGS 确认 3840×2160@59.998849Hz；恢复服务并接收视频。
三次恢复后的短测 fps 分别 59.974、60.759、60.154（5 秒短样本），都有真实帧推进。
模式步骤发布单 DTD 720p60 EDID，实际读取 1280×720@59.998979Hz，随后恢复原 EDID，
重锁 UHD60 并恢复解码；不以源端 backing raster 代替线上时序。

同一浏览器会话 600.003572 秒新增 36,000 帧，59.999652fps，3840×2160；
framesDropped、packetsLost、freezeCount、pliCount 增量全为 0。前后内核日志无新增
WARN/SError/Oops，最终 link_ready=1、taint=4096。TMDS measurement ready 信息仍会出现，
不是全日志零输出；未见失锁错误或解码冻结。原始稳定性 JSON SHA256 见部署收据。

## Wi-Fi

预检：NM WIFI-HW enabled、WIFI disabled；rfkill soft blocked=yes、hard blocked=no；
NM-MANAGED=yes、FIRMWARE-MISSING=no，manager helper 的 enabled=false/mode=off。
brcmfmac 已加载 BCM43752/2 固件 18.35.387.23.88 / FWID 01-16e134aa。
这些证据支持软件关闭，不支持把 unavailable 判作驱动加载故障；不推断是谁关闭。

经 `nmcli radio wifi on` 与既有 manager helper `wifi-activate
974bbec1-7e28-4f64-91b4-674c72bc37e9` 连接已保存的 NETGEAR_5G_Game，未读取或猜 AP 密码。
5200MHz、约 −36dBm，wlan0=192.168.50.156；eth0=192.168.50.210。
有线默认 metric=100、无线=600，到 Mac 管理端 192.168.50.239 仍 dev eth0。
Mac 用 `iperf3 -s -1 -B 192.168.50.239 -p 5209 -J`，板端命令：

```sh
timeout 620 iperf3 -c 192.168.50.239 -p 5209 -B 192.168.50.156 --bind-dev wlan0 -t 600 -i 10 -J
```

600.003618 秒发送 19,075,039,232 字节，254.332Mbit/s；接收 19,072,679,936 字节，
254.308Mbit/s，TCP 重传 61。60 个每 10 秒监测点全部 `100 (connected)`；
wlan0 TX 约 19.943GB（含协议开销），证明确实走无线。
无新增 firmware trap/halted、−110、−52 或 devcoredump；旧两份 10月22日 dump 原样保留。
但新增 **23 条 `brcmf_fws_txs_process: unexpected txstatus`**，以及一次 SDIO
unaligned sg len/disabling descriptor DMA 信息。接口 RX dropped=57、TX errors/dropped=0；
不能写成零告警或零丢包，也不能称历史崩溃已修复。本轮不修这些信息，P2P 无真实对端不测。

finally 执行 `nmcli radio wifi off`，IPv4/IPv6 路由表均恢复测试前内容；SSH 路由 eth0，
manager HTTP 200、四项服务 active。原始 RAM dump/凭据不入库；取证 tgz 留在私有忽略目录。
归档 sysfs devcoredump/disabled 的伪文件出现 tar size 警告，最终 glob devcd* 为空，
不把此警告当作真实崩溃或新的转储。

## 窗口、失败与证据

所有板访问都由 FIFO `tools/board-queue run --who board-batch --purpose ... --max-min ... -- SCRIPT`
执行；下表是共享 history 的实际持票秒数。成功功能窗、Wi-Fi 窗分别 11.35、10.25 分钟；
没有单票超过 30 分钟。失败均收证据后释放，再离线修正脚本。

| 票号 / purpose | 秒 | 结果 |
|---|---:|---|
| 427 readonly-preflight | 5.233 | 软件关闭原因与初始路由 |
| 429 registration-inspect | 0.635 | 取回登记、启动器、服务定义 |
| 430 cor-deploy-verify | 32.005 | vermagic 后缀重复，写模块前拒绝；收 journal 超时 |
| 432 cor-deploy-verify-r2 | 15.406 | 模块已写，生成未使用 initramfs 时 boot 空间不足；未重启 |
| 433 cor-deploy-verify-r3 | 36.518 | 完成登记及唯一一次正常重启；Node 直连 EHOSTUNREACH |
| 434 cor-functional-stability | 68.962 | SSH 转发可用，因源睡眠无解码帧而停止 |
| 436 cor-native-verify | 1.491 | 临时 fixture 路径层数错误，访问视频前退出 |
| 437 cor-native-verify-r2 | 2.717 | 实际 QUERY_DV_TIMINGS=ENOLINK，恢复服务退出 |
| 438 source-status | 1.054 | 确认无 TMDS 输入 |
| 439 m6-wake | 21.490 | 一次 Control 唤醒及截图，恢复锁定 |
| 440 cor-functional-stability-r2 | 681.167 | 三次撤回、模式切换、600秒解码全部通过 |
| 441 wifi-10min | 614.786 | 有界流量与恢复通过，有 txstatus 信息 |
| 442 final-proof | 5.867 | 全部登记产物哈希与默认项通过 |

heavy 独立票 428/431/435 分别 6.580/2.346/0.188 秒，不持板票。
首次 make 错传 LOCALVERSION 导致重复后缀，修正为 `LOCALVERSION=+` 后重编；错误产物未安装。
initramfs 失败后核对 FullKvm 无 INITRD 字段，不再构建无用 initramfs；boot 剩余约 4.1MiB。
未删除他人产物。整个过程无 panic，不执行循环故障注入；pstore、journal、UART 已保留。

证据在本 worktree `logs/board-batch/`：`build-r2.log`、`cor-window-r3.log`、
`cor-functional-r2.log`、`initial/cycle1/cycle2/cycle3/mode/stability.json`、
`cor-before-soak.dmesg`、`cor-final.dmesg`、`cor-journal.log`、`cor-pstore.tgz`、
`cor-uart.log`、`wifi-window.log`、`wifi-evidence.tgz`、`wifi-server.json`、`final-proof.log`。
脚本副本也封存在该忽略目录；板上取回的登记原件在 `build/board-batch/registration-{before,after}.tgz`。

## 协调者锁更新

按主仓提交 `e56261e`，`kernel.revision` 跟随正式分支目标
`f2e8424261af18690ee1fbf2c032365da9185568`，正式分支快进由协调者完成。
`tested_build` 与 `retained_runtime` 的原字段保持原整包证明不变。
当前部署由 `retained_runtime.module_overlays.t7_hdmirx` 及部署收据描述，
`tests/test_uhd5_lock.py` 校验收据与锁的一致性。

未解决：txstatus 原因、历史 Wi-Fi 固件崩溃根因、真实 P2P、运动场景及超过 10 分钟的稳定性未验。

提交前主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：489 项，
477 通过、12 项环境跳过；`git diff --check` 通过。
