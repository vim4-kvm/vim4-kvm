# 2026-10-22：Wave5 尺寸与关闭路径防护正式部署

第二轮完整回归通过，正式部署已保留，双锁已释放；首轮关键失败及自动回退见下文。
本轮合入尺寸保护和正常完成 IRQ 的关闭顺序修复；没有实现固件无响应后的通用复位恢复，
不开放非 8 对齐 HEVC。前置现场证据见
[候选现场验证](2026-10-22-wave5-hevc-field.md)，源码边界见
[离线分析](2026-10-22-wave5-hevc-hang-analysis.md)。

## 源码与发布边界

用户授权无人值守正式部署，失败按既有关键项策略回退；SSH 失联超过 180 秒停止，
不等待现场 RESET、不循环重启。起点为
[pstore 正式部署](2026-10-22-edge-pstore-deploy.md) 的 1262da082ba5，
build ID `f283ab1f8a001a19bab5247afc4f9b0c00c1da99`。

VM `/home/deepdream/src/linux-7.3` 的 `vim4-kvm-7.3` 已快进并推送：

- `2df3c915a8de02315ac68704a5be643e9e0df756`：拒绝不合法编码 crop/固件尺寸；release 在移出 IRQ 分发前结束正常任务。
- `537ad90f65620c8e7bf74f3ccf16d6544b0fc916`：有界编码/取消取证脚本。
- `0196fe22ecf0104d96b7ef0fa497ca2317bd20bb`：核验输出实际尺寸/帧数，防止静默填充误报成功。

最终 tree `6d92e84e1d2135e3abf601cf3a5bbfc6c6976f51`。
相对 1262da08 只有 Wave5 目录内五个文件，无 `vim4-vdec` 改动。
Git 默认凭据失败后，通过 Mac 的 `gh auth git-credential` 完成推送，未改 Git 配置。
构建仍用独立干净 worktree `/home/deepdream/src/linux-7.3-wave5`；主工作树仅作用户要求的快进。

## 完整构建与部署命令

准确配置 `packaging/kernel-edge/uhd1.config`，全新独立 O=，保留 BTF：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build bash \
  /mnt/mac/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/packaging/kernel-edge/build.sh \
  /home/deepdream/src/linux-7.3-wave5 /home/deepdream/build/kernel-wave5-deploy \
  /mnt/mac/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/packaging/kernel-edge/uhd1.config
# 同一 heavy 锁约束下，package-final.py 打包完整模块树和实际板端 MAC：
# source=/home/deepdream/src/linux-7.3-wave5
# output=/home/deepdream/build/kernel-wave5-deploy
# destination=/home/deepdream/build/kernel-wave5-deploy-payload
# --commit 0196fe22ecf0104d96b7ef0fa497ca2317bd20bb --mac c8:63:14:74:70:0d
```

Mac 发布目录 `build/wave5-deploy/`，日志 `logs/wave5-deploy/`。
final-regression prepare 使用默认九类检查，原始 HDMI 抽样 `5,7,18`，不启用 Wi-Fi 扫描。
将额外 Wave5 几何测试接在关键 h265 检查后，失败进入同一自动回退事务。
stage 使用 `--kernel-only --verify-pstore`，One-KVM 保留 382efb70e7ebb，
manager 保留 4ea748426935；PD/journal 配置只比较哈希，不替换。

部署使用现有 final-window.py 事务，本地 `build/wave5-deploy/window.py` 仅增加
180 秒失联停止和重启后 UDC not attached 时 usb-pd-init 的用户指定策略。
外层 lockf 同时持 board/heavy，传入 --locked，覆盖备份、安装、两次启动、全部检查和必要回退：

```sh
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/wave5-deploy/window.py window \
  --bundle build/wave5-deploy/bundle \
  --backup /var/backups/vim4-edge-wave5-20261022 \
  --logs logs/wave5-deploy/window \
  --archive-remote-to /var/tmp/vim4-deploy-pre-wave5-20261022 --execute --locked
```

失联停止策略不会声称完成回退。普通关键项失败且板子可达时，由原事务完整回退并重启确认。
不覆盖旧远程暂存目录，先归档到上述 pre-wave5 路径。

## 回归口径

1366×768 HEVC 不能以 gst 返回 0 验收：S_SELECTION 必须 errno=22，
脚本必须发现实际输出为填充宽度并返回 1，无超时和残留任务。
1368×768 HEVC、1366×768 H.264 各输出准确尺寸的 180 帧并软件解码。
这些小尺寸使用 videotestsrc，只检验编码入口，不声称覆盖完整 HDMI 1366 链路。
One-KVM 的 1366 HEVC 应用回退及实际 HDMI 链路由编码往返回归覆盖，step 8 不改。
正常编码退出通过不能证明 IRQ 丢失或固件不完成时有界恢复。

本轮离线：Wave5 20 组参数、8 组关闭/IRQ 顺序、观察器 3 项通过；
已有 buffers、cleanup（32 cases）、geometry、intra_refresh、profiles 全通过。
部署前主仓 182 项、5 skipped、OK。

## 完整产物身份

新配置 SHA 与已部署 uhd1 相同；DTB 的板端 MAC 保持 c8:63:14:74:70:0d。

| 项目 | 身份 / SHA256 |
|---|---|
| release | `7.3.0-vim4kvm-uhd1+` |
| build ID | `3a61b75bccf8c46e9411dee92928999884bbfc7f` |
| Image | `34fcacc47825b82abab0b0ba41e0e3b7bf4f9e93729d2d71e8532ca18b33d2d8` |
| DTB | `d2333e962326d0710300b71e758440a94b177eb273921f70e5ba12eb5f640cf6` |
| modules.tar.gz | `90ef5b8ea749636ec9453098a93fa2f3b0575bca29919913b249de11574d5412` |
| config | `86746fde4d0e6d377264466262a27b4953206ce5e07441c8b870eee5ca05957f` |
| 模块数 / BTF | 2335 / 保留 split BTF |
| Wave5 build ID | `e4c1ef1943745fe507cd1b72be2c483b1fe3832c` |
| Wave5 压缩模块 | `a5e30410968e0026f9252abb64329d957c220344b3badac001dd9e91fb737960` |

manifest 含全部模块哈希及11个加载build ID，已核对sources.toml。
完整payload在 `build/wave5-deploy/kernel/`，日志build.log/package.log；未复用单模块测试包。

## 第一轮自动回退

首轮 baseline 为 `/var/backups/vim4-edge-wave5-20261022`，Mac 副本
`logs/wave5-deploy/window/baseline/`。六个文件下载后逐哈希核对才安装。
首次启动实际 `CRITICAL_HEALTH_VERIFIED 3a61b75b…`、`NEW_WARNINGS []`，
完整文件树、真实加载模块、服务和 taint 通过。
HDMI 三档抽样和 H.264 九模式正反共 18 次通过。

H.265 的 640×480 首档通过；下一档 720×400 浏览器曾收到帧并完成快照，
但资源采样发现 `Total 0 objects, 0 bytes`，触发 `capture stopped during the browser sample`。
应用 journal 同时有 HDMI 切换期间的 capture/poll 错误；未证实原因，
没有把它归为测试假阳性，也未发现 Wave5 超时或整板挂死证据。
关键 h265 失败触发完整自动回退，正常重启后实际输出：

```text
BASELINE_RESTORED f283ab1f8a001a19bab5247afc4f9b0c00c1da99
```

回退后 manager/One-KVM active、UDC configured、taint=0。
首轮未执行额外几何检查和后续六类回归，不能沿用上轮候选结果作本轮通过证据。
证据为 window.log、window/h265.log、failure-board.log、failure-source-mode.log。

保留完整失败记录后，以同一发布包和不变的检查门槛完整重试一次。
第二轮使用 `bundle-r2`、`regression-r2`、`logs/wave5-deploy/window-r2/`，
备份 `/var/backups/vim4-edge-wave5-20261022-r2`，首轮远程目录归档到
`/var/tmp/vim4-deploy-wave5-failed1-20261022`。第二轮结果如下。

## 第二轮通过并保留

同一发布包重新安装后，九类回归全部 passed，无降低门槛或忽略失败：

| 检查 | 实际结果 |
|---|---|
| 原始 HDMI | 720p50、1366×768、4K60 三档，帧推进、图案/颜色、步幅和 DMA 回收通过 |
| H.264 / H.265 | 九模式正反 18 次 / 八模式正反 16 次通过；首轮失败的720×400本次通过 |
| HEVC 尺寸保护 | 1366×768、1440×900、1680×1050 的 ioctl 均 errno=22；1368×768 ret=0 |
| 1366 HEVC | gst=0，但1376×768/180帧；观察器=1，准确报告尺寸错误，无超时、残留任务 |
| 合法小尺寸 | 1368×768 HEVC、1366×768 H.264 各180帧，尺寸正确，软件解码返回0 |
| 4K60运动源 | 各15秒、预热3秒，H.264 59.97479 fps、H.265 59.97730 fps，dropped/lost/freezes/PLI增量全0 |
| 音频 | 同连接48k→44.1k→48k，各15秒，原生速率及稳态波形检查通过 |
| HID | 实际Mac窗口收到键按下/抬起、绝对/相对鼠标、点击和滚轮；额外重启后再测通过 |
| 虚拟盘 | 主机只读/可写访问、1MiB写入哈希回读、应用重启保留、主机eject清LUN；设置已恢复 |
| GPU | Panfrost，10秒304帧，runtime resume后3秒91帧，gl_error=0；自动调频保留 |
| manager / PD | 4ea7484二进制、正式内核选择、PD卡、390px页面、无pageerror；额外重启后通过 |

HEVC非法尺寸判错是 ioctl/观察器的成功防护，不能描述为 gst 本身返回错误。
4K呈现回调有跳号：H.264/H.265 callbackMissed=71/26，p99=33.9/33.5ms，
均无超过50ms回调间隔；没有据平均60fps宣称每次回调都平滑。
音频切换后健康报告出现两条 ASoC hw_params `-11`；最终重启后 `NEW_WARNINGS []`。
短测不推翻历史音频偶发跳变/长期稳定性边界，也未确定首轮采集停止的原因。

第二轮写入普通 console 标记，正常重启后读回：

```text
PSTORE_MARKED VIM4_PSTORE_DEPLOY_8ab33aa4-7167-4cc1-92e5-695abfe2baad
PSTORE_READBACK VIM4_PSTORE_DEPLOY_8ab33aa4-7167-4cc1-92e5-695abfe2baad {'console-ramoops-0': 31615}
CRITICAL_HEALTH_VERIFIED 3a61b75bccf8c46e9411dee92928999884bbfc7f
UBOOT_UNCHANGED 751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0
DEPLOYMENT_RETAINED {"kernel":"0196fe22ecf0104d96b7ef0fa497ca2317bd20bb", ...}
SUCCESS: final deployment retained; no baseline reboot
```

最终 boot ID `fcca52f8-0d54-4fd9-9d0d-8296934b341d`，kernel build ID 3a61b75b…、
Wave5 e4c1ef19…，intree=Y，vermagic匹配，taint=0，manager/One-KVM active，
UDC configured，无failed unit。没有持续失联超过180秒或物理RESET，未调用usb-pd-init。
systemd-pstore临时mask已撤销，console已正常归档；本轮只验证正常重启，不主动panic。
归档旧 dmesg-ramoops 为43324字节、时间01:57:34 UTC，早于本轮；前后SHA相同，不能当本轮新崩溃。

12项保留文件前后哈希相同，包括 manager SHA
`3fc215e3de431d1c65e08e62b3179b6329e190d803ab77e89dae3c3d90728eb1`、PD与journal配置。
PD仍为固件超时/Type-C fallback，开机服务按原策略跳过，没有重协商或伪造合同。
持久journal列出本轮各启动，上一启动可读，占用215.9MiB，原256MiB上限和rsyslog mask未改。
runtime-build.json已登记新源码、完整模块包和第二轮备份位置。

## 备份与回退

**当前部署对应第二轮备份** `/var/backups/vim4-edge-wave5-20261022-r2`，Mac副本
`logs/wave5-deploy/window-r2/baseline/`；不是首轮日志目录。
两端核对通过的SHA256：

```text
files.tar       07e146fb527175f33b28c3f4138b40c12ef080d87085bc73ac1b0d5fcc826373
modules.tar     a16f82a3157255acbd3026425f1541195d422289cac55b61bfd3b1e8d59ce91c
application.tar 2bb8c6311b5deff1acafb1c39fcaca91a4305ef1ad109dc8a695a0b37100a80c
```

以下恢复部署前1262da08内核、完整模块和配置快照，重启后应回到f283ab1f…。
执行前另存晚于快照的应用配置；不会刷U-Boot。回退目录必须新建：

```sh
python3 packaging/kernel-edge/final-window.py rollback \
  --bundle build/wave5-deploy/bundle-r2 \
  --backup /var/backups/vim4-edge-wave5-20261022-r2 \
  --logs logs/wave5-deploy/rollback --execute
```

入口自动持双锁。无人值守仍需180秒停止策略时，使用上文双lockf窗口和
本地window.py，将window子命令改为rollback、保留--locked，并去掉archive参数。
本轮已实际验证首轮自动回退；未执行保留后的第二轮手动回退。

主工作树184项/5 skipped、发布worktree184项/9 skipped，均OK；sources.toml身份与manifest匹配。
发布只纳入sources.toml、本记录及README索引，不纳入并行VDEC修改。
日志包括window-r2.log、regression-results.json、health.json、各类回归、UART、
preserve-before/after.json、final-readonly.log、pstore-before/after.tar、previous-kernel.log。
180秒停止包装器仅离线仿真，未触发实机失联。
