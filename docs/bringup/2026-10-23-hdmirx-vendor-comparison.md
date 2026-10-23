# 2026-10-23：HDMI RX 同链路 7.3 / 厂商 5.15 十分钟对照

摘要：同一 Mac HDMI 源、线缆、运动程序、4K60 RGB/4:4:4 8bit、H.264 下，
正式 7.3 十分钟出现 12 次浏览器冻结、12 条 TMDS 拒绝事件；厂商 5.15 十分钟
冻结、RX 信号丢失及重新锁定事件均为 0。不能继续将这些停顿统称为源/线缆物理失锁，
已定位 TOP meter 的短暂无效标志被误判为 ENOLINK；修复候选十分钟零冻结、零停流，
四次 HPD 与采样率切换自动恢复，无 ASoC 错误。
一次配对不能证明所有线缆/源或长期场景都健康。

## 版本、同条件与窗口边界

入场主仓 `70eab885`，先 pull；正式内核 `0a775305f0ad8`，build ID
`3a3cd15ca69e6084238d3bda54e41c56f6a16776`，M0 DTB；One-KVM
`672b8fd9fdec`、manager `9b141c5833c0`。厂商运行内核为
`5.15.137-vim4kvm`、build ID `389f77352dc8ab21aa80d8cf36819bb9da31d7ee`；
参考源码 Linux `80a07ad5406d` / common_drivers `4cfb128d36f8`。
部署基线见 [PCM/SARADC 正式窗口](2026-10-23-kvm-audio-capture-stability-deploy.md)，
启动方法见 [厂商一次性启动](../vendor-boot-baseline.md)。本次用户明确授权无需现场值守的对照。

Mac 持有 `/tmp/vim4-board.lock` 与 `/tmp/vim4-heavy.lock`，覆盖启动、采样与恢复；
队列不占板等重型编译。Mac 同一 `latency-source --motion --verify-coherence --no-labels`
生成运动标记；Chrome 156.0.8078.47、同一 One-KVM H.264 设置、同一采样程序，
连接预热 15 秒后观测 600 秒。每十秒读 WebRTC 统计和 64×36 像素摘要，首尾截图；
板上每秒只读 RX/采集状态和程序内计数，不用 strace、不轮询大图或注入失锁。

首次 5.15 预检发现仅有 4K30 可选模式，没有计入对照，预检超时后正常回 7.3 并验 HID。
原因是厂商 `rpt_edid_selection=2` 将 HDMI-OUT 采集卡能力与输入 EDID 取交集。
第二窗口按 `hdmi_rx_edid.h` 的 `use_edid_def=1`，仅在运行时向 RX `param` 写
`rpt_edid_selection 1`，调用已安装 `vim4-edid` 的 `load()` 重新发布同一 RTK 表。
没有调用其持久保存接口，也没有调整 PHY/EQ/CDR、日志级别或厂商失锁门限。
Mac 读回 256 字节 EDID SHA256 与 7.3 完全一致：
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。
Mac 实际模式为物理 3840×2160、逻辑 1920×1080@60Hz；厂商 `mode=2160p60hz`、
`colorspace=444`、`colordepth=8`。厂商初始 EDID 哈希不同，故初始 4K30 数据不能混入。

## 配对十分钟结果

| 指标 | 正式 7.3 | 厂商 5.15 |
|---|---:|---:|
| UTC 计时区间 | 16:25:10.766–16:35:10.802 | 16:49:47.306–16:59:47.375 |
| 解码帧增量 | 35,089 | 36,004 |
| 按接收统计时间计算平均帧率 | 58.47709 fps | 60.00029 fps |
| 浏览器冻结 / 累计冻结时长 | 12 / 15.695 秒 | 0 / 0 秒 |
| 浏览器丢帧 / 丢包 | 0 / 0 | 0 / 0 |
| TMDS 拒绝日志 | 12 条 | 0 条信号丢失/离开 READY 日志 |
| 采集队列停止增量 | 15（15→30） | 无 drain/SM 离开稳定态事件 |
| 1Hz 只读采样最大开销 | 1.089 ms | 1.517 ms |

两侧连接均保持、SSRC 不变、像素摘要持续变化。7.3 的 15 次队列停止不能当成
15 次独立物理失锁：包含同一恢复过程里的 `dma-wait`、`link-not-ready` 等后续动作。
7.3 同一窗口 12 条事件的 journal 单调时间（秒）：

```text
1537.524105 1713.748577 1718.376684 1722.310081
1777.929801 1800.111371 1825.028454 1832.229316
1972.518695 2013.354110 2040.865360 2107.333552
```

其中八条逐帧检查日志仍为 `pll=1 align=1`；另四条是 link worker 的资格撤销。
631 个 1Hz RX 快照中 SQO、PLL 均为 1，仅一个快照 alignment=0，四个 link_ready=0。
低频快照可能漏掉短暂变化，且恢复本身会改 PHY 状态；这些证据不足以归因物理失锁。

厂商计时范围内 600 个 1Hz 样本始终 `hw_info=13b11`、signal_stable=1、
`sm_state=5`、`draining=0`。采集首尾样本间隔 599 秒，received 8,211→44,152，
delivered 977→36,918，dropped 始终 0。预检重新发布 EDID 时确有一次 signal lost，
发生于启动后约 63.8 秒；正式计时约在启动后 178 秒才开始，明确排除该人为事件。

## 拒绝瞬间定位与修复候选

厂商 `aml_get_tmds_valid_t7()` 使用 SQO、`is_tmds_clk_stable()` 与 alignment；
T7 的两路时钟由独立 meson 测量通道 44/43、32µs 窗口更新缓存。
7.3 每帧直接要求 TOP 两路 meter 的有效标志、非零计数和 2MHz 匹配，任一失败就
返回 ENOLINK 并停止队列。两者在测量有效性、瞬态处理及 PHY 自适应流程上存在差异。
不通过放宽有效门限或盲改电压/均衡系数来掩盖问题。

在 `fix/hdmirx-tmds-qualification` 上加入限频原始快照，诊断提交 `1a9c921cd4c0`，
保持原判定行为；同次完整 Image/模块 build ID `282e99f6538f14ffda6414744cbe293b17450d08`
用静态 PID1、私有模块目录及 RAM sysboot 一次性启动。300 秒运动采集复现三次冻结，
累计 3.756 秒。关键实际输出：

```text
[194.661450] TMDS admission: sqo=1 cable=0x8000c5ff tmds=0x317fd reference=24000000 ratio=4
[194.661738] link readiness revoked: reason=tmds-invalid error=-67 retries=0 users=1 configured=1
[237.561600] TMDS admission: sqo=1 cable=0x8000c5ff tmds=0x317fc reference=24000000 ratio=4
[237.562071] capture check: tmds-invalid error=-67 width=3840 height=2160 ticks=2777823 lease=3840x2160/2777825 pll=1 align=1
[252.928644] TMDS admission: sqo=1 cable=0x8000c5ff tmds=0x317fd reference=24000000 ratio=4
[252.928702] link readiness revoked: reason=tmds-invalid error=-67 retries=0 users=1 configured=1
```

三次 TMDS 计数均对应约 594MHz，却短暂缺少 bit31 VALID；SQO=1，逐帧失败时 PLL、
alignment 也仍为 1。随后重训才出现 `cable=0x22 tmds=0x86` 等小计数。
由此确认本次停流的直接触发为软件把测量空窗等同于链路消失，不能倒置恢复状态与起因。
诊断窗口结束回 `3a3cd15c…`，同文件/模块、60 秒零冻结冒烟及 HID/隔离检查通过后释放双锁。

功能修复提交 `b1300eb808f43`：TOP 任一路测量 VALID 暂不可用返回 `-EAGAIN`，
VDIN 丢弃该帧后继续采集；不输出每次重试日志。5V、SQO 或 alignment 丢失仍立即 ENOLINK，
已完成但非零/差频条件不满足仍 ENOLINK，2MHz 容差不变。既有 link worker 允许四次
250ms 重试，持续异常仍撤销资格，待 DMA lease 释放后恢复，不会无限保留无效流。
这只改变视频测量分类，ASoC `hw_params`/prepare 生命周期及 One-KVM 资格/退避实现保持兼容。

13 个 HDMI 离线测试脚本全部通过；新增实际 capture/timing-query 边界验证：两路 meter
分别缺 VALID 时可重试、查询不发布无效输出，真实 SQO/alignment/5V 丢失和差频仍拒绝，
恢复有效计数后成功；既有 worker 测试覆盖持续 EAGAIN 有界恢复及 lease 保护。
两个提交 checkpatch 均为 0 errors / 0 warnings / 0 checks。功能候选 build ID
`eeddb005df059a850853876d52ef603aa1af192b`。

## 修复候选一次性验证

同源、同模式、同程序，UTC 17:24:40.097–17:34:40.130 的 600 秒窗口：
解码增加 36,002 帧，59.99954 fps，冻结/冻结时长/丢帧/丢包均为 0，SSRC 不变；
61 个像素摘要各异。600 个窗口内只读样本的 stream_stops 增量为 0。
invalid_frames 增加 14,382，是既有混合拒帧计数，不能全归为 meter 空窗或当作停流次数。
未添加逐帧日志；真实 ENOLINK 原始快照仍限频。

随后四次 HPD 失锁，依次确认 48k/44.1k/32k/48k 的非零解码声音；实际输出
`AUDIO_LOSS_CONTINUITY_PASS SAME_APPLICATION_PID 919`、`AUDIO_RESTORED_48000`、
`AUDIO_NO_RESIDUAL_ERRORS_PASS`。EDID 读回恢复原哈希。失锁后再次确认候选 build ID、
全启动日志无 ASoC error/oops/BUG/panic/WARNING，taint=0、isolated=0、三服务 active、
UDC configured；原生键鼠 HID 通过。

正常回 `3a3cd15c…`，12 个文件及两个完整模块目录与入场相同，60 秒运动冒烟及 HID/
隔离检查通过；删除本次私有候选目录并 sync，窗口退出释放双锁。
功能分支两提交推送后，正式分支仍为其祖先 `0a775305…`，故直接 fast-forward 至
`b1300eb808f43` 并推送，没有 rebase 或引入其他子系统，复用同次已验证完整构建。
正式安装使用部署文档的单一 RX 子系统门禁，不重复九类全量。

## 恢复与原始证据

第二个厂商窗口正常重启 25.551 秒到 UART login，默认回到 `3a3cd15c…`；
没有改默认启动项、U-Boot 环境、Image/DTB、模块或运行登记。12 个受保护文件和
两个内核完整模块清单逐项与入场一致。厂商 taint=12288 对应既有树外/缺签名模块，
不能写成厂商 taint=0；返回 7.3 后 taint=0、isolated=0、UDC configured，
one-kvm/manager/Wave5 monitor 均 active。60 秒 4K60 运动冒烟零冻结；真实原生 HID
键按下/抬起、绝对/相对鼠标、点击与滚轮均通过。临时 boot 配置已删除并同步目录。

完整日志不入库，位于 `logs/kvm-stability/`：
`vendor-compare/`（7.3 十分钟、首次 4K30 预检与回退）、`vendor-compare-second/`
（厂商十分钟、EDID 两次读回、UART、恢复清单及 HID）、`vendor-comparison-summary.json`。
诊断候选与修复的离线/构建日志分别为 `tmds-diagnostic-*`、`tmds-fix-*`。
记录保留全部预检失败，没有将其算作可比的 4K60 样本。
