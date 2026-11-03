# 构建与部署

板级自动化先读 [board-tools.md](../board-tools.md)：组件包部署、远程进入 OOWOW、
本地镜像刷写、启动日志与只读服务检查统一使用 tools/board.py。

Ubuntu 隔离构建与组件打包先读 [ubuntu-build.md](../ubuntu-build.md)。
PiKVM 使用 `--component pikvm` 单独构建和验证，部署仍使用 board.py。切换应用前先在 USB 主机安全弹出虚拟介质。
内核打包与离线候选镜像组装见 [ubuntu-image.md](../ubuntu-image.md)。

按目标再读：内核 [kernel.md](../kernel.md)、PD [usb-pd.md](../usb-pd.md)、应用安装见各应用 VIM4.md。

SSH 为 ssh vim4（khadas@192.168.50.210），串口默认/示例为 /dev/cu.usbserial-100，921600 8N1。
设备名以本次环境为准，接线与默认值见[硬件](../hardware.md)。
命令使用 tools/uart-run.py，只读日志用 tools/uart-log.py，输出放不入库的 logs/。
串口超时不表示板上命令终止，长任务后台运行并轮询。

默认账户 khadas/khadas、root/khadas 见 [硬件](../hardware.md#默认账户开发环境)；
日志和命令行参数不写入密码，经 stdin 传给 sudo。
配置先 scp 到临时位置再 sudo cp，避免密码与 heredoc 共用 stdin。
长期命令使用 nohup setsid command </dev/null >log 2>&1 &，避免 sudo -b 挂住 SSH。

板级日志策略由 `board/install-logging.sh` 与 board 组件包共同安装：persistent journal
上限 256 MiB，停用/mask rsyslog，保留原文本日志。排查前一启动用 `journalctl -b -1`；
预算、实测和回退见 [持久日志部署](../bringup/2026-10-22-p2-journal-deploy.md)。

5.15 内核安装见 [kernel.md](../kernel.md)；主线安装合同与当前身份见[主线内核开头](../kernel-mainline.md)。
面板切换只保存默认启动项并重启，不格式化数据。
重装清空 eMMC，须用户明确确认；
优先使用 tools/board.py recover 远程进入 OOWOW；系统无法响应时，按住 FUNCTION、
短按 RESET、松开 FUNCTION（要求 U-Boot 已能运行到按键检测）。若早期循环复位，
先拔 SD、断开全部供电/回供，按住 FUNCTION 冷上电进 OOWOW。
U-Boot 候选必须先从 microSD 验证，见 [现场恢复](../bringup/2026-10-22-uboot-sd-recovery.md)。
刷写见板级工具文档，禁止直接用 OOWOW /shell/write。

镜像构建需记录各仓库提交、模块、插件、板级服务和应用配置。
上板关键发现按 [上板记录索引](../bringup/README.md) 新建条目，跨子系统教训归
[LESSONS.md](../../LESSONS.md)、子系统教训归对应文档的「错题」，临时实验配置不能写成已验证默认值。

## 内核开发流程与部署门禁

单板统一使用 [board-queue / board-window](../board-window.md)：先在 `--heavy` 共享锁下
完成构建和归档，编译时必须释放板锁；每次持板窗口上限30分钟，采样前 `sampling on`，
结束 `sampling off`。超时只告警并让后继取得租约，不强杀板上操作，原持有者立即收尾；
不要把长编译塞进持板的 run 中。释放后重新排队，已有等待者先行。

同批候选可以直接链式 RAM 启动；批次结束 `return-baseline`，核对保留基线的
release/build ID、服务、UDC与启动文件哈希，默认启动项全程保持原值。
支持5.15或sources.toml当前正式锁的精确release；首次采集确认默认LINUX/FDT指向捕获的基线。
正式基线核对release目录、完整模块文件、采集/kbase加载身份、DT属性及原应用，
恢复时必须提供 `--video-check` 视频推进检查命令。恢复基线必须仍有完整启动文件和模块，不能引用已清理产物。
同Image不同DT的候选必须有独立payload ID、DT属性与完整模块证明，见[窗口合同](../board-window.md)。
基线按当天、内核/程序/启动文件哈希及测量参数复用并注明原始时间；哈希变化或跨日
重新测量。只改模块时可只重编匹配模块、沿用同一内核进行针对性迭代，保留模块哈希、
vermagic与证据；不覆盖基线模块目录。正式候选才全量回归并使用新 release 名。

按内核社区流程推进：功能分支上小步提交（checkpatch、离线/KUnit 测试），候选只用
一次性启动（packaging/kernel/display-once.py）上板做针对性验证，复位即回基线；
通过后合入 vim4-kvm-7.3 并部署，回归问题由夜间全量回归发现、按提交 bisect，
不在每次部署时重复全套验收。门禁按改动范围分级：

| 改动范围 | 部署门禁 |
|---|---|
| 单一子系统（采集、显示、Wave5 等） | 该子系统针对性测试 + 约 5 分钟冒烟：画面、一路编码、HID/UDC、无新增 oops/taint |
| rebase、全局配置、电源管理或多子系统 | 九类全量回归 |
| 自上次全量以来的所有改动 | 夜间全量回归与性能基线 |

冒烟中的新内核告警需判断归因：本次改动引入的阻塞部署，既有或可恢复的记入记录后修复。

## 一次性启动与硬件看门狗

候选锁、整包暂存和原子切换合同见[正式构建与整包升级](../kernel-mainline.md#正式构建与整包升级)。
危险候选以一次性启动保留默认基线；先确认硬件看门狗能复位当前板子。
运行时复位证据见[主线相关记录](../kernel-mainline.md#相关记录)，不保证电源、总线或
secure firmware 故障时计数器继续运行，也不能证明睡眠期硬锁可恢复。
系统挂起时 watchdog suspend 回调停止计数；s2idle/deep 试验须有独立复位或经验证的
睡眠期 watchdog 契约，见[PM 审查](../archive/platform-pm-offline.md#系统挂起与唤醒缺口)。

`board/60-vim4-watchdog.conf` 经板级安装与 Ubuntu board 包安装到
`/usr/lib/systemd/system.conf.d/`；PID 1 共用 `RuntimeWatchdogSec=30s`、
`RebootWatchdogSec=60s`。下一次启动生效，受控窗口可用 `systemctl daemon-reexec`。
核对 `systemctl show -p RuntimeWatchdogUSec -p RebootWatchdogUSec`、journal 的
`Using hardware watchdog` 及 /dev/watchdog0 持有者 PID 1，不能只检查文件。
管理员可在 /etc/systemd/system.conf.d/ 覆盖；关闭设置 RuntimeWatchdogSec=off 后 reexec 或重启。

`board/60-vim4-panic.conf` 同样经板级安装和 Ubuntu board 包安装到 /usr/lib/sysctl.d/，
正式部署窗口纳入备份与回退。启动时设 kernel.panic_on_oops=1，配合 panic=20 和看门狗；
构建容器不修改宿主参数。重启后核实 `sysctl kernel.panic kernel.panic_on_oops`；
管理员可在 /etc/sysctl.d/ 覆盖。该策略不替代驱动的超时恢复与设备隔离。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| 内核编译占板锁近两小时，后继超时；过早offer导致整组作废 | 编译先完成再排≤30分钟窗口；采样阻塞heavy；先确认服务/UDC/管线出帧，再offer，解码首帧后计时；同日同哈希基线复用 | tools/board-queue、tools/board-window，tests/test_board_queue.py、tests/test_board_window.py |
| 部署后不久内核 panic，刚装的 sudoers 变成 0 字节 | 原根分区 data=writeback、commit=600。新部署配置 ordered/commit=5；所有组件安装成功前 sync，网页更新复核文件后再重启。它不保证升级原子性，也不证明其他文件没有损坏 | tools/rootfs-policy.py、[上板记录](../bringup/2026-10-13-hid-lifecycle-deploy-reliability.md) |
| 从 HDR 分支构建管理器后，已部署的趋势图表消失 | 图表在另一工作树的未提交改动中。部署前同时核对固定分支与已部署功能，合并到同一可构建提交；保留原工作树不等于保留线上功能 | vim4-manager onekvm 分支、logs/one-kvm/manager-final.png |
| 提高应用包对平台包的版本下限后，网页更新一律失败 | 五个更新入口都只允许替换自身一个包，APT 预演需要升级平台组件或新装系统依赖时直接拒绝。只有在新依赖已部署或已进镜像后才提高要求，平台组件先单独发布 platform。NanoKVM 网关配置在运行时强制生效，不依赖系统 ruamel.yaml 迁移；CI 通过不代表现有板子能网页升级 | packaging/ubuntu/package.py PLATFORM、vim4-manager-helper update |
