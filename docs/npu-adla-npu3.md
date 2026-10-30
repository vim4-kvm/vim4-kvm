# ADLA npu3：离线修复与下一窗口

本轮未访问板子；GPU分支、主仓GPU改动不回滚、不混入提交。保页例外仍为
**代理暂定，待用户确认**。本文区分可复现的代码缺陷与尚未在硬件上闭合的因果链。

## YOLO：创建失败先于DMA执行

证据为上一轮`build/npu-board-20261030-r6/`的完整输出、probe.log、dmesg：
每轮有一次INVOKE失败，101次task create fail；第三输出为固定量化零对应的浮点常量，
前两个输出正确。`adlak_submit.c`的adlak_invoke_add_queue在adlak_invoke_create失败后
直接退出，尚未加入待执行队列。**这条失败路径不执行命令补丁、DMA提交或输出缓存同步**，
不能把该task create错误归因于执行中的DMA方向、缓存或IOVA映射。
大对象分配、用户复制等失败分支另有专门日志，现场没有对应日志。

已确认并用实际C校验块复现两处误拒绝：

- npu2的`:980–988`始终用task.config_size校验地址fixup；命令发射器在压缩模式
  选择config_v2.common_size。合法common_size=128、config_size=0、loc=124被错误拒绝。
- count=0的fixup区间根本不会被遍历，旧校验仍要求其offset落入本次fixup数组；
  空数组带未使用的模型全局offset会被拒绝。现在空区间不访问offset，非空/负count仍严格检查。

修复后的注册校验也按实际格式选择命令来源：压缩common/modify范围以其DMA缓冲区长度为界，
不拿旧config_total_size作上限；reg/dep/address fixup均使用对应命令长度。
复制失败不再把pmodel_attr改成ERR_PTR后又解引用清理；失败返回保留具体errno，
计数/保留task只在校验成功后更新。运行中的单个保留task禁止重复使用。
拒绝路径新增限频诊断，记录task/fixup索引、范围、loc/shift/unit/size，不泄露用户指针。

**关联的限度**：已有日志没有被拒task/fixup的原始参数，无法离线证明YOLO现场具体命中
上述哪一个条件。创建拒绝与缺少第三输出具有明确的时序对应，但npu3仍须做到
101轮全字节一致、task create计数0，才能确认该模型已修好；不把合成回归当作真实模型通过。
闭源SDK会吞掉内部INVOKE失败并返回有限输出，内核errno改进不能替代全张量比较。
最终bc8324源码入口：`drv/common/adlak_submit.c:719`选择注册时的命令范围，
`:991`选择invoke的fixup长度，`:1219`为创建失败到入队之间的分界；`:2020`为执行器的对应选择。

## cancel、WAIT与close的释放顺序

以下路径相对VM `~/src/linux-7.3-npu/drivers/misc/adla/`：

| 缺陷证据 | 修复与可观察合同 |
|---|---|
| drv/common/adlak_submit.c原:1524：取消忽略删除返回值；待执行任务被删除，运行任务只置flag；WAIT找不到终态就继续等 | 保留每个context最近invoke的终态；取消成功后WAIT/GET_STAT明确返回ECANCELED，下一有效提交才清除 |
| drv/port/platform/linux/adlak_fops.c原:300：CANCEL持dev_mutex；worker循环也需要该锁 | 取消修改队列后释放dev_mutex再等待排空，避免锁住worker；接口有5秒排空上限，失败返回明确错误 |
| drv/common/adlak_inference.c原:76：IRQ等待可很长，取消不唤醒worker | worker使用10ms等待片检查取消（另有jiffy取整/调度延迟），不伪造IRQ；取消走软复位，确认停止DMA后再退役任务 |
| drv/common/adlak_submit.c原:1799：WAIT超时直接返回；adlak_mm.c:175随后因invoke_cnt非零拒绝FREEBUF | WAIT超时先取消并等待排空，再返回ETIMEDOUT；GET_STAT保留同一超时终态，避免把“用户等待到期”当作“DMA已停止” |
| 完成通知后worker仍通过ptask访问context | 在队列锁内先清除共享task指针，再通知；移除worker在解锁后的context解引用，防止close/CANCEL回收与通知竞争 |
| close等待到期没有迟到完成的回收所有者 | context移交给完成事件驱动的work；确认DMA停止后回收DMA/IOVA/映射并归还模块引用。专用workqueue由devres排空，避免卸载与回调竞争 |

正常取消、超时、close不设置全局wedged来掩盖回收问题。close若暂时超过等待上限，
由上述work负责迟到清理，不以重启作为正常回收机制。真实软复位失败仍明确报错并保留
可能被DMA使用的页；其硬件停止效果和该例外政策仍不能算作已验收。
取消退役任务后，SDK仍拥有显式REQBUF缓冲；由后续FREEBUF/detach/close释放，
不能为“回收成功”而抢先释放仍由SDK复用的模型缓冲。

宿主测试执行实际C函数/代码块，覆盖：压缩与旧格式末端fixup、空区间、越界及unit=0；
pending/finished计数、运行取消、复位失败不提前释放；有限/无限IRQ等待的取消；
WAIT超时排空；迟到close移交→完成→回收、通知前引用退役、模块引用归还。
既有IOVA分配回收/失败回滚、ABI和边界测试保留；ASan/UBSan继续用于相应harness。
最终入口为`drv/common/adlak_submit.c:1546`（取消）、`:1690`（引用退役/通知）、
`:1849`（WAIT排空），`drv/common/adlak_context.c:41`、`:164`（迟到回收），
`drv/common/adlak_inference.c:408`、`:435`（取消后的软复位完成路径）。

## Wave5：恢复正式uhd1候选策略

已保存的正式7.3配置`build/gpu-runtime/extlinux-before.conf:30`使用
`cma=512M@0x10000000-0xf0000000`及
`modprobe.blacklist=crg_udc,t7_hdmirx,t7_vdin_test,wave5`，由匹配服务显式加载这些模块。
npu2沿用了5.15命令行，没有cma参数；其UART明确为
`Reserved 256 MiB at 0x00000000cf000000`，与CONFIG_CMA_SIZE_MBYTES=256一致。
该地址仍低于4 GiB，不能误判为Wave5 32位DMA掩码覆盖不到。

新打包器只改候选APPEND：将CMA容量/可分配范围及冷插拔黑名单恢复到上述uhd1策略，
保留HDMI/VDIN匹配模块选项。原始baseline_cmdline/哈希证明保持原样。
ADLA DT无独占reserved-memory或memory-region；相对213f271505411的DT变更是ADLA节点、
板级enable/supply，不是新增CMA预留。npu2的256MiB配置差异已证实；它是否足以解释
全部Wave5 -ENOMEM，仍需npu3先做NPU关闭的4K视频基线，不能离线宣布编码已恢复。

## 交付与验证

内核分支vim4-npu-adla，npu3使用独立`7.3.0-vim4kvm-npu3+`；
VM输出`~/build/npu-adla3`、载荷`~/build/npu3-candidate`。
旧npu1/npu2载荷保留。中间未交付的npu3草稿另存，不得用于上板。
静态PID1、Image/DTB及完整匹配模块一起打包；五个助手只增加npu3白名单，5.15分支不变。
最终bundle仍需下一窗口新现场证明后prepare/stage，本轮不伪造证明、不部署。
下一窗口按载荷runtime清单备份/安装匹配助手，再取证明；使用主仓新版打包器，不能复用npu2的旧脚本：

```sh
python3 packaging/kernel-edge/display-once.py prepare \
  --payload ~/build/npu3-candidate --init ~/build/npu3-candidate/npu-once-init \
  --baseline baseline-current.json --output ~/build/npu3-once \
  --release 7.3.0-vim4kvm-npu3+ \
  --baseline-release CURRENT_RELEASE --baseline-id CURRENT_BUILD_ID
```

CURRENT_RELEASE/CURRENT_BUILD_ID替换为现场默认内核读回；原始cmdline及文件证明必须匹配后才能stage。

| 产物/验证 | 结果 |
|---|---|
| 内核提交 | `cfabbf9a71f80`（校验/取消）、`bc8324ccb9292`（迟到close与引用退役） |
| 主仓代码提交 | `09e3a33`（npu3路由、CMA与冷插拔策略） |
| build ID | `3a822b8a9f47a8f1a8a74016e5128d9d14d104f5` |
| Image SHA256 | `e391ec1ebd2093b4674983e2304cc037ac0930a13c1ccf972bc3dd828cd745db` |
| 完整构建/打包 | Image/dtbs/modules、2338个匹配模块；归档内逐文件SHA与静态PID1 ELF/release独立校验通过 |
| checkpatch strict | 累计补丁0 errors/0 warnings/0 checks |
| 宿主测试 | 四个Python harness（含新增真实代码回归）、bounds/ABI C测试通过 |
| schema/DT | ADLA binding和匹配DT检查通过 |
| W=1/sparse | 实际24个CHECK；厂商存量声明/类型/kernel-doc等诊断保留，包括原有adlak_submit_wait缺少原型提示，不宣称全驱动零警告 |
| 主仓unittest | 308项，7跳过，其余通过；不混入GPU文件 |

本机载荷副本为`build/npu-r7/candidate/`；VM日志位于`~/build/npu-adla3/`的
`full.log`、`verified-build.log`、`w1-sparse.log`、`host-tests.log`、`schema.log`、
`dtbs-check.log`、`checkpatch.log`、`package.log`。上述全部是离线门禁，不能当作YOLO或视频实测通过。

## 下一窗口≤30分钟

| 分钟 | 门禁 |
|---|---|
| 0–5 | 独占锁、5.15默认/服务/UDC/启动文件备份核对；刷新现场证明，核对旧SDK/探针/模型输入SHA；RAM一次性启动npu3 |
| 5–10 | 确认CmaTotal=512MiB且区域位于规定范围，ADLA/HDMI probe正常；先NPU关闭跑HDMI＋Wave5，编码推进、无ENOMEM，失败则本项停止 |
| 10–15 | 三模型101轮完整输出对照既有5.15，重点YOLO第三输出和task create计数0；报告均值/P50/P99/max，字节差异直接失败 |
| 15–21 | 同一context反复cancel/短WAIT超时/close/kill；记录终态errno、pending/scheduled/finished、内存/IOVA可得计数及后续正确输出；无释放失败或残留上下文。单项timeout≤5分钟 |
| 21–25 | 同一视频会话NPU关/开，比较帧推进、编码错误/丢帧与NPU延迟，保持运动源条件，不主动操纵被控机 |
| 25–30 | 普通重启回5.15，恢复助手，核对全部启动文件哈希、四服务和UDC；保存数据并释放锁 |

不发HID（另一台Mac mini M6）、不测声音、不ptrace、不写PWM、不猜电压，测量不并行编译。
不注入真实硬件挂死；计数接口不足不能以CmaFree单点代替全部IOVA回收证明。
发生oops、probe失败、输出错误即停本项；板子无法自动恢复则停止并报告。
