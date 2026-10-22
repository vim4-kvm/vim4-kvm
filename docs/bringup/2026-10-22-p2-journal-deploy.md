# 2026-10-22：P2 有界持久 journal 部署并保留

结论：通过仓库 `board/` 安装入口部署 persistent journal，正常重启后能读回上一启动。
rsyslog 已停用并 mask，旧文本日志保留。**本项是用户批准保留的长期配置**，
不随 ramoops 候选内核回退；内核、应用、U-Boot 仍按指定基线管理。

## 消费者核对与实现

对主仓库 board/tools/packaging/tests/docs 和 workspace 中各应用源码、部署文件做
`/var/log/syslog|/var/log/kern.log|rsyslog` 精确检索，再扩大为 syslog。
未发现必须消费这两个文本文件或 rsyslog 的服务/工具；未改应用子仓库。
PiKVM `kvmd/deploy/vim4/nginx.conf` 使用 `syslog:server=unix:/dev/log`，
该 socket 由 journald 提供，重启后 `logger` 写入/读取实测通过。
其他命中是提案、TODO、第三方 Go syslog API 或内核网络日志配置，并非文件消费。
原始检索：`logs/p2-round2/log-consumers.txt`、`log-consumers-broad.txt`。

板上 rsyslog 配置还加载 imklog，直接读取内核消息。因此选择**停用 rsyslog**，
不另改发行版 `ForwardToSyslog=yes`：仅关 journal 转发仍不能消除 imklog 的重复写入。
mask 防止 syslog socket 或手工依赖重新激活；`/dev/log` 继续由 journal 接收。
没有删除 `/var/log/syslog`、`kern.log`、auth.log 等历史文件。

可复现入口：

- [60-vim4-journal.conf](../../board/60-vim4-journal.conf)：安装到 `/usr/lib/systemd/journald.conf.d/`。
- [vim4-logging](../../board/vim4-logging)：安装为 `/usr/libexec/vim4-logging`，停用/mask rsyslog，
  live 系统重启 journald 并 flush/sync；镜像 chroot 只配置后续启动策略。
- [install-logging.sh](../../board/install-logging.sh)：单独安装本项；完整 `board/install.sh` 也调用。
- [组件打包](../../packaging/ubuntu/package.py) 的 board payload 和 postinst 调用同一 helper。

配置为 `Storage=persistent`、压缩、`SystemMaxUse=256M`、`SystemKeepFree=1G`、
`SystemMaxFileSize=32M`、`MaxRetentionSec=7day`、`RuntimeMaxUse=32M`、`SyncIntervalSec=5m`。
依据[第一轮预算](2026-10-22-p2-persistent-logs.md#写入量估算与容量)：1 条/秒约 84 MiB/日，
256 MiB 约留 3 天；活跃测试窗口 5.71 条/秒约留半天。7 天是期限上限，不保证保存时长。
五分钟同步降低同步频率；突然断电仍可能丢最后一段。存量上限不限制累计 eMMC 写入。

## 上板命令与实际证据

`/usr/bin/lockf /tmp/vim4-board.lock python3 -u build/p2-round2/logging-window.py`
全程持锁。脚本复制三个 board 文件到 `/var/tmp/vim4-p2-logging`，执行
`sudo sh /var/tmp/vim4-p2-logging/install-logging.sh`，写 journal 标记、正常重启并核验。
备份/初始服务状态：`/var/backups/vim4-p2-logging-20261022/`。
第一次准备因误用 VM 用户名 chown 失败，仅创建空目录；改为远程 `id -un` 后完成部署。
完整日志 `logs/p2-round2/logging-deploy.log`：

```text
 -1 a1e99c9ae1ae483dad3b3af0fd06e664 ... 14:15:51 UTC ... 14:50:29 UTC
  0 ba80561be77f4e8bb0e67ba7be579f88 ... 14:50:44 UTC ... 14:50:54 UTC
Oct 22 14:50:26 ... vim4-p2-journal: persistent-before-reboot-20261022
System Journal (...) is 25.8M, max 256.0M, 230.1M free.
Runtime Journal (...) is 4.0M, max 32.0M, 28.0M free.
Archived and active journals take up 28.2M in the file system.
masked
Oct 22 14:50:54 ... vim4-p2-journal: dev-log-still-works
active
active
configured
7.3.0-vim4kvm-uhd1+
```

`journalctl -b -1 -t vim4-p2-journal` 成功读回标记；legacy-sizes.txt 与
legacy-sizes-after.txt diff 为空，syslog/kern.log 重启前后没有增加。
ramoops 窗口结束后再次核对，journal 占用 57.0 MiB、有效上限仍为 256 MiB，
rsyslog masked/inactive；两个旧文件仍为 115074703 / 17339575 字节，与部署时相同。
最终只读证据 `logs/p2-round2/logging-final-readonly.log`。
这证明 journal 的有效上限被采用，未用大量日志灌满磁盘验证轮转边界；没有 24 小时
写放大或 eMMC 寿命测量。服务检查为 one-kvm、vim4-manager；实际 HID 与内核身份的
最终复核见 [ramoops 记录](2026-10-22-p2-pstore.md)。

离线 shell 语法、board 包 payload/权限/postinst 组装检查通过；未构建完整 Ubuntu 镜像。
主仓库测试 `python3 -m unittest discover -s tests -p 'test_*.py'`：163 项、5 skipped、OK。

## 回退命令（未执行）

原 rsyslog 为 enabled/active，两个新增目标文件原先不存在。持板锁执行以下命令，
只移除本项策略；不要覆盖整个 journald.conf 或删除历史 journal：

```sh
sudo rm /usr/lib/systemd/journald.conf.d/60-vim4-journal.conf
sudo rm /usr/libexec/vim4-logging
sudo systemctl unmask rsyslog.service
sudo systemctl enable --now rsyslog.service
sudo systemctl restart systemd-journald.service
sudo journalctl --flush
sudo systemd-analyze cat-config systemd/journald.conf
sudo systemctl is-active rsyslog one-kvm vim4-manager
```

原 `/etc/systemd/journald.conf` 中 Storage=volatile 会重新生效；历史 `/var/log/journal`
不会自动删除。若未来发布含本策略的 board 包，回退也应回退包/源码，避免下一次安装重新应用。
