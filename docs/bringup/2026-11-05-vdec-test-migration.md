# 2026-11-05：解码测试迁移清单

驱动测试迁移前的审计基线为内核
`8c94ee343220cebc8f208097daf2308fd5a04c76`。目录
`drivers/media/platform/amlogic/vdec/` 有七个 Python 文件、49 个测试方法；
此前“24 项”是历史阶段数，不能当作当前范围。
下表在删除前登记原风险与替代验证；“迁移/删除”是处置计划，不表示已经完成。
所有原名省略 `test_` 前缀。不保留 Python 或重新构造假的 vb2/V4L2 对象。

## 逐项处置

K＝纯逻辑迁 KUnit；V＝删除 mock，交给带流 compliance/实板；
B＝删除 mock，交给电源、DMA、时钟实板验证；F＝删除像素夹具，交给标准码流。
V/B/F 替代证据没有实际运行时必须记未验，不能把删除当作通过。

### test_h264_headers.py（3）

| 原测试 | 风险与处置 |
|---|---|
| matrix_scan_and_constraint_bit_order | K：SPS constraint 位序和 PPS scaling matrix 扫描序错误 |
| signed_extremes_and_long_poc_cycle | K：有符号 Exp-Golomb 极值溢出、长 POC 周期截断 |
| capacity_and_emulation_prevention_boundaries | K：容量不足写越界、防竞争字节扩大长度、非法矩阵 |

### test_hevc.py（5）

| 原测试 | 风险与处置 |
|---|---|
| eos_subscription_and_notification_follow_last_capture | V：LAST/EOS 重复、漏发或提前；当前只有订阅接口实板通过，带流未验 |
| reordered_frames_keep_their_storage_until_output_and_drain | V：显示重排提前回收；B 帧和 drain 标准流未验 |
| capture_planes_cover_sao_burst_lengths | K：SAO burst 对齐容量不足；实板 DMA 检查补充 |
| job_synchronizes_stop_before_returning_dma_ownership | B：超时后仍写已归还缓冲；需真实停机与调试内核 |
| geometry_tiles_and_reference_boundaries | K：参数位移、tile 边界、缺失参考、POC 回绕；这是固件参数处理，不是内核解析码流 |

### test_hevc_core.py / test_hevc_power.py（各 1）

| 原测试 | 风险与处置 |
|---|---|
| stop_reset_and_failed_load_preserve_dma_ownership | B：停止失败时错误释放 DMA；空闲停止已有记录，故障路径不能据此认定通过 |
| power_preflight_and_every_backend_failure_preserve_ownership | B：关闭域内 MMIO、失败回收引用错误；正常供电已有记录，注入另验 |

### test_mjpeg.py（5）

| 原测试 | 风险与处置 |
|---|---|
| jpeg_interface_maps_shared_engines_and_cleans_partial_links | V：节点注册/共享调度和部分注册清理；compliance、重开；注入未验 |
| drain_preserves_last_frame_and_empties_only_sentinels | V：drain 丢最后帧；带流 EOS |
| header_truncation_sampling_and_capture_bounds | K：截断 JPEG、unsupported sampling、尺寸/输出容量边界 |
| irq_errors_do_not_complete_buffers_or_free_dma | B：IRQ 与停机之间提前返还缓冲 |
| failed_stop_quarantines_jpeg_staging_buffer | B：失败停止后 staging DMA 被释放 |

### test_mpeg12.py（6）

| 原测试 | 风险与处置 |
|---|---|
| initial_ip_field_pair_needs_no_previous_frame | K：首个 I/P 场对参考选择；F：现有场流补充，标准 MPEG-2 验证 |
| codec_switch_discards_previous_picture_and_iq_mode | V/B：跨 codec 遗留参考与矩阵；交替流与重开 |
| vbv_units_matrix_updates_and_interlaced_header | K：VBV 单位、矩阵更新与隔行头部序列化 |
| rebuilt_ipb_headers_preserve_software_decoded_pixels | F：删除主机 FFmpeg 像素比对；fluster 未运行前不得宣称替代证据已通过 |
| irq_signals_result_without_returning_dma_or_buffers | B：IRQ 提前归还硬件所有权 |
| close_retains_all_dma_when_stop_cannot_be_proven | B：close 后 DMA 悬空 |

### test_t7_lifetime.py（28）

| 原测试 | 风险与处置 |
|---|---|
| mpeg2_full_reset_preserves_power_and_keeps_bus_isolated_on_error | B：reset 错误打开总线或丢供电引用 |
| format_probe_selects_codec_and_capture_keeps_real_plane_count | V：格式协商和 plane 数；三个节点 compliance |
| native_configuration_requires_dpb_handshake_before_slice | B/F：固件 DPB 握手顺序；标准 H.264 流及 IRQ 日志 |
| native_headers_stage_payload_and_propagate_failures | B：暂存/分配失败；纯序列化由 headers KUnit 覆盖 |
| weighted_duplicate_references_use_parsed_slice_counts | K：加权重复参考列表数量错误 |
| internal_canvas_targets_dma_planes_without_external_allocations | K：地址与 stride/LUT 编码；B：实际 canvas/DMA 生命周期 |
| b_picture_reordering_preserves_each_reference_list | K：两组参考顺序被覆盖；F：B 帧标准流 |
| parameter_tables_initialize_slots_and_encode_signed_fields | K：未初始化 slot、带符号 QP 和尺寸字段截断 |
| fifo_ring_includes_padding_without_exposing_unallocated_memory | K：输入环与 padding 边界；B：DMA 暂存生命周期 |
| timeout_snapshots_before_latching_and_waking_both_queues | B：超时队列不退出、日志丢失 |
| streamoff_releases_own_canvas_after_hardware_owner_is_cleared | B：streamoff 后硬件仍用 canvas |
| job_pins_unwind_and_quarantine_without_idle_mapped_flags | B：pin 回收/隔离错误，须真实内存与 DMA |
| m2m_job_binds_codec_only_until_dma_stop | B：共享任务在停机前切换 |
| multiple_files_keep_independent_queues_and_pm_references | V/B：多实例队列与 PM 所有权串扰 |
| snapshot_guard_stops_internal_access_but_allows_abort | B：关闭域内 debugfs MMIO；已有正常路径记录，错误路径另验 |
| apb_clocks_are_held_before_dos_and_unwound_on_failure | B：总线访问先于时钟，错误回收 |
| vendor_path_selection_propagates_errors_before_rate_programming | B：时钟路径失败后继续操作 |
| physical_clock_guard_rejects_closed_gates_and_wrong_recipe | B：CCF 状态与实际 gate 不符 |
| parent_is_owned_before_top_access_and_child_power_and_released_last | B：电源父子域顺序 |
| mdec_single_read_requires_all_prerequisites_and_verified_power_off | B：探测访问未供电模块 |
| runtime_resume_requires_opt_in_and_completed_power_test | B：实验驱动提前开启硬件 |
| power_test_never_touches_dos_before_secure_domains_report_on | B：secure 域尚未开启就 MMIO |
| canvas_allocation_failure_preserves_unallocated_sentinels | B：部分分配失败错误释放；不为模拟 allocator 保留 mock |
| platform_core_respects_explicit_domain_ownership | B：驱动间错误释放域 |
| stop_mmio_errors_and_busy_status | B：未停 DMA 却报告停止 |
| finish_only_after_confirmed_stop_and_no_retry | B：首错后继续启动任务 |
| vb2_close_keeps_faulted_plane_references | B：故障 close 释放仍被 DMA 使用的 plane |
| dos_lease_and_permanent_quarantine | B：共享 DOS 故障后错误复用；真实并行负载/故障路径 |

## 验证顺序与状态

先迁纯逻辑并用 arm64 QEMU 实际运行 KUnit，完成 W=1、有效 sparse、模块/内建、
strict checkpatch 和改动头文件 kernel-doc 检查后提交。变更 binding 时追加 schema
与板 DTB 检查。硬件语义不造 mock，使用现有窗口的 compliance、fluster 与调试
内核实板证据；标准故障注入只在调试配置启用。

原有上板记录见
[H.264](2026-11-04-h264-boundaries.md)、[MPEG-2](2026-11-04-mpeg2-request.md)、
[MJPEG](2026-11-04-mjpeg-decoder.md)、[HEVC](2026-11-05-hevc-stateful.md)；
这些历史正常路径证据不能证明所有故障路径通过。

## 已完成：H.264 头部

`02ad5d554b856` 补充最小配置缺失的 REGMAP_MMIO 依赖；`32885171b804a` 将
`test_h264_headers.py` 三项迁入 `h264_headers_kunit.c` 并删除原 Python 文件。
测试调用实际内核序列化函数，使用条件 KUnit 导出，不抽取 C 代码、不模拟内核对象。
入口为内核 vdec 的 [.kunitconfig](https://github.com/vim4-kvm/linux/blob/hwdecode-parity/drivers/media/platform/amlogic/vdec/.kunitconfig)。

实际执行 `tools/testing/kunit/kunit.py run --arch arm64`：三个用例全部通过，
保存完整 QEMU 输出、JSON 和配置。内建驱动/测试已运行；生产配置模块和
KUnit 测试模块均编译通过。改动文件 W=1 和 C=1 有实际 CC/CHECK、无诊断；
sparse 固定源码 `84ec0658c81db4ccc4aabc420d3dc118c2c6a310`，报告版本
`v0.6.5-rc1-21-g84ec0658`。系统旧 sparse 不作为有效结果。

strict checkpatch 为零 error/warning/check；只忽略新文件自动提示
FILE_PATH_CHANGES，已人工确认 MAINTAINERS 的 vdec 目录通配覆盖新文件。
本步未修改头文件或 DT binding；kernel-doc 额外检查原有 h264_headers.h 无诊断。
smatch 未安装，未运行，不能称通过。

保留失败和范围边界：首次全内核 W=1 被未改动的 arm64 syscall 表
override-init 警告阻断，不能算全内核检查通过；正常配置 KUnit 之后才通过。
最小配置缺少 REGMAP_MMIO 的编译失败由上述独立依赖提交修复。
扩大到整个驱动目录的 sparse 还报告原有 `aml_S4_dec_ops` 缺少声明；内建准备
阶段还报告未改动 vdso 的 `__kernel_getrandom`。这些不是本次新文件诊断，
不宣称整棵树零警告。

原始输出在 `build/hwdecode-parity/`：`h264-kunit-run.log`、`run2.log`、
`run3.log` 保留各次构建；`h264-kunit-qemu.log`、`h264-kunit-result.json`、
`h264-kunit.config` 是实际运行证据；`h264-kunit-static-module.log` 与
`h264-kunit-module-config.log` 保存模块、内建及 sparse 输出，
`h264-kunit-commit.log` 保存最终 checkpatch。没有访问板子。

剩余六个 Python 文件仍在迁移中；本节不表示第 1 节已经全部完成。
