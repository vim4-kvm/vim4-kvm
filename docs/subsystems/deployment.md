# 构建与部署

板级操作按[board-tools](../board-tools.md)，统一用 tools/board.py；隔离构建/组件打包按[ubuntu-build](../ubuntu-build.md)，内核打包/离线镜像按[ubuntu-image](../ubuntu-image.md)。
PiKVM单独构建验证，切应用前USB主机安全弹出介质。
按目标选读：[内核](../kernel.md)、[PD](../usb-pd.md)、应用VIM4.md。

登录/串口接线和默认值见[硬件](../hardware.md#默认账户开发环境)，设备名按本次环境。
串口命令用 tools/uart-run.py，只读日志用 tools/uart-log.py，输出到不入库的logs。
超时不表示命令终止；长任务后台运行、轮询，确认shell空闲再发下一条。
密码不写日志/命令行，经stdin给sudo；配置先scp再sudo cp，禁与密码共用heredoc stdin。
长期任务用nohup setsid并重定向三路标准流，sudo -b会持会话描述符、挂住SSH。

日志策略以[安装脚本](../../board/install-logging.sh)和[journal配置](../../board/60-vim4-journal.conf)为准，板级安装/组件包一致；保留旧文本日志。
查前启动用journalctl，见[预算、实测与回退](../bringup/2026-10-22-p2-journal-deploy.md)。

5.15安装按[内核](../kernel.md)，主线安装/身份按[主线合同](../kernel-mainline.md)。
面板切换只存默认启动项并重启，不格式化；重装清eMMC须用户明确确认。
优先board工具远程进OOWOW；系统无响应时按住FUNCTION、短按RESET、松FUNCTION，前提是U-Boot能到按键检测。
早期循环复位须拔SD、断全部供电/回供，按住FUNCTION冷上电。
U-Boot候选先microSD验证，失败断电拔卡；[恢复证据](../bringup/2026-10-22-uboot-sd-recovery.md)。
GPT曾被清空；仅用板级工具的专用校验刷机脚本，禁OOWOW /shell/write及未核对流式刷盘。

镜像记录仓库提交、模块、插件、服务和配置；关键发现按[索引](../bringup/README.md)记，错题按[归属](../workspace.md#文档维护)，临时配置不称已验默认。

## 内核开发流程与部署门禁

单板按[board-queue/window](../board-window.md)：heavy共享锁下先构建归档，编译释放板锁，不塞进持板run。
持板上限/任务预算见[规范](../code-standards.md#上板与测试)；采样前开启sampling，结束关闭。
超时仅告警/让后继取租约，不强杀操作；原持有者立即收尾、释放重排，已有等待者先行。

同批可链式RAM启动，批末return-baseline；全程不改默认项。
主线正式默认保留固件PD状态，APPEND含`module_blacklist=fusb302`；Mainline登记/升级及普通RAM候选
保留该策略，无线变体合并模块黑名单而不覆盖它。Vendor策略不变。正式proof已切换到
[sources.toml正式锁](../../packaging/kernel/sources.toml)指定的基线清单；
[本次默认部署](../bringup/2026-11-07-deploy42-default.md)按用户决定仅核身份和被动视频，未做九类/K9/解码冒烟。
PD策略的前后hash及持续观察边界见[切换记录](../bringup/2026-11-07-pd-firmware-default.md)。
核对基线release和build ID，以及服务、UDC和启动哈希；仅支持5.15或sources.toml正式锁的精确release，首次确认默认LINUX/FDT指向捕获基线。
正式基线须核对release目录、完整模块、采集及kbase身份、DT属性和原应用；恢复须视频推进检查，启动文件/模块必须仍完整，不能引用已清理产物。
同Image不同DT须独立payload ID、DT属性、完整模块证明，详见窗口合同。
同日且内核、程序、启动文件哈希及测量参数相同，可复用基线并注明原时间；跨日/哈希变须重测。
仅改模块可重编匹配模块、沿同内核迭代，保留哈希、vermagic和证据，不覆盖基线模块目录；正式候选全回归并用新release。

功能分支小步提交，并做checkpatch、离线和KUnit测试；候选用[一次性启动](../../packaging/kernel/display-once.py)针对性测，复位回基线。
通过后合正式集成分支并部署；夜间全回归发现问题、按提交bisect，不每次部署重复全验。

| 范围 | 门禁 |
|---|---|
| 单子系统 | 针对性测试及约5分钟冒烟，检查画面、一路编码、HID和UDC，无新增oops或taint |
| rebase、全局配置、电源或多子系统 | 九类全回归 |
| 自上次全回归的所有改动 | 夜间全回归/性能基线 |

冒烟新增告警须归因：本次引入则阻塞部署，既有/可恢复记记录后修。

## 一次性启动与硬件看门狗

候选锁、整包暂存及原子切换按[升级合同](../kernel-mainline.md#正式构建与整包升级)。
危险候选留默认基线，先确认看门狗能复位本板；[运行证据](../kernel-mainline.md#相关记录)不证明电源、总线或secure firmware故障时仍会计数，也不证明睡眠硬锁可恢复。
suspend回调停止计数；s2idle/deep须独立复位或已验睡眠watchdog契约，见[PM缺口](../archive/platform-pm-offline.md#系统挂起与唤醒缺口)。

[watchdog配置](../../board/60-vim4-watchdog.conf)由板安装/Ubuntu board包共同安装，PID1共用；下次启动生效，受控窗口可daemon-reexec。
检查systemctl实际属性、journal启用记录、设备持有者PID1，不只看文件；管理员可用/etc/systemd/system.conf.d/覆盖，禁用后reexec/重启。
[panic配置](../../board/60-vim4-panic.conf)同样成套安装，正式窗口纳入备份/回退；构建容器不改宿主参数，重启后核实sysctl实际值。
管理员可用/etc/sysctl.d/覆盖；策略不替代驱动超时恢复/隔离。

## 错题

| 触发 | 做法 | 验证 |
|---|---|---|
| VM本地分支过期误报版本 | 按[工作区](../workspace.md#构建)先status，以fetch后origin/SHA为准 | tools/vm |
| du /*使orb全卡死 | Mac virtiofs与回到VM的NFS遍历进D态，只能强重启、丢构建；只统计VM本地源码/构建或du -x / | 2026-10-31磁盘清理 |
| 窗口死亡/oops、finally卡住留半安装 | 回退不依赖候选Linux/清理；默认留基线、候选仅当次U-Boot RAM选择；恢复stop有界，失败仍写回启动文件/sync | [M1](../bringup/2026-10-23-display-m1-safety.md)：离线注入中断安装/无清理退出 |
| U-Boot mock通过、eMMC早期循环复位 | mock不覆盖上电顺序、总线不返回或供电复位；先SD验证，恢复按上文 | [事故](../bringup/2026-10-22-p2-uboot-combined.md) |
| 编译长占板/过早offer废整组 | 先构建再排窗口，采样阻塞heavy；确认服务和UDC正常、管线出帧后再offer，解码首帧后计时；同日同哈希复用基线 | tests/test_board_queue.py、tests/test_board_window.py |
| panic后sudoers变空 | 原writeback/长commit丢数据；策略按[脚本](../../tools/rootfs-policy.py)，组件成功前sync、网页更新复核后重启；非升级原子性/其他文件完整性证明 | [事故](../bringup/2026-10-13-hid-lifecycle-deploy-reliability.md) |
| 构建HDR分支管理器丢线上趋势图 | 功能在其他工作树未提交；部署前核对固定分支/已部署功能，合至同一可构建提交，仅保留工作树不算保留线上 | logs/one-kvm/manager-final.png |
| 提高平台依赖下限后网页更新全拒 | 更新入口仅换自身包，APT需平台升级/新系统依赖则拒；先部署依赖或进镜像、单发platform，再提要求；Nano网关运行时强制，不依赖系统YAML迁移，CI非旧板升级证明 | packaging/ubuntu/package.py PLATFORM、vim4-manager-helper update |
