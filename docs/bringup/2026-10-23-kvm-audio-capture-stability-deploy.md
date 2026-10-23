# 2026-10-23：HDMI 稳定性自动恢复验收与部署

承接[诊断与27轮历史](2026-10-23-kvm-audio-capture-stability.md)。用户接受真实链路失锁后
自动恢复，不接受永久停流、重启应用才能恢复、ASoC残留错误、taint或UDC掉线。
此标准不表示物理链路已修复，也不把坏窗口从证据中删除。

## 为什么更换 da19093a

da19093a…的27轮有24轮完整通过，3轮旧source-change门禁失败但应用自动恢复。
正式窗口依次保留在logs/kvm-stability：

| 窗口 | 实际结果 |
|---|---|
| formal-window | 19模式通过，H.264 1680×1050在成功快照后遇到ENOLINK及空DMA，旧即时断言中止 |
| formal-recovery-window | 原始模式、H.264/H.265及4K60过；音频48k段失锁产生21/35个track/tab坏窗口，约3.18秒报告恢复，但旧零中断门禁失败 |
| formal-qualified-window | 九类及四次HPD恢复全过，正常音频310/308个窗口、HPD616/613个窗口，bad均0；最终health发现两条ASoC -11，未finalize |

每次都自动回退7b8372b8…并核对三服务active、UDC configured、isolated=0、taint=0及实际键鼠/滚轮。
第三次错误位于启动后360.718/360.719秒：snd_soc_dai_hw_params和__soc_pcm_hw_params打印EAGAIN。
它违反用户保留的门禁，不能因音频已恢复而豁免；故没有正式部署da19093a…。

## 新候选及验证方法

内核功能分支fix/hdmi-capture-stability提交b076a35c47e7be0ef43da5431d9d6cd288ff2970，
基于aa2f875bec2fc；build ID d5740facf3a13781995e1f7267dac46e5f944d88，完整2334模块。
One-KVM仍为672b8fd9fdec1c35c35149265f901dc43da79394，manager仍为9b141c5833c0。
M0 DTB、Wave5隔离监控、配置与部署helper不变；本轮没有修改final-board.py。

新增修复仅把ASoC的EAGAIN与ENOLINK重试诊断记debug，保持errno和拒绝配置；
EIO/EINVAL/ENODEV/ERANGE仍报error。实际C测试各100次重试及真实错误、HDMI音频全套通过，
差异checkpatch为0 errors/warnings/checks。完整构建日志asoc-retry-build.log，测试asoc-retry-diff-tests.log。

复验四组各五轮0,1,1,0序列，保留帧推进、颜色、标记、快照和DMA断言及有界计数。
若ENOLINK后DMA为空，允许45秒新帧资格等待并复查3秒fps>5、内容、快照和DMA，PID/SSRC必须不变。
音频坏窗口只有同时存在RX失锁和音频自动恢复日志时才允许一次原采样率完整片段复验，
不重启应用、不刷新网页、不改源来帮助恢复；坏窗口单独保存，波形阈值不变。
所有音视频采样持board/heavy双锁，各组回退基线并通过实际HID后释放锁。

板上空间有限，清理只针对经manifest逐文件核对的候选暂存和candidate-modules；
基线files.tar/modules.tar/application.tar、元数据及独立rollback.sh均保留。
五轮窗口复用同一已备份基线，后续组先verify-restore，再安装候选。

## 待完成

新候选20轮、正式九类全量、finalize和部署分支/锁的发布尚未完成。
没有7b8372b8…同方法停流/恢复基线对照，按用户决定不补跑。
物理失锁的受控源/厂商5.15对照方案见[厂商差距](../vendor-parity.md)，需要用户现场窗口。
