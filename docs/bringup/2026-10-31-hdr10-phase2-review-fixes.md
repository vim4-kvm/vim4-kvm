# 2026-10-31：原生 HDR 第二阶段四项审查修复

核对独立审查原文与调用路径后，四项均确认为实际缺陷。本轮仅修复这四项、补离线回归并更新
修正包来源；**没有上板、M6操作或新增硬件验收结论**。仍须等待 main 的 tested_build 登记 uhd6。
后续[窗口补审](2026-10-31-hdr10-phase2-window-fixes.md)已另修C1–C4并以r14c替代本记录的r14b归档。

## 修复与提交

| 项目 | 提交 | 修复 |
|---|---|---|
| A1 PiKVM Wave5 SDR持续重建 | uStreamer `97eb951d10a0ccebd312d6951acc91624f5f0876` | 共享源选择与启动时HDR策略分别保存；运行期及退出后比较策略快照，真实失败保留退避，退避期间策略改变可唤醒 |
| A2 metadata丢AU后预测帧泄漏 | gst-venc `3a74cc9c0f074ff8bf980440e426438bba65d1db` | controls读取对EINTR重试；真正丢AU后等待IRAP，恢复时请求关键帧；恢复首AU携带新鲜SEI并设DISCONT |
| B3 sampling清理异常中断恢复 | main `eb8d884b118fcb844a898e53c96c59cf45d696ca` | sampling、服务、转发终止/回收及回基线分别尝试；异常汇总并保留原始失败；每段操作前验证剩余租约覆盖有界工作及恢复 |
| B4 reuse-staged权限/内部链接遗漏 | main `961ad98dc5fa208e2a6abe5bf2dae104e4d6043b` | 复用逐级核验root所有者、真实0555目录、按首次staging归一化的0555/0444文件及内容哈希，拒绝内部链接目录 |

A1/A2已push各自 `p0-5-native-hdr`。B3/B4在独立 `p0-hdr-tool-fixes` worktree 从最新
origin/main实施，全套通过后以快进合入main并push；main为eb8d884。HDR分支已同步这些工具，
没有修改内核或正式制品锁。工具修复不包含任何新应用功能或额外性能调优。

租约已失效或恢复时间不足时，工具不向板子发送无票据的服务/重启操作；保存
`recovery-required.json` 留待协调者交接。SSH转发仍在本机独立清理。
原始测量异常保持为主异常，清理异常附在notes并保存到 `cleanup-errors.json`。

## 离线证据

| 门禁 | 结果与边界 |
|---|---|
| PiKVM生产循环回归 | `tests/test_vim4_hdr_loop.py` 提取实际生产循环，使用真实GStreamer bin/bus、模拟帧/时钟/策略；SDR多次轮询只建1次，HDR→映射→HDR共3次，真实失败进入退避；连同既有解析测试2项通过 |
| uStreamer/Janus | ARM64增量构建通过；不作为实际采集/硬件编码或声音测试 |
| metadata读故障 | 新 `/hdr10/interrupted-metadata-read` 验证一次EINTR后读成功、EIO不重试，输出BE metadata正确 |
| AU恢复 | 新 `/h265-source/metadata-loss-recovery` 丢一个IRAP后抑制预测AU、只请求一次关键帧，恢复首IRAP带当次新鲜137/144及DISCONT；下一预测帧正常通过。为合成AU边界测试，不宣称解码器像素/板上故障注入通过 |
| 编码插件 | DMA生命周期通过，公共源9项、HDR10 4项通过，无跳过；实际插件重新编译通过 |
| perf-quick | 5项通过：sampling off异常仍恢复原服务；过期拒绝越权并留交接；预算不足操作前拒绝；编码器之间重查预算；接收失败后sampling/转发/回基线多处失败仍逐项尝试，保留原始错误 |
| staging | 新7种破坏用例：init去执行位、runtime去执行位/增加写权限、内部目录链接、目录/文件非root所有者、目录可写；全部拒绝，既有完整复用与大小写模块用例保持通过 |
| main全套 | 375项，14跳过，其余通过；日志 `/tmp/herdr-workers/hdr-tools-full-tests.log` |

ARM64构建与回归日志保留在HDR worktree `build/p0-5/review-c-final.log`；工具故障注入日志为
`/tmp/herdr-workers/hdr-tools-quick-tests.log`、`hdr-tools-stage-tests.log`。所有构建/全量测试经
共享board-queue heavy票据运行，没有持板编译。未重新构建完整内核或未修改的应用。

## 修正包

旧 `hdr10-p0-5-userspace-r14a` 包含A1/A2缺陷，已由 `hdr10-p0-5-userspace-r14b-review.tar.gz`
替代；旧两份uhd5 RAM干跑包只保留历史清单证据，禁止当作修复包或上板候选。
新包仅替换上述两个二进制，其余文件逐个对照旧封存SHA不变，再完整读取新归档复验。
来源与逐文件SHA见[当前清单](../../packaging/hdr10/phase2-sources.json)。

```text
archive SHA256 8cd6fb4dcd4d54b9f09a0953439cff4a41519029cc2c9fbfa6a25039d9cb0f19
libgstvim4hevc10.so f0de5d107d4d2c55a4ac2dfd2bf47054363ad90a45fab19c38b4ab41e0931e21
ustreamer 9d9a568dfe65d0378791a7272b188a9953ba3fe9dba347049032a64a53f25e34
```

新包在 `build/p0-5/`，清单仍为 `hardware_validated=false, kernel_included=false`，不是可直接启动
的内核候选。后续只从该包组装匹配uhd6的两种GPU payload；四项修复及此前窗口脚本仍待独立复审。
实际UU解码/渲染、三应用HDR/切换/缩放、原生SDR截图、非零真实metadata与两GPU栈实板门禁均未补验。
