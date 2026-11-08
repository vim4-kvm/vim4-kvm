# 2026-11-05：解码测试迁移清单

驱动测试迁移前的审计基线为内核
`8c94ee343220cebc8f208097daf2308fd5a04c76`。目录
`drivers/media/platform/amlogic/vdec/` 有七个 Python 文件、49 个测试方法；
此前“24 项”是历史阶段数，不能当作当前范围。
下表在删除前登记原风险与替代验证。七个文件现已全部移除，纯逻辑迁移的
17 项 KUnit 已通过；其余硬件验证仍待运行，见[执行结果](2026-11-05-vdec-kunit-results.md)。
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
H.264、MPEG-2、
MJPEG、HEVC；
这些历史正常路径证据不能证明所有故障路径通过。

迁移提交、实际命令、原始输出和未验边界集中在[执行结果](2026-11-05-vdec-kunit-results.md)。
