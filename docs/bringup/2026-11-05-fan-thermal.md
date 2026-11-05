# 2026-11-05：风扇迁移到标准 thermal（离线，尚未上板）

用户接受15级阶梯、step_wise、取消5%限速、保留1s/100ms轮询与零滞回。
温区未知至少15%、MCU写失败每秒重试不再保留，初始档位沿用标准驱动。
本记录不是新内核的实板验收；不影响U-Boot上电风扇测试。

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
平台相关跳过不计通过，smatch不可用未运行；实板所有项目均未运行。

## 预备批量板窗（不在本任务执行）

集成阶段改为只接收构建者给出的生产RAM归档、release和外部SHA256；不使用本任务自建Image。
执行步骤、manager构建/临时安装/原件恢复、.3身份校验及24–28分钟估算统一见
[集成窗口准备](../fan-thermal-window.md)。本轮只离线准备，不排heavy或板票，候选到手后仍等协调者通知上板。

温度对照要求两边相同负载和锚点，分别预热3分钟、采至少5分钟并验证末段稳定；
判据仍为最高温增加≤3°C、常见负载CPU<85°C、无新增降频。噪声仅主观判断。
首次proof包含原manager文件哈希，候选只做RAM bind覆盖，结束正常返回.3并核原manager/风扇配置/视频推进。

逐trip仿真、跨区max、面板读回、系统睡眠等phase保留，均须提供外部candidate-plan并校运行身份；
不默认塞进完整温度对照窗口。真实读温/MCU写错注入装置未提供，不能用emul_temp冒充故障注入。
晚注册、睡眠失败恢复、物理起转仍为未验项；标准路径不再新增解绑最大档行为。
