# 2026-11-06：.40 解码修复板验

本轮达到批准的累计第二次冷复位停止条件，**已停止，由 integration41 取代，不再续跑**。
离线门禁通过，正常无参probe/metadata PM有实测；compliance、各格式解码和HEVC132条均未运行。
没有修复通过或回退结论，未部署、合并或 push。
基准为 [.39 的独立132条](2026-11-06-vdec-integration39-results.md) 和
[r97 的 .38 同包其他格式补测](2026-11-06-vdec-integration39-baseline.md)。

## 源码、构建与封包

| 项 | 锁定身份 |
|---|---|
| 内核 | `bc651815ee7d912f58a1c2e3d6348f93189f7077`，基于 `0ae8beaa` |
| tree | `758751eb474e2e9f6785c2b59549bdfff1920d71` |
| release | `7.3.1-vim4-20261106.40` |
| build ID | `732f894e2037d900b1211997c9a0c0362cfee233` |
| 生产配置 SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| 普通 RAM SHA256 | `1505ca10fb122dc94e040077d6229aaa9577c566c9ae5cb4d494b814097a65a3` |
| 无线屏蔽 RAM SHA256 | `2ca7da18580352c559053536ded0be74cd96cda31fb84ced17775bd5e6cf9e74` |
| manifest SHA256 | `26b97d55a693bc239f1a8f57e286cd8583bcdd2edcc50c3413cfd2fa5686d090` |
| 统一组件包 SHA256 | `c60564804c26f0e51e60f2f6a2370e3a97dbb16085462a5bd98e6ac283dac06d` |

独立 VM task/source/O= 为 `vdec-integration40`，未复用被协调者清理的 .38/.39 kernel O=。
生产整包直接 W=1 编译：1168条既存告警，与 .39 按文件及文本比较零新增，VDEC 零告警；
实际 auto.conf 与生产配置逐项一致，15份真实编译命令含额外告警选项，无 KASAN 配置。
同源独立 arm64 QEMU KUnit 实际 **64/64**，无跳过/崩溃。
统一封包器核完整2341模块（2338基础+3外部）的身份、BTF、vermagic、depmod及native来源。
RAM变体2357文件不变，仅 extlinux.conf/trial.json 改无线屏蔽参数和相应摘要。

主仓工具固定 `3cd632b`，使用正常 runtime PM 入口，不传三个旧门、不做 debugfs 电源/固件实验。
上传逐文件 SHA、保护清单2372项、旧计划字段拒绝、缺脚本/摘要失败、历史拆行 ioctl、
旧Success像素差异拒绝及目标改善接受的离线回放留有输出；原工具31测试通过。
构建后主仓全套 **608项OK，17跳过**。提交前最终检查另存 `final-tests.log`。
未修改 DT/binding，不重复无关 schema 检查。

证据根 `build/hwdecode-parity/integration40/`：`build40.log`、`offline-production.json`、
`tip.kunit.json`、`tip.qemu.log`、`artifact-identity.json`、`identity.json`、
`pre-board-tests.log`、`tool-failure-paths.log`、`window105-offline.log`。
封包且 r105 结束后，仅删除本任务两个 O= 下11744个可重建 `.o`（4269087528字节），
清单 `rebuildable-objects.tsv`；保留 Image/模块/vmlinux/包/日志，不删历史证据。

## r105：自然 probe 门禁停，未执行解码

FIFO **1614**，sampling，30分钟票；无线屏蔽 .40 仅请求一次候选启动。
候选 SSH release/cmdline/notes build ID/boot_id 与封包匹配，模块自动加载且 parameters 为空。
随后自然 probe 的三节点检查失败，实际只有 `t7-vdin-test` 与 `C&M Wave5 VPU encoder`。

原始 UART：

```text
[    5.019842] aml-vdec-drv fe320000.video-codec: T7 VDEC requires Wave and JPEG drivers unloaded
[    5.019854] aml-vdec-drv fe320000.video-codec: probe with driver aml-vdec-drv failed with error -16
```

`aml_vdec_drv.c:aml_vdec_drv_probe()` 在注册节点前调用 `meson_t7_dos_get(..., true)`；
`drivers/media/platform/amlogic/t7-dos.c:meson_t7_dos_get()` 在编码器租约存在时返回 `-EBUSY`。
这是既存 probe 期 DOS 租约互斥，不能解释为旧 opt-in 门残留，模块存在也不能代替绑定/节点证据。

协调者裁决：r105 记门禁停，**不计回退**。编码器/解码器同时 probe 与 KVM 推流不受影响，
由另一个 K9 运行期租约候选验证；本包不改驱动。后续先保留自然启动快照，再按现有
prepare_acceptance 停应用、卸载 Wave/JPEG，无参数正常 probe 后继续本轮验收。

本窗 compliance、全I、各格式和132条全部未运行；在节点断言之前停止，HEVC PM 快照也未覆盖。
自然启动失败不证明两组 HEVC 修复通过或失败，不计入 Fluster Fail。

恢复正式 `fd41fb5`，2372 protected_files 全过，默认启动及 cmdline 未改；
被动3840×2160视频60.17fps，解码帧3→304，无新增掉帧/冻结/丢包；无线模块恢复与入场相同。
候选1次、正式恢复1次 Linux 启动，冷复位 **0/2**，无新 splat/DMA 故障证据。
原始 UART SHA256 `851c606f16b9d1ff3862b610ff098e347294168923c133915de9d30ad0ea0e8e`。
归档801文件逐项 SHA 核验后清本任务板端上传；2372 proof和视频原始输出保留。

证据：`logs/hwdecode-parity-r105/` 的连续UART、SSH身份、`returned-baseline-identity.json`、
`returned-video.log`、`complete.json`；`build/hwdecode-parity/run105/archive/results/` 的
`kernel.log`、原始kernel journal、`natural-probe/probe.json`，以及同运行目录的
`board-upload-files.json`、`brief.json`。正式proof与视频通过不等于候选解码通过。

r106替代票在只读入场时因正式 uptime 未满300秒被门禁拒绝：未上传、未暂存、未重启，
零候选启动/零解码。此次排票过早，后续先按恢复启动时间确认满300秒，不放宽入场条件。
原始拒绝见 `build/hwdecode-parity/run106/window.log`。

## r107：正常 probe 与共享域判据

FIFO **1616**。入场正式 uptime 满300秒，候选仅启动一次；自然probe仍为编码器先占，
按r105裁决留证。正常prepare停应用、卸载Wave/JPEG后，无参数modprobe注册三个解码节点。
普通metadata open/close三节点均成功，平台runtime_status前后均suspended，VDEC[4]=1、NIC3[39]=0。

首次PM门禁按“须有另一个active consumer”停止，未跑compliance或解码。原始标准摘要为：

```text
T7_DOS_HEVC                     on                              0
    fe09a000.temperature-sensor     unsupported                 0           SW
    genpd:2:fe320000.video-codec    suspended                   0           SW
```

协调者裁定 **PM通过**：genpd用pm_runtime_suspended判断能否断域，未启用runtime PM的
温度传感器虽显示unsupported，仍不算suspended，会保留共享域on。应记“decoder已释放，
共享域由温度传感器（无runtime PM）保持on”；不是decoder泄漏，也不把unsupported改写为active。
比较器以r107实际摘要回放通过；只接受`fe09a000.temperature-sensor`作为该持有者，
decoder不suspended或出现其他持有者仍停。未新增接口、关传感器或读取MMIO。

恢复正式时一次cold_boot：距Linux起点 **7.270499958秒**（主机UART块时间），
最后内核行为4.843067秒的brcmfmac固件加载；无panic证据。仅被动等待，下一次自然正式启动成功，
2372 proof全过；被动3840×2160、60.16fps、帧2→303，无新增掉帧/冻结/丢包。
UART SHA256 `70c82c11e1f8f8f0c6baf16240751b81cfea80d4e082ae7f7557e49bec4d5671`。
归档802文件逐项核SHA并清本任务上传。候选累计2/0、正式恢复3/1；本任务cold_boot累计1，
尚未到第二次停止阈值；下一窗仍先确认正式uptime≥300秒。

证据：`run107/archive/results/controlled-probe/before-metadata-open-genpd.log:91–93`、
`run107/execution.log`、`run107/brief.json`、`logs/hwdecode-parity-r107/`，
以及`build/hwdecode-parity/boot-ledger.json`；相对路径均以本工作树为根。

## r108：无线屏蔽候选早期冷复位，停止系列

沿同一无线屏蔽 RAM 包，**不是正式cmdline**：候选追加
`module_blacklist=brcmfmac,hci_uart,btbcm`、
`initcall_blacklist=mmc_pwrseq_simple_driver_init`、`systemd.mask=bluetooth.service`。
包 SHA 即前表无线变体值；正式默认及恢复cmdline从未追加这些参数。
UART估算正式已运行327秒后才排票，入场SSH仍独立核uptime≥300秒。

候选仅请求一次，在acceptance及SSH身份确认前回到T7 ROM；距`Booting Linux`约
**7.043434833秒**。末条内核日志为 `[4.732881] Adding 1006652k swap on /dev/zram4`，
无panic证据。该次UART缺Linux version行，不能以封包身份代替运行身份；只记
“按已验无线屏蔽包请求 .40，未完成SSH release/build ID/boot_id核验”。
不因原始UART有缺字将实际Linux启动计成零，也不把请求身份写成已确认身份。

不重试候选，仅被动等待正式自然恢复。2372 proof全过，被动3840×2160视频59.57fps、
帧6→304，无新增掉帧/冻结/丢包；无线恢复与入场一致。归档773文件逐项核SHA，
板端本任务固件副本/候选/上传均按归属与摘要清理，正式模块及启动配置不动。
UART SHA256 `a47ca4c5ce9c2855ce7919e415cca645034fa2fa0c288278d379220cc2d223c5`。
证据为 `logs/hwdecode-parity-r108/`、`run108/brief.json` 及归档清单；仍以本工作树为根。

## 逐流结果与未验证范围

独立[132行总表](data/2026-11-06-vdec-integration40-full.csv)全部 **Not run**，
Success/Fail/Error/Timeout均0；不是把冷复位记为码流Timeout。
CSV SHA256 `0981b126df5710f3e6ea176f2b32a9c42470dc4ca15a6fdd3fa4297f71e332fb`；
[汇总及逐启动账本](data/2026-11-06-vdec-integration40-summary.json)保留缺失运行身份。

| 目标流 | 本轮结果 |
|---|---|
| SLIST_B_Sony_9 / SLIST_D_Sony_9 | 均Not run，65帧及参考MD5未验证 |
| BUMPING_A_ericsson_1 | Not run，49帧未验证 |
| NoOutPrior_A_Qualcomm_1 / NoOutPrior_B_Qualcomm_1 | 均Not run，40/47帧未验证 |
| OPFLAG_B_Qualcomm_1 / OPFLAG_C_Qualcomm_1 | 均Not run，98/96帧未验证 |
| RAP_B_Bossen_2 | Not run，80帧及416×240→448×256未验证 |
| RPS_D_ericsson_6 | Not run，POC847/1108与首错改善未验证 |
| VPSSPSPPS_A_MainConcept_1 | Not run，逐AU错误隔离/后续消费未验证 |

原120条Success本轮覆盖0条，不能称“零回退”；其余旧Error/Timeout也无改善或不回退证据。
stateless/media/JPEG/HEVC compliance、全I和三短流、H.264三流、MPEG-2四流、JPEG三样本均Not run。
自然编码器/解码器同时probe和KVM推流不受影响的K9门禁，亦不由本轮证明，交integration41。
正常无参probe与三节点metadata open/close成功、VDEC suspended为本轮已得硬件证据；
共享HEVC域由无runtime PM温度传感器保持on的判据经原始摘要和协调者裁决确认。

## 启动计数与收尾

| 窗口 | Linux启动 | 冷复位 | 运行身份覆盖 |
|---|---:|---:|---|
| r105 | 2 | 0 | .40候选与正式恢复均SSH确认 |
| r106 | 0 | 0 | 只读uptime门禁拒绝，无上传/重启 |
| r107 | 3 | 1 | .40 SSH确认；正式恢复复位，随后自然正式恢复proof确认 |
| r108 | 2 | 1 | 请求无线.40在SSH确认前复位；自然正式恢复proof确认 |
| 合计 | 7 | 2 | 2次SSH确认.40、1次未确认候选、4次正式启动 |

正式4次/1复位与候选请求3次/1复位分开列，后者仅2次身份确认，不能混成3次完整验收。
与.39候选7/0、正式10/1相比，本轮样本及启动阶段覆盖有限，不作因果/显著性推断。
跨任务正式eMMC由截至.39至少71/13变为至少75/14；拓扑仍Mac→USB-C功率计→板子，
无新功率读数、无物理测量，不归因于PD、供电或本系列。

最后一次正式恢复完整proof/视频后释放FIFO，按累计第二次冷复位硬停，不再申请板票。
integration41另写计划审查，其新冷复位预算不能追用于本轮。物理测量等用户回来。
