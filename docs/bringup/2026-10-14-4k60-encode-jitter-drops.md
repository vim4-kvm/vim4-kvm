# 2026-10-14：4K60 编码链路抖动与丢帧检查

NanoKVM 现有配置（3840×2160、30000 Kbps、GOP120、cbr），Mac HDMI 运行
`latency-source --motion`，Chrome 单 viewer 采样 60 秒，临时开启
VIM4_VIDEO_TIMING 与 vfmcapsrc 计时，结束后已移除并重启服务。

- 板端稳态 3736 帧、59.998fps：采集序号无间断，采集间隔 p99 16.81ms、
  最大 24.05ms；DQBUF 等待 p99 0.06ms；vfm_cap frames_dropped 为 0。
- 采集到应用拷贝：P 帧 p50 11.98 / p99 14.91ms；关键帧 p50 18.45ms，
  超过 16.7ms 但未造成后续积压或丢帧；最大一次 37.70ms（关键帧），后续帧恢复。
- 编码输出间隔标准差 1.55ms；关键帧约 650KB，实际码率 30.88 Mbps。
- Chrome：60.0fps，丢帧、丢包、freeze、NACK、PLI 均为 0；抖动缓冲平均 2.25ms，
  解码帧间隔标准差 7.64ms，大于板端编码输出抖动。

证据：忽略入库的 `logs/encoder-jitter/`（journal.log、chrome.jsonl、分析脚本）。
