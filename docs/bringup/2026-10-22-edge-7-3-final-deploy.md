# 2026-10-22：v7.3 正式部署尝试与自动回退

本轮按用户第二轮授权执行，成功后保留正式版，仅启动、网络、HID、HDMI 采集关键项
失败时恢复 rc7。全程双锁；不刷 U-Boot、不操作 Wi-Fi/P2P，不提交、推送或合并功能分支。
候选曾成功启动，19/19 原始模式通过，但恢复默认 EDID 后检查器立即读到 link_ready=0，
触发自动回退。已确认恢复 rc7 build ID 52d5e46…、原应用/运行时、完整模块及 active 服务。
正式版没有保留，发布锁和“当前部署”继续指向旧基线；不能把这轮写成完整验收通过。
后续第三轮使用同批产物与修正检查器重新部署并保留，见
[第三轮记录](2026-10-22-edge-7-3-final-retained.md)；本条保留第二轮当时的结论。

## 源码与产物

| 组件 | 分支 / 完整提交 |
|---|---|
| Linux | vim4-kvm-7.3 / `e0346697f25035c7eaa77fa44641a54d6e31e327` |
| One-KVM | vim4-hdmirx-audio / `382efb70e7ebb5e7fb8c9b13f1e6da5a161c84d1` |
| manager | deploy-7.3-final / `7a69cedb6d5263dfb2a348708b07928986975d43` |

Linux tree 为 `cd948a7dea18fa4ef124512b3981a650af6e4699`，上游 v7.3 解引用提交
`c03c1a14507dfaf8b856c2608f9ac216021fc222`。主工作树未改动；VM 独立 detached 工作树
`~/src/linux-7.3-deploy` 与 `O=~/build/kernel-7.3-deploy-final`，未创建另一条正式版分支。
使用 uhd1.config、GCC 13.3、8 个并行任务，同次完成 Image/dtbs/全部 2335 个模块，
保留 split BTF；编译日志未发现 warning/error。使用 audio-test DTB，保留既有以太网 MAC
`c8:63:14:74:70:0d`。内核 build ID 为 `3ed254bfa838ab50732fdce1c5134400a1663fd5`。

| 本次候选产物（安装后已回退） | SHA256 |
|---|---|
| Image | `47c53206718adeaa81961c10d589f3e7cbc40fa6c075fbd4d854918a78df7bc7` |
| vim4.dtb | `8cd68e30d5c7adf4fa063ae9c2ab9561912c46133ce24f1637fd36d14a2d95d8` |
| modules.tar.gz | `1bfe777105521c9d6bc8a945b03638b60520f01c2b3c6602048e0b8e7ac1f876` |
| 最终 .config | `64df2a7789045390e22f06175f084913a4dd0873c75e152cf05ae6ba4c7232ba` |
| One-KVM | `72db30c07aa2351a27499e06d2ac28ccde3a74e1cb18d0927766a7ba35d37b0d` |
| manager | `ad7b8aa3e068cb4f5e4ef8e8c2fb6df623c791a1c4ed82949e616cd6fd01f67c` |

One-KVM 使用独立 `build/deploy-7.3-final/One-KVM`，容器 vim4-deploy-final-build，
独立 target volume；前端 npm ci/build 后重新 cargo build --locked --release --features vim4。
release 构建成功，19 条既有 Rust 警告；DMA allocator 的实际 C 测试通过，产物与板上
库同为 `7aaf2373e9d47b581181b3b019c7217c605b7aee52d009e39299a7ca6af3a82d`，无需替换。
manager 使用上一轮已经核对的干净 release 产物，Go 内嵌 revision 匹配、vcs.modified=false；
测试与构建范围见 [离线准备](2026-10-22-deploy-7-3-final-prep.md)。

## 构建、暂存与单次上板窗口

内核构建使用 `build/deploy-7.3-final/recipe/` 的配方副本，revision 指向批准的 HEAD；
不提前把主仓 tested_build 改成未经上板的产物。重型构建和打包在 Mac heavy 锁内执行：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build bash \
  /home/deepdream/build/deploy-final-recipe/build.sh \
  /home/deepdream/src/linux-7.3-deploy /home/deepdream/build/kernel-7.3-deploy-final \
  /home/deepdream/build/deploy-final-recipe/uhd1.config
```

package-final.py 消费同次 O= 目录，modules_install/strip/depmod 后生成完整清单及登记证明。
最终 Mac bundle 为 `build/deploy-7.3-final/bundle`；stage 与 dry-run 的实际输出：

```text
STAGED build/deploy-7.3-final/bundle
OFFLINE_BUNDLE_VERIFIED
DRY_RUN: no SSH, no locks, no builds, no board writes
```

执行命令（入口自动在整个窗口嵌套持有两把 lockf，锁证据保存为 locks.txt）：

```sh
python3 -u packaging/kernel-edge/final-window.py window \
  --bundle build/deploy-7.3-final/bundle \
  --backup /var/backups/vim4-deploy-7_3-final-20261022 \
  --logs logs/kernel-edge/deploy-7.3-final --execute \
  > logs/kernel-edge/deploy-7.3-final-window.log 2>&1
```

板上备份：`/var/backups/vim4-deploy-7_3-final-20261022`。
Mac 备份：`logs/kernel-edge/deploy-7.3-final/baseline/`（目录权限 0700）。
files.tar 含启动文件、内核登记清单、两个应用和被替换运行时；modules.tar 含完整 rc7 模块；
application.tar 用 SQLite backup API 保存一致数据库，并保留 MCP/UU 配置。
不复制、删除或改写已有虚拟盘镜像。state.json 保存原文件/模块/链接/启动参数和固件 SHA；
附原 dmesg/err,warn 清单。每个文件在安装前已经下载到 Mac 并逐项比对板上 SHA。

| Mac 与板上相同的备份 | SHA256 |
|---|---|
| files.tar | `4eae729c81aa84ae59fab3e3b8797cee820643195693984e639894d331d15055` |
| modules.tar | `86a081c16bad47ac1331b957e5c63cad7f0311ad68258685713c07f771f62648` |
| application.tar | `e5b6e9f451b4b03f003587e107f96d80415d465b192b8b783c8a79d9a336ab3a` |

保留 Stock/5.15、旧 rc7 模块及现有启动文件链接。备份完成后才安装，更新整个模块目录及
Image/DTB，登记 FullKvm，再正常重启。未在更新阶段启动或重启 PD。

## 回归证据

首次启动输出：

```text
running
CRITICAL_HEALTH_VERIFIED 3ed254bfa838ab50732fdce1c5134400a1663fd5
NEW_WARNINGS []
PD bootstrap skipped: firmware timeout or Type-C fallback
```

正在运行的 .config、全部模块文件、11 个加载模块 build ID、One-KVM 与 manager 的
/proc/PID/exe SHA 均核对成功。hwrng 为 fe440788.rng，读出 32 字节；IR 默认为
rc-khadas、NEC；风扇首次 sensor_fault=0、13%、49°C；taint=0，无失败 systemd unit。
HID configured，HDMI link_ready=1、VDIN faulted/stream_error=0。

19 种模式均完成每种两帧推进、stride/颜色、无 VDIN fault 及采集停止后 DMA 回收，
`video/raw-modes.jsonl` 的 passed ID 完整覆盖 0–18。随后夹具恢复默认 EDID、重启应用，
紧接着的 verify 没有等待源端重新锁定，只读一次状态就把过渡期当成关键失败：

```text
REGRESSION_PASSED hdmi-modes
AssertionError: port: 1
source_5v: 1
link_ready: 0
width: 3840
height: 2160
phy_pll_locked: 1
RESTORED_REBOOT_REQUIRED
running
BASELINE_RESTORED 52d5e46fb006230785110a1fa5ba0dd1383b732f
```

这证明检查器缺少恢复等待；因为随后立即回退，未观察此候选是否能在限时内重新锁定，
不能断言只是误报，也不能据此判定内核存在持久采集回归。按关键项失败约定，本轮不再开
第二个安装窗口。H.264/H.265 往返、4K60 帧率、48→44.1→48kHz 网页播放、实际 HID、
虚拟盘、GPU 负载/恢复、manager 内核/PD 页面均未执行，不能引用历史结果冒充本轮通过。

后续只做离线修复：final-board.py 对 HDMI/VDIN 状态最多等待 35 秒，保留最后失败状态；
持续丢链/采集故障仍失败。新增测试用受控时钟覆盖两次 link_ready=0 后恢复、持久丢链和
VDIN fault 超时；部署器同时在后置检查前写入已经完成的回归结果，避免本轮成功项记录缺失。
本轮原始 bundle/远端 helper 保留事故时版本；离线修正版未重新 stage 或上板验证。

启动健康证据：`startup-health.json`、`startup-warnings.txt`，新增 err/warn 为零；
原基线的 CRG 正常回调和风扇首次缺温区告警从启动 warn 清单中消失。
完整窗口、失败状态及恢复日志分别为 `logs/kernel-edge/deploy-7.3-final-window.log`、
`failure-board.log`、`restored-proof.log`，UART 包含候选和恢复两次启动。

恢复后再次只读核对：

```text
7.3.0-rc7-vim4kvm-uhd1+
one-kvm / vim4-manager / vim4-kvm-pd: active / active / active
UDC: configured; taint: 0
One-KVM SHA256: 3d0062dd22de50cfdcf7c205c5538102eb07c0504e38fb1724da80f3b0ed1d84
manager SHA256: 4494f89ce85ef8da13c6dd07b7aca0e9d397aba054b594357b920ab1107ffea7
```

verify-restore 已逐项比较旧 Image/DTB/运行时/应用 SHA、全部 rc7 模块、链接、启动参数与
5.15 保护文件。恢复前后 U-Boot FIP 区间 SHA 均为
`751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0`，没有刷写固件。
PD 新脚本在候选启动时正确跳过超时回退快照；恢复后的旧运行时仍打印 inherited from U-Boot。
本轮没有实际触发缺 USB comm 位时的协商修复，没有测试冷插拔或新合同。

## 恢复方法与边界

仅关键项失败时自动恢复备份、重启，核对原 rc7 build ID 52d5e46…、文件/模块/链接和
应用 active。其余失败写入 regression-results.json 或 health.json，保留正式版。
脚本离线测试覆盖关键失败回退顺序、音频/GPU/页面等失败仍继续检查并保留。
手工恢复入口（仅需要恢复时使用，自动重新获取双锁）：

```sh
python3 packaging/kernel-edge/final-window.py rollback \
  --bundle build/deploy-7.3-final/bundle \
  --backup /var/backups/vim4-deploy-7_3-final-20261022 \
  --logs logs/kernel-edge/deploy-7.3-final-rollback --execute
```

SSH 无法返回时脚本明确记录 RECOVERY_NOT_VERIFIED，串口日志保留，不能声称已自动恢复。
不改动 U-Boot，也不为验证 PD 修复拔插线；已有音频 32kHz 短窗、48kHz 偶发跳变及
格式切换竞态 -EAGAIN 仍按 [音频记录](2026-10-22-edge-hdmi-audio.md) 保留限制。

再次部署须重新 stage 修正版，保留现有 backup/日志及事故 bundle；本轮远端目录已存在，
入口会拒绝直接覆盖。先在新的双锁窗口内归档该暂存目录，再选择新的 backup/logs 路径。
主仓 sources.toml/workspace.toml 不更新至未验收提交，没有提交、推送或合并操作。

离线修正后执行 `python3 -m unittest discover -s tests -p 'test_*.py'`：
共 163 项：158 通过，5 项环境跳过；含恢复等待、结果保留和事务回退边界。
日志：`build/deploy-7.3-final/main-tests-after-window.log`。
