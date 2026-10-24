# 2026-10-24：厂商 5.15 周期黑屏修复

接续 [5.15 透传交付](2026-10-24-vendor-passthrough.md)。用户报告日常周期黑屏、自动恢复，
暂停合入并追加定向修复授权。

## 只读诊断

35 秒记录 227 次读回变化，RX 59.86–59.99Hz，其中 59.98/59.99 各 102/94 次；
41 次不匹配全部为 frac_rate_policy，没有 attr、sname 或 ready 不匹配。
原例：RX 59.97Hz 旧算法选 fractional=true，TX 仍 `"0\\n"`；
attr 为 `"444,8bit\\n\\n"`，ready 为 `"1\\n"`，sname 为 `2160p60hz`。
旧代码已 strip 外围空白，实际根因不是换行，而是每次取最接近的 60/59.94Hz，
在约 59.970Hz 分界两侧反复翻转，以读回不相等为由整批重设 TX。
相应 78 秒内有 18 次 `hdmitx_set_dispmode`，HPLL frac_rate 0/1 交替。
证据在 `logs/passthrough-515/blackout-readonly-{diagnosis.jsonl,kernel.log}`。

审计和测试确认 status 只读、不调用 tick；与 manager 轮询交错不是多 writer 的证据。
实际写入者为独占 flock 的 watch。

## 修复与验证

`vim4-manager@bf878a5`：

- 七次 RX 采样中值、分界 ±0.005Hz 滞回，新输入/sink 模式稳定两秒才重配。
- 缓存输入尺寸、稳定刷新率类别与 EDID 指纹；同一意图不因 TX 读回漂移反复 modeset。
- 规范化 sname 别名、颜色空白/后缀、数值；ready=0 防抖两秒，不能触发重设。
- 失败不每 0.5 秒重试，异常保留读回；真正重配记录原因、不匹配项和原值。
- status 不写硬件，第二 watch 在获得写权限之前被 flock 拒绝。

回归覆盖真实轨迹回放、真实 59.94/60 切换、输入抖动撤销、单次提交、失败不循环、
别名规范化、ready 瞬态/持续下降、只读轮询与双 writer。
manager Python 174 项（12 跳过）、Go 全套和 vet 通过。
备份 `/var/backups/vim4-passthrough-blackout-20261024`，仅替换脚本并重启跟随服务，
不重启 One-KVM、manager 或板子，不改内核/默认项。
脚本 SHA-256 `0f99b055660f1fffafb61a6761a26653183733ef0253c67d1c33c7791c45118f`。

15:16:56–15:26:56 UTC（排除服务初启五秒）600 秒内重设为 **0 次**，持续 running，
实际 RX/VDIN/TX 为 4K60。证据 `blackout-fixed-actual-4k-600.json`、`blackout-fixed-observe.jsonl`。
真实 1080p kernel cursor 观察未开始；用户最终说明仍发 4K、1080 为逻辑缩放，
取消 1080p 十分钟和新目视请求，授权保持板子现状、直接合入推送。
这不等于真实 1080p 或修复后长期目视无黑屏已通过。
