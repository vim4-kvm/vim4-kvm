# ADLA 离线候选

本轮工作在 VM `~/src/linux-7.3-npu`、分支 `vim4-npu-adla`，基于
`213f271505411`。正式部署锁不变。驱动在 `drivers/misc/adla`：其接口是
下游闭源 SDK 字符设备兼容接口，本轮不声明 DRM accel 支持。

## 第三轮离线状态

内核分支为 `vim4-npu-adla`，第三轮提交：
`efd8fb22f425d`（恢复顺序、错误传播、PM回滚、范围检查与宿主测试），
`ec52a0f711cd7`（取消计数与供电失败测试），
`40c653d43f711`（移除端口适配引入的未使用探测函数）。
输出目录为VM `~/build/npu-adla1`，独立release为
`7.3.0-vim4kvm-npu1+`，不修改正式源码锁或uhd1模块目录。
最终完整构建与打包通过，载荷有2338个模块，内核build ID为
`5f66186d0cc2e53b89c4bbf91226ec7b0b70d6ce`；M0 DTB的ADLA状态为okay。
主仓配套提交为`306c744`，303项unittest通过、7项跳过。

恢复先完成软复位，再发布失败完成事件，避免close提前释放DMA页。
WAIT改用可中断等待，按invoke查询完成状态；超时返回ETIMEDOUT，
硬件/恢复失败返回EIO，信号中断保留内核等待错误。GET_STAT同样报告失败。
正常取消/close释放资源；close等待DMA静止有界，不能在等待失败后继续释放。

**无法确认DMA停止时不允许释放可能仍被硬件访问的页。** 当前实现锁定故障状态、
拒绝后续请求、保留模块与相关DMA/IOVA资源直到重启，并禁止sysfs解绑。
这不等于该异常路径已经满足“全部资源回收”；该例外仍需用户决策，
且故障停止/复位的硬件效果不能由宿主测试证明。

标准PM路径处理resume-and-get、父时钟、设频和启钟失败；引用失败回滚，
regulator由devres行动成对释放。IRQ注册先于worker启动，避免probe失败时
在持有dev_mutex期间等待需要该锁的worker退出。
worker所需定时器在启动前分配，创建失败不再被解锁的返回值覆盖。

宿主测试运行实际C函数或实际错误状态分支，以控制事件替代硬件：
`test_iova.py`覆盖分配失败、排除区、碎片复用、耗尽和回收；
`test_platform.py`覆盖PM/时钟及regulator各步失败回滚；
`test_lifecycle.py`覆盖复位与完成顺序、WAIT错误、信号和close；
`test_cancel.py`覆盖pending/finished计数及scheduled取消时保留任务。
IOVA、生命周期和取消测试启用ASan/UBSan；边界与ABI测试继续保留。
这些测试不证明真实页表、缓存、中断、电源域或DMA停止。

构建/验证日志位于上述输出目录：
`r3-delivery-build.log`、`r3-delivery-package.log`、`r3-w1-all.log`、`r3-sparse-real.log`、
`r3-schema.log`、`r3-dtb.log`。
系统sparse 0.6.4曾被内核跳过，旧C=2成功退出不能算sparse通过；
实际检查使用私有sparse 84ec0658c81d，安装在 `~/build/sparse-npu`。
新增核心适配strict checkpatch清零；取消测试提交的MAINTAINERS提醒由已有
`F: drivers/misc/adla/test*.py`覆盖，单独记录该元数据提示，不隐藏代码诊断。

W=1存量诊断分类：未使用赋值变量13、缺失原型11、旧式inline声明5、
printf属性建议4、fallthrough 1、格式符1；另有旧模板kernel-doc警告。
按相对上一轮的新增行范围比对，W=1诊断没有命中新改代码。
这些是存量清单，不代表整个驱动无告警；sparse另按实际日志记录。
实际sparse执行了24个CHECK；新增行未命中诊断。存量包括类型/地址空间不匹配49、
gfp_t退化6、整数NULL 3、符号未声明13（其中1个来自内核vDSO），以及上述编译器告警。
这些诊断没有通过关闭W=1、sparse或全文件格式化规避。
T7C固定启用内部MMU后产生的未使用属性探测函数已删除，不归入厂商存量免责项。

## 兼容合同

保持 `/dev/adla0`、magic X 的 ioctl、packed 外层结构、嵌套 task/fixup、
QUERYCAP 的 NULL 查询长度、ioctl 内映射和 UID mmap。
`/sys/class/adla/adla0/device/debug/{hw_info,clk_core,dpm_period}` 的路径及
hw_info 文本标签属于兼容合同，不以 debugfs 取代。
保留 KMD 1.4.0.3 标识不意味着已完成硬件验收。

5.15 本板只读启动日志确认 `nn_adj_vol=0, package=1, efuse=2`，设置
890000 µV；原日志的 `mv` 标签错误，代码单位是 µV。候选不引入多频 OPP。
证据来自第二轮只读 `dmesg`：`ADLA KMD nn_adj_vol = 0, nn_package_id = 1,
nn_efuse_type = 2`，随后打印 `regulator_set_voltage 890000mv OK`。
厂商实现见 `common_drivers/drivers/adla/kmd/drv/port/platform/linux/adlak_regulator.c:159`
（890000常量）、`:198`（nn_adj_vol=0分支）、`:231`（regulator_set_voltage）。
这是驱动请求值及API成功日志，**不是物理电压测量，也不是regulator_get_voltage读回**；
下一轮须核对5.15 regulator读回与7.3读回，并记录对应频率和板型。
DT 计算时钟设 800 MHz，实际工作频率需下轮基线记录，不能当作本轮实测。

## 模型和工具

固定 Khadas 提交与六个文件的 SHA256 在 `tools/npu-models.json`。
不提交模型二进制。检测模型选 YOLOv8n，尚未在本板执行，不能称为已验证。

```sh
python3 tools/npu-validate.py prepare build/npu-models
cc -O2 -Wall -Wextra tools/npu-probe.c -lnnsdk -lm -o build/npu-probe-bin
python3 tools/npu-validate.py run --help
python3 tools/npu-validate.py compare baseline/result.json candidate/result.json
```

prepare 在开发机执行，需要 Pillow；生成 BGR HWC 或灰度 float32，记录 Pillow
版本与输入哈希。两内核必须使用同一份输入文件，不能各自重新生成。
run 要求显式模型/输入 SHA，输出目录必须不存在。101轮包含一次预热；逐轮保存
全部张量，比较时每个文件大小和 SHA 必须一致，再检查平均退化不超过5%，
同时报告 P50/P99/最大值。输出差异直接失败；分析差异不自动放宽标准。
本工具不证明采样环境可比，需窗口负责人控制频率、温度、视频负载并重复配对。

超时先 TERM 后 KILL，均有界；D态进程不能靠用户态清理保证消失，必须报告，
不能继续复用硬件。工具不删除旧目录，不发 HID、不测声音、不 ptrace 视频进程。

独立UAPI程序在VM编译，须使用候选内核UAPI头：

```sh
cc -Wall -Wextra -Werror \
  -I ~/src/linux-7.3-npu/drivers/misc/adla/drv/uapi \
  -I ~/src/linux-7.3-npu/drivers/misc/adla/drv/uapi/linux \
  tools/npu-uapi-probe.c -o npu-uapi-probe
timeout 30 ./npu-uapi-probe attach
timeout 30 ./npu-uapi-probe profile
```

attach从REQBUF取得连续页后再导入同一物理页，验证映射别名并先detach再free；
不会导入任意猜测的物理地址。profile连续两次测试无network错误路径，覆盖互斥锁释放。
正向profiling另用同一C probe追加第五参数 `--profile`，执行SDK的enable/get/disable，
须与普通性能测量分开运行。本轮只编译，没有运行这些硬件程序。

## 独立候选产物与一次性启动准备

完整构建、DTB和匹配模块来自VM `~/build/npu-adla1`；载荷目录为
`~/build/npu1-candidate`，manifest记录源码、build ID、配置和全模块哈希。
不向正式sources.toml登记，不发布、不修改板上启动文件。
打包器新增显式 `--release 7.3.0-vim4kvm-npu1+`，默认uhd1合同保持。
静态PID 1由display-once-init.c以 `-DADLA_TRIAL` 和独立RELEASE构建；
校验运行build ID后创建独立模块挂载点，失败重启回默认。
现有启动器按release白名单分派，npu1须配套更新vim4-board-runtime、vim4-kvm-run、
one-kvm-edge、mainline-prepare和mainline-gadget-prepare，才能沿用Wave5运行时。
这些候选文件另放载荷的runtime目录并记录哈希；本轮不安装。下一轮先备份并核对
5.15路径行为，再安装这些仅增加npu1分派的文件，不重启服务，随后采集baseline证明。
baseline证明还须包含这五份运行时文件的哈希，避免一次性启动使用不同路由。

最终一次性bundle须使用下一轮刚读出的5.15证明，不能拿历史启动文件哈希冒充当前状态：

```sh
python3 packaging/kernel-edge/display-once.py prepare \
  --payload ~/build/npu1-candidate --init ~/build/npu-adla1/npu-once-init \
  --baseline baseline-515.json --output ~/build/npu1-once \
  --release 7.3.0-vim4kvm-npu1+ \
  --baseline-release 5.15.137-vim4kvm-hdrdual6 --baseline-id BASELINE_BUILD_ID
```

BASELINE_BUILD_ID必须替换为实际40位GNU build ID；proof须含cmdline、启动文件与运行时登记哈希。
prepare只读输入并写新目录，不stage、不SSH、不重启。下一轮stage仍须root、板锁/媒体锁、
当前release/build ID、cmdline和全部文件哈希一致；U-Boot只在RAM执行生成的sysboot命令。
已经离线测试跨release归档和基线身份保持；真实启动、模块加载和用户态适配不能离线证明。

## 下一轮上板顺序

1. 先在5.15持板锁和媒体锁，记录SDK/模型/输入/内核哈希、实际频率和电压。
   用同一工具采集三模型逐轮完整输出与计时，外部物理地址导入和profiling另测。
2. 离线门禁全部完成后才准备7.3一次性启动；保留5.15默认，不覆盖正式源码锁。
   Image/DTB/modules须来自同次完整构建。
3. 三模型输出字节一致、配对平均退化≤5%；性能不通过就不登记为追平。
4. 计数器证明提交/中断推进、空闲门控及再唤醒；区分温度计持域与计算时钟。
5. 受控超时、取消、进程退出、软复位恢复与失败状态；不盲写寄存器注入。
6. 与HDMI/Wave5固定运动负载并行，检查帧推进、错误、超时和NPU尾延迟。

每项≤10分钟，只用脚本和计数器；不发HID（被控机为Mac mini M6），不测声音。
整机挂起另需平台PM资格，不能用设备clock-gating替代。
预计板上独占约55–75分钟：5.15基线与接口测试10–15分钟，候选准备/启动/回退10–15分钟，
三模型输出与配对性能10–15分钟，PM/超时/退出10–15分钟，视频并行10分钟，收尾5分钟。
按多个≤10分钟小项执行；任何oops、DMA错误或输出不一致立即停止本项，不扩大故障注入。
