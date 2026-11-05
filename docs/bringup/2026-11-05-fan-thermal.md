# 2026-11-05：风扇迁移到标准 thermal（基线未稳定，候选未测）

用户接受15级阶梯、step_wise、取消5%限速、保留1s/100ms轮询与零滞回。
温区未知至少15%、MCU写失败每秒重试不再保留，初始档位沿用标准驱动。
本次板窗因旧内核基线未稳定而停止，不能作为新内核的实板验收；不影响U-Boot上电风扇测试。

## 行为与证据边界

板DT六区各15个 active trip 和固定上下限 cooling-map，CPU passive/hot/critical保持原样。
驱动只管 cdev、MCU写档位、供电和PM；不再采温、插值或创建私有sysfs。
档位定义以 [板测脚本](../../tools/fan-thermal-check.py) 的仿真对照与内核板DT为准；
面板保留L/M/H三个锚点，后台写六区90个标准trip温度，全部读回后才持久化。
旧mainline和5.15用户态接口保留兼容，工具按type发现cdev/温区，不依赖枚举编号。

7.3源码核验基线为d4eee9d02eede：

- `drivers/thermal/thermal_helpers.c:166` 对同一cdev全部实例取最大请求。
- `drivers/thermal/thermal_core.c:558` 读温失败不调用governor，旧请求保留；
  `:261` 安排重试，非EAGAIN持续失败可能禁用温区，不承诺1秒恢复或15%输出。
- `drivers/thermal/thermal_helpers.c:179,191` 不保证MCU设档失败后恒温同请求自动重试。
- `drivers/thermal/thermal_of.c:89` 给OF trip设置RW_TEMP；`thermal_sysfs.c:420,433`
  分别按TEMP/HYST flag设置写权限，当前OF滞回默认只读。
- `drivers/thermal/amlogic_thermal.c:163` 中T7 get_temp忽略regmap_read返回值，通常不报告
  实际读温错误；因此不能把成功读temp当传感器故障检测已经通过。
- `drivers/thermal/thermal_helpers.c:90` 的仿真仍要求真实读温成功；emul_temp不能代替读温失败注入。

用户已接受这些故障语义变化，不新增core故障策略、用户态调速守护进程或私有调试ABI。
有效100°C请求仍能压过其他低请求，但依赖真实MCU写入成功，百分比不证明风扇转动。

## 原分支离线验证（不是集成RAM候选输入）

内核返工后为a79be4150c7e8（生命周期）、82979d5b8b83f（DT）和8096c2400ff5e（策略删除），主仓库用户态92379c0，
面板a0e15b6与85ef0b1。精确命令和原始日志见协调者收到的任务结果文件。
内建/模块对象W=1及有效sparse 84ec0658通过；fan/MCU无诊断，共同准备步骤的vDSO有未改动声明告警。
对format-patch输出跑strict checkpatch：生命周期/DT零诊断，策略删除无错误但有MAINTAINERS提醒（exit 1）。
旧提交只检查diff的“通过”结论已在任务结果文件中撤回，原始format-patch命令和输出均已保存。
MCU/thermal schema及11个VIM4 DTB（含vdec-test）的定向与完整schema检查通过，
反编译确认每板90个固定fan map及CPU保护和轮询保留；DTC仍有未改动pinctrl节点告警。
生产配置Image、dtbs及2338个模块完成，独立fan模块完成MODPOST/链接/BTF，不作为部署候选。
整树W=1存在未改动代码告警，不能写成零告警。构建最初因直接legacy锁阻塞板窗被协调中止，
后续通过heavy队列增量完成；中止不是编译错误，构建入口已在工具目录改为队列。
用户态已跑主仓库unittest、管理器Go/前端构建、助手unittest及两种曲线的浏览器controls回归。
平台相关跳过不计通过，smatch不可用未运行；上述原分支离线验收不包含实板结果。

## 获批生产.90窗口：基线不稳定，首错停止

UTC 13:40:56–13:49:40，FIFO票`cd1e261d305d44cc8d529b3b383b49c3`，
总计523.8秒；按30分钟上限准备，实际未启动候选。板票结束后队列及两个legacy锁均空闲。
环境温度29°C来自用户现场读数。本次没有重新申请板票、延长采样或放宽稳定性条件。

输入是协调者提供的生产`7.3.1-vim4-20261105.90` RAM包，源
`fd41fb5950b9da1fb336ce00d5137d27ee9755fa`，build ID
`6c5ebf0605c190d7670374fb6ea880958f54cba1`；归档及Image的SHA256均与外部提供值一致。
原包在兄弟工作树`vim4-kvm-kunit-migration/build/kunit-migration/integration-73/candidates/production/ram/candidate.tar`，
校验plan保存在本工作树`build/fan-candidate-plan.json`。

manager `fan-thermal`仍基于最新fetch到的origin/main `710698bb2b0f069ce2605360c6f9725e1d6c0bfd`，
HEAD `85ef0b1287c2dd428003b609e575ce33cbc4f99a`，仅超前两个风扇提交，源码未改。
占板前经heavy队列构建ARM64组件包，Go/helper测试、前端构建和sudoers检查通过。
构建日志为`build/manager-package.log`，deb及源码/构建器收据在
`build/packages/2.5.1+vim4.20261029.102.dev.1.g85ef0b1/`；新manager及helper均未安装。

实际命令与临时执行脚本快照保存在下述证据目录。窗口入口为：

```sh
tools/board-queue run --who fan-thermal \
  --purpose '.3 versus production .90 thermal and manager comparison; restore .3 and video' \
  --max-min 30 -- python3 build/fan-window.py
```

基线身份是`7.3.1-vim4-20261104.3`，build ID
`e595ad243d663f6c33b92678a4de6e0b78ec16d5`。
沿用板上原H.265/40Mbps请求与60/80/100°C锚点，未切换成准备文档中的30Mbps示例。
Chrome 156.0.8078.80实际接收3840×2160视频500.001秒，解码12→30011帧，
平均59.998fps，RTP接收约15.314Mbit/s，丢帧计数未增加；相邻解码推进间隔最大57.4ms。
帧计数不能单独证明源画面有运动，本次未独立核验运动图样。
预热180秒后采样300.582秒，共299条约1Hz记录。

| 温区 | 最高温°C | 五个分钟组均温°C | 组均温最大差°C |
|---|---:|---|---:|
| a73 | 58.0 | 54.330 / 54.863 / 55.017 / 54.737 / 55.224 | 0.894 |
| a53 | 53.5 | 52.072 / 52.330 / 52.422 / 52.552 / 52.756 | 0.684 |
| gpu | 52.9 | 51.862 / 52.115 / 52.178 / 52.283 / 52.505 | 0.643 |
| nna | 52.9 | 51.880 / 52.127 / 52.175 / 52.283 / 52.493 | 0.613 |
| vpu | 52.7 | 51.885 / 52.117 / 52.155 / 52.318 / 52.490 | 0.605 |
| hevc | 53.7 | 52.858 / 53.128 / 53.137 / 53.313 / 53.515 | 0.657 |

六区均超过已准备的0.5°C组均温差门槛，多数温区仍缓慢升温，故基线无效。
不能删掉前几分钟、改用末段或据此宣布候选温差通过。这里不是候选内核失败：候选启动、
新manager安装、候选采样及两组比较均未执行，最高温≤+3°C验收尚无结论。
基线CPU最高58.0°C；两个cpufreq cdev全程state=0，performance governor下
policy0固定2208000kHz、policy4固定2016000kHz，没有观察到基线被动降频。
原风扇报告23/24/28%，sensor_fault全程0；这些观测不能覆盖真实读温/写MCU故障注入。

收尾没有重启或换manager，因为中止发生在任何候选修改之前。
首次与结束baseline-proof完全相同，含2370项文件摘要、运行模块、cmdline、应用及DT属性；
外部包的固定baseline_files不含manager，因此独立原件证明另核二进制/helper及进程exe哈希。
原manager PID仍为1189、unit/InvocationID不变，风扇配置、锚点、编码设置一致，taint保持4096。
服务active、UDC configured，结束时另接收10秒视频为59.992fps。

完整证据在本工作树`logs/fan-thermal-90-20261105-134056/`：
`baseline.json`、`baseline-receiver.json`、`analysis.json`、首次/结束proof、
原/结束manager证明、dmesg、events.log和result.json；执行入口日志为`build/fan-window-run.log`。
本窗口首错停止后只离线整理，没有再次碰板。下一窗口需要协调者安排并重新取得有效稳定基线；
目前不能批准候选温度验收，也不自动扩大预热时间或调整门槛。

## 后续批量板窗步骤与未验边界

集成阶段改为只接收构建者给出的生产RAM归档、release和外部SHA256；不使用本任务自建Image。
执行步骤、manager构建/临时安装/原件恢复、.3身份校验及24–28分钟估算统一见
[集成窗口准备](../fan-thermal-window.md)。后续执行仍由协调者安排，不能把上述失败基线复用为通过证据。

温度对照要求两边相同负载和锚点，分别预热3分钟、采至少5分钟并验证整个采样窗稳定；
判据仍为最高温增加≤3°C、常见负载CPU<85°C、无新增降频。噪声仅主观判断。
内核首次proof与独立原manager文件证明均须保留，候选只做RAM bind覆盖，
结束正常返回.3并核原manager/风扇配置/视频推进。

逐trip仿真、跨区max、面板读回、系统睡眠等phase保留，均须提供外部candidate-plan并校运行身份；
不默认塞进完整温度对照窗口。真实读温/MCU写错注入装置未提供，不能用emul_temp冒充故障注入。
晚注册、睡眠失败恢复、物理起转仍为未验项；标准路径不再新增解绑最大档行为。
