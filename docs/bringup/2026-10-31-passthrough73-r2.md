# 2026-10-31：7.3透传r2首窗现场阻塞与离线推进

架构推荐和应用改动面见[计划](../passthrough-73-plan.md#r2-架构决定独立常驻采集与分发服务)。
采用独立常驻V4L2/PRIME分发服务，撤销显示依赖One-KVM的接入方式。

## 首窗读回

经Mac共用队列 `run --who passthrough --purpose r2-native-probe --max-min 30`
执行 `board-window collect` 及已审阅的TX具名状态读取；票据已释放。
队列order=64，持有约1.71秒，读回后立即退出，未等待工具构建或在板票据内编译。
实际运行 `5.15.137-vim4kvm-hdrdual6`，默认extlinux仍指该版本。
One-KVM/板级服务状态及UDC configured记录在collect产物中。

| OUT读回 | 结果 |
|---|---|
| hpd_state | 0 |
| rawedid | 仅换行，无EDID字节 |
| ready | 0 |
| disp_mode | active/tmds/时序均0，name=(null) |
| 原uhd4 build-ID候选目录 | 已存在，未覆盖、删除或重命名 |

这些读回表明当前TX看不到sink，不能确认实际OUT接线目标，也不能归因于7.3候选。
遵守“需要物理动作时停止并写明”约束，停止启动、未要求插拔；已询问现有接线信息。
**没有执行boot-candidate，因此native KMS/VD1/VIM4HDMITX/ELD、4K60接收、
CMA/oops/taint增量均未测；没有把5.15状态算作候选通过。**
未切换内核或改板文件，因始终处于5.15，没有执行无意义的return-baseline重启。
这不是完整候选启动/回退窗口，仍待具备有效OUT状态后补齐。

原始证据在本worktree忽略目录 `logs/passthrough73-r2/`（collect JSON、dmesg、
baseline-probe.json、证据包），编排日志 `logs/passthrough-73/window-r2.log`。
全程没有HID、音频播放、ptrace、寄存器盲扫或供电写入。

## payload准备与目录冲突

heavy票据下逐文件核验正式uhd4 payload清单后，复制到VM自己的
`~/build/passthrough73-r2-payload`；仅替换同次构建的M3-video DTB并更新其manifest哈希。
Image/2338模块/One-KVM db848a52与私有GStreamer沿用正式uhd4匹配产物，未重编内核。
DTB SHA为 `f42db15be0296bca8b68b9938f4b23228eed0c7f9db9616d666295a15e7f12f1`。
payload保留在VM，未暂存到板子；不能用该旧路径payload覆盖原build-ID目录。

公共 `board-window-payload-id@65f172d` 随后已提交，后续应评审/复用其命名空间支持，
重制对应PID1/manifest/extlinux再启动。此轮没有改工具或修改该会话工作树。
仅解决目录命名不消除OUT无信号条件。

## 阶段2离线实现

独立服务的[帧租约核心](../../packaging/passthrough73/leases.py)与
[适配合同](../../packaging/passthrough73/README.md)已加入，8项确定性测试通过：
无远程订阅时本地120帧连续、应用切换、disconnect保留scanout、慢客户端latest pending、
旧generation迟到归还拒绝、fault pin、池预算/采集工作槽准入、零消费者及时归还。
本核心只收已完成帧元数据，不进行像素复制；无ioctl/IPC adapter，尚非可运行服务。
后续先接唯一DQBUF/EXPBUF所有者和真实DRM退休，再替换四款应用输入。

离线主仓全套361项、13项按环境跳过，其余通过；新增文档链接检查8项通过。
日志 `logs/passthrough-73/unittest-r2.log`、`docs-r2.log`。本轮未运行KUnit或新内核构建。
