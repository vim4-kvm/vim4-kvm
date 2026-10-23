# 厂商 5.15 一次性性能对照启动

结论：可复用 [M1安全网](bringup/2026-10-23-display-m1-safety.md) 的 **U-Boot RAM中
sysboot选择一次、默认仍为7.3** 原理；不能直接复用绑定7.3 release/build ID的
display-once.py或静态PID1。5.15使用自己的initrd和独立模块目录。
[2026-10-23短窗口](bringup/2026-10-23-vendor-boot-gpu.md)已验证mmc1:1加载5.15
Image/initrd/DTB、SSH及正常重启返回默认7.3；硬挂死自动复位仍未验证。

## 离线生成与下次窗口门禁

`tools/vendor-boot-plan.py` 只读本地快照、输出新目录；不执行stage/reboot。
历史extlinux Default用 `/Image`、`/initrd.img`、`FDTDIR /dtb`和 `${bootargs}`，
因此必须从新清单解析真实链接、当前U-Boot变量与正确板型，提供显式profile。
不能从7.3的 `/proc/cmdline` 猜厂商参数。示例profile仅示意结构，APPEND必须换成
审查后的真实厂商参数（root/console/CMA/PD等），不要直接上板使用示例：

```json
{"LINUX":"/vmlinuz-5.15.137-vim4kvm",
 "INITRD":"/initrd.img-5.15.137-vim4kvm",
 "FDT":"/dtb-5.15.137-vim4kvm/amlogic/kvim4n.dtb",
 "APPEND":"root=PARTUUID=REPLACE_WITH_VERIFIED_ROOT rootwait rw rootfstype=ext4"}
```

```sh
python3 tools/vendor-boot-plan.py --extlinux /path/to/fresh/extlinux.conf \
  --vendor-label Default --vendor-profile /path/to/reviewed-vendor.json \
  --output /tmp/vendor-once-plan
```

生成器拒绝默认非 `/edge/Image`、无版本路径、缺initrd/DTB/root、变量展开、
init覆盖与命令注入；它**不验证产物存在/匹配、实际分区、APPEND的硬件语义**。
旧Stock标签是5.15.137原厂镜像，不等同于本任务的5.15.137-vim4kvm，不能混用。
plan.json保留原extlinux哈希与完整已解析profile，生成固定路径 `perf-vendor-<hash>.conf`。
正式部署可能更新7.3；必须以窗口开始的新清单为回退目标，不硬编码7b8372b8旧build。

每次取得双锁后按以下顺序执行，任一门禁失败即停止：

1. 核对新7.3 build ID、完整模块清单、Image/DTB/extlinux/uEnv/kernels.json/
   runtime-build.json哈希；保存服务配置、应用数据库一致性备份、USB LUN/PD状态。
   确认taint=0、Wave5未隔离、真实HID/音视频健康。主机安全弹出全部虚拟盘。
2. 对5.15 Image/initrd/正确kvim4n DTB与 `/lib/modules/5.15.137-vim4kvm` 做完整哈希，
   与既有同次构建产物核对（release/vermagic相同不充分）。`lsinitramfs` 核对模块、
   根设备/文件系统驱动与挂载方式，确认没有指向7.x模块。只读检查dtc反编译的
   reserved-memory/ramoops、CMA与供电节点，禁止为测量临时合并7.3 DT属性。
3. 核对运行器/manager当前安装文件哈希与双内核集成版本；保留应用配置不降级数据库。
   确认两个内核均能启动同一应用版本，厂商插件/分配器存在。GPU栈按性能协议先发现。
4. 核实eMMC boot确为mmc1:1、配置路径从分区根解析。先以独立配置选择**当前7.3
   的同一Image/DTB/APPEND**验证sysboot路径，再复位确认原默认启动正常。原M1走
   mmc1:2根分区，本方案把小配置放现有boot分区，只引用其版本化5.15文件，避免复制大包。
5. 将生成的extlinux.conf复制到plan给出的 `/boot/perf-vendor-<hash>.conf`，使用新文件
   独占创建，不覆盖；读回核对哈希并fsync文件/所在目录。复查全部受保护文件未变。
   不改默认、Image链接、runtime登记、U-Boot环境、引导区或已有模块目录。
6. 接串口并抓日志，中断**当次**autoboot，仅发送plan里的命令，例如：
   `sysboot mmc 1:1 any ${pxefile_addr_r} /perf-vendor-HASH.conf; reset`。
   不saveenv，不使用管理器切默认，不把该命令写入任何自动开机脚本。
7. 120秒启动预算内验证5.15实际build、模块、manager、One-KVM实际厂商codec、音频、
   UDC configured与主机收到HID；应用成功启动不是全兼容证明。失败保存串口/日志，
   正常重启或外部RESET，禁止热解绑网口/UDC作为恢复捷径。
8. 第一轮短启动后即回7.3，验证新基线build/哈希、模块、服务、PD/UDC、实际HID与
   有运动的视频/非静音音频；恢复原配置。仅在这一往返通过后才排三组性能采样。
   清理本次小配置文件之前保留plan和日志；不删除5.15产物。

## 自动返回的边界

| 故障 | 自动路径 | 尚需证明/补救 |
|---|---|---|
| sysboot读取/加载失败并返回 | 命令末尾reset→未改动的7.3默认项 | 必须先验证独立7.3配置与复位默认路径 |
| 5.15进入panic | profile追加oops=panic、panic=20→复位→7.3 | 某些锁死不进入panic；供电/固件复位路径须实测 |
| 用户空间可运行但应用/网络失败 | 窗口控制端经串口请求正常reboot | 串口超时不表示命令退出，不能继续堆命令 |
| 内核/总线硬挂死、早期initrd卡死 | 只有已验证、跨故障持续计时的硬件watchdog或独立外部RESET控制器能自动复位 | 当前无该证明；必须有人可RESET，不承诺自动恢复 |

自动化长窗口的前置条件是验证外部串口看门狗/RESET执行器（独立供电、串口启动预算
120秒、失联预算60秒、每轮最多触发一次、返回7.3后停止）；不能仅凭systemd软件定时器
或Mac的finally声称覆盖硬挂死。当前没有已知可调用的RESET执行器，不生成猜测GPIO/电源
命令；没有该设备时只允许有人值守短窗口。`RuntimeWatchdogSec` 也不是早期引导保证，
其驱动、实际喂狗停止、超时复位行为需先验证，不能在本性能任务中擅自改持久配置。
这意味着“一次性选择”方案可准备，但“无人值守硬故障自动回7.3”仍是未满足门禁。

## 兼容性与风险评估

| 对象 | 已有证据及剩余风险 |
|---|---|
| One-KVM/manager | [双内核集成](bringup/2026-10-21-dual-kernel-integration.md)有历史往返验证；当前 `board/vim4-kvm-run` 5.15选vendor插件、One-KVM独立LD_LIBRARY_PATH，共用数据目录；7.3选mainline插件。当前部署任务会更新版本，所以历史通过不能代替新安装清单。切换不调用manager写默认的接口 |
| 模块/固件/initrd | 5.15 release不同，不需M1的同release bind mount；仍必须同次Image/全模块，initrd中不能残留不匹配副本。保留 `/lib -> usr/lib`，不解包覆盖根链接；缺模块就停，不能拿7.3模块补 |
| ramoops/pstore | 不假定5.15与7.3保留区地址/大小/record-size一致。核对两DT/config、CMA不重叠，并在每次切换前归档 `/sys/fs/pstore` 与journal。5.15可能覆盖7.3记录或不保留；无记录不代表无崩溃；串口为独立证据，不为跑分临时改内存布局 |
| UDC/HID | 5.15必须包含队列生命周期/cdev与CRG中断修复；旧版本热重绑有panic风险。先停应用并释放FD、正常整机重启，不测重绑压力；LUN必须弹出。重启USB会重新枚举，实际主机输入必须复核 |
| PD/供电 | `board/vim4-board-runtime` 按内核选择vim4pd的vendor模式；两内核/固件PD交接与I²C路径不同。保持供电拓扑不变、禁止运行中拔单线供电、不能以UDC configured证明PD合同。无稳定供电/现场RESET则不启动 |
| 网口 | 已有5.15 carrier正常却收不到包、热解绑Oops教训；串口始终保留，正常复位回默认，不热重绑。故障轮次不计性能通过 |
| 共享用户态 | 只切内核不等于文件系统回滚；写盘/数据库升级不会因RESET撤销。禁升级安装、记录服务/应用设置并恢复；发生D状态时不覆盖打开的SQLite/WAL，回健康基线后处理 |

完整采样方法和指标见 [性能基线](performance-baseline.md)，细化后的窗口预算与排队顺序见
[整夜执行计划](overnight-performance-plan.md)，开跑时间待用户确认。
