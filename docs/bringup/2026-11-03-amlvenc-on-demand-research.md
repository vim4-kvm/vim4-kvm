# 2026-11-03：5.15 amlvenc 按需 IDR 离线调研

用户决定先不改 5.15。本记录只保存离线结论和登记的 issue，未持板、未运行编码。
7.3 的做法见 [Wave5 AVC 恢复帧 QP](2026-11-03-wave5-avc-recovery-qp.md)。

## 结论

- **H.265**：可以只改各应用的 amlvenc 参数：`gop=0`、`intra-refresh-rows=0`、`i-qp-min=26`。
  5.15 HEVC 已实测 GOP 0 与 −1 只在启动和请求时出关键帧。插件没有关闭 CU 级码控与 HVS 的属性，
  所以无法严格复现 7.3 的帧级码控 D；关键帧之后画面能否继续补清晰，要上板测。
- **H.264 F**：系统 `libvpcodec.so` 导出 `vl_video_encoder_change_qp`，但应用经由的
  `libamvenc.so` 和 `amvenc.h` 只开放 `change_bitrate`。实现需要在中间层加 change_qp 转发、
  开启 `ENABLE_PARA_UPDATE`（0x2），再在插件里按 IDR 重置计数，属于小范围用户态改动。
- **收益**：去掉行刷新后，One-KVM 和 UU 的静止带宽下降，5.15 记录为 AVC 4.28→0.52 Mbps、
  HEVC 约 19.8→10 Mbps（编码控制）。NanoKVM、JetKVM 的
  GOP 120 和 PiKVM 的 GOP 30 改为 0 后，可消除周期关键帧尖峰。

## 登记 issue

评分均为频率 × 严重度。5.15 只作后备内核，以下各项都只登记，没有改代码。

| 位置 | 问题 | 评分 |
|---|---|---|
| `gst-plugin-venc/amlvenc/gstamlvenc.c` 输出缓冲 | 只把 `encoder-buffer-size`（默认 2048 KiB）的裸指针交给 SDK，没有传容量；关键帧加参数集超出时可能越界写，返回后再比较长度太迟 | 2 × 8 = 16 |
| `gstamlvenc.c` 同步帧标记 | 按请求的帧类型而不是实际输出标记 SYNC_POINT，编码器自发的首帧会标成非同步帧；下游 parser 只能修正一部分 | 2 × 3 = 6 |
| `gstamlvenc.c` 错误日志 | `encode_data_len` 初始化为 −1 后未填充，所有无效 metadata 的错误日志都打印 −1 | 2 × 1 = 2 |
| NanoKVM、PiKVM 设置校验 | 本轮把 Wave5 默认 GOP 改为 0 时放宽了下限，5.15 vendor 后端现在也接受手动设置 GOP 0；按上述结论这能工作，但未在 5.15 上板验证 | 1 × 3 = 3 |

输出缓冲一项评分达到 16，再在 5.15 上做编码相关工作时先修。完整调研见
`logs/wave5-refresh/aml515-moonlight.result.md`（不入库）。
