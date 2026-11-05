# 2026-11-05：冷复位的 Wi-Fi probe 排除实验

E1 在内核明确拒绝加载 brcmfmac 后仍发生 cold_boot，Wi-Fi 驱动 probe 不是这次复位
发生的必要条件。E2 的默认供电前提无法确认，按协调者边界未执行。没有扩大实验、
构建内核或修改 PD。最终恢复正式 `.3`，完整身份和4K视频通过。

## 唯一变量和离线校验

复用原调试 `.83`、源码 `53d7db5f377e8`，GNU ID
`1b57097ac560331fb0f652b8976f7335d84dda2c`，不是尚在构建的集成候选。
原RAM归档SHA256为
`cec26cbfcdd430623c9d9ba74faa8bb76f228230a0f16f3c6d910b190d4867dc`。
只在私有extlinux的APPEND末尾加一个 `module_blacklist=brcmfmac`；原token逐字不变。
Image、DT、静态init、全部模块与其他2357个文件SHA不变，metadata只更新extlinux摘要。
没有持久modprobe配置，不改变调试配置，也不把禁用Wi-Fi当作最终修复。

`.83` 的BRCMFMAC为模块。本树 `kernel/module/main.c:2952` 注册内核参数，`:3405`
在模块进入初始化前返回EPERM，因此用户态显式加载也不能绕过；这实现协调者要求的
等效“不让brcmfmac probe”。原有modprobe.blacklist名单保持不动。

实验归档SHA256：
`4c21eb2e44d87f7d5959b4d63b4a971cba110b0fdb087ad5d1eb261639fb8537`。
本机validate_bundle全量校验通过。归档、命令行差异证明在
`build/debug-splat-fixes/board/experiments/e1/`，生成脚本与窗口脚本为
同目录上级的 `prepare-e1.py`、`e1-window.py`、`e1-isolation.py`、`e1-emmc.py`。
完整脚本SHA与恢复步骤已在首次上板前写入worker结果文件，全部py_compile通过。

沿用已编译init要求的splat/debug83路径；前次payload已删除，暂存仍拒绝覆盖已有目录。
原始 `.83` 包保留，本实验单独封存归档与日志。未编译、未申请heavy、未改内核分支。

## E1 实板结果

普通FIFO板票 `2f135d51161641408c44eaba9d660d36`，实际持板 **226.02秒**。
先验证 `.3` 的2370文件/身份、视频和空间，再单次高地址RAM启动；没有saveenv。
计划在候选就绪后读取debug_locks，做16MiB私有文件direct写/读与SHA，再观察600秒。
首个复位或告警即停止；没有第二次E1。

原始证据：`logs/debug-splat-e1/uart.raw`、`uart-chunks.jsonl`，后者记录每块主机
UTC/单调时戳及字节offset。候选中明确记录：

```
[18.913596] Module brcmfmac is blacklisted
[18.915368] Module brcmfmac is blacklisted
```

候选段没有BCM43752固件初始化记录，也未见新的BUG/WARNING/KASAN/lockdep告警
（排除带标签的历史pstore文本）。随后仍直接回ROM，U-Boot报告cold_boot。
首条候选Linux输出到ROM **23.660133084秒**，ROM主机UTC
`2026-11-05T11:52:18.291629+00:00`。

TCPM仍被接管，日志见Soft_Reset TX `21.177885`、TX complete `21.186978`，
之后安排60ms响应期限 `21.189927`；未采到其实际到期、Hard_Reset或VBUS下降，
不能把“安排Hard_Reset”写成已执行或确定的复位原因。

候选未就绪，因此指定eMMC直接写读、`/proc/lockdep_stats`快照和600秒观察均未运行，
没有补齐MMC调试验收。恢复后 `.3` 的文件或锁信息不能代替候选结果。

本次只排除了brcmfmac驱动probe的必要性；MMC/SDIO主机枚举、Wi-Fi电源时序、
公共供电或其他路径仍存在，不能推广为所有Wi-Fi相关硬件均无关。

## 恢复途中另一次未请求的 .3 复位

候选失败后正常默认启动 `.3`，但它也有一次本脚本未请求的cold_boot：

| 主机UTC | UART事件 |
|---|---|
| 11:52:28.555161 | 自动回到 `.3` 的首条Linux输出 |
| 11:52:36.072687 | 再次ROM；距该Linux输出7.51754075秒 |
| 11:52:46.337318 | 第二次默认 `.3` 首条Linux输出 |
| 11:53:00.507111 | 恢复前采证JSON在主机写完，之后脚本才发起一次正常恢复重启 |
| 11:53:10.643526 | 正常恢复的reboot.target |
| 11:53:10.977625 | 正常恢复ROM，后续watchdog_reboot |
| 11:53:21.258946 | 最终 `.3` 首条Linux输出 |

首次自动 `.3` 的命令行没有实验module_blacklist，其额外复位前没有正常关机标记，
且早于脚本能够发起恢复重启的时间。这里记录“未由本脚本请求”，不据此认定物理
掉电、用户操作或与候选完全相同的根因。不能只归因于KASAN/lockdep运行开销。
本脚本只有最初选候选与最后恢复各一次reboot请求，没有自动重试候选。

最终 `.3` 的2370文件、GNU ID、服务/UDC证明通过，4K真实接收 **59.9886fps**，
新增丢帧/冻结/丢包0。`result.json` 的 `restored=true`、`own_payload_removed=true`，
没有恢复错误；本窗payload逐文件核验删除，固件副本清理，实验参数随默认启动消失。
证明是 `returned-baseline-identity.json`、`returned-video.log`；采证JSON与归档保留。
目录内dmesg是最终 `.3`，不用于证明E1候选通过。

## E2 未执行的理由

协调者要求先确认完全禁用TCPM/FUSB302后，电源退到默认5V且板子仍可正常供电。
现有证据不足以满足这个前提：

- 本板当前为单线USB-C供电，VBUS供整板，没有已确认的独立VIN维持电源，见
  [供电拓扑与实测边界](2026-11-04-boot-pd-tcpm.md#基线与硬件)。
- 禁用模块只阻止Linux接管，不主动撤销固件旧合同，不能保证已进入默认供电档。
  历史5V合同或来源PDO也不证明本次默认电流足够。
- DT仍启用FUSB302时，板级服务即使无驱动也拒绝旧I2C协商，不能假定存在自动兜底，
  见[开机PD边界](../usb-pd.md)。

因此按明确授权的“没把握就不做”停止，没有执行E2；不通过卸载活动PD驱动、原始I2C、
强制Hard_Reset、拔线或新的实验来试探供电。E1结果不能单独证明TCPM/FUSB302是根因。

当前内核v2与集成修复均未被本任务修改，后续统一候选与验收仍按
[集成记录](2026-11-05-debug-splat-integration.md)。本轮仅提供区分证据，不扩展实验。
