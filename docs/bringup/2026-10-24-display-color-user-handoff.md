# 2026-10-24：颜色候选交付门禁失败，恢复基线并保留管理器预览

接线固定为 HDMI IN 接 Mac mini、HDMI OUT 接真实4K显示器，没有要求用户插拔。
`vim4-display-color@c24465df` 一次性启动成功，但刚开始 H.265 4K60 采集即出现
ERROR buffer，按用户要求立即重启回基线，**没有将候选留给用户实测**。
manager 预览版独立保留。此前颜色实现及矩阵见 [自环记录](2026-10-24-display-color-loop.md)。

## 版本与安全边界

| 项目 | 版本 |
|---|---|
| 候选源码 | `c24465df1dd70525a73557d26889e5ce15c35feb` |
| 候选 build ID | `35d54c1c03846949e84e0b88b097ea5086535704` |
| Image SHA256 | `d47b42f0ecd4926fcd13f02bda7d0bb3595b27d0f01d68ba614281fbbad5cb5d` |
| 默认、最终运行 build ID | `eeddb005df059a850853876d52ef603aa1af192b` |
| manager 源码 | `passthrough-ui@974ab40` |
| 新 manager 包 | `2.5.1+vim4.20261018.44.dev.3.g974ab40` |
| 原 manager 包 | `2.5.1+vim4.20261018.44.dev.2.gb1e49a8` |

持有 `/usr/bin/lockf /tmp/vim4-board.lock` 与 `/tmp/vim4-heavy.lock` 完成窗口；
构建先于性能测量。选择颜色分支 HEAD，因为末尾 bus format 提交已通过离线协商测试，
未改变矩阵系数与 TX 写入；本次实际启动 HEAD，不能借此前提交的颜色样本宣称长测通过。
使用 display-once prepare/stage、RAM sysboot，未 saveenv、未切换默认项、未合入正式分支。
窗口前后 Image、DTB、extlinux、uEnv、内核/runtime 登记文件和 One-KVM 二进制哈希相同。

候选 panic=20、panic_on_oops=1、PID1 watchdog=30s；未设置自动回基线定时器。
故障守卫每200ms检查 ERROR/失锁/error stop/fault，到期只退出，不因时间到而重启。
返回后 watchdog=30s、panic=20，原基线 panic_on_oops=0 仅在本次运行设为1，未改持久配置。
最终无本任务回退 timer 或运行中的守卫，重启仍进入原默认基线。

## 候选门禁与基线恢复

| 检查 | 候选 | 返回基线后 |
|---|---|---|
| One-KVM / manager | active / active | active / active |
| UDC | configured | configured |
| 真实 HID | 门禁失败提前中止，未执行 | 键盘、绝对/相对鼠标、点击、滚轮通过 |
| Mac 输入 | 3840×2160p60，RX AVI VIC97 | 同一接线、同一输入时序 |
| VDIN ERROR | invalid_frames 0→6，拒绝时 stream_frames=15 | 短测期间 0→3084，仍不合格 |
| RX 锁定 | 守卫采样均 link_ready=1 | 测前、测后 link_ready=1，未做连续锁定统计 |
| H.265 | 启动即中止，5分钟未完成 | 仅做60秒恢复检查，3840×2160，60.009 fps |
| 浏览器丢帧 / 丢包 / freeze | 无有效持续统计 | 本次测量增量 0 / 0 / 0 |

驱动 `t7_vdin_thread()` 的 EAGAIN 会递增 invalid_frames，随后发布
`VB2_BUF_STATE_ERROR`。守卫观察到采集活动的两个采样相隔约0.201s，后一采样即有6个错误；
写证据、sync 后立即重启。不能用浏览器持续60fps掩盖原始采集错误。
基线本次同样出现 ERROR，不能证明显示改动是原因，也不能称基线采集稳定性通过；
未做因果定位或 bisect，后续调查见 [透传前置稳定性](2026-10-24-hdmi-passthrough.md)。

候选 boot ID `9d95964c-f7fc-4b0d-a659-222b6a50f4b0`，返回后
`f3a13424-5f39-45f8-b556-cf3a35642d4c`。基线 taint=0、无 failed unit，dpkg audit 清洁。

## HDMI OUT 证据范围

KMS dumb 图案包括黑白、灰阶、RGBCMY、75% bars、近黑近白。
CTA 3840×2160p60/594MHz 下，TX active=3840×2160，CSC0/1=`00/00`，
input mask=`2a`、output map=`0440`；AVI packet
`82 02 0d 4c 12 a8 08 61 00 00 00 00 00 00 00 00 00`
声明 RGB、BT.709、Q=full、VIC97，packet enable=`e0`，SCDC config/status=`03/0f`。
这符合 RGB full 的 POST2 输出域与 TX CSC bypass 合同，本次未另读 POST2 系数表。

EDID 首选详细时序是 3840×2160、533.120MHz、约59.982Hz，随后按 DRM preferred 标志
设置成功（fb61、pitch15360）。该模式寄存器读取过早，捕获 modeset 中间状态：packet
尚未启用、VIC仍为旧值。因此不能当作首选模式最终 AVI/链路验证；故障后未重启候选补测。
没有用户物理颜色确认或本次原始帧颜色验收，当前基线画面不属于颜色候选实测。

## manager 安装、页面与回退

构建 manager 单组件包，隔离验证的 checksum、ELF/依赖、sudoers、配置保留、损坏文件
拒绝、更新 feed 均通过。标准版本分配到 dev.3，确保高于已安装 dev.2。
部署前用 dpkg-repack 重建旧包，另备份 manager 配置/状态，未更改密码。
安装及启动成功；board.py 的部署尾部检查因默认预期5.15而返回失败，显式
`--kernel 7.3.0-vim4kvm-uhd1+` 重跑检查通过，不属于包安装失败。

浏览器验证未登录状态401、登录成功，概览、应用、介质、磁盘、存储、采集、HDMI输出、
散热、网络、服务、更新、账户共12页无 JS 异常。候选和恢复后的基线上均检查输出页：
「当前内核不支持」，API supported=false、state=unsupported，符合透传尚未实现的预期。
用户当前可在管理面板检查这些页面。

板上 `/var/backups/vim4-display-user-20261024/` 保存 `manager-before.deb`、
`manager-state-before.tar.gz` 和 `rollback-manager.sh`。旧包 SHA256 为
`b6af3fb5270bb9b0401872f06dea5add7419ded21be00dbcdbfddc15bf480b38`。
回退脚本验证包 SHA、持有 manager 锁、停服务、安装旧包、重启服务；保留当前配置。
本地及板上 bash -n、备份包版本/SHA检查通过，未实际执行降级。

```sh
ssh vim4
sudo bash /var/backups/vim4-display-user-20261024/rollback-manager.sh
```

内核已回基线；一次性候选正常回退命令为 `sudo reboot`，无需更改启动项。
日志在 `logs/display/user-handoff/`：candidate-entry/rejected JSON、guard-samples.jsonl、
candidate-journal.log、output/preferred-status.txt、before/after-health.json、manager-verify.log、
manager-live-final.log、baseline-hid.log、baseline-h265.log、baseline-recovery-after.txt。
登录状态备份仅作本地恢复，不提交或公开。
