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

## 离线验证

主仓库、面板、内核的精确提交、检查命令和原始日志见协调者收到的任务结果文件。
内核构建与schema检查未完成前不标通过；实板所有项目均未运行。
当前已执行用户态测试：主仓库unittest、管理器Go/前端构建、助手unittest及两种曲线的
浏览器controls回归。平台相关跳过不计通过，详见任务结果。

## 预备批量板窗（不在本任务执行）

等解码调试窗口结束，由协调者预约独占板窗；先核候选Image/DTB/完整模块和BTF来源一致。
脚本不自动申请板锁；调用者按板窗规范持锁并将原始JSON/日志保存到本记录对应证据目录。
默认每阶段15分钟超时，实板每任务累计不超过30分钟，首错退出离线分析。

1. 基线：在旧安静曲线、同环境、固定应用/信源/编码设置下预热至温升趋稳。
   `python3 tools/fan-thermal-check.py sample --exclusive --ambient 25 --workload IDENTIFIER --output baseline.json`
   采5分钟，记录六区温度和cpufreq cooling状态。基线与候选应由同一环境条件配对。
2. 标准对象：六区完整enabled，policy=step_wise，一个fan cdev/max_state=100，各区15个fan map；
   CPU保护map未变。无新BUG/Oops/WARNING/taint或热关机。
3. 仿真：`python3 tools/fan-thermal-check.py emulation --exclusive`。
   逐区逐trip边界正反向注入，2秒内达到期望档位，六区轮流100°C均全速；
   另一有效区仍热时冷区更新不能覆盖它。脚本finally清除仿真；不会注入critical以上。
   可能触发既有CPU passive/hot，不能把仿真降频当真实负载降频。
4. 面板后台：`python3 tools/fan-thermal-check.py panel --exclusive`。
   65/85/100写入90个trip并读回一致，启动恢复路径一致，最后恢复原始曲线与配置文件。
   这测生产助手，不冒充真实网页/API上板验收；另在面板执行一次应用/刷新，确认显示一致，
   非法60/62/100拒绝且未改硬件，重启面板后恢复保存值。
5. 候选负载：同基线预热、同参数采5分钟到candidate.json；
   `python3 tools/fan-thermal-check.py compare --baseline baseline.json --candidate candidate.json`。
   环境温度差≤1°C、最高温相对增加≤3°C、常用负载两组CPU均<85°C、无新增被动降频/热关机。
   热关机/内核错误另检查journal，脚本的温度对比不能代替系统日志。
   噪声由用户主观判断，不设dBA指标，不从MCU百分比推导定量噪声。
6. 系统睡眠：确认平台支持RTC唤醒后，在低档/高档负载分别运行
   `python3 tools/fan-thermal-check.py suspend --exclusive`，验证整机睡眠/唤醒后2秒内按新温度收敛；
   停扇/供电现象、regulator/I2C日志和服务状态另记。显示器休眠不能替代整机睡眠。
7. 晚注册：只在专用可模块化候选和短冷板窗口延迟正常sensor模块加载，出现后2秒内绑定15个map并参与max；
   无可用候选则明确未验。脚本不自动解绑活跃传感器或移除CPU热保护。

未提供真实传感器错误/MCU写错误注入装置，不能以emul_temp覆盖这两项；用户已选择默认内核行为。
睡眠失败恢复、解绑最大档、物理起转仍需后续合适候选和窗口，未通过负载观察自动算通过。
