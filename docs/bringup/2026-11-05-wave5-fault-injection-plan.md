# 2026-11-05：Wave5 离线故障注入方案

本记录只准备后续批量占板输入，未运行任何注入、未访问板子。
目标是验证原挂死、隔离、复位、恢复 mock 所防的真实 DMA 所有权风险，
不是用返回错误模拟总线停机。所有场景当前均为**待实板**。
迁移背景与原风险见 [Wave5 结果](2026-11-05-wave5-kunit-results.md)及其清单链接。

## 注入接口与安全边界

源码入口相对内核 `drivers/media/platform/chips-media/wave5/`：

| 点 | 标注与调用者约束 | 可验证的失败 |
|---|---|---|
| `wave5-hw.c:wave5_vpu_enc_finish_seq` | ERRNO；唯一调用者 `wave5-vpuapi.c:wave5_vpu_enc_close` 在调用前清零 `fail_res`，检查负返回值并释放本次 PM/锁引用，不标记 destroyed、不释放 DMA；`wave5_stop_encoder` 随后执行隔离 | DESTROY 未完成时 close/STREAMOFF 的错误回收、隔离与后续恢复 |
| `wave5-hw.c:wave5_vpu_reset` | ERRNO；入口已有不修改状态的参数错误分支；初始化、重初始化、恢复及 remove 调用者均检查失败，不能把返回错误当作 DMA 停止 | 恢复复位失败时停止恢复、永久隔离和保留 DMA；不证明复位内部的总线时序 |

两处 `ALLOW_ERROR_INJECTION(..., ERRNO)` 均用 `CONFIG_FAIL_FUNCTION` 包围。
其 Kconfig 依赖链经过 FAULT_INJECTION、DEBUG_KERNEL、debugfs 与
FUNCTION_ERROR_INJECTION/KPROBES。生产配置关闭 FAIL_FUNCTION 时，
即使 FUNCTION_ERROR_INJECTION 开启也不生成这两个 whitelist 条目。
不加新模块参数、私有 ABI 或默认开启的注入逻辑；生产函数体与调用顺序不变。

按同一源码树的 `Documentation/fault-injection/fault-injection.rst` 中
“Error Injectable Functions”审查，不能给 `wave5_vpu_wait_interrupt` 或
`wave5_wait_vpu_busy` 直接加入口错误标注：它们的超时分支承担隔离副作用，
跳过函数体会绕开这个义务。`wave5_vpu_recover_hardware` 入口还消费旧的
`recovery_fail_step`，也未直接标注。旧 `timeout_command` 和
`recovery_fail_step` 不是本方案使用的标准注入接口；本方案要求它们保持零。

调试候选需显式启用 FAIL_FUNCTION 的依赖，以及 KASAN、DMA_API_DEBUG、
DEBUG_LIST、PROVE_LOCKING；failslab/FAIL_PAGE_ALLOC 场景另启用相应能力。
用实际 `.config` 核对 Kconfig 依赖结果；配置片段本身不能证明已启用。
生产配置以[当前构建配置](../../packaging/kernel/kernel.config)为依据，不改 release 配置。

## 后续窗口的公共步骤

遵循[板窗规则](../board-window.md)，离线先准备匹配 Image、模块、配置与符号，
核对 build ID、源提交、平台设备与编码节点；批量 RAM 启动，预留恢复时间。
独立 UART 持续取证；暂停会自动重启或重建编码器的管理服务，由窗口统一管理。
先以无注入候选跑通短编码和正常停止，失败则不进入注入。

fail_function 是全局注入器，只选择表中 Wave5 符号；不对通用 PM、DMA、IRQ
函数任意加标注或全局返回错误。恢复运行在 worker 上，不能只对用户 PID
设 task-filter 并假定 worker 也会中招。窗口须隔离其他 Wave5 使用者。
以下是待板端执行的配置顺序，**本轮没有执行**：

1. 核对 debugfs `fail_function/injectable` 包含目标，禁用概率并清空旧目标。
2. 写入目标名，在各自 `retval` 用 `printf '%#x' -110` 设置 ERRNO；
   核对回读值。按该内核文档设置 space 为零、interval 为一、verbose 为二，
   task-filter 关闭。只在选定符号且独占 Wave5 时启用。
3. 单点场景设置 times 为一；组合场景设置为二。最后才设置 probability 为满值。
   禁止配置 fail-nth：它会覆盖一般属性并可能同时影响其他注入器。
4. 按下表触发一次，保存配置前后值、内核注入日志/调用栈和工具原始输出。
   times 未消耗或无法确认实际目标时记“未命中”，不能记通过。
5. 禁用概率、清除目标；保留日志和故障状态。若进入永久隔离，禁止下一次编码、
   rmmod 或热解绑，按窗口恢复流程正常重启一次；硬锁按 UART/看门狗恢复交接。

不对整个窗口持续设置无穷次注入。注入配置写入失败、剩余任务、锁告警、Oops、
DMA/KASAN 报告或恢复预算不足均立即终止后续场景，不循环重试。

## 场景、预期与判定

| 场景与原风险 | 注入/负载 | 预期行为与通过标准 |
|---|---|---|
| H1：`test_hang` 的 active close/IRQ 交错 | 成功开始编码后选 finish_seq，分别执行 TERM close、OUTPUT 先 STREAMOFF、CAPTURE 先 STREAMOFF；每次独立单点注入 | 关闭有界返回；destroy 失败进入隔离，不把未完成画面报 DONE；调度等待被唤醒。允许恢复成功后清掉硬件隔离，但旧实例须报错、不能重新提交；重新打开后标准流可正常编码 |
| H2：`test_buffers`/`test_encoder_cleanup` 的 lookahead 与 destroy 失败 | 同 H1，额外持有 DMA-BUF 导入、MMAP 与导出引用，先确认有实际在途编码帧 | 完成恢复之前无释放仍由硬件占用的 plane/辅助缓冲，无越界、重复完成或双重释放；成功停机后引用按持有人关闭回收。用户 fd/VMA 消失不能被当作 DMA 已停止 |
| I1：`test_isolation` 的多实例与 cancel | 两个编码实例持有不同输入；向其中一个停止路径注入 finish_seq 失败，另一个保持在途/等待 | 所有旧实例的双队列退出等待，无 ioctl/调度锁死；旧实例不再提交；成功恢复后须由新实例重新编码。其他实例不能在恢复完成前复用旧 DMA |
| R1：`test_reset`/`test_recovery` 的恢复停止失败 | 同时选择 finish_seq 与 reset，times 为二；先触发一次已建上下文的停止。只允许这个用户停止和其隔离 worker 消耗两次故障 | 两个点都须有命中证据；第二次发生在恢复复位。进入最终隔离状态，不能掉电/重载/重新开启 IRQ 后继续任务；DMA 映射和模块/设备引用保留，新的编码提交拒绝。不能把仅第一个点命中当作通过 |
| R2：复位入口失败的初始化清理 | 无消费者时仅选择 reset，在新 debug 候选的 probe/初次 INIT 路径测试；与 R1 分开 | 上层停止初始化并报告错误，不启动编码；只回收已证明不归硬件所有的资源。需单独准备候选模块加载工具，不卸载已永久隔离的模块 |
| A1：注册/帧缓冲分配失败 | 使用 failslab 或 fail_page_alloc，限定到执行该分配的测试任务、调用栈/缓存与单次分配；先记录真实分配栈再选一次点，不盲扫全局分配 | 错误返回；已分配但未交硬件的资源回收，交给固件的 DMA 保留至确认停止。KASAN/DMA_API_DEBUG/lockdep 无新报告；每次故障结束后清除注入，再验证短流与重开 |

R1 的 times 是共享计数，不保证自动按两个点各命中一次。若重入或其他调用消耗
预算，结果不成立，保留现场后离线分析，不追加故障“补命中”。
A1 的调试器无法命中 CMA/coherent 路径时记未覆盖，不能用普通 kmalloc 失败替代。
同理，驱动/板端工具支持哪些存储类型和并发实例，以其实际接口为准，不创建假框架。

观察只用已审阅的 `isolated`、`recovering`、`isolation_reason`、
`isolation_time_ns` sysfs 属性、uevent、原始 dmesg、DMA-BUF 引用资料与用户态队列结果，
不扫未供电 MMIO。允许 ftrace/function graph 记录 reset、finish_seq、恢复函数与
DMA 释放路径，先核对 available_filter_functions，记录 PID/时序和注入调用栈。
内存计数回落只作辅助，不能独自证明引用正确或物理 DMA 已停。

每例记录：候选提交/配置/模块身份、负载及存储类型、注入点/errno/命中数、
关闭耗时、所有实例队列状态、隔离/恢复状态变化、DMA 引用的保留/释放边界、
诊断日志、恢复后的短流结果。没有命中证据、只看到“没有崩溃”或历史成功均不能通过。

## 仍需准备的内部阶段故障

这些不由两处入口标注覆盖，继续记待实板，不能宣称替代完整原 mock：

| 风险 | 后续准备与观测要求 |
|---|---|
| 真正丢 completion/迟到 IRQ、watchdog/cancel 与 ISR 竞态 | 需在真实完成路径增加仅调试配置的标准 fault_attr/debugfs 点，丢弃一次通知但保留现有超时/隔离路径；必须先审查在哪一侧丢弃不会破坏硬件应答，不能直接注入 wait_interrupt 的返回值 |
| FIO_READY、bus idle、复位完成、bus re-enable 的各阶段超时 | 需逐点审查 read/write 的输出契约，选择无成功副作用依赖的注入点；必须保留实际总线关闭，不伪造 idle 成功；记录复位/总线使能顺序。当前 reset 入口失败没有执行这些阶段 |
| 域 off/on 失败、冷 INIT/reload 失败、恢复中再次隔离 | 需在恢复调用者的真实错误处理边界设计标准 fault_attr/debugfs，保留每个阶段的 PM 引用平衡；不能对通用 PM 函数全局失败或跳过其 reference-consumption 语义。旧 recovery_fail_step 不作为本方案实现 |

内部点本轮未实现，后续窗口不得直接执行这些未准备好的场景。本轮只新增两处
debug-only 标注，真实掉电、DMA 停止、恢复后数据正确性均未验证。

## 离线验证记录

标注独立提交于内核 `8d3530f41a4db`。
原始日志位于主仓库 `build/kunit-migration/wave5-injection-build.log` 与
`wave5-injection-final.log`。heavy 锁下编译 debug 模块/内建，W=1、有效 sparse、
strict checkpatch 完成；无改动头文件。QEMU arm64 既有 KUnit 9/9，通过期间
没有配置或触发 fail_function。未修改 binding/DTS，未运行板端验证。

debug 对象 `nm` 可见两个 `_eil_addr_wave5_*`；另以 FUNCTION_ERROR_INJECTION=y、
FAULT_INJECTION=n/FAIL_FUNCTION=n、KUNIT=n 重编生产模块，确认两项全部不存在。
这是编译产物排除检查，未加载模块或访问 debugfs。保留原有 vDSO sparse
`__kernel_getrandom` 准备阶段诊断，Wave5 修改范围无诊断；smatch 未安装。
