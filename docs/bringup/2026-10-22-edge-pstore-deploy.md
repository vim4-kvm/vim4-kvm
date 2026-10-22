# 2026-10-22：正式部署 7.3 ramoops/pstore

本轮由用户授权正式部署并保留 pstore 内核、推送内核分支和主仓部署锁。
结果：九类正式回归和正常重启 console 读回通过，新内核已保留，taint=0；
最终新增一条 SARADC channel 2 超时警告，未将“零新增警告”检查记为通过。
U-Boot 未刷写，Wi-Fi/P2P 未操作；
manager、One-KVM、PD 运行时和持久 journal 配置按安装前哈希保留。

## 来源与复用证明

`vim4-p2-pstore` 相对 `e0346697f25035c7eaa77fa44641a54d6e31e327` 仅增加
`1262da082ba528be27c17adc62a92d90ed18b158`，两文件、11 行：VIM4 reserved-memory
ramoops 节点和三个选项的 config fragment。没有合入 vim4-vdec 或 vim4-wave5-hang。
VM `/home/deepdream/src/linux-7.3` 原分支 `vim4-kvm-7.3` 干净，执行
`git merge --ff-only vim4-p2-pstore` 后推送 GitHub fork，远端从 e0346697… 快进到 1262da08…。

两个工作树 HEAD/tree 完全相同，tree 为 `f0ce0a0139240eb56601ce22e7a71def001517b6`。
旧构建 `/home/deepdream/build/kernel-p2-pstore/source` 指向干净的 pstore 工作树；
原构建 Image、vmlinux build ID、最终 config 与上轮已验证 payload 全部相符。
`logs/pstore-deploy/source-audit.log`、kernel-merge.log、kernel-push.log 和 candidate-audit.json
保留本轮核对。没有重编译或重新压缩模块，复用上轮完整匹配产物。

`scripts/diffconfig` 证明旧 uhd1 profile 与候选只差 PSTORE、EFI_VARS_PSTORE 和
REED_SOLOMON 依赖项。主仓 `uhd1.config` 更新为候选 `.config`，逐字节比较通过。
自动生成的注释版本也从 rc7 更正为 7.3.0；未改音视频、USB 或 BTF 配置。
现有 build.sh 可重建同一配置/源码；编译者、构建时钟和归档时间影响二进制哈希，
这里没有宣称重新构建能逐字节重现旧候选。

| 产物 | SHA256 / 身份 |
|---|---|
| release | `7.3.0-vim4kvm-uhd1+` |
| build ID | `f283ab1f8a001a19bab5247afc4f9b0c00c1da99` |
| Image | `855f0fa8caa49fdb9973bd7cd1cbbfaa2c5f62138574862e651e16eb0fda42b5` |
| DTB | `d2333e962326d0710300b71e758440a94b177eb273921f70e5ba12eb5f640cf6` |
| modules.tar.gz | `523f0a358573a6ca2786cace805c38a698df562a26ff2dc12a5f4f472b7efcbb` |
| config | `86746fde4d0e6d377264466262a27b4953206ce5e07441c8b870eee5ca05957f` |
| 模块数 | 2335，保留 split BTF |
| One-KVM | `382efb70e7ebb5e7fb8c9b13f1e6da5a161c84d1` / `72db30c07aa2351a27499e06d2ac28ccde3a74e1cb18d0927766a7ba35d37b0d` |
| manager | `4ea748426935f782cb2bc0a6e724a1e8075c741f` / `3fc215e3de431d1c65e08e62b3179b6329e190d803ab77e89dae3c3d90728eb1` |

保留区沿用厂商地址 `0x07400000–0x074fffff`，与安全固件、CMA、加载区的核对见
[候选记录](2026-10-22-p2-pstore.md)。本轮没有改变其内存布局。
Mac 产物 `build/pstore-deploy/kernel/`；正式部署 bundle `build/pstore-deploy/bundle/`。
仅给原 manifest 补齐源码 tree、11 个模块 build ID，Image/DTB/模块归档未变。

## 工具与部署窗口

final-board.py 增加显式 baseline 身份及同 release 模块目录替换/恢复：
原模块整体移到备份，恢复时不与候选混装；覆盖“移动前、移动后、候选安装后失败”的离线测试。
final-window.py stage 的 `--kernel-only` 只核对用户态文件，不替换或降级它们；
`--verify-pstore` 在回归后写 console 标记、正常重启、读回，再验 HID/manager。
种子或固件流程不在此工具内。pstore 读回失败也走完整自动回退，离线故障注入测试通过。

准备与执行：

```sh
python3 packaging/kernel-edge/final-regression.py prepare \
  --destination build/pstore-deploy/regression --logs logs/pstore-deploy/window \
  --sample-modes 5,7,18
# stage 使用上表三个完整提交、上述 kernel payload 和当前应用二进制，增加：
# --baseline-release 7.3.0-vim4kvm-uhd1+
# --baseline-build-id 3ed254bfa838ab50732fdce1c5134400a1663fd5
# --kernel-only --verify-pstore --bundle build/pstore-deploy/bundle
python3 -u packaging/kernel-edge/final-window.py window \
  --bundle build/pstore-deploy/bundle \
  --backup /var/backups/vim4-edge-pstore-20261022 \
  --logs logs/pstore-deploy/window \
  --archive-remote-to /var/tmp/vim4-deploy-pre-pstore-20261022 --execute
```

stage/dry-run 校验完整模块归档、inventory 和所有 payload 哈希后才连接板子。
execute 自动持 `/tmp/vim4-board.lock`、`/tmp/vim4-heavy.lock`，覆盖备份、安装、
两次正常重启、回归及必要回退；未与 vdec 重型构建同时采样。
`logs/pstore-deploy/locks.txt`、window.log 保存锁和命令；不使用 --wifi-scan。
manager 与 PD 文件和两个持久日志文件共 12 项安装前后哈希核对，不覆盖运行时策略。

备份：板上 `/var/backups/vim4-edge-pstore-20261022`，Mac
`logs/pstore-deploy/window/baseline/`（0700），包括启动文件、完整旧模块、运行时清单、
SQLite 一致快照与应用配置。六个备份文件下载后逐哈希比较，通过才安装。
旧暂存目录移到 `/var/tmp/vim4-deploy-pre-pstore-20261022`，不覆盖旧部署证据。

双端相同的备份 SHA256：

```text
files.tar       1297900b351255c327c687dec8e371de81ca41a7ff78ac7a6c36f07515bda189
modules.tar     1102c32bcb5a06906c12f232bc69c54ee50abfe1037cfe235cb2e086280e2bf8
application.tar 0f636c3810f8eb5558f15dd7a4ff0a79c84e26a530ae6d3051cbf114ba947806
```

## 回归与保留证据

首次启动实际输出 `CRITICAL_HEALTH_VERIFIED f283ab1f…`、`NEW_WARNINGS []`；
running config、Image/DTB、完整模块树及 11 个加载模块 build ID 均匹配，taint=0，
manager 的运行中二进制 SHA 为上表 3fc215e3…，无 failed unit。

| 项目 | 本轮结果 |
|---|---|
| 原始 HDMI 抽样 | 720p50、1366×768、4K60，两帧推进、标记/颜色/步幅及 DMA 回收通过 |
| H.264 往返 | 9 模式正反共 18 次，通过帧推进、颜色、快照与帧率门限 |
| H.265 往返 | 8 模式正反共 16 次通过，未测 1366×768 HEVC |
| 4K60 运动采样 | 各 15 秒、预热 3 秒；H.264 59.98145 fps、H.265 59.98164 fps；dropped/lost/freezes/PLI 增量均 0 |
| 音频 | 同连接 48k→44.1k→48k，各 15 秒，实际 HDMI/ALSA 速率和网页波形检查通过；不推翻历史偶发跳变/长期稳定性边界 |
| HID | 原生 Mac 窗口收到键按下/抬起、绝对/相对鼠标、点击/滚轮；额外重启后再测通过 |
| 虚拟盘 | 主机只读/可写访问，1 MiB 写入 SHA 回读一致、应用重启保留介质、主机 eject 清空 LUN；USB 设置恢复 |
| GPU | Mali-G52/Panfrost，10 秒 304 帧、runtime resume 后 3 秒 91 帧；gl_error=0，观察到 250/400/800 MHz，自动 governor 保留 |
| manager / PD | 初次及额外重启后页面/API 通过，正式版可用且选中，PD 卡存在、390px 无横向溢出、无 pageerror；运行 SHA 保持 3fc215e3… |

第二次启动的 PD 仍是固件超时/Type-C fallback（flags=208、Rp=3A、无本次合同），
开机服务按既有策略跳过；没有冷插拔、重新协商或伪造合同。

在启动 `22208739-c1f3-4fd9-8814-0c35fca867a3` 写入 `<3>` 普通日志标记后正常重启，
新启动 `75e4d1aa-e850-47a8-9e88-5b4cc1ad1050` 实际读回：

```text
PSTORE_READBACK VIM4_PSTORE_DEPLOY_22208739-c1f3-4fd9-8814-0c35fca867a3 {'console-ramoops-0': 31396}
OF: reserved mem: 0x0000000007400000..0x00000000074fffff (1024 KiB) map non-reusable ramoops@7400000
pstore: Registered ramoops as persistent store backend
ramoops: using 0x100000@0x7400000, ecc: 0
/sys/fs/pstore none pstore rw,nosuid,nodev,noexec,relatime
```

验证期间临时 mask systemd-pstore，防止它抢先移走 sysfs 条目；读回后撤销 mask 并启动
标准归档服务。最终 pstore 仍挂载，console 已归档到 `/var/lib/systemd/pstore/console-ramoops-0`；
另存板端 `/var/tmp/vim4-deploy-7.3-final/pstore-readback/` 与 Mac
`logs/pstore-deploy/console-ramoops-0`。归档目录里原有 Oct 20 的 dmesg-ramoops 文件不是本轮 panic 证据。

最终健康项中，模块 build ID、manager、failed units、taint、hwrng、IR 键表、自动风扇、
GPU governor、PD 均通过；**new_warnings 未通过**，第二次启动多出：

```text
[6.509976] meson-saradc fe026000.adc: failed to read sample for channel 2: -110
```

没有据此推断是 pstore 导致，也没有修改 ADC 驱动或触发额外复位；板载 ADC 按键未做物理验收。
工具按既有关键项策略保留部署，九类回归结果均 passed，最终 taint=0、服务 active、UDC configured。
此次启动无扫描操作，不能据没有 MMC 扫描警告宣称旧问题已修复。

持久 journal 的上一启动可读，最终占 87.3 MiB，有效上限 256 MiB；rsyslog 保持 mask。
12 项保留文件逐哈希核对通过，runtime-build.json 登记新内核、当前应用提交、哈希和备份位置。
最后输出：

```text
CRITICAL_HEALTH_VERIFIED f283ab1f8a001a19bab5247afc4f9b0c00c1da99
UBOOT_UNCHANGED 751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0
DEPLOYMENT_RETAINED {"kernel":"1262da082ba528be27c17adc62a92d90ed18b158", ...}
SUCCESS: final deployment retained; no baseline reboot
```

证据：`logs/pstore-deploy/window.log`、window/regression-results.json、window/health.json、
各分类日志/manager 截图/串口日志、final-readonly.log。sources.toml 的 kernel revision/tree
及 tested_build 全部产物身份已更新；workspace.toml 的应用锁不变。
主仓离线测试 178 项、5 skipped、OK，见 root-tests.log；没有提交 vdec 会话文件。

## 回退到本轮开始时的内核

先确认板上仍为本次部署、备份仍匹配当前应用数据，再执行；这会恢复部署前的
Image/DTB、模块、清单和应用配置快照，晚于该快照的配置修改应先另行备份。
manager 4ea7484、PD 文件和持久 journal 不属于本轮替换项。

```sh
python3 packaging/kernel-edge/final-window.py rollback \
  --bundle build/pstore-deploy/bundle \
  --backup /var/backups/vim4-edge-pstore-20261022 \
  --logs logs/pstore-deploy/rollback --execute
```

入口自动持双锁，正常重启并核对 `3ed254bfa838ab50732fdce1c5134400a1663fd5`、
完整文件/模块树和服务；之后仍应运行实际 HID。日志目录必须新建。
不要复用旧 rc7 回退目录，也不要刷 U-Boot、改分区或替换 `/lib` 链接。
本轮未验证断电或 panic 日志，只验证正常重启 console；不触发 echo c、系统挂起或非对齐 HEVC。
