# 2026-11-06：解码功能修复批 A

基于重构 `0ae8beaa56d3a798e8078c5f727c34ed3acafd9c`，完成去门、工具配套、
删 HEVC/VDEC1 实验、单次 RPS resolver 和裁剪回退。按 reviewA 先删实验再去门。只做离线实现；本轮没有板验。
integration39 若修正重构基线，按协调者审定版本 rebase 后重新核验。

## 系列与边界

VM 工作树 `/home/deepdream/src/linux-7.3-vdec-fixes`，分支 `vdec-fixes`，
O= `/home/deepdream/build/vdec-fixes/{kunit,module}`。没有修改其它工作树或构建目录。

| 项 | SHA | 改动 |
|---|---|---|
| K2 | `2ec22a40b8b99987a8e7fca77477c1c019c8f565` | 先删 HEVC 预检和 VDEC1 power_test/mdec_test/register_step 及全部专用诊断状态；正常上电序列展开为私有固定步骤。 |
| K1 | `d6cbbc8f493ce172ab9e4f92fc1c1e9ef02f45a8` | 实验已删除后再去掉三个 bring-up 门，保持 runtime PM 引用边界及硬件安全检查。 |
| K3 | `66413bef83f0ecce995ddae217a5d1ad1425a1ee` | 每 picture 首 slice 解析一次 RPS；后续 slice 只校验一致性及建立各自参考列表。 |
| K4 | `e0507657c4432d38c8d7dceed341cf30d3e2bc62` | 无效 RPM 裁剪回退整幅，格式/selection 共用一个纯 helper 的缓存结果。 |

K1 保留原 runtime PM 引用边界：普通 metadata open 只获取 VDEC1，close 后同步挂起；
HEVC 核仍只在实际 job acquire 上电。probe 不运行寄存器或固件实验。
secure 域/时钟检查、共享 DOS 租约、DMA stop 和 fault/quarantine 未删除。
写入式实验已全部删除，open 不再有 probe_step 判断；power_state、faulted 只读属性保留原位。
原 vdec_enable 也调用步进 helper，现保留正常路径共用的时钟/域转换并按用途重命名，
把正常流程的寄存器访问、返回检查和九次 mb 展开为固定序列，不留参数化步号。
静态顺序表见 build/vdec-fixes/reviewA/normal-power-order.csv；不能代替实板轨迹。

K3/K4 的 HEVC 源文件与前版 ad2b7c62 逐字节一致；只随前两提交重排而改变父 SHA。

K3 的纯 resolver 输出 ST before/after、LT curr/foll 槽位；缺失槽显式保留。
先确定 ST 占用，再匹配 LT，同 LSB 恰好等数的候选按 POC 降序分配；真正歧义拒绝。
apply 和 set_ref_lists 不再各查一次 LT。后续 slice 忽略 RPS_END 之后无语义的 RPM 填充，
有效 RPS 不同则报码流错误；num_ref_idx/list modification 仍逐 slice 生效。
厂商结构依据 `decoder_v4l/h265/vh265.c:4133-4248`；MSB 周期缺失没有被猜测补齐。

两个新 RPS KUnit 使用实采 POC330、847 的 RPM 字，覆盖 ST326/LT70 排他分配、
LT761/505 分配、后续 slice 列表变化和 RPS 不一致；保留前图作为 LT 的旧回归。
POC1108 的拒绝用码流 LT 目标构造三候选/两条目，**不是板上实采 RPM**：
已有采样停在847，不能把构造字冒称后续固件读回。resolver 失败不部分修改 DPB 或已保存结果。

K4 保持 b54ff9b7 语义，未带入撤回的 EOS 提交。厂商正常解码路径 :5785-5815
对无效裁剪回退，CSD 的 :2155-2200 拒绝逻辑不适用于正常图像。
两个裁剪 KUnit 覆盖有效四边、SLIST 两份坏偏移、裁空及原尺寸/chroma 校验。

## T1 工具配套

`packaging/kernel/vdec-window.py` 正常加载模块，不再传三个参数或写 permission；
acceptance 不再强制跑 power/mdec/hevc 预检。等待 udev 后普通 open/close 三类解码节点，
确认 runtime suspend。HEVC 电源、固件和像素由实际解码验收。
计划删除 `hevc_diagnostic_api`，旧字段明确拒绝，不回退旧 passing 缓存。
power/mdec/snapshot 已从 ACTIONS 删除，旧动作在 argparse 解析时拒绝，不保留执行分支、步进表或函数桩。
同步测试和[工具合同](../vdec-validation.md)。补丁交协调者代提交，不在本工作树提交。

工具专项 **31 项通过**；全套 unittest **608 项 OK、14 跳过**。
少三项是随原实验函数删除的旧测试；超时、PM 失败与恢复标记的测试改为正常 metadata open 触发，仍保留。
原始日志 `logs/vdec-fixes/`，补丁及提交说明 `build/vdec-fixes/T1-tools.patch`、`T1-message.txt`。

## 构建产物来源与清理

reviewA 指出的41个 ignored 文件确属本 worker。已封存 .cmd、mtime、完整文件清单和产物归档。
第一轮 sparse 使用 make O=... M=drivers/... modules；M= 进入外部模块模式，
O= 选择内核构建根，但外部模块输出仍默认落在 M= 源目录。
本树 Makefile:137-138/195 明确区分 MO/KBUILD_EXTMOD_OUTPUT；原日志也进入了源码 vdec 目录，
.cmd 引用本任务 source/O=，产物时间与该命令吻合，来源已确认。

按 dry-run 清单执行 git clean -fdX，仅清理自有源码的 drivers/media/platform/amlogic/vdec。
正常模块构建继续用完整 make O=... modules；sparse 改为带绝对 O= 的树内目录目标，不使用 M=。
逐提交/最终门禁均检查 git status --porcelain --ignored，源码目录出现产物就失败。
原始证据在 build/vdec-fixes/reviewA/，旧 final/ 和脚本移入 previous-* 保留，不混作本版证据。

## 离线门禁

本版固定新 SHA 经正式 heavy **FIFO1591**，票
`d833d6da805d4735a81d227e0968d5ff` 已 released。四提交逐个 W=1 模块及 arm64 QEMU
KUnit 通过，按 K2/K1/K3/K4 顺序为 **46/46、46/46、48/48、50/50**。
strict 完整 format-patch 零 errors/checks，仅 K2 一条删除文件的 MAINTAINERS 通用提醒。
首轮新增的屏障缺说明提醒已补齐并折入 K2；未改屏障位置或数量。正文75列、diff --check通过。
测试配置四条既存 KUnit 模块缺 MODULE_DESCRIPTION 的 modpost 提醒保留。
尖端测试配置模块 SHA256：
`f18ae6ff5764274e6aabb4fff63756d888e1d9da57a514df9ff5b95215f80465`。

CONFIG_KUNIT=n、DEBUG_FS=n/y 两配置完整内核链接和 W=1 模块均通过，模块日志零 warning/error；
模块 SHA256 同为 `f61ba453a85c28e36a2a1a9139a553516a5aef7935a41034167f15a1cf0a4713`。
新版 sparse v0.6.5-rc1-21-g84ec0658 对模块配置和内建配置实际 CHECK，驱动范围零诊断；
内建同时 W=1 编译含 KUnit。准备阶段两份日志都有既存 VDSO __kernel_getrandom 提醒，
不宣称全树零诊断。源码目录逐提交及最终 source-status.txt 全为空，构建输出只落自有 O=。
这仍是离线配置验证，不是正式整包或实板证明。

原 FIFO1584/1587/1588 只对应旧尖 ad2b7c62，不作为本轮新尖通过证据。
本轮首次排队 keeper 报 Operation not permitted，未开始；失败日志保留在 reviewA/heavy.log。
smatch 未安装；kernel-doc 的旧 node/diag_started 提醒与基线对照保留，不记零提醒。

固定尖端复现脚本 `build/vdec-fixes/validate.sh`，VM 同路径位于自己的构建目录；
每提交原始 patch、strict、KUnit JSON/QEMU、配置和模块哈希存 `build/vdec-fixes/reports/<SHA>/`，
配置组合和 sparse 日志在 `final/`。源码快照也留在自己的 build/，没有厂商整文件复制。

## 交协调者的板验清单

1. 自然启动无需模块 opt-in 或预检：节点自动注册，udev/v4l_id 后 VDEC1 idle suspended，
   HEVC idle 关闭，冷复位次数/boot 身份与 integration39 对照。正常解码后再次核对释放及 fault=0。
2. SLIST_B_Sony_9、SLIST_D_Sony_9 各65帧：目标为逐帧/整流 MD5、顺序和数量完全一致，
   Captured status0、LAST、零 ERROR；不以“不再拒绝 RPM”代替 Success。
3. RPS_D_ericsson_6：应排除旧索引30错误、越过 POC847，真正缺 MSB 的1108歧义可拒绝；
   只比较实际完成帧，不承诺整流68帧 Success。保留 RPM/参考列表错误证据供后续 LMEM 实验。
4. 旧120条 Success 不回退；全 I、三短流5/8/17帧、RPS_B/E各300帧，接口、事件和像素保持。
   HEVC56/56、stateless60/60、media8/8 及 JPEG 原窗口判据对照 integration39。
5. 原 Success 退步、新 WARN/fault/泄漏、额外自然复位或 PM 无法释放立即停下离线定位。
   超时沿既定恢复；不为 LTRPSPS_A/WPP_D 现场换参数或延长超时。

未实现批 B（头解析、disposition、C.5.2、单 AU 错误隔离）；未修改 HEVC EOS、输出顺序或固件序列。
本轮未碰板、未排板票、未 push/合并；等待协调者审查批 A。
