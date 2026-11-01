# 2026-10-31：P0-3 真实挂死注入安全审查

**E03 未完成：已有正式恢复实现，但没有获准直接上板的真实挂死注入方法。**
本轮只做离线核对与夹具验证，未占板、未 SSH、未注入、未重启。
存在需物理 RESET 的历史证据或尚未排除的总线风险，按本任务安全要求停止上板。
未新增危险注入入口，未移除保护，未更新源码/产物部署锁。

## 正式分支现状

主仓独立 worktree `../vim4-kvm-p0-3`，分支 `p0-3`，起点 `c7c2342`。
内核独立 worktree `/home/deepdream/src/linux-7.3-p0-3`，分支
`p0-3-wave5-recovery`，起点为 fetch 后的正式分支
`dc220366a1222a03423d5b5987fab3f027ec1d7a`。未切换或覆盖其他内核工作树。

```sh
git fetch origin
git rev-list --count 39d42b6393f9 ^origin/vim4-kvm-7.3
# 0
```

因此[恢复分支](2026-10-23-wave5-genpd-recovery.md)已进入正式历史，
不能再次把它当作待移植实现。[五轮软件注入](2026-10-23-wave5-runtime-window.md)
仍只证明健康固件上的恢复路径，不证明真正挂死后恢复。

本轮按上述正式提交审查以下生产入口（目录前缀为
`drivers/media/platform/chips-media/wave5/`）：

| 入口 | 当前实际行为 |
|---|---|
| `wave5-hw.c:wave5_wait_vpu_busy()` | 真实 BUSY 轮询超时会隔离；`timeout_command` 仅在 BUSY 已清零后伪造超时，不能作固件挂死证据 |
| `wave5-isolation.c:wave5_job_timeout_work()` / `wave5_vpu_job_abort()` | 帧 watchdog 5秒、abort 等待1秒，触发全设备恢复；IRQ 同步后让旧实例 queue_error、scheduler 单次完成 |
| `wave5-vpu.c:wave5_vpu_recover_hardware()` | checked FIO 排空及 ON_BOOT 内部复位，genpd OFF/ON 通知确认，PC=0 检查，复制保存的固件镜像并冷 INIT；不依赖固件 SLEEP |
| `wave5-isolation.c:wave5_recover()` | dev→irq→hw 锁；旧 fd 永久错误，成功后仅新 open 可用；同步旧 IRQ/FIFO；成功后回收延期 DMA 所有权 |
| `wave5_quarantine_memops` | 恢复未成功前保留 MMAP/export/import backing、attachment 和映射；失败保留到重启，不能以 job_finish 证明 DMA 停止 |

源代码支持“尝试恢复，失败隔离”，并非必定恢复。真实挂死时 FIO/MMIO 是否仍返回、
bus idle 是否可达、SMC 是否返回，仍是硬件验收缺口。本轮没有测量板上当前运行版本。

厂商参照再次核对固定 `common_drivers@4cfb128d36f8` 的
`drivers/media_modules/frame_sink/encoder/multi/vpu_multi.c:vpu_hw_reset()`：仍仅返回0。
VM 当前 CD HEAD 为 `563cff9dab2c8cd44590bf57c8ffaa7e2dae35e1`，同函数仍为空操作，
`hw_reset()` 仍写 `0xfe000044 bit28`。该地址与 ACODEC 门控冲突的推导见
[既有审查](2026-10-23-wave5-runtime-recovery.md)，不能据函数名作为安全复位依据。
不重写已有 genpd 生命周期实现，也不改为未确认的桥 reset。

## 注入方法与安全门槛

“可重复发起”与“确实导致固件不再执行”是两个条件。一次命令拒绝、流不出帧、
驱动伪造 ETIMEDOUT 均不足以证明后者。下面均为设计审查，未实现或执行。

| 方法 | 可控性与真实挂死判据 | 板子风险与结论 |
|---|---|---|
| 非法 opcode / 合法地址内的非法编码参数 | 一次性替换命令或字段，可固定输入；固件可能直接拒绝，须证明实际进入停滞路径 | 未知 opcode 的固件分支不可审查，参数可能影响访问范围；没有保证不会发出越界 DMA。不能先上板枚举 |
| 重放历史非对齐 HEVC | 固定旧参数与录制源；历史只有超时现象，未取得固件 PC/等待链 | [历史复现](2026-10-22-wave5-hevc-hang-analysis.md)两次1366×768超时，退出/重启挂起，最终物理 RESET。不能移除现有几何保护来试验 |
| 破坏 bitstream 内容 | 编码器的 bitstream 是输出；仅改输出内容通常不影响固件执行。解码畸形输入属于另一条路径 | 不能用接收端解码失败证明编码固件挂死；不扩张为硬件解码器测试 |
| 错误 DMA 地址 / 缩短映射 | 可固定一次地址替换，但不能约束设备最终访问范围 | 越界写、访问无响应目标或 AXI outstanding 不消退，可能造成内存损坏、external abort 或整机挂死；禁止直接上板 |
| ENC_PIC 中途停 A/B/C 时钟 | 可使硬件停止推进，但首先属于外部停机，不等于固件内部死循环 | 未取得各时钟与 AXI/APB/FIO 依赖合同；可能使恢复第一步的 MMIO/FIO 永不返回。软件 timeout 无法打断不返回的总线读；禁止直接上板 |
| VCPU restart / core-start 写零、仅停 VCPU 请求 | 寄存器名称不定义 halt 语义；现有代码仅用 core-start=1启动。停请求可能只让取指等待 | 未找到 T7 专用 halt/ack 与在途事务契约，不能从定义或正常 reset 序列推出任意时刻停机安全；暂不实现 |
| 专用测试固件的受控死循环 | 首选后续方向：在已解析 ENC_PIC、尚未发帧 DMA 的明确点进入无访存循环，保留宿主总线与独立复位接口 | 需要可审查的 Wave521C 固件源码/厂商测试镜像、入口协议和总线隔离合同。当前没有这些材料；未猜测 ISA 或修改二进制指令 |

推荐的测试固件协议：默认正常；仅一个实例、一次 token 触发；先写专用 ACK/token，
随后在片上执行循环，不关外部时钟、不写共享域、不发新 DMA；宿主真实发 ENC_PIC，
以硬件 BUSY/完成不响应及固件 ACK 证明已进入停滞。测试镜像与正常镜像都固定哈希，
恢复冷加载正常镜像后重新编码。若选择不同镜像，须另实现并测试镜像选择和失败 unwind；
现有恢复只重载 probe 时保存的同一镜像，不能假定已支持切换。

上板前还须有独立于该循环、针对 T7 的证据，证明 APB/FIO 可继续访问、stop 能排空
已接受的 AXI 事务、内部 reset 和 DOS_WAVE OFF/ON 不依赖 VCPU 应答。
可以由厂商合同和可审查实现/硬件仿真补足；宿主 mock 只能验软件顺序，不能证明这些性质。
PC 多次相同也可能是正常空闲循环，单凭此值不作为挂死判据。

## 验收方案与保护退出条件

取得上述安全证据并完成代码、strict checkpatch、宿主/KUnit适用项及完整候选构建后，
使用现有 `board-queue` / `board-window`，申请≤30分钟窗口，采样时禁编译。
首次仅一轮；任何 MMIO/FIO、idle、OFF/ON、INIT 异常立即停止，不绕过 drain 强制断电。
确认可恢复后再做累计≥5轮，不重新启动整机或服务来代偿恢复。

每轮保留注入 token、固件/内核/模块哈希、真实停滞确认、恢复阶段与单调时钟、旧 fd EIO、
新实例编码、浏览器真实 `framesDecoded` 增量、尺寸/codec和运动像素摘要。
同负载预热后、恢复后与关闭全部测试消费者后的 CMA/fd/映射分别记录；不能将单点
CmaFree 或运行中池大小差当作泄漏结论。每轮比较完整内核日志，无新增 WARNING/oops。
最后同连接连续接收约300秒，确认全窗口帧数推进；只确认音频服务状态，不测声音，
不向开发 Mac 发 HID；批次结束回5.15并核对身份/服务/默认文件。

失败隔离仍是必要兜底。即使五轮成功，也不据此删除 DMA 保留：必须另证明每个复位失败
分支在归还 buffer 前已经停止 DMA。尺寸/AVC回退保护的退出另需原危险参数的等效编码、
实际可见尺寸、边界与逐帧解码证据；本轮不满足。任何保护删除须单独提交。

## 本轮验证与交付边界

通过 `board-queue run --heavy --who P0-3 --purpose wave5-offline-fixtures --max-min 15`
在 VM 运行正式提交的全部12个 Wave5 `test_*.py` 及
`drivers/pmdomain/amlogic/test_secure_pwrc.py`，退出0：包含51项 FIO/reset、
冷加载8个失败边界/5种注入、12项 PWRC转换与隔离/延期回收夹具。
这些是既有生产代码的宿主模型复验，没有新增 KUnit 用例或真实硬件证明。

本轮无内核代码/DT改动，checkpatch、dt-binding 和内核构建不适用，未声称执行。
主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：365项、14 skipped、OK。
原始本机证据保存在
`logs/p0-3-wave5/{register-audit.txt,fixtures.log,source-audit.txt,unittest.log}`，未纳入 Git。

| 上板门禁 | 本轮结果 |
|---|---|
| 真实挂死≥5次、运行时复位/冷加载 | 未运行：安全前置证据不足 |
| 每轮 WARNING/oops、CMA、恢复耗时 | 未测量 |
| 恢复后真实解码帧数、300秒KVM冒烟 | 未运行 |
| 回5.15 | 不适用：本轮没有进入候选 |

P0-1交接：正式内核已含 `39d42b6393f92c4a5bc4bf6d73877dcb83c7d257`；
本轮审查基点 `dc220366a1222a03423d5b5987fab3f027ec1d7a` 无新增内核提交。
不得将 E03 标为通过，不应因本轮推进统一候选的内核锁或退出保护。
文档以独立 `p0-3` 分支交付；未满足内核合入条件，不推正式内核分支。
下一步需要安全测试固件及 T7 停机/总线合同；单纯允许冒险或准备 RESET 不满足本任务前置条件。
