# 2026-11-05：r50 全集采样预算与 Sharp 尾帧缺失

`.27` r50 在预算内运行 65 条不同码流：54 Success、11 Fail，70 条未运行，
没有 Error/Timeout。两条 Sharp 的 Fail 实际是各少一帧，现有帧都与对应参考
逐字节一致；尚未证明缺帧发生在 GStreamer 还是 V4L2 队列排空，不修改驱动。
候选身份和前置检查见[场缓冲记录](2026-11-05-vdec-field-lifetime.md)。

## 窗口与结果

先对 Sharp_MP_Field_1_B、Sharp_MP_PAFF_1r2 使用 Fluster 原生 `--keep`，
再按 JVT-AVC_V1 顺序遍历 135 条。只保留点名码流的原始输出，未改解码插件。
顺序遍历完成索引 0–62（54 Success、9 Fail），触及预留恢复预算后正常停止；
两条提前运行的 Sharp 位于索引 120、123，均 Fail，合计 65 条不同码流。
70 条未跑项将在新基线候选上重新跑全集，不能把不同源码结果合成通过总数。

原始证据：

- `logs/hwdecode-parity-r50/validation-fluster-1793894984359970000/results/`：
  主目录为 Field，`fluster-followup-0` 为 PAFF，`fluster-followup-1` 为全集部分；
  各目录保存原始逐流 JSON、日志和全套状态（含 Not run）。
- `window-status.json`：流程成功，conformance 未全通过；全集摘要明确
  `window budget reserved for recovery`。不是超时中断。
- `build/hwdecode-parity/run50/board-upload.tar` 与 `board-upload-files.json`：
  700 个文件逐项 SHA 核对，并复核板端未变后删除本轮上传目录。
- `run50/retained-output-sizes.json`：两个文件均为 7,257,600 字节，
  小于期望 7,776,000 字节；原始错误输出已归档，未因长度不符丢弃证据。

恢复后 `.3` release/build ID/正式文件身份核对通过。Mac 实际解码 3840×2160
H.265，5 秒 298 帧、59.57 fps，新增 dropped/freeze/lost 均为零，见
`logs/hwdecode-parity-r50/returned-video.log`。本次没有运行 HEVC/JPEG，
没有观察到内核 BUG/WARNING/Oops 或解码超时；仍只代表生产配置功能检查。

## Sharp 逐帧与逐场证据

宿主 FFmpeg 解码相同且 SHA 核对的输入，两条参考均为 720×480 I420、15 帧，
长度满足 `15 × 720 × 480 × 1.5 = 7,776,000`，MD5 与锁定 Fluster 套件一致。
原始硬件文件均为 14 帧，满足 `14 × 720 × 480 × 1.5 = 7,257,600`。

| 码流 | 参考 MD5 | 硬件输出与参考对应（索引从 0 开始） | 缺帧 |
|---|---|---|---|
| Sharp_MP_Field_1_B | `069ca95648563a3d0d78121588b506ee` | 输出 0–13 逐字节等于参考 0–13 | 参考显示帧 14 |
| Sharp_MP_PAFF_1r2 | `e31b7df5a2e5dde2b5c8ede9d3aec16d` | 输出 0–12 等于参考 0–12；输出 13 等于参考 14 | 参考显示帧 13，即最后解码的 B frame |

Field 没有已有帧的首个错误像素，差异从参考第 15 帧缺失开始。PAFF 若按位置
直接比对会把输出索引 13 判为错误，但跨帧精确匹配证明它是正确的参考帧 14；
不能将缺帧后的移位误判为参考预测或场像素损坏。每帧 Y/U/V 的偶数行、奇数行
分别保存差异计数及跨参考场匹配结果。

分析产物在 `build/hwdecode-parity/sharp-analysis/`：`*.reference.json` 保留
ffprobe 的显示/编码顺序与 pkt_pos；`*.reference.log`、`reference-run.log`
保留实际参考解码输出；`*.comparison.json`、`*.out` 和 `*.reference.i420`
保留逐帧/场比较、硬件与参考原始文件。一次性分析脚本仅在 build/，不是仓库测试。

## 码流条件与定位边界

已有 FFmpeg trace_headers 原始 trace 和 `*.slices.json` 表明：

- Field 为 15 对上场 I / 下场 P，POC type 1，没有 B slice、MMCO、长期参考或
  显式参考列表重排。最后一对 frame_num=14，上场 I；下场 P 使用默认 L0，
  `num_ref_idx_l0_active_minus1=8`。
- PAFF 混合 frame/field，POC type 1，没有 MMCO、长期参考或显式列表重排。
  缺失的最后解码图像是 frame_num=6 的 B frame，spatial direct，默认 L0/L1，
  active_minus1 分别为 3/0。它应显示在最后一个参考 P 场对之前。
- 两条流末尾均有 NAL 10/11。已输出的所有参考帧和场像素正确，现有证据不支持
  直接修改 PicNum/LTR、colocated 或合成场地址。

接下来同时检查锁定 GStreamer 1.24.2 的 parser/decoder EOS 与 bump/drain，
以及驱动 `v4l2_m2m_ioctl_stateless_decoder_cmd()` 的 FLUSH、最后 job 的 HOLD
释放。用 V4L2 日志确认末帧是否提交、CAPTURE 是否 DQBUF，再决定修改位置；
现在不能把缺帧归为固件或已证实的用户态限制。若证实为用户态问题，按 CVFC1
登记限制，不维护私有插件补丁。

随后在宿主构建同一锁定源码中未修改的 h264parse，独立运行
`filesrc → h264parse → byte-stream/AU → filesink`。Field 的 30 个 slice、PAFF
的 23 个 slice 全部保留，逐 NAL payload SHA 与原输入顺序一致。证据为
`sharp-analysis/parser-identity.json`、`parser-probe.log`、`*.parsed.trace` 和
`parser-slice-comparison.json`。此实验没有 V4L2 设备，只排除了该宿主 parser
路径丢弃 slice；不能替代板端 decoder/DQBUF 跟踪，也未确定缺帧归属。

按协调要求，后续内核先 rebase 到集成基线
`fd41fb5950b9da1fb336ce00d5137d27ee9755fa`，保存 range-diff 并逐提交重新构建与
运行 KUnit。`.27` 部分全集结果不代表新基线通过。
重放与逐提交检查见[集成基线记录](2026-11-05-vdec-integrated-rebase.md)。
