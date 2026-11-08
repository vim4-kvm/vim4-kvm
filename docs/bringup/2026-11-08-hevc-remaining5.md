# 2026-11-08：HEVC 剩余 5 条失败的修复与 .44 板验

标签：kernel video

起点是 `.42` 全集 127/132（[.42 逐流结果](2026-11-07-vdec-integration42-pd-results.md)）。
最终内核为 `vim4-kvm-7.3` 34fbda5a776e，release 7.3.1-vim4-20261108.44，GNU build ID
42de7aef726351e659cc2d1dbae153e25102e5c8。用户已批准有限的内核码流解析：slice LT 语法、SPS/PPS
前缀缓存，以及对固件限制的快速拒绝。

## 根因与处理

| 码流 | 根因 | 处理 | .44 结果 |
|---|---|---|---|
| RAP_B_Bossen_2 | 内部编码尺寸/CTU 变化时，可见格式、crop、min buffers 都没变，stateful 层仍发 SOURCE_CHANGE 和 LAST，并停掉 CAPTURE | stateful 层比较查询值。值不变时无 LAST 交付 pending、内部重配、重放同一 OUTPUT，不发事件 | Pass，80 帧，1 次 SOURCE_CHANGE、1 次 CAPTURE STREAMON |
| RPS_D_ericsson_6 | 固件 RPM 的 LT 条目只有 LSB；POC1108 的 DPB 同 LSB 有 1017/761/505，无法按 LSB 分配 | 解析 slice LT 语法（含 delta_poc_msb_cycle_lt，按 7-52 累加），按完整 POC 匹配，并与 RPM 交叉校验 | Pass，68 帧 |
| VPSSPSPPS_A_MainConcept_1 | 未解决。首 AU 约 300 个参数集，固件返回的 RPM 中 SPS 字段全为 0 | "SPS 先于其 VPS"的假设被否定：前缀重排会触发，只把 VPS1 提前也一样，仍是 invalid RPM（-74）。重排提交未合入 | Error，0 帧，快速失败、无超时 |
| LTRPSPS_A_Qualcomm_1 | 固件解析非空 SPS 长期参考列表时卡死。全 I 母本：列表 0 条 Pass，1 条超时（status 02、shift 0x50）；LTRPSPS 首 AU 列表清零后 Pass | AU 含有或激活非空 SPS LT 列表时，在送固件前返回 OUTPUT ERROR | Error，0.27 秒，无内核超时 |
| WPP_D_ericsson_MAIN_2 | WPP 加 1 列 CTB 的 inter 图卡死。64x240 CTU64 关 WPP 能解（12 帧 Pass），2 列 WPP（WPP_E）也能解 | 激活 entropy_coding_sync 且 PicWidthInCtbsY==1 的图一律拒绝（含 IDR） | Error，0.27 秒，无内核超时 |

排除了一个假设：SCRATCH8（swap overlay 地址）并非只在上电时恢复。每个 job 的 `aml_hevc_prepare_hw()`
都会在 reset 后写回，主机的 RPM 地址写的是 SCRATCH1。原分析误读了这一点，对应的重复提交已丢弃。

## .44 板验

两次 RAM 候选启动，均回到正式基线（原视频约 59.6 fps，零丢帧）：

- 离线门禁：arm64 QEMU KUnit 77/77；模块 W=1 与 sparse 通过；6 个提交的 strict checkpatch 通过
  （新增测试数据头的 FILE_PATH_CHANGES 已豁免，MAINTAINERS 覆盖 vdec/）。
- v4l2-compliance 56/56。
- HEVC JCT-VC 132 条：129 Pass / 3 Error（即上表三条），原 127 条无退步。JPEG/MJPEG 3/3。
- hang fixture：控制项 hevc-intra、LT0、LTRPSPS 首 AU 清零、WPP_E、CTU64/WPP0 全部 Pass。
  LT1/LT8 由内核拒绝（每个 AU 都是 OUTPUT ERROR，0 条 `hevc: timeout`），但 GStreamer 管线 30 秒后 Timeout。
  原因：码流里没有任何一个 AU 能解码，CAPTURE 从未建立；按 dev-decoder.rst，STOP 不会启动 drain，
  而 v4l2h265dec 在 EOS 处一直等。这是客户端限制，任何完全不可解的流都一样，不是驱动回归。

注意：`build-integration.py` 打包的是普通 DTB，解码节点 disabled。解码窗口要换成同次构建的
vdec-test DTB（同 package-vdec.py）。第一次启动就因此在解码前停下。

原始证据（未跟踪）位于 `build/hevc-int43*/`、`logs/hevc-int43*/`；协调者状态文件为
`~/.local/state/herdr-workers/hevc-*.result.md`。
