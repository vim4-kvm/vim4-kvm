# 构建与部署

板级自动化先读 [board-tools.md](../board-tools.md)：组件包部署、远程进入 OOWOW、
本地镜像刷写、启动日志与只读服务检查统一使用 tools/board.py。

Ubuntu 隔离构建与组件打包先读 [ubuntu-build.md](../ubuntu-build.md)。
PiKVM 使用 `--component pikvm` 单独构建和验证，部署仍使用 board.py；复用 `.24`
或更新板级组件。切换应用前先在 USB 主机安全弹出虚拟介质。
内核打包与离线候选镜像组装见 [ubuntu-image.md](../ubuntu-image.md)。

按目标再读：内核 [kernel.md](../kernel.md)、PD [usb-pd.md](../usb-pd.md)、应用安装见各应用 VIM4.md。

SSH 为 ssh vim4（khadas@192.168.50.210），串口 /dev/cu.usbserial-100，921600 8N1。
命令使用 tools/uart-run.py，只读日志用 tools/uart-log.py，输出放不入库的 logs/。
串口超时不表示板上命令终止，长任务后台运行并轮询。

默认账户 khadas/khadas、root/khadas 见 [硬件](../hardware.md#默认账户开发环境)；
日志和命令行参数不写入密码，经 stdin 传给 sudo。
配置先 scp 到临时位置再 sudo cp，避免密码与 heredoc 共用 stdin。
长期命令使用 nohup setsid command </dev/null >log 2>&1 &，避免 sudo -b 挂住 SSH。

板级日志策略由 `board/install-logging.sh` 与 board 组件包共同安装：persistent journal
上限 256 MiB，停用/mask rsyslog，保留原文本日志。排查前一启动用 `journalctl -b -1`；
预算、实测和回退见 [持久日志部署](../bringup/2026-10-22-p2-journal-deploy.md)。

5.15 内核安装用 tools/kernel-install.sh。7.x 独立保留在 `/boot/edge`，安装匹配的
Image / 完整模块后，用 `packaging/kernel-edge/register-runtime.py` 核对构建清单并登记；
过程见 [双内核集成](../bringup/2026-10-21-dual-kernel-integration.md)。
面板切换只保存默认启动项并重启，保留 5.15 Image、Stock 与实验入口，不格式化数据。
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

按内核社区流程推进：功能分支上小步提交（checkpatch、离线/KUnit 测试），候选只用
一次性启动（packaging/kernel-edge/display-once.py）上板做针对性验证，复位即回基线；
通过后合入 vim4-kvm-7.3 并部署，回归问题由夜间全量回归发现、按提交 bisect，
不在每次部署时重复全套验收。门禁按改动范围分级：

| 改动范围 | 部署门禁 |
|---|---|
| 单一子系统（采集、显示、Wave5 等） | 该子系统针对性测试 + 约 5 分钟冒烟：画面、一路编码、HID/UDC、无新增 oops/taint |
| rebase、全局配置、电源管理或多子系统 | 九类全量回归 |
| 自上次全量以来的所有改动 | 夜间全量回归与性能基线 |

冒烟中的新内核告警需判断归因：本次改动引入的阻塞部署，既有或可恢复的记入记录后修复。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| 部署后不久内核 panic，刚装的 sudoers 变成 0 字节 | 原根分区 data=writeback、commit=600。新部署配置 ordered/commit=5；所有组件安装成功前 sync，网页更新复核文件后再重启。它不保证升级原子性，也不证明其他文件没有损坏 | tools/rootfs-policy.py、[上板记录](../bringup/2026-10-13-hid-lifecycle-deploy-reliability.md) |
| 从 HDR 分支构建管理器后，已部署的趋势图表消失 | 图表在另一工作树的未提交改动中。部署前同时核对固定分支与已部署功能，合并到同一可构建提交；保留原工作树不等于保留线上功能 | vim4-manager onekvm 分支、logs/one-kvm/manager-final.png |
| 提高应用包对平台包的版本下限后，网页更新一律失败 | 五个更新入口都只允许替换自身一个包，APT 预演需要升级平台组件或新装系统依赖时直接拒绝。只有在新依赖已部署或已进镜像后才提高要求，平台组件先单独发布 platform。NanoKVM 网关配置在运行时强制生效，不依赖系统 ruamel.yaml 迁移；CI 通过不代表现有板子能网页升级 | packaging/ubuntu/package.py PLATFORM、vim4-manager-helper update |
