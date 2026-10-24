# 2026-10-23：HDMI 模式切换失锁的基线对照与稳定判定

承接 [正式批次回退](2026-10-23-wave5-formal-deploy.md)，先对照正式基线和原失败
候选，再验证 RX 修复。所有板端变更与测量在 Mac heavy → board 双锁内串行执行；
候选使用 display-once.py 的 RAM sysboot，默认启动文件保持原基线。

## 基线与原候选对照

正式基线内核 `b1300eb808f43e7161d4971d47c689af28e67e83`，实际 build ID
`eeddb005df059a850853876d52ef603aa1af192b`，One-KVM `672b8fd9fdec`、
manager `9b141c5833c0`，M0 DTB、taint=0、UDC configured。
原候选内核 `9d33f6ad27898d4cb1b5cb52dc328edceca96f7f`，实际 build ID
`0b2385440a358dddcd5d96b496c5fab4d187808d`；对照时应用保留基线版本。
两版 `drivers/media/platform/amlogic/t7-hdmirx/` 无源码差异。

复用正式门禁的 EDID、19 模式表、configure、动态标记图案与帧检查器。
每模式核对两帧的三处一致性标记、帧前进、RGB 主色、stride 与 DMA 回收；
单模式失败后保存状态并继续，以便完成完整矩阵。ENOLINK 计失败，只有原门禁已有的
EAGAIN 有界重试。每轮和异常收尾恢复原 EDID，原始 SHA256 为
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。

| 实际运行 | 结果 | 失败模式 |
|---|---|---|
| 基线第一轮 | 17/19 | 1680×1050 QUERY_DV_TIMINGS ENOLINK；1080p24 抓帧 ENOLINK |
| 基线第二轮 | 19/19 | 无 |
| 基线额外 800×600 ↔ 1024×768 十轮往返 | 20/20 | 无 |
| 原候选第一轮 | 18/19 | 1600×900 QUERY_DV_TIMINGS ENOLINK |
| 原候选第二轮 | 17/19 | 1080p30、4K60 QUERY_DV_TIMINGS ENOLINK |
| 基线，改用标准EDID接口，两轮 | 38/38 | 无；所有总行长/总场长匹配，像素时钟偏差均小于0.05% |

本轮1024×768：旧fixture下基线12/12、原候选2/2，标准接口下基线另2/2通过，
未复现上一轮同模式失败。
两版均有偶发模式切换失败，不能将上一轮单次失败归为候选独有回归；
当前没有稳定的候选独有复现供bisect。该对照也不证明所有失败都只有同一个原因。

基线1680×1050失败时 `link_ready=0`，cable/TMDS均118998046Hz、
PLL=1、SQO=1、align=1；新增日志包含 `reason=5v-or-align` 与
`cable=0x8000001a tmds=0x80009eaa`。就绪曾被撤销，稍后的状态已经恢复，
不能以恢复后的单次快照否定瞬态故障。
1080p24失败时记录过PLL=0、短暂非法FDET，以及74.25MHz时钟；
PLL=0可能来自接收器恢复动作，不能据此断言PLL是初始故障。
原候选1600×900日志出现cable约108MHz、TMDS约102.3MHz的多次admission拒绝，
失败后快照恢复为108MHz、PLL/SQO/align=1。
每模式日志保存前后增量；主动切换EDID引起的预期HPD事件不能当成独立的自发失锁。
原始帧矩阵没有持续V4L2 streaming，`stream_stops=0`、`faulted=0`；
不能将它表述为持续流恢复测试。

后续连续采样分析发现，1080p24曾在ready保持约4秒后才失锁，因此不能将全部失败
归因于初次判稳过早。Mac的mac-hdr-mode无参数调用只读取状态，图案程序不设置显示模式；
这些代码事实也不能排除源端后续重训、内容相关PHY问题等其他原因。

旧正式fixture通过/dev/mem直接写EDID RAM、拉HPD，绕过驱动的标准接口及link锁。
补充对照在停止One-KVM后，用相同EDID生成器、模式表、图案与判定，仅将传输层改为
VIDIOC_S_EDID/G_EDID：实际基线两轮38/38通过，原EDID已通过标准接口恢复并读回。
ABI与ARM64 Linux UAPI编译结果核对：结构大小40、指针偏移32、G/S命令
`0xc0285628`/`0xc0285629`。该结果提示必须区分测试协议与驱动故障，但样本量不支持
断言旧fixture就是全部故障根因。持续流源端变化测试不能替换成停服务后写EDID；
修复候选同时保留旧fixture测试与标准接口测试，不放宽ENOLINK判定。

原候选对照后正常重启回基线，独立inventory比对实际build ID、默认文件、
完整7.3/5.15模块文件、cmdline、UDC与taint一致，实际输出
`DEFAULT_FILES_MODULES_BASELINE_RESTORED`；服务active、UDC configured、taint=0。

## 厂商依据与修复候选

厂商源码固定linux `80a07ad5406d57855c996285ae75a50a1b9147ae`、common_drivers
`4cfb128d36f8511b2db1bd13c08d5704347ded49`。以下路径相对common_drivers：

- `drivers/media/vin/tvin/hdmirx/hdmi_rx_hw_t7.c` 的PHY表、PLL与
  `aml_eq_cfg_t7()`：65MHz对应PHY band1/PLL band1，低频4倍oversampling、
  10-bit CDR与宽PLL带宽设置，当前驱动已有匹配参数；没有证据支持另猜一组系数。
- `drivers/media/vin/tvin/hdmirx/hdmi_rx_wrapper.c:5244` 的 `FSM_SIG_STABLE`：
  更新视频信息、比较前后时序，连续达到 `sig_stable_max` 才进 `FSM_SIG_READY`。
  计数默认10；应复用连续稳定判定原则，不能直接照抄不同轮询周期的计数。

原驱动在PCS复位后只相隔20ms检查两次video_status，未比较跨轮询周期的时序与色彩。
新候选在已有250ms link worker中要求连续三次匹配的FDET/AVI观察再发布ready；
失败、时序或色彩变化重新计数。正常情况下首次准入多约500ms，
已经准入的持续流不增加逐帧延迟。保留现有有界EAGAIN处理与DMA lease保护，
等待稳定本身不重训PLL、不复位PCS；debugfs增加 `video_stable_samples`。

EDID替换主动拉低HPD时，旧驱动也保留ready，直到异步link worker发现失锁。
第二个修复在link锁内先撤销ready并清除判稳计数；写入失败恢复旧EDID也须重新判稳。
相同EDID的无操作更新和因DMA lease拒绝的更新保持旧状态。实际EDID操作测试覆盖这些边界。

分支 `fix/hdmirx-lowclock`，两个提交 `b1e6e76c1f739`、
`28f714cb714debc43fc9af610004c5cd13a336ce`，已推送fork；
基于fetch后的 `8b2553f7b3c62`。确定性测试执行实际link worker，覆盖短暂有效后失锁、
稳定恢复不重训、时序变化、色彩变化及未稳定前拒绝DMA。
RX目录全部13个离线测试通过，提交strict checkpatch：0 errors/warnings/checks。
这修复了可证明的准入缺口；是否消除现场所有模式切换失锁仍须上板验证。

完整Image、dtbs、modules构建通过，GCC13.3，无编译warning/error。
配置SHA256仍为 `8af98a1fbefdf163c407f9f04bb31372178b8f8d7d6f00f5dff162b930c968bf`，
Image SHA256为 `7b76924878e6d1e501a55da64882d1c99368348adab35271ead90b5a16f0cf3b`。
使用独立源码worktree `linux-7.3-hdmirx-lowclock`、O=`~/build/hdmirx-lowclock`，
未修改或切换内核主工作树。开始构建时再次fetch并检查远端基线为候选祖先；
当时仍为 `8b2553f7b3c62`。

## 第一版一次性验证与后续校准候选

第一版实际build ID `6179d3d853b838e0872cf6a31fc7b2446ee37c3f`，
RAM sysboot与完整模块核验通过。旧fixture首轮19/19、第二轮18/19；
第二轮4K30抓帧ENOLINK，1024×768两轮通过。因此未合入、未安装正式包，
后续标准接口与5分钟冒烟未执行，九类正式门禁未开始。

250ms连续采样显示4K30约356.876秒发布ready，359.887秒时PLL/SQO/align及
两路时钟读数归零，360.137秒ready撤销，361.895秒重新就绪；HPD请求与5V保持1。
失败后PHY只读快照与+3秒恢复快照均保留。计数器读数也可能受恢复动作影响，
不能仅凭这组异步快照断言源端停钟或模拟PHY是初始原因。
默认重启后inventory逐项比对kernel ID、默认文件、完整模块、cmdline、UDC、taint，
输出 `DEFAULT_FILES_MODULES_BASELINE_RESTORED`，仍为eeddb005、taint=0、UDC configured。
窗口释放双锁；正式版本锁保持原值。

进一步核对厂商 `hdmi_rx_hw_t7.c:497` 的 `aml_hyper_gain_tuning_t7()`，
由同文件 `aml_eq_cfg_t7():854` 在DFE收敛后、启用CDR锁检测前无条件调用：
选DFE tap0状态，等待100us，三路分别以tap0<0x12决定DCHA0[14:12]。
当前驱动遗漏这步。失败快照DCHD_STAT=`0x333534`，三路均高于阈值，
但DCHA0=`0x13270fff`仍保留初始全开增益；这证明与厂商初始化流程有差异，
不证明它就是本次ENOLINK的根因。

追加提交 `329be18274d5459937651ab73bd05758e41746f8`，仅恢复上述逐通道校准，
不猜测新PHY表参数；仍在既有DMA lease排除区间执行。测试实际PHY函数，覆盖三路
全部8种组合、0x12阈值、旧调试选择器、无关位保留、DFE/CDR先后顺序。
RX全部13测试与逐提交strict checkpatch通过，功能分支已推送，下一版仍须一次性验证。

增益校准版实际build ID `a6376319dfbb7d9094e84f9a30e3b5fa2ba5d6c4`，
旧fixture两轮34/38：640×480、800×600各失败两次，1024×768两轮通过。
640×480出现lease-timing拒绝，但日志只有宽高与ticks；其ticks差在现有500ppm范围内，
尚缺同步脉冲/前后肩的同次快照，不能据此修改比较容差。
该版也正常回eeddb005并通过相同完整inventory比对，没有合入或正式部署。
增益差异证据来自高频PHY band3；低频表的增益本来就是0，不能将校准描述为所有低频
失败的已证实修复。

追加 `ac7da8e03e8588302424306b49e8ef2292d1bb9f`，扩展原有ratelimited
lease-timing日志，打印前后两组全部FDET计数器，不改变比较规则。
时序离线测试、strict checkpatch及完整目标构建通过；实际build ID
`10eca3504dc2a2d6b1963137200c72cdf7964085`，2334个模块清单核验通过。
这个诊断版与上一版没有功能语义差异：短矩阵8/8、原19模式两轮38/38通过，
未抓到新的完整lease差异；这些通过不能覆盖上一版的失败或证明问题全部消失。
两次窗口均回默认eeddb005并输出完整恢复核验标记。Mac只读轮询记录模式变化，
不设置显示模式。随后标准接口候选两轮36/38，持续流冒烟未执行；
本阶段按用户指令结束，详见[收尾与待办](2026-10-23-hdmirx-lowclock-closeout.md)。

## 证据位置

本地忽略目录 `logs/rx-lowclock/` 保存baseline/results.json、baseline/samples.jsonl、
baseline-stress/results.json、original-candidate/results.json、baseline-api/results.json、
baseline-api/samples.jsonl，以及每模式前后状态、串口候选/回基线记录。
构建和候选验证追加到同目录；临时诊断脚本与小型构建元数据已归档到
`logs/rx-lowclock/reproduction/`，`build/rx-lowclock/` 已在收尾时删除。
