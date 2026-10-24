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
| 原候选第二轮 | 17/19 | 1080p60、4K60 QUERY_DV_TIMINGS ENOLINK |

本轮1024×768：基线累计12/12、原候选2/2通过，未复现上一轮同模式失败。
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

## 证据位置

本地忽略目录 `logs/rx-lowclock/` 保存baseline/results.json、samples.jsonl、
baseline-stress/results.json、original-candidate/results.json、每模式前后状态与
串口候选/回基线记录。构建和后续候选验证追加到同目录；临时诊断脚本在
`build/rx-lowclock/`，不作为产品运行时依赖。
