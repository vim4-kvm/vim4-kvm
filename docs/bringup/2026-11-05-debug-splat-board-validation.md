# 2026-11-05：启动修复实板复验与生产吞吐准备

调试 `.81` 因新的 ADLA mutex lockdep 报告和随后 cold_boot 首错停止，没有完成零告警验收。
已恢复正式 `.3`，完整身份和 4K 视频通过。生产 `.82` 已封存，但根分区剩余空间不足，
等待协调清理其他已结束候选后再执行 600 秒吞吐测试，不把未运行写成通过。

后续协调者已清理旧候选；ADLA 宏修复及新 `.83/.84` 验证见
[后续记录](2026-11-05-adla-mutex-pd-timing.md)。本页保留首次窗口的历史结果。

## 来源与离线准备

内核工作树 `linux-7.3-debug-splat-fixes`，干净提交
`f911e1d8817fb1ebab4acf94ed96ddf9404e193c`，tree
`dc28148a192ecc497deeb4280ebb1d1618f7c71f`。部署基线 `2662456a1a636` 后恰好五个提交：

- `17d29954473b6`：移植上游 brcmfmac 有界注释解析，保留作者、签署和 Link。
- `496597ebdf195`：真实解析器 KUnit，arm64 QEMU + KASAN 3/3。
- `4c4126df2f8a`：ADLA 按现有 DMA 上限分 SG，不放大上限。
- `0a35577b8de2`：PWM 每 chip 独立 key，arm64 QEMU 锁依赖回归 1/1；同 chip ABBA 保留。
- `f911e1d8817fb`：MMC sync/unmap/完成恢复到 IRQ 线程，SDIO 短寄存器锁改 raw。

前四项的根因、来源及静态验证见[原记录](2026-11-05-debug-splat-fixes.md)，
MMC 的上游核对、真实 RT 根因和逐项离线检查见后续记录。
本轮未更改上述代码，没有合入解码分支或 HEVC 草稿。

两个候选分别持 heavy 票全量构建 Image、DT、2338 树内和 3 外部模块，独立封包。
调试配置保留 KASAN、DMA_API_DEBUG、PROVE_LOCKING、PROVE_RAW_LOCK_NESTING；
生产配置摘要等于仓库正式配置。两个 RAM 包均在本机通过来源 SHA 和逐文件 validate_bundle。

| 身份 | 调试 A | 生产 B |
|---|---|---|
| release 后缀 | `20261105.81` | `20261105.82` |
| GNU ID | `b974258d0cd43da35a942f26f8d6746d832e5b74` | `29556f5cd579e50ec81c06ea32b0e46ec92ae226` |
| 配置 SHA256 | `16e40afca3bc9019d1c7379268ea23ea36dfbc781444abf45f9cab16b4be47bc` | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA256 | `b9677167ffc039b3ae423ee02aad89614899ca70a55dedc222555616f5fce30b` | `6f6bada46bd5fe7a0ac07e33eebf2a6ce497e6bcb6db32e3d9b3d8370fcaec6e` |
| RAM SHA256 | `f5965e5e741a64aac681765898abe783df9abae4481205c6af378a3be1d468ca` | `c95f2a3a79834de4d0f026b214a004ee7562539f5fe5a53c2dd3451fe85b28a9` |

归档、完整清单、私有 sources.toml、构建日志和可执行窗口脚本位于本机
`build/debug-splat-fixes/board/`；VM 对应 `/home/deepdream/build/debug-splat-fixes/board/`。
调试中间对象在封存后回收空间，vmlinux、Image、配置、符号表和 DT 保留在 VM
`debug/kernel-evidence/`。未修改正式来源锁、默认启动项或生产配置。

## A 实板结果与新锁报告

等待 `hwdecode-parity` 的构建/封包/板票全部结束后排队。首次本地证据目录创建失败，
取票后立即退出，没有 SSH/UART；修正父目录创建后从队尾重新申请。
实际 A 票 `66d8b68717d1482eb3cc502ca01120d0`，358.53 秒。
首次候选前正式 `.3` 的 2370 文件证明与真实 4K 视频通过。

ARM64 头校验后按既有工具在本次 RAM 环境设置 `kernel_addr_r=0x20000000`，
不 saveenv。串口确认进入 `.81`，私有 init 挂载同次模块；启动期限放宽到 600 秒，
并在 exec systemd 前启动有界 PD/watchdog/pstore 软件采证。

18.567267 秒出现新的 `WARNING: possible recursive locking detected`：

```
held: ffff000113ae0260 (&pmutex_inner->mutex_hd)
want: ffff000113ae0160 (&pmutex_inner->mutex_hd)
adlak_os_mutex_lock -> adlak_mem_smmu_register
 -> adlak_mem_init -> adlak_device_init -> adlak_platform_probe
```

两个地址不同。`drivers/misc/adla/drv/port/os/linux/adlak_os.c:216` 的包装函数
把所有 ADLA mutex 在同一 `mutex_init()` 调用点初始化为同类。
`drv/common/adlak_device.c:69` 持有 `dev_mutex` 后调用 `adlak_mem_init()`，
`drv/common/mm/adlak_mm_smmu.c:1195` 再获取 SMMU mutex。
这是新暴露的 ADLA 锁类别问题，独立于 SG 上限；本轮只定位直接触发路径，
尚未完成全驱动反向锁链审计或编写修复，不凭不同地址认定整个驱动没有真实死锁。

20.925577 秒打印 BCM43752 `.217` 固件初始化成功，随后回到 ROM/cold_boot。
脚本首错停，没有第二次调试候选启动。

| 门禁 | 本轮结论 |
|---|---|
| 原 MMC Invalid wait context | 此段启动 UART 未再出现；不替代完整 I/O 回归 |
| 原 PWM、73,728/65,536 DMA、NVRAM KASAN 特征 | 此段未出现；新的 ADLA 锁报告先关闭锁检查，整体验收不通过 |
| `debug_locks=1`、ADLA 绑定快照 | 未取得，不能判通过 |
| eMMC 私有文件 direct 写/读、30秒 SDIO 流量 | 未运行，候选未就绪 |
| Wi-Fi 固件初始化 | 串口确认成功，不等于流量/长期 KASAN 通过 |
| 同 chip PWM ABBA、解码 | 未访问、未修改、未运行 |

## 冷复位同步证据

原始 UART 为 `logs/debug-splat-a81/uart.raw`，逐块 UTC/单调时戳和字节 offset 为
`uart-chunks.jsonl`。ROM 标记主机 UTC 为 `2026-11-05T09:40:51.504394+00:00`。
首条 `.81` Linux 输出到 ROM **23.93750225 秒**；最后 `21.486935` 内核输出到 ROM
**1.082128375 秒**。不是此前仅凭最后 Linux 时戳估算复位时间。

采证子进程保存到：

- TCPM/FUSB302 约 19.986 秒开始软件初始化与 PORT_RESET；20.935844 秒检测
  Rp-3.0，21.140326 秒进入 SNK_WAIT_CAPABILITIES；21.145846 秒安排
  310ms 后 SNK_SOFT_RESET。该行是待执行调度，不是已发送 Hard_Reset 的证据。
- 20.900 秒 tcpm-source online=0、电压/电流=0，为初始化期间驱动缓存状态；
  不能当成已测到物理 VBUS=0。日志中的 `vbus is already off` 同样不能替代电压波形。
- PID1 7.253300 秒声明 watchdog timeout=30s。配置 `WATCHDOG_SYSFS=n`，没有
  timeleft/status/bootstatus 属性，采证未打开 `/dev/watchdog`、未改变超时。
- 复位后仍为 firmware reason 0x00、sticky=0、cold_boot，没有 panic 输出。
  恢复前后 pstore/journal 已存 JSON；其中 console 是旧 `.3` 的重启内容，两个
  dmesg-ramoops 为更早 uhd6，不能拿它们的 panic 解释 `.81`。

PD 接管与复位的时间关系更明确，但缺 Soft_Reset 的实际发送/应答、Hard_Reset、
CC/VBUS 下降及 watchdog 连续计数，仍不能闭环判定原因。没有猜改 PD、供电或看门狗。
下一窗口需补上述协议尾部和同轴 VBUS/RESET/PD 分析仪证据；若需要 watchdog sysfs，
应先审定可观测性配置，不把当前缺字段写成“看门狗正常”。

## 恢复与容量边界

意外复位自动启动 `.3` 后，脚本采证并按原计划正常重启一次。
管理器持续因写 TLS key 的 ENOSPC 退出，180 秒恢复就绪期限到期，没有盲重启。
根分区 29G 已满，inode 使用仅12%；本次暂存前没有检查 payload 外的运行空间，
这是窗口准备缺陷。原恢复票释放后重新排短恢复票，不清其他任务目录。

`recover.py` 经 stdin 传完整清单，确认运行 `.3`、无候选 init/挂载，逐文件核对本次
`.81` payload 与 metadata、无额外文件或 symlink，然后只删除本次私有 payload、
空模块目标和匹配 SHA 的本次固件副本。不再重启。管理器自动恢复，2370文件、
GNU ID、服务/UDC 核对通过；真实 3840×2160 视频 **59.574fps**，新增丢帧/冻结/丢包0。
短恢复票 **27.84秒**。证明在 `space-recovery-baseline.json`、
`space-recovery-video.json`、`space-recovery-result.json`，pstore/journal 再次备份。
不能把前一个票超时写成恢复成功；恢复成功由上述后续证明单独成立。

恢复后根分区可用约405MiB，而 B payload 合计684,756,967字节。已暂停 B，等待协调
清理其他已结束候选；不擅自删除他人文件。私有 window.py 已增加暂存前容量门禁：
payload 全部文件大小之外再保留512MiB供服务运行，恢复票也计入累计窗口预算。

## 待完成

生产 `.82` 的 600秒单TCP反向吞吐仍未运行，不能与历史369.55 Mbit/s作结果比较。
容量满足后仍按[既有方法](2026-11-02-wifi-sdio-formal.md#安装后无线测量)，
无 tracing/诊断负载，保留均值和600个区间分位；明显下降报告协调者，不恢复硬 IRQ 完成。
每窗正常返回 `.3` 并再次验证视频。调试窗口整体条件仍是零 lockdep/KASAN/DMA-API
告警、锁检查仍开启、ADLA/Wi-Fi probe和真实 eMMC/SDIO 完成路径通过。
