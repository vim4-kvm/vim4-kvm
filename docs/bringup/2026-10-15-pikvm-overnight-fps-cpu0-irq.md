# 2026-10-15：PiKVM 隔夜降帧：采集线程与 CPU0 中断争用

用户另一台电脑的 Chrome 连续观看一夜后，报告约 30fps 并伴随停顿。
保留 `.40` 的运行现场：服务未重启，uStreamer 已运行约 8 小时，H.265、
3840×2160、60fps、12000kbps、GOP30。输入仍约 59.98Hz，但采集与编码
输出约 32fps；温度约 55°C，内存充足，无交换压力。此前各 300 秒的测试
没有覆盖这种运行时间和调度状态，不能据此宣称隔夜稳定。

JPEG 编码线程运行在 CPU0，而 Ethernet IRQ53 与 JPEG IRQ65 也全部落在 CPU0。
该线程累计 CPU 占用约 54%，主要是内核态；UDP SndbufErrors 累计超过 284 万，
Janus 连续报发送失败。未重启任何服务，仅改变该线程亲和性后恢复约 60fps。
进一步对照：固定到 CPU0 六秒，帧率降到 35–50fps，UDP 发送错误增加 575；
移到 CPU1–3 六秒，恢复到 60fps，发送错误不再增长。CPU0–3 是 A73、
CPU4–7 是 A53；两组避开 CPU0 都能恢复，不能归因为“大核性能不足”。

kvmd `68c8a046` 用 taskset 将 uStreamer 及其工作线程限制在 CPU1–7，
保留其他服务与中断配置；组件包显式依赖 util-linux。此为针对已复现争用的
调度规避，没有修改 JPEG 内核驱动。初步双观看者测试仍出现过短暂 UDP 发送
错误，需要结合浏览器 freeze 和长时采样判断，不能只凭板端 60fps 判定全部卡顿消失。
证据：`logs/pikvm/overnight/initial.txt`、`cpu0-vs-cpu1-3.txt`、
`live-affinity-board.jsonl`、`live-affinity-soak.log`（同目录）。

保留旧进程的 600 秒浏览器观察解码 35962 帧，其中一次 0.519 秒 freeze、328 个
丢包，对应同一秒板端新增 656 个 UDP 发送错误；其余采样 59–61fps。另一新会话
在双观看者窗口观察 180 秒，解码 10800 帧，零丢帧、丢包与 freeze，最大回调
间隔 66.7ms。这说明亲和性修正已消除持续降帧，但旧现场仍有一次短暂停顿，
其独立原因尚未确认，不能把此次结果记为“全部卡顿修复”。

`.41`（`2.5.1+vim4.20261015.41`，配方 `bf20d4f`）干净构建、隔离验证、
board.py deploy 通过；重启后逐一核对视频线程 CPU 允许集合均为 1–7，
sudo dpkg -V 无差异。正式包 H.265 双观看者加运动窗口观察 300 秒：解码
17994 帧，RTC 丢帧、丢包、freeze 增量均为 0，最大画面回调间隔 83.4ms；
运动检查取得 8 个不同哈希，JPEG 快照通过。此处运动标记为 1200×800、10Hz，
并非全屏 4K 高运动负载；启动阶段的 video playback quality 累计丢帧为 36，
不包含在稳定窗口的 RTC 增量结论中。采样期间板端 UDP 发送错误未增加。
smoke 的运动标记现在在 soak 前启动，避免“运动测试”实际只覆盖长测结束后的几秒。

留下有明确结束时间的诊断：板端 `vim4-pikvm-monitor-41.service` 最长运行 12 小时，
每 10 秒将流状态、温度和 UDP 计数写入 `/var/tmp/vim4-pikvm-monitor-41.jsonl`；
Mac 的临时 headless Chrome 每分钟写入
`logs/pikvm/overnight/package-41-12h-browser.jsonl`，12 小时后关闭。
它们不随产品安装；后续需检查实际记录，尚未完成隔夜验收。
正式包证据：`build/pikvm-package-41.log`、`build/pikvm-verify-41.log`、
`logs/pikvm/deploy-41/`、`logs/pikvm/overnight/package-41-motion.log`。

候选镜像 `build/images/vim4-kvm-ubuntu-pikvm41/` 同步包含该包，默认 PiKVM/H.264；
离线组装、验证、导出校验和 flash dry-run 通过，未刷写 eMMC，未验证首次启动。
