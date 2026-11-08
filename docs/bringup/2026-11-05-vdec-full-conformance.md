# 2026-11-05：完整 AVC/MPEG-2 一致性集合与 bit21 实验

`.25` 全部 135 条 JVT-AVC_V1 与 43 条 MPEG2_VIDEO-MAIN 均已执行。H.264
通过 58 条，MPEG-2 通过 18 条；失败尚未修复。HEVC 只调整 bit21 条件仍超时。
5.15 实际启动后、解码前发生 hard lockup panic，对照没有运行。各窗口均恢复
`.3` 并验证 4K 视频，上传已归档清理，正式内核/启动项不变。

## 完整结果与证据边界

[逐流 CSV](data/2026-11-05-vdec-conformance.csv) 保存每条码流的实际结果、原始
Fluster 状态、证据窗口、特性和原始 JSON 路径。分组及源码定位见
[失败聚类](2026-11-05-vdec-failure-groups.md)。

| 套件 | 通过/总数 | 像素 Fail | 解码 Error | 内核超时 | 未运行 |
|---|---|---|---|---|---|
| JVT-AVC_V1 | 58/135 | 73 | 1 | 3 | 0 |
| MPEG2_VIDEO-MAIN | 18/43 | 19 | 6 | 0 | 0 |

Fluster 原始 H.264 汇总是 58 Success / 73 Fail / 4 Error；其中 `FM1_FT_E`、
`SP1_BT_A`、`sp2_bt_b` 的 Error 对应内核 `dec timeout=500`，报告中明确归为
Timeout，原始 JSON 没有改写。另一个 Error 是 `FM2_SVA_C`。MPEG-2 的 Error
为 `MEI`、`MEI.stream16`、`tcela-16`、`tcela-18`、`tcela-19`、`ccm1`。
这些 Error 的管线未正常完成，不能归类为像素摘要不匹配或固件能力限制。

窗口沿用上一轮 `.25` 身份、
生产配置、同一私有模块和锁定输入。未重跑 compliance，引用 r37 同一产物的结果；
本轮结果不能替代调试内核锁/DMA/内存验证。FR-EXT High、MPEG2 422、HEVC 全套与
性能/共存测试仍未运行。

| 窗口 | 实际范围 | 结束条件 |
|---|---|---|
| r40 | AVC 索引 0–66 | 为恢复保留预算，后续 Not run |
| r41 | AVC 索引 67–130 | 同上；内核超时识别遗漏，见下文 |
| r42 | AVC 索引 131–134，再 MPEG-2 全 43 条 | 完成；新超时检查有效，无内核解码超时 |
| r45 | 新启动复跑 AVC 95–125、128–134，共 38 条 | 完成，逐流结果与先前相同，无解码超时 |

r41 第一次申请采样锁时碰到其他 worker 构建，10 秒内退出，未接触板子；
`logs/hwdecode-parity-r41-preflight-only/` 与 `run41/sampling-busy.log` 保留此次门禁。
之后按协调顺序重新排 FIFO；其间允许 debug-splat-fixes 的板窗正常插队列，
没有在持板锁时等构建。

### 超时停止规则的补漏

主仓库 `e6084fe` 改为逐流保存像素失败后继续，逐流检查内核异常/DMA 状态；
`window-status.json.success` 仅表示窗口安全执行，`conformance_passed` 才表示
所选码流全部通过。预算不足的项保留 Not run，而非写成解码超时。

r41 暴露了这个版本的不足：Fluster 把内核 500 ms 超时记为 Error，而不是
Timeout，脚本因此继续了后续码流。发现后补上 `aml-vdec-drv` 的解码超时日志
识别，将对应项记为 Timeout 并立即终止；三个旧超时的原始状态不抹去。
不能将 r41 的后续数据直接作为干净启动的验收：r45 在新启动中重新运行首次
超时之后的非超时区段，所有 38 项结果相同。三个超时都只保留故障证据，没有
再次运行它们。CSV 的后段证据指向 r45，超时仍指向 r41。

安全检查与结果解析使用已有工具测试，不新增内核 Python/mock 测试。离线
539 项回归通过、11 项跳过；日志 `build/hwdecode-parity/run42/main-tests-timeout.log`。

## HEVC bit21 单变量实验

仅在独立候选工作树 `vdec-sequence` 上，将 `h265_config_decode_mode()` 的 bit21
无条件设置改为 `h->pic_w * h->pic_h > 4096 * 2304` 时设置；尺寸只在现有参数
验证后写入，首 AU 为零，不启用该模式。固件、WAIT_FLAG、FIFO、ACTION、CPU reset
顺序与读回都没有改动。`hwdecode-parity` 工作树保留原草稿，未提交此实验。

复用 `/home/deepdream/build/vdec-sequence/kernel`，实际运行 W=1/C=1 sparse
模块构建，`bit21/build.log` 有 `CHECK hevc.c`，没有该改动的诊断。没有为本次
私有实验声称内建构建或 format-patch 检查通过，也没有据此提交内核改动。

| 证据 | 身份/结果 |
|---|---|
| Image | `.25`，build ID `915bf903142f874b6f7836568eb89332d8d782be` |
| 有效私有模块 | build ID `75c6b12081f766719982f3b44291d82080abfa4d` |
| 模块 SHA-256 | `9b73436b4ac46ece49971eea91f0680371086e53d0a018268b85a68a0954499a` |
| 草稿 SHA-256 | `3c82a4eaa7842022c2029fd554e593d05556401b1978829aa9fd79814d036c49` |
| r46 实际流检查 | `v4l2-test-buffers.cpp:1738`，SOURCE_CHANGE 超时；未进入 Fluster |
| 超时寄存器 | irq/status `00/00`，PC `00000a1d`，SHIFT `00000072` |

对照 r37 的 PC `00000a1e`，SHIFT 没有推进。单改 bit21 条件不足以解决启动问题，
不能记为修复。下一次只改 ACTION/CPU reset 顺序及 reset 读回，继续保持草稿。

r43 是无效实验：VM 到 Mac 的模块传输尾部缺失（2,555,904 而非 2,560,616 字节），
板端 `modinfo` 在加载前拒绝；没有打开 HEVC。错误在宿主未将传输后的 SHA 与
VM 原产物比较。r46 重新传输并 fsync，双端 SHA、ELF、vermagic/build ID 离线
核验一致后再测试。两轮均恢复，旧坏文件/日志保留作证据，未覆盖成“成功实验”。

## 5.15 一次性启动与中止

已离线准备 `5.15.137-vim4kvm-hdrdual6` 的 Image、配置、DTB 与 1,535 项部署
登记产物；实际普通文件 SHA 与登记一致，启动前还核对 overlay 文件、root UUID。
使用该版本独立 extlinux 文件，默认 Mainline 不变，不 saveenv。

`build/hwdecode-parity/vendor-comparison/` 保存 Image/config/DTB、manifest、
解析后的启动参数及一次性配置。Image 内有两个 GNU note：第一个属于嵌入的 VDSO
（用 `readelf -n` 确认），内核 note 为 `4a9b69d62ba7b3a5adeb41b213f7f3e573006165`。
这是预期运行身份，**未获得成功启动后的 `/sys/kernel/notes` 匹配结果**。源码
来源没有确证，manifest 不把当前 common_drivers HEAD 冒充已部署内核源码。

r44 原计划用相同输入对照主线未通过的 102 条码流。UART 确认启动的是目标 5.15，
但在打开解码器前已出现 DRM vblank WARNING，随后约 33.568750 秒报
`Watchdog detected hard LOCKUP on cpu 2` 并 panic。启动就绪门禁失败，全部
102 条对照未运行，不能报告任何“5.15 通过/主线失败”的结论。按协调决定暂停
5.15；仅在某组主线问题离线无法定位时，再核对本轮启动参数/DT 与正式厂商环境。
没有修厂商内核、放宽警告检查或再次启动它。

完整 UART：`logs/hwdecode-parity-r44/uart-1793878759163992000.log`；恢复 UART、
身份与视频证明在同目录。一次性配置和空上传目录已删除。

## 恢复、归档与构建清理

各窗口恢复 `.3` 的 build ID/基线文件均通过，3840×2160 H.265 五秒视频约
59.55–59.98 fps，新增丢帧/冻结/丢包均零。各自根日志有
`WINDOW_FINISHED baseline restored=True`，板票全部释放。

每轮上传在 Mac 保存 `runNN/board-upload.tar` 和逐文件 SHA 清单，删除前再次
核对远端。最后归档清理旧 r38/r39 与共享 r32 码流目录，今后复验须重新从宿主
校验后上传；没有删除用户或其他 worker 数据。最终根分区可用 9,369,620,480
字节、使用率 69%，见 `build/hwdecode-parity/final-upload-cleanup.log`。
协调者保留的 seq25/joint23 RAM 候选没有删除。

已清理本任务三个既有 O= 目录及两个 vdec 模块目录的 `*.o`，保留 Image、`.ko`、
归档和日志；具体路径/数量/字节见 `build/hwdecode-parity/object-cleanup.json`。
没有新建每轮 O=，没有触及其他 worker 构建目录。
