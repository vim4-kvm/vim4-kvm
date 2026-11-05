# 2026-11-05：KUnit 迁移集成候选离线准备

本轮只准备：未排 heavy、未编译、未访问板子。集成 SHA 等协调者通知，
不以迁移分支代替集成结果。顺序按 `~/.local/state/herdr-workers/integration-plan.md`，
本轮不含 hwdecode-parity。以下板测均为**待实板**。

## 构建交接

入口：[build-integration.py](../../packaging/kernel/build-integration.py)。只接收完整
SHA，要求指定源码工作树已经干净地停在该提交；不 checkout、不 fetch、不改来源锁、
不排票、不部署。只有协调者放开 heavy 且提供 SHA 后，才由
[board-queue](../../tools/board-queue) 的 heavy 租约包住整个命令，VM 内运行。
输入路径/选项见其 parser；调用骨架如下，本轮未执行：

```sh
python3 packaging/kernel/build-integration.py "$INTEGRATION_SHA" \
  --source /home/deepdream/src/linux-7.3-kunit-migration \
  --build /home/deepdream/build/kunit-migration-integration \
  --destination "$CANDIDATE_DIRECTORY" --vendor "$KBASE_VENDOR_SOURCE" \
  --baseline "$RETAINED_BASELINE_PROOF" --mac "$BASELINE_ETHERNET_MAC" \
  --build-number "$UNUSED_BUILD_NUMBER"
```

调用位置为 VM 可见的本主仓库路径。vendor 是 kbase/build.py 锁定版本的只读
源码输入，不修改其工作树。baseline 为已有正式基线的 board-window proof；
没有合格 proof 时先报告缺项，不为准备脚本访问板子。构建号由协调者分配当日未用
生产号，调试用紧随其后的号；UTC 日取调用时刻，SHA/配置/产物另有精确身份。

生产配置逐字节核对 [kernel.config](../../packaging/kernel/kernel.config)。调试
从同配置合入 [vdec-debug.config](../../packaging/kernel/vdec-debug.config)，
olddefconfig 后核对片段要求，完整配置差异进入 identity.json。两者保持 KUnit 和
函数错误注入关闭；不把本次普通调试候选用于 Wave5 fail_function 注入。

复用同一个外部 `O=`，每次构建前 make clean，避免跨配置复用对象。每套完成后
先封存 Image、当次 display-m0 DTB 经现有 kbase 构建器生成的候选 DTB、完整内核
及三个外部模块；外部模块从当次 vmlinux/Module.symvers 重新构建，绝不复用基线
`.ko`。DTB 保留本次集成的温控/设备树内容，MAC 来自基线；不拿旧部署 DTB 覆盖它。
沿用 [display-once prepare](../../packaging/kernel/display-once.py) 生成 RAM 包。
生产构建归档后才切调试配置；全部封包成功后删除自身 `O=` 和外部构建目录内
`*.o`，保留最后一套 Image/.ko、两套包、身份和日志。提取的完整模块 stage 在封包后
删除，模块仍完整保留在包内。失败保留日志/现场，不写 complete.json，不交付半成包。

每套生成 `payload/manifest.json`、`module-identities.json`、`identity.json`、
`ram/candidate.tar`、`ram/trial.json`；核全部 modules.order、vermagic、BTF、
build ID、SHA-256，保留 config/Module.symvers/System.map/vmlinux.btf。
根目录 `production.log`/`debug.log` 存实际命令与原始输出，`complete.json`
仅两套成功后生成。包只用于 RAM 链，不改默认项/登记、不安装用户态。
编译 W=1；既有 ADLA 等诊断保留，不将编译退出成功写成静态零告警。

## 生产候选板窗预算

总预算 **19 分钟**，含启动/身份 2 分钟、串行测试 13 分钟、恢复/交接 4 分钟。
这是改动相关冒烟，不代替全部 V/B/F 验收。与前一 worker 同日同候选且身份未变时
复用其准入证据；不复用其测试结论。每步使用整体超时，首错采证后直接进入恢复，
不挤掉恢复预算。[板窗合同](../board-window.md)管理租约、UART、RAM 交接和
基线视频推进；默认启动项与持久模块保持基线。19 分钟到点不追加测试。

板窗前必须在离线端准备好 ARM64 二进制、Python/GI/浏览器依赖、已锁模型/输入、
当前私有插件、标准接口工具和运动图样；不在持锁期间编译、下载或补依赖。
以下工具参数以各自帮助为准，所有输出写入本次独立目录，状态快照与原始日志保留。
停止所有实际视频消费者后才独占 DMA/编码器；USB 操作前确认无介质，数据线仅接
已授权测试主机 M6。不得向开发机 M4 注入 HID，不拔单线供电 USB-C。

| 子系统 / 时长 | 板上做法（按表串行） | 通过判据 / 限制 |
|---|---|---|
| HDMI RX，2 分钟 | 按 QUERY_DV_TIMINGS/节点名确认当前运动信源；已编译 [hdmirx-stream-check](../../tools/hdmirx-stream-check.c) 对真实 VDIN 节点做短 MMAP 与 DMABUF/持导出轮，保存首末帧；[frame-check](../../tools/hdmirx-frame-check.py) 在离线端核对图样。 | 每轮有界 STREAMON/OFF、帧几何/时间戳/错误标志正确，运动标记推进；退出后导出/fd/CMA 归还，无新 DMA/IRQ 错误。全模式/compliance 另窗，不能凭帧数证明内容。 |
| T7 JPEG，1.5 分钟 | 使用当前私有插件运行 [edge-jpeg-check](../../tools/edge-jpeg-check.py)，缩短为每轮 30 帧，保留其六组质量/尺寸/重复退出覆盖，保存首末 JPEG。 | 工具所有断言通过，JPEG IRQ 推进、实际软件解码成功、PTS 递增、DMA 对象清空且 CMA 回归；离线比对运动与颜色。缺 4K 信源/插件则待验，不改工具降低要求。 |
| DRM/显示，1 分钟 | `modetest -M meson -c -p` 记录连接器/模式/plane；[GBM 探针](../../tools/gbm-scanout-probe.c) 传入实际 card 节点，做当前模式的短扫描输出/释放，与 RX 同开。 | modeset/释放完成，RX 仍出帧，无 fence/引用/PLL 超时；无接收器或 DRM master 被占则 scanout 待验，不抢 master。探针不覆盖 page-flip/完整 IGT/AFBC 故障。 |
| ASoC 音频，1 分钟 | 复用 [audio-continuity](../../tools/one-kvm-audio-continuity.mjs) 与 [HDMI 已有源音](../../tools/hdmi-audio-tone.c)，按原 [音频准备流程](../../packaging/kernel/final-regression.py) 核对 ALSA 输入路由后，做短接收；记录 aplay/arecord 枚举及 amixer 状态。 | 实际 AudioData/渲染音频非零且已知频率正确，无 XRUN/异常中断；结束恢复原速率/路由/服务。只读 ALSA 枚举不能替代此项；AED 控件边界、所有速率另验，不盲读 audiobus MMIO。 |
| brcmfmac，1.5 分钟 | 保存 `iw phy` 能力与 `iw dev`；有现成 SAE 连接及有线恢复时运行 [check-wifi-p2p](../../packaging/kernel/check-wifi-p2p.py) 一轮，覆盖能力查询、STA+GO 建立/删除、ping 和管理归还。 | 无固件 trap/NVRAM 越界，声明能力与接口角色一致，STA 不丢失、GO 有建立/删除证据，恢复原 NM。无 SAE 前提则该步骤待验；真实对端协商/传输没有现成已验对端，不宣称通过。600 秒 TCP 属前一 worker 窗口，不在此重复。 |
| ADLA，1.5 分钟 | 用已锁模型/输入与已编译 probe 运行 [npu-validate run](../../tools/npu-validate.py) 短轮（至少两次），离线 compare 既有同模型金值；并对驱动的 utilization sysfs 属性采 idle/load/结束值，先保存开关，再启用计时并恢复。 | 推理输出张量匹配金值、完整轮序列、退出无 DMA/锁/SG 异常。**7e35e3b 需实板回归**：记录 hw_info、当时核心时钟、模型 MACC 与内部计时，按旧硬件当前频率公式核利用率分母；空闲读数可为 0，不以它代替负载。已有推理工具没有采集全部分母输入的专用入口，见下文缺口。 |
| CEC，0.5 分钟 | 找到绑定 Meson 的 `/dev/cec*` 后 `cec-ctl -d "$CEC" --info`；有支持对端时用标准 `cec-compliance -d "$CEC"`，整体限时。 | adapter/物理地址与当前 HDMI 一致，标准测试无失败；无 CEC 对端（当前 M6 路径未证实）只记录枚举，TX/RX/路由和完整 compliance 待验。未发现仓库内专用自动入口。 |
| secure genpd，0.5 分钟 | 各实际负载前后保存已审阅的 `/sys/kernel/debug/pm_genpd/pm_genpd_summary` 与对应设备 runtime_status，关联上方 JPEG/显示/ADLA 的启停。 | 活动消费者保持供电、退出引用合理、无 SMC/轮询超时；共享温度等消费者仍持域时不要求强制掉电。不主动解绑、不写 SMC、不触 HEVC。SMC 拒绝/超时没有现成注入入口，待单独调试窗。 |
| HID/UAC2，1 分钟 | 先核对实际 configfs 组合、UDC configured 及主机枚举。用 [hid-rebind-check](../../tools/hid-rebind-check.py) 小轮数测试持 fd/epoll 的解绑重绑；UAC2 若已启用，用 [uac-record-level](../../tools/uac-record-level.swift) 从指定 USB 音频设备录短音。 | 重绑每轮成功、fd/epoll 关闭无 panic；已知 USB 音频数据非零/频率正确、关闭和重新打开成功；只向授权 M6 发数据。没有 UAC2 组合/输入前提则音频端点待验，不擅改整套 gadget。 |
| CRG，0.5 分钟 | 在上一项重绑同时保留 `/sys/class/udc/*/state`、主机枚举和 IRQ 前后证据，另核正常控制请求/描述符读取。 | 配置/重连成功，无重复入链/EP0 告警或悬挂。旧 [crg-udc-check](../../tools/crg-udc-check.py) 仅允许历史专用 release，不能直接用于本候选；不改 release 绕门禁。完整 SETUP/异常控制流仍待专用接口验证。 |
| FUSB302/TCPM，0.5 分钟 | 按 [已部署合同](2026-11-04-boot-pd-tcpm.md) 保存 Type-C port 的 power/data role、power_operation_mode，关联 power_supply online/电压/电流、IRQ/驱动 notes；使用本次启动的协商日志。 | sink/device 与真实供电合同一致，CRG configured，IRQ/协商无新异常；不重用历史测量数值作阈值。单线拔线会断电，热插拔、运行中 reset、睡眠唤醒不在此窗。 |
| Wave5，1 分钟 | 用 [vim4-driver-bench](../../tools/vim4-driver-bench.c) 的 edge 后端，对 H.264/H.265 各做短真实采集编码、EOS/释放/再开，保存短码流供离线解码；核设备名为 Wave5 与当次插件。 | 输出帧与输入一一对应、PTS 前进，退出/再开有界、fd/CMA 回归，无 VPU timeout/isolation。旧 [lifecycle-check](../../tools/wave5-lifecycle-check.py) 限历史 release，本候选不直接调用；使用现有 bench 的两次独立调用。正常编码不证明挂死/隔离恢复，通过标准见 [故障注入方案](2026-11-05-wave5-fault-injection-plan.md)，此生产窗不注入。 |

## 缺口及停止条件

ADLA 仅在计时启用且有任务时计算利用率。需对应 hw_info、clk_core、模型 MACC
及 invoke_time_elapsed_total；取得不了同次推理分母时，数值正确性留为**未验**，
不造寄存器读取器、不改时钟。开关原值拿不到则不写；退出后 0 不证明 break 正确。

DRM 无接收器、CEC 无对端、UAC2 未启用、Wi-Fi 无 SAE、模型/金值或旧工具的
release 限制等都在入窗前确认。缺条件的条目仍占待验清单，不因未运行算通过；
不在板上临时造工具。secure SMC 与 Wave5 隔离/复位故障必须使用单独审过的调试
注入配置，生产窗口不运行；同 PWM 控制器 ABBA 仍是已登记问题，不在此任务修。

每步前后保存 dmesg 增量、taint、内核/模块 notes 与资源计数；有新的 BUG、WARNING、
Oops、超时、失联、输出停滞即停止测试、保留 UART/日志并按窗口合同交接恢复。
既有 vendor 问题需登记来源/调用栈，不能静默忽略，也不能把旧 sparse/W=1 失败改记通过。
结束只认原应用视频实际推进及身份/启动文件/模块恢复证明，不以 SSH 或 uname 代替。

## 本轮离线检查

Python 字节编译、三项配置门禁单测通过；主仓库完整 unittest 为 543 项，
14 skipped，OK，原始输出在 `build/kunit-migration/integration-prep-main-tests.log`。
未调用构建 main 或板端入口；提交记入 worker result。待 SHA/heavy 放行后补真实构建。
