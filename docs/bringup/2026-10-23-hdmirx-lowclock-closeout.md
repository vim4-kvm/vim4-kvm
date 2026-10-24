# 2026-10-23：RX 阶段收尾，保留稳定 KVM 与未部署候选

用户结束本阶段：停止迭代，不再启动候选或运行新矩阵。本次收尾只读核实运行状态，
离线检查并推送已有提交，持双锁清理本任务产物。RX 偶发失锁尚未解决；未合入内核
生产分支、未正式部署、未 finalize，sources.toml/workspace.toml 的部署锁未改。
前序合同、基线对照及逐次现场见[详细记录](2026-10-23-hdmirx-lowclock.md)。

## 本轮已有矩阵结果

每次完整矩阵为19模式、两轮。下表是此前窗口的结果，收尾未重跑。

| 对象 / 接口 | 结果 | 失败与范围 |
|---|---|---|
| 正式 eeddb005，旧 fixture | 17/19、19/19 | 首轮1680×1050查询ENOLINK、1080p24抓帧ENOLINK |
| 正式 eeddb005，标准 EDID ioctl | 38/38 | 1024×768连同额外往返累计14/14；未重现稳定的候选独有失败 |
| 原9d33候选，旧 fixture | 18/19、17/19 | 1600×900、1080p30、4K60查询ENOLINK；RX目录与正式基线相同 |
| 第一版判稳候选 28f714cb714d | 37/38 | 第二轮4K30抓帧ENOLINK |
| 第二版增益校准 329be18274d5 | **34/38** | 640×480、800×600两轮均抓帧失败；日志含ENOLINK及lease timing拒绝 |
| 完整lease日志 ac7da8e03e85，旧 fixture | 短8/8、完整38/38 | 仅增加诊断，不能覆盖第二版失败或证明功能已修好 |
| 同一ac7da8e，标准 EDID ioctl | **36/38** | 首轮2560×1440查询ENOLINK；第二轮640×480查询ERANGE |

最后标准接口窗口实际build ID `10eca3504dc2a2d6b1963137200c72cdf7964085`。
2560×1440报 `Link has been severed`，640×480报 `Numerical result out of range`，
均发生在QUERY_DV_TIMINGS阶段，尚未抓帧，无本次lease-timing差异日志。
失败后的640×480快照已恢复ready、PLL/SQO/align，时钟约25.18MHz、总尺寸800×525；
恢复后的状态不能代表失锁瞬间。改用标准接口仍失败，不能归咎于旧fixture一个因素。
名为 `api-smoke` 的窗口因矩阵失败跳过后续5分钟冒烟和主动HID检查；九类门禁未重跑。

## 保留的分支与检查范围

内核fork `fix/hdmirx-lowclock` 已推送，基于 `8b2553f7b3c62`，提交依次为：

- `b1e6e76c1f739`：跨轮询周期连续三次FDET/色彩一致后发布ready。
- `28f714cb714de`：EDID替换前同步撤销旧ready，失败恢复也重新判稳。
- `329be18274d54`：按厂商T7流程在DFE收敛后做逐通道增益校准。
- `ac7da8e03e858`：输出完整lease前后时序差异。
- `c3e6a61417868`：在PHY恢复前输出失效计数器、时钟、PLL/SQO/align及新旧cable样本。

最后提交为中断前已有诊断改动，收尾只整理提交说明换行并完成离线检查。
RX全部13个脚本通过，最后提交strict checkpatch为0 errors、0 warnings、0 checks。
最后提交未构建、未上板；此前ac7da8e的Image/dtbs/modules构建通过，有2334模块清单。
增益校准的差异证据来自高频band3，低频表本来就是0，不能称作所有低频失锁的根因修复。

One-KVM `vim4-wave5-visible-hevc` 已推送，提交
`20d8010d000a2cfae082ec72b398f8e4feb9d332`，**待部署**；生产 `vim4` 仍为
`672b8fd9fdec1c35c35149265f901dc43da79394`，未合并功能分支。
`panic_on_oops=1` 板级包/安装代码保留，**待部署**；同时在
`fix/board-panic-on-oops` 保存 `ec88e220f8639938d75f2a24ba4b99c3631ad4be` 功能快照。
这部分代码此前已入主仓，
失败批次回退后板上实际值仍为0。本次未安装、未写sysctl，不把源码存在当作已生效。

## 下一阶段待办（本轮不执行）

1. 在另行批准窗口使用最后诊断提交，获取恢复前FDET完整计数器、meter原值及有效位、
   PLL/SQO/align、sampled/previous cable。区分真实源端停钟、PHY/EQ/CDR恢复、
   meter重装/有效位竞争、瞬态不一致计数器与真实lease时序变化。
2. 分开分析无DMA用户的QUERY错误与持续采集错误。现有活动用户路径可将ERANGE转为
   EAGAIN，不能据此直接放宽普通查询、时序比较容差或猜测低频PHY系数。
3. 旧fixture绕过DDC复位和驱动锁，标准EDID ioctl也有失败；保留两者与Mac源端事件的
   对照。源端图案进程在query后才启动，不能假定第一次ready以后所有源端行为都稳定。
4. 1024×768缺少稳定的候选独有复现条件，目前没有可用的二分判据。根因修复后另排
   针对性验证、5分钟冒烟及正式多子系统九类门禁；通过后再处理应用合并和部署锁。

## 最终板状态与清理

只读命令为 `ssh vim4 'systemctl is-active one-kvm vim4-manager'`、读取UDC state、
tainted、`/sys/kernel/notes`，以及 `sudo fuser /dev/hidg0 /dev/hidg1`。
实际build ID为 **`eeddb005df059a850853876d52ef603aa1af192b`**，无需再恢复/重启。
One-KVM与manager均 `active`，UDC `configured`，taint `0`，Wave5 isolated `0`；
HID字符设备存在，两个节点均由One-KVM PID915持有。本次未发送键鼠事件。
实际 `kernel.panic=20`、`kernel.panic_on_oops=0`。
inventory比对kernel ID、默认文件哈希、完整模块、cmdline、UDC、taint六项全部一致。

清理命令在Mac以 `lockf /tmp/vim4-heavy.lock lockf /tmp/vim4-board.lock` 包住，完成即释放。
删除板端本任务七个 `/var/tmp/vim4-rx-*` 目录和三个候选display-m1目录（6179、a637、10ec）；
删除前再次从kernel notes核实eeddb005，确认目录没有挂载且不是符号链接。
保留当前正式回退点 `/var/backups/vim4-kvm-tmds-final` 与
`/var/tmp/vim4-deploy-7.3-final`，未触碰其他任务文件。
删除VM `~/build/hdmirx-lowclock`、Mac `build/rx-lowclock` 和旧 `build/wave5-release`；
源码worktree/分支保留，小型复现脚本、manifest及构建信息先归档到本地忽略目录。

本地证据：`logs/rx-lowclock/{gain-candidate,api-smoke}/results.json`、各窗口状态/日志，
`timing-build.json`、`reproduction/`、`closeout-inventory.json`、`closeout-state.txt`、
`closeout-cleanup.txt`；清理后只读核验另存 `closeout-final-inventory.json`。
主仓收尾离线测试：`python3 -m unittest discover -s tests -p 'test_*.py'`，
共236项，结果OK（其中10项跳过）；文档链接、工具目录与体积检查均通过。
