# 2026-11-06：DOS 解码租约随 runtime PM 持有（K9）

r105 中编码器先 probe，原解码器在 probe 取独占租约，以 -EBUSY 失败而没有节点。
交换加载顺序则可能阻止 Wave5 注册，影响 KVM 编码。两者都不应由空闲解码器的注册决定。
本轮只改租约寿命，不允许编码/解码同时操作 DOS，不修改 Wave5 或 t7-jpeg。

## 系列与修改

基于重构尖 `0ae8beaa56d3a798e8078c5f727c34ed3acafd9c`，在自有 VM
`/home/deepdream/src/linux-7.3-vdec-fixes` / `vdec-fixes` 重排为九提交：

| 顺序 | 项 | SHA | 摘要 |
|---|---|---|---|
| 1 | K2 | `2ec22a40b8b99987a8e7fca77477c1c019c8f565` | 已审删除原始 DOS 实验入口，提交不变。 |
| 2 | K9 | `dd87f5ed0913b8f7e4058620abbebbf33aa5e4f6` | 租约随 runtime PM；中性 debug 提示；纯仲裁 KUnit。 |
| 3 | K1 | `d45b6a4bcd5ada75bf9f6f82a2f20d3ea9327772` | 去门，保留 K9 的运行期租约。 |
| 4 | K3 | `085f35100d9f88988af18de5de79edf872b3e2fe` | 已审每图 RPS 解析。 |
| 5 | K4 | `d217a4fb624edb50abfae1cac11dfe0847e1ce51` | 已审无效裁剪回退。 |
| 6 | K5 | `51513512e731c2b8e3efa4a8868f80c67eaecc93` | 已审最小头解析，包括 reviewB 的非主层/保留 VCL 忽略。 |
| 7 | K6 | `c87c0af7635b22fec56f395d5c72dc820a08a02b` | 已审共享 stateful discard。 |
| 8 | K7 | `852bc787269411bf811a1e546daee89da3719986` | 已审 C.5.2 输出过程及头文件轨迹。 |
| 9 | K8 | `f41a9bfd20c09220978f0e348385ad8aaa164048` | 已审单 AU 错误隔离。 |

K9 排在 K1 前，防止去门后出现 probe 竞争的中间提交；排在 K2 后，确保没有绕过 runtime PM
的实验入口。K1 的两处冲突只删除旧门而保留新租约；K5 的 Makefile 冲突保留两组 KUnit 对象。
作者、签署与既有七个提交说明保留；K2 原 SHA 不变。
相对初审通过的 bc651815，所有 codec/DPB/硬件编程文件无差异；新增差异仅为 K9 的七文件。
`build/vdec-fixes/k9/rewrite-diff.log` 保存逐行 diff/range-diff，`codec-behavior.diff` 为空。

`aml_vdec_drv.c:405` 的 runtime resume 先取独占租约，再调用 vdec_enable；失败即 put。
runtime suspend 先停 HEVC、放 HEVC 电源引用、关闭 VDEC1，全部成功才 put。
失败仍保留租约，原 fault/poison 路径不变；enable 失败归还计数也不能解除 poison。
probe/remove 及其错误路径不再取、放租约，空闲注册不阻止编码器 probe。
解码器 active 时，编码器 probe 仍返回 -EBUSY，符合本项继续互斥的范围。

`t7-dos.c` 的状态转移抽到私有 t7-dos-state.h，生产包装仍持同一 dos_lock。
KUnit 在独立局部状态上直接调用同一生产函数，验证多个共享租约直到最后一次释放、
独占对全部其它租约排斥，以及释放后 poison 仍优先返回 -EIO；不修改全局租约、不访问硬件。
原模块自引用和永久 poison 逻辑不变。提示改为中性 dev_dbg，普通 -EBUSY 不打印 dev_err/WARN。
公共头文件和 Kconfig 的寿命说明同步更新。

## DOS 访问与 HEVC 覆盖核对

核对记录 `build/vdec-fixes/k9/source-path-audit.log`，按执行顺序的 CSV 为同目录 `lease-paths.csv`。
下列位置相对 `drivers/media/platform/amlogic/vdec/`：

- `aml_vdec_drv_probe`：匹配平台、DMA mask、分配对象、注册 V4L2 及节点；T7 分支在
  `pm_runtime_set_suspended` / `pm_runtime_enable` 后注册节点，成功直接返回，不在 probe 调 resume。
  保留的 probe vdec_enable 仅走非 T7 平台。
- `dev_request_hw_resources`：VDEC1/HEVC IRQ 都用 IRQF_NO_AUTOEN；映射 DOS 并创建 regmap，
  不读写寄存器。T7 用内部 canvas，不取得外部 canvas。硬件句柄建立不会执行固件/复位。
- `pm_vdec_power_domain_init`：attach 电源域，T7 device link 不加 DL_FLAG_PM_RUNTIME；
  NIC3 同样只 attach，不调用 resume。`vdec_clock_gate_init` 只 get 时钟及 provider regmap，
  不 prepare/enable、不读写 DOS。
- 两个剩余 sysfs 属性中，faulted 读软件状态；power_state 只做 read-only SMC 状态查询。
  从 probe 到首次 runtime resume 没有 DOS MMIO；首次 DOS 编程受已取得的独占租约保护。
- `fops_vcodec_open` 在初始化上下文和允许 ioctl 前成功执行 pm_runtime_resume_and_get；
  -EBUSY 只释放刚分配的 ctx 并返回用户，不建立 fh/job，也不会写 DOS。
  `fops_vcodec_release` 先 v4l2_m2m_ctx_release 等待取消/停止，再放 PM 引用。
- HEVC 唯一上电链是 hevc_job_acquire → aml_hevc_prepare_hw → aml_hevc_power_on。
  该链在已经成功 open 的 m2m job 中，且 aml_hevc_power_on 已检查 vdec1.powered。
  HEVC 末尾停机/断电仍在 runtime suspend 释放 DOS 租约之前。无独立的 probe/实验上电路径。
- 本树 PM core 的 rpm_callback/rpm_resume 不把 resume 的 -EBUSY 留作永久 runtime_error；
  失败恢复 suspended，resume_and_get 回退 usage_count。编码器最后一次释放后可重新 open。
  该结论是源码核对，加载顺序和电源状态仍须实板验证。

`prepare_acceptance_decoder` 普通路径先卸载 decoder/Wave/JPEG，再加载 decoder 并测 metadata open，
因此无需修改主仓库工具。并发 encode/decode 的 coexistence performance 模式仍不受本项支持，
不能用它替代“节点可注册，但 open 返回 -EBUSY”的加载共存检查。

## 离线检查与待运行门禁

九个完整 format-patch strict 预检零 errors/checks；K2/K9/K5/K7 各一条新增/删除文件
MAINTAINERS 通用提醒，原目录覆盖。diff --check 通过。
KUnit 三例已编写，**新八提交的 W=1/QEMU、尖端 sparse 和 DEBUG_FS=n/y 尚未运行**。
未改 SHA 的 K2 保留原门禁46/46及W=1记录，不能证明新提交通过。

两次正式 `tools/board-queue run --heavy`（FIFO1617/1618）都在 keeper 报
`[Errno 1] Operation not permitted` 后退出，票均 released，未启动 VM 构建。
原始输出在 `logs/vdec-fixes/k9/heavy*.log、keeper*.log`；票据在 `build/vdec-fixes/k9/`。
没有绕队列执行构建。协调者可直接代跑：

```sh
tools/board-queue run --heavy --who vdec-hevc-port --purpose K9-final \
  -- orb -m vim4-build sh /home/deepdream/build/vdec-fixes/validate.sh
```

固定尖端 validate.sh 默认逐九提交执行 strict、W=1完整模块和 arm64 QEMU；
之后跑 DEBUG_FS=n/y、模块/内建有效 sparse，包括 t7-dos.c 的实际 CHECK。
源码状态检查覆盖整个 amlogic 目录，使用独立 O= 树内目标，无 M=。
脚本本地副本 `build/vdec-fixes/k9/validate.sh`，原入口已转入它。
主仓库全套 **608项OK、14跳过**，日志 `logs/vdec-fixes/k9/repo-tests.log`；
kernel-doc 对新增/修改的仲裁头文件无诊断，保留旧 node/diag_started 缺注释提醒。
本记录不引用旧尖的 heavy 结果作为新尖通过。

## 交 t3k 的板验判据

integration 候选先通过上述门禁，再由协调者安排：

1. 默认编码器先加载、KVM 正常推流时加载 decoder：节点全部注册，metadata open 返回 -EBUSY；
   runtime 仍 suspended、faulted=0、无 DOS IRQ/MMIO异常及 WARN，编码视频不受影响。
2. decoder 先加载且空闲，再加载 Wave/JPEG：编码器注册成功；decoder open 返回 -EBUSY。
   卸载编码器后无需重载 decoder，同一节点可以正常 open/close，close 后 suspended。
3. decoder 实际 active 期间编码器 probe 返回 -EBUSY 是预期；close/确认 suspended 后可加载。
   分别保存节点、runtime、模块状态与日志，不能把 active 互斥判成“同时解编通过”。
4. 编码器卸载后沿既有 integration40 清单复测 decode、EOS/compliance 与回归流；
   窗末恢复编码栈并验证真实 KVM 推流。新 WARN/fault、租约未归还或原 Success 退步即停。

本 worker 未碰板、未排板票、未push/合并/提交主仓库。上电/停机时序、加载顺序与实板像素尚未验证。
