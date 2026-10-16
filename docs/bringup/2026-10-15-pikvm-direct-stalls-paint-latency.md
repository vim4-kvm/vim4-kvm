# 2026-10-15：PiKVM Direct 周期停顿与绘制延迟

用户确认只开一个播放页面。`.50` 的 Direct H.265 在 20 秒内出现 40 次超过
40ms 的 WebSocket 收帧间隔，最大 87.3ms；采集 memsink 同期独立短测最大
26ms，无超过 40ms 的间隔。单接收客户端的 WebSocket 压缩对照中，启用
permessage-deflate 时最大 80.49ms、40 次长间隔；禁用时最大 31.36ms、零次。
原因是 aiohttp 默认对已压缩视频再次压缩，大关键帧阻塞发送，并非采集帧率不足。

kvmd `dc508ede` 仅对媒体 WebSocket 禁用压缩，保留其他 WebSocket 的原有默认。
真实 aiohttp 握手回归验证客户端请求压缩时不协商扩展，元数据和心跳仍正常。
`.51` 构建、隔离校验和部署通过；12 项 Python 回归通过。用户刷新后反馈
“明显改善或已消失”。同样 4K60、12000 Kbps、GOP30、JPEG quality80 下：

| 20 秒窗口 | 收帧最大间隔 | 绘制最大间隔 | 超过 40ms 次数 |
|---|---|---|---|
| Direct H.265 修复后 | 33.1ms | 35.4ms | 0 |
| Direct H.264 修复后，预热完成 | 25.7ms | 36.5ms | 0 |

WebRTC 使用 RTP，没有上述 WebSocket 二次压缩路径。H.264 短测 60fps、零
丢帧/丢包/冻结，视频回调最大 33.4ms。H.265 短测也是 60fps、零统计丢帧/丢包/
冻结，但视频回调出现两次 100/116.7ms 间隔，不能声称所有模式完全无停顿；
回调可能错过已呈现帧，不能直接拿回调数量当解码帧率。

同一 H.265 连接对 jitterBufferTarget 做默认→0→默认对照，每阶段预热 4 秒、
采样 12 秒。实际缓冲驻留（jitterBufferDelay / emittedCount 的增量）为
12.99→11.17→10.17ms，均约 60fps、零丢帧/冻结，未证明设置 0 有可逆收益，
故不修改生产 WebRTC 缓冲策略。全程约 48 秒回调仅有两次 50ms 间隔。

kvmd `7729e1f6` 将 Direct 同一刷新周期内待绘制帧替换为最新解码帧，释放旧帧；
不丢弃尚未解码的依赖帧。确定性回归验证突发三帧只绘制最新帧、正确释放资源、
停止后不绘制残留帧；与 HEVC 解析共 3 项 Node 测试通过。编码切换/无音频
提示字号缩为原来的 80%。

Legacy MJPEG 浏览器确认 3840×2160 画面，另一个 HTTP multipart 接收器预热
3 秒后采样 20 秒共 936 帧（约 47fps），最大收帧间隔 28.89ms，超过 40ms
为零。该接收器使用带 Content-Length 的普通分段；浏览器仍使用 advance_headers。
不能把此传输节奏测量当作浏览器呈现帧率，亦未证明 MJPEG 能达到 60fps。
最初诊断错误地在 advance_headers 流中查找 Content-Length，所得空样本已作废。

`.52` 的 PiKVM/配套管理器包构建、隔离校验、部署健康检查通过；管理器现有开发
改动原样保留。板上 dpkg audit 无输出，PiKVM active，HDMI InvocationID 仍为
`3b6f4877c9184fc2b99525504ede4a06`。Chrome 确认提示为 12.8px、父元素 16px。
`.52` 两种 Direct 各 20 秒约 1200 个编码帧；H.265/H.264 最大收帧间隔
28.9/27.2ms，最大绘制间隔 37.2/37.6ms，超过 40ms 均为零。绘制周期内
合并帧会使 drawImage 次数少于解码数，不能把编码 60fps 等同于每秒绘制 60 次。
部署后 WebRTC H.264 的 20 秒回调最大间隔 33.5ms；H.265 延长到 60 秒后
有 7 次超过 40ms 的回调间隔，最大 100ms，解码仍为 60fps、统计丢帧/丢包/
冻结均为零。尚未定位这些零星长间隔的原因，未将 Direct 修复误称为修复了
WebRTC H.265 的全部停顿，也未通过缩短 GOP 或强行清空缓冲掩盖它们。
离线 Chrome HEVC 真解码、重连、菜单切换回归通过；主仓库 48 项测试通过。
最终编码 H.265；新增部署/回归证据在 `logs/pikvm/deploy52/`、
`logs/pikvm/cadence52-*` 和 `logs/pikvm/direct52-offline.log`。

证据：`logs/pikvm/cadence-*`、`logs/pikvm/buffer-rtc265.*`、`logs/pikvm/deploy51/`。
测量端为本机 Chrome、有线局域网、当前 HDMI 桌面；Direct 诊断浏览器临时将
板子 HTTP 地址视为安全上下文，不改变产品 HTTPS 要求。此处是帧间隔和浏览器
局部缓冲测量，不是运动场景、光学端到端延迟或所有浏览器/网络的稳定性承诺。
