# 2026-10-22：P2 持久日志与 ramoops 方案

第二轮已授权实施：[持久 journal 部署](2026-10-22-p2-journal-deploy.md)、
[ramoops 候选验证](2026-10-22-p2-pstore.md)。以下为第一轮方案与当时状态。

结论：建议后续评估“小容量 persistent journal＋消除重复 syslog”的组合，
以启动历史和服务故障诊断为主；ramoops 可补充崩溃末尾内核日志，但当前 7.3
配置未启用、尚无验证过的跨重启保留区域。本轮只写方案，**没有修改板子日志配置、
加载模块、部署 DTB、写 /dev/kmsg、触发 panic 或做 pstore 重启试验**。

## 当前状态与观测范围

Linux `e0346697f2503`、build ID `3ed254bfa838ab50732fdce1c5134400a1663fd5`，
systemd `255 (255.4-1ubuntu8.18)`。只读入口：

```sh
ssh vim4 'journalctl --disk-usage; systemd-analyze cat-config systemd/journald.conf;
  systemctl is-active rsyslog systemd-pstore; df -h /var/log;
  sudo stat -c "%n %s" /var/log/syslog /var/log/kern.log'
```

实际 journald `Storage=volatile`、`Compress=yes`、限流 10000/30s，runtime journal
占 8 MiB；发行版 drop-in 又配置 `ForwardToSyslog=yes`。
rsyslog **active**，当次 `/var/log/syslog=114138430` 字节、`kern.log=17339283` 字节。
因此 volatile journal 不等于日志不写 eMMC；贸然打开 persistent 可能重复存同一批消息。
`/var/log` 位于 eMMC 根文件系统，约 7.7 GiB 可用；systemd-pstore inactive，
`CONFIG_PSTORE` 未设置。文件现有大小不代表日写入量。

重启后剔除首分钟的一次 279.14 秒只读统计：1594 条、MESSAGE 文本 537248 字节，
约 5.71 条/秒、1925 B/s。含本轮 SSH 查询、应用和并行任务活动，**不是静置基线**，
不推导长期平均或 eMMC 耐久度。journal 按块预分配，不能拿 8 MiB 除以 uptime 当写入率。
原始聚合值在 `logs/p2-20261022/log-rate.json`，配置/磁盘快照在 `logging-readonly.txt`。

## 写入量估算与容量

下面是预算场景，假设每条消息含 journal 字段/索引后平均产生 1 KiB 逻辑数据；
压缩、去重、metadata、同步频度、ext4 与 FTL 会改变实际值，不是板上 NAND 测量：

| 场景 | 日 journal 逻辑数据 | 假设总放大 2–4 倍时的物理写入预算 |
|---|---:|---:|
| 0.1 条/秒 | 8.44 MiB | 16.9–33.8 MiB/日 |
| 1 条/秒 | 84.4 MiB | 169–338 MiB/日 |
| 10 条/秒 | 843.8 MiB | 1.65–3.30 GiB/日 |
| 本轮活跃窗口 5.71 条/秒 | 约 482 MiB | 约 0.94–1.88 GiB/日 |

本轮纯 MESSAGE 文本外推约 159 MiB/日，与完整 journal 存储量不同。
真实放大系数未知，2–4 倍仅作敏感性预算；不能据此承诺 eMMC 使用寿命。
若持续 1 条/秒，逻辑量约 30 GiB/年；10 条/秒约 301 GiB/年，还没计其他应用写盘。
存量上限只控制占用，**不限制累计写入**；轮转会持续替换历史。

可供后续评审的配置（未写入板子）：

```ini
[Journal]
Storage=persistent
Compress=yes
SystemMaxUse=256M
SystemKeepFree=1G
SystemMaxFileSize=32M
MaxRetentionSec=7day
RuntimeMaxUse=32M
SyncIntervalSec=5m
```

限流先保留现值，按具体噪声服务调整；全局过严会丢掉崩溃前上下文。
256 MiB 在 1 条/秒场景约保留 3 天，本轮活跃率仅约半天；7day 是最长保留时间，不保证
一定有 7 天历史。大小限制按活动/归档文件与轮转粒度生效，不是文件系统硬配额。
默认五分钟同步节约同步频度，但骤断电/死机可能丢最后一段；严重等级触发同步也不能
保证已失效的存储/内核写出。语义依据
[systemd journald.conf](https://www.freedesktop.org/software/systemd/man/latest/journald.conf.html)，
部署前再以板上 systemd 255 手册和有效 drop-in 复核。

启用前应先清点 rsyslog/监控对文本文件的消费，避免同时保留两份重复内核和服务日志。
这里不建议直接停 rsyslog；是否取消 ForwardToSyslog 或保留特定 facility 需依真实消费者决定。
测量计划是固定负载 24 小时，记录 journal 逻辑增量、journald/rsyslog 进程 I/O、
mmcblk0 sectors-written 差值和其他写盘进程；块设备总量只能给系统级写入，不能全归因日志。

## 诊断收益与替代方案

| 方案 | 主要收益 | 限制 / 成本 |
|---|---|---|
| persistent journal | 跨正常重启保留 boot ID、unit、单调时钟和 kernel/user 日志，便于查前次启动和服务崩溃 | 增加 eMMC 写入；硬锁死、突然断电、存储故障末尾可能丢；注意日志中的凭据/私人信息与读权限 |
| 现有 volatile＋rsyslog | 已有文本日志持续写盘，可先治理噪声和轮转 | journal 的结构化前次启动历史丢失；文本可能重复，仍有 eMMC 成本 |
| 远端日志 / 串口 | 远端保存，降低本地持久写入；串口可覆盖网络不可用时的 printk | 依赖接收机、网络或串口；断链后缺失，串口过量打印也会扰动时序 |
| pstore/ramoops | RAM 中保存 console/oops/panic 尾部，正常工作时无需持续 eMMC 写入，下一启动导出 | 要求保留内存跨重启不被固件覆盖；掉电通常丢；容量小，不能代替完整用户态日志 |
| netconsole | 将内核消息发到外部接收机，不要求落盘 | 仅内核、依赖网卡和传输路径；网卡/DMA/网络故障可能同时失去日志 |

## 7.3 ramoops 可行性与未做候选的原因

源码已有 `fs/pstore/ram.c`、`ram_core.c`、reserved-memory/ramoops binding，
不需要移植驱动。内核候选至少需要 `CONFIG_PSTORE=y`、`CONFIG_PSTORE_RAM=y`、
`CONFIG_PSTORE_CONSOLE=y`；早期注册比模块方式更有利于保留启动上下文。
DT 需要明确的物理保留区，不能只打开配置或随意指定一个“看起来空闲”的地址。

当前 DT 保留 BL31 `0x05000000–0x052fffff`、BL32 `0x05300000–0x072fffff`，
还有动态 PCIe restricted DMA pool；启动参数指定 512 MiB CMA，内核/U-Boot 的
Image、FDT、加载缓冲及 relocation 也会占 RAM。需同时审核 Linux memblock、U-Boot
加载/清零范围、BL2 DDR 初始化与复位后保留行为。本轮只读 /proc/iomem 不足以证明
任何选定区域能跨固件重启保留，故没有制造一个未经依据的固定地址 DTS 候选。

后续可以从 2 MiB 保留区预算开始：console 512 KiB，剩余用于 256 KiB dmesg records，
暂不启用 ftrace/pmsg；具体物理地址待上述审核确定。按 7.3 ramoops 文档保留默认
mem-type=0，不能随意换为 ARM 上可能不适合原子操作的强序映射。
ECC 是可选纠错，不保证断电/固件清零后还能恢复。

若另行实现并验证候选，安全验证路线是：

1. 独立内核 worktree/O= 构建匹配 Image、完整模块和带保留区的 DTB，保存基线。
2. 持 board/heavy 双锁，临时安装；核对 memblock 保留区、ramoops 注册和 HID。
3. 通过 `/dev/kmsg` 写唯一标记，然后正常重启，读回 `console-ramoops-*`。
   要验证的是 PSTORE_CONSOLE；仅写 dmesg 再普通重启不保证产生默认只针对 oops/panic
   的 dmesg-ramoops record。禁止 `echo c`、故意 Oops 或 watchdog 挂死。
4. 检查 systemd-pstore 是否已把内容移到 `/var/lib/systemd/pstore`；空 /sys/fs/pstore
   不能单独判失败。记录标记、boot ID、内存范围后恢复原 Image/DTB/模块与配置。

这一路线只能证明该次正常重启的保留与读回，不能证明 panic、安全复位、断电或全部
固件路径。当前没有执行步骤 1–4，最终仍运行指定 7.3 基线；收尾证据见
[P2 基线核对](2026-10-22-p2-kaslr.md#基线恢复与范围)。
