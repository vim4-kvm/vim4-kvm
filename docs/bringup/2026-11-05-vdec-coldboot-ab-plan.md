# 2026-11-05：正式包与 `.28` 同 RAM 封装冷复位对照计划

**t48 已批准 20 次及单票 50 分钟；工具提交仍须先审，未排板、未启动。** 本轮仅落实
离线差异方案 的第 1、2 步。
A/B 都基于 `fd41fb5`，不再拿 `.27` 的 MMC/ADLA/fan 差异作为本轮变量。
目标是比较统一 RAM 封装下两个既有内核包的启动表现，不改内核，不测解码。

## 固定输入与对照

| 组 | 既有源码 / release | GNU build ID | 权威输入 |
|---|---|---|---|
| A | `fd41fb5` / `7.3.1-vim4-20261105` | `bdbfa439f298e92b5bad092528d11119a974f262` | [正式 manifest](../../packaging/kernel/releases/7.3.1-vim4-20261105/manifest.json) |
| B | `9601323` / `7.3.1-vim4-20261105.28` | `81bb2f999ffffb38d549afbf8b15fb3048184c0f` | `build/hwdecode-parity/run58/package-manifest.json` |

两个 manifest 的 config SHA-256 相同：
`7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`。
A 本地归档 `build/deploy-73/vim4-kernel-7.3.1-vim4-20261105.tar.gz` 已存在，
来源 SHA 为 `a12069066760768a833803ad11e7e1fc212674e4ff09f40bdf2017cc1d55e204`，
见正式 release 的 deployment-inputs。B 使用已归档 r58 RAM 包内的既有产物，
来源 SHA 为 `1ff9d5241ae352abf2acc18f6a3c8aaeff7353f24f1dd7395c6a27fb08f77870`。
本轮计划阶段只核对清单/文件存在性；执行准备时重新校验归档与每项产物。
不得用已合入的 `c99c3ed` 重建 B，否则不是获批的 `.28`。

两组都重新用**同一版** RAM launcher、静态 PID1 源码、采证程序、服务策略、
看门狗及宿主编排封装。release、build ID、对应模块目录和 payload 路径是必要
身份差异，不能要求两个静态 init 二进制逐字节相同；提供规范化后的封装差异清单，
仅允许这些身份及包内 Image/DTB/模块差异。独立 namespace/payload ID，拒绝覆盖旧包。
同一正式 rootfs、manager、One-KVM、HDMI 输入、USB 供电及主机状态，全轮保持不动。

各包沿用自己的 manifest DTB，不偷偷换同一个 DT 或加伪造 DT 属性来通过门禁；
离线反编译 DT 差异、核对模块/外部驱动与固件清单后归档。因此结论对象是
**内核包（含 DT/模块）**，不能仅凭 A/B 差异定位到某个解码函数。
同一 Wi-Fi 固件内容同时准备两组 release 查找路径并核 hash，不能让 B 意外回退
到另一版固件。仅创建本任务缺失的私有文件，记录归属并在收尾清理。

## 顺序、分母与单次观察

固定 `A1 → B1 → A2 → B2 → … → A10 → B10`，20 个计划 Linux 启动，
每组 10 个，不因冷复位重跑同一序号，也不因像素或早期概率结果改顺序。
板间 FIFO 如需拆窗，保存游标并从下一序号续跑，不能重复完成的样本。

每次记录发出 reboot、进入 U-Boot、发送 RAM sysboot、首条 Linux 标识、
SSH/服务 ready、观测结束、复位/恢复的宿主时间。只有实际进入所选候选 Linux
才占一个实验序号；选错包、未进入 Linux、身份不明均记无效并停止调查，不自动补样。
A 与正式回退包 release/build ID 相同，必须再核 cmdline 的私有 `init=`、
模块 bind 来源和新 boot ID；不能用 uname 或 build ID 单独把自动回退算成 A。

从首条 Linux 启动标识起固定观察 **60 秒**，服务 ready 后继续观察到同一截止点，
不因快启动提前结束。只运行正常开机服务，不加载 `enable_t7=1`，不调用
acceptance/MDEC/HEVC 实验，不进行 modprobe 干预、解码、吞吐或性能测试。
保留既有 KVM 自动启动行为；窗口开始和最终恢复各验一次真实视频推进。

冷复位发生于这 60 秒内，记为该实验启动的失败结果。其后默认正式包的自动启动
单列为 `automatic-recovery`，核其身份/ready 后继续**下一**实验序号。
故意发出的 reboot 必须有 TX/操作事件，不能算非请求冷复位。自动恢复、窗口基线
与最终恢复均计入另一个“所有实际 Linux 启动”表，**不纳入实验 20 次分母**；
所以整轮实际启动总数可能大于 20。分组报告冷复位数/有效实验启动数及未完成数。

## 每次采证与早期缺失边界

串口由单一进程从首次操作前一直持有至最终恢复确认，不在 login/ready 处断开，
不同时运行第二个 UART reader。保存原始字节流及逐块索引：UTC ns、宿主 monotonic ns、
字节 offset/length、RX/TX、实验序号；按收到的块即时落盘。内核单调时间另保留，
不把 USB UART 收包时间说成精确硬件事件时间。

两组用相同、仅 RAM 生效的早期采集器：静态 init 核验身份后、exec systemd 前
异步启动采集；不保证首份快照先于 systemd 完成，不等待采集或主动改变模块加载顺序。
在 Linux uptime 约 3/5/8/15/45/60 秒尝试快照，ready 后及观察结束传宿主；
若开始太晚或上次读尚未完成，则记 skipped/deadline，不能补写早期数据。
该探针本身可能扰动时序，A/B 必须同版同策略，比较历史数据时注明。

每份完整快照包含：

- `/proc/cmdline`、boot ID、`/proc/uptime`、release、build ID；
- `lsmod` 与 `/proc/modules`；枚举 `/sys/module/*/parameters/*` 的值/错误，
  明确 `aml_vdec_drv` 目录存在与否、`enable_t7` 等实际值；模块存在和设备绑定分别记；
- `/etc`、`/run`、`/usr/local/lib`、`/usr/lib`、`/lib` 下实际存在的
  `modprobe.d`、`modules-load.d` 文件清单、内容 hash、symlink/覆盖关系，另采
  `/etc/modules` 和有效 modprobe 配置；只读，不执行 modprobe 或加载模块；
- dmesg/journal 原文、boot/collector 时间、读权限错误与超时；ready 时的服务状态。

完整参数输出先放 RAM，ready 后立即传宿主并校验；在串口只输出紧凑的
boot ID/uptime、采集序号、aml_vdec 是否存在及门禁参数，避免大量输出阻塞启动。
每轮采集有独立时限，不读取 debugfs/MMIO、不主动触发 probe。权限拒绝、模块
消失、参数读取超时均保留原错误；配置原文只存本地受限证据，不把可能的密钥入库。

5–6 秒冷复位可能使 RAM 快照在 SSH 前丢失。此时保留连续 UART、已收到的早期
标记与缺失阶段；**不能保证每个失败 boot 都有全部 sysfs 数据**，不得把恢复 boot
的 lsmod/参数当作失败 boot 的状态。部分采证缺失单列，不改变冷复位计数。

## 工具需先完成的离线改动

现有工具不能直接执行本计划，批准后先实现/验证以下范围，再排板：

1. `display-once.py:prepare()` 与 `board-window:verify_candidate_dt()` 当前
   将同 build ID 仅用于不同 DT 实验，会拒绝 A。新增**显式 RAM 基线对照模式**：
   要求正式 Image/DT/完整模块与 baseline proof 逐项相等、独立 payload 身份、
   私有 init cmdline、新 boot ID 与模块 bind 证明。保留默认门禁，不伪造不同 DT。
   A 的持久模块目录不可清理或覆盖，返回后核全部保护文件。
2. 改造既有 `board-window.boot()` 的 UART 生命周期：它目前在 login 或 60 秒
   后关闭串口再等待 ready；本轮需跨完整批次连续接收和主机时间戳。保留原
   sysboot、身份、proof、清理、watchdog 机制，不另建一套绕过门禁的启动器。
3. 加入上述有界只读采集器和明确的 cold-reset 分支。只有已确认自动回到正式包、
   ready 且没有内核错误时，才允许继续序列；既有通用失败停止规则不全局放宽。

离线验证覆盖真实失败路径：A 被误当普通默认启动、错误 hash/bind 来源、UART
跨块复位与计划 reboot 区分、冷复位后游标只推进一次、预算耗尽不再启动，以及
BUG/WARN/恢复失败立即终止。这是用户态编排验证，不新增内核 Python/mock 测试。
最终脚本、归档 hash、两组规范化封装 diff 和验证输出必须在占板前齐备；本记录
没有将尚未实现的采证功能标为已验证。

## 停止条件、预算与恢复

申请批准：**本任务累计最多 50 分钟，一张 FIFO 票 `--max-min 50`，全程 sampling**。
这是对默认累计 30 分钟的明确预算申请，不因已有 20 次目标自行视为已获授权。
目标约 32–40 分钟，硬上限拆分如下：

| 项目 | 上限 |
|---|---:|
| 正式 proof、前置视频检查、两组 stage/哈希核对 | 4 分钟 |
| 20 个实验序号，每个至多 120 秒，含切换与采证 | 40 分钟 |
| 正式恢复、完整身份/文件校验、视频、归档清理 | 6 分钟 |

单次 reboot→Linux 标识最多 45 秒；ready 必须在 Linux 起点后 45 秒内达到；
正常观测到 Linux+60 秒，并在本次 120 秒槽内完成采证。若有冷复位，槽内
剩余时间用于等待默认正式包就绪；不足以确认恢复则不启动下一次，进入收尾。
下一序号开始前至少余下 120 秒加完整 6 分钟恢复预算，否则记录未运行并收尾。
不把预算不足解释为用户允许延期，不续票、不无限自动重启。

任何内核 BUG/WARNING/Oops/KASAN/lockdep、挂死、设备不可用、身份失配或恢复
失败立即终止实验并收尾。识别内核 WARN 特征/栈，而非只搜大小写 `warn`：
既有 `iwconfig` 弃用提示或 ADLA 普通日志不等同内核 WARN，仍原样保存；
无法分类的异常按停止处理。**已确认的冷复位本身不停止**，但若其后正式默认
再次冷复位、未 ready 或无法证明恢复，则属于恢复失败，停止而非重启循环。

入场依据 sources.toml 的 retained_runtime 与正式 release proof，不随源码分支
合入改变恢复目标。protected_files 从本次 baseline.json 生成并在排票前逐项断言相等。
默认启动项全程不变，不 saveenv。正常完成或提前停止都由既有 return-baseline
做一次正常默认启动，核正式 build ID、完整保护文件、运行模块/DT、manager、服务、
UDC，并用既有视频检查验证真实解码推进及新增 dropped/freeze/lost。
自动回退不替代最终完整恢复 proof；恢复失败保留交接信息，不宣称已恢复。
所有本任务上传先归档到 Mac、逐文件核对，再清理私有目录和本任务创建的空目标；
不删正式模块、应用数据或其他 worker 文件。

## 报告口径与批准项

输出 A/B 逐次状态表、冷复位阶段与距 Linux 起点的时间区间、所有额外恢复启动、
采证缺失、保护文件/视频恢复证明。20 次无复位只能提供有限样本证据；若两组都
复位，只能指向共享路径或背景因素，不能直接定罪 RAM 封装；若仅 B 复位，
也仅支持包相关差异，不能直接定位解码器。正式包的历史非 RAM 启动不是同期随机
对照，本轮不擅自加第三组或关模块实验。

t48 已批准上述 A/B 20 次、累计 50 分钟上限；附加要求是两个工具选项显式开启、
默认路径不变并有离线回归，工具先提交供审。工具审过、封包核验入记录后再按 FIFO
排票；无论结果如何不追加样本、不加第三组。
