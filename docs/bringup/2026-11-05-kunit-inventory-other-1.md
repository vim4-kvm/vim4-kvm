# 2026-11-05：内核测试清单 other（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/gpu/drm/msm/registers/gen_header.py`

类型：源码生成工具（上游，保留，不属于项目测试迁移）。

## `drivers/media/cec/platform/meson/test_ao_cec_t7.py`

类型：测试；处置待确认，保留。

原自述：Compare T7 CEC pad/filter programming with the vendor CECA implementation.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 165 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/amlogic/vdec/test_t7_lifetime.py`

类型：测试（vdec，其他分支负责，保留）。

原自述：Compile actual driver functions against deterministic failing backends.  No hardware, kernel module loading, duplicated stop implementation or sleeps. The backends inject every MMIO failure, stuck status and ownership transition.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 57 | `test_fifo_ring_includes_padding_without_exposing_unallocated_memory` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 84 | `C main` | 待确认：核对内嵌 C 的断言 |
| 113 | `test_timeout_snapshots_before_latching_and_waking_both_queues` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 123 | `C main` | 待确认：核对内嵌 C 的断言 |
| 133 | `test_streamoff_releases_own_canvas_after_hardware_owner_is_cleared` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 155 | `C main` | 待确认：核对内嵌 C 的断言 |
| 186 | `test_job_pins_unwind_and_quarantine_without_idle_mapped_flags` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 235 | `C main` | 待确认：核对内嵌 C 的断言 |
| 276 | `test_m2m_job_binds_codec_only_until_dma_stop` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 335 | `C main` | 待确认：核对内嵌 C 的断言 |
| 366 | `test_multiple_files_keep_independent_queues_and_pm_references` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 425 | `C main` | 待确认：核对内嵌 C 的断言 |
| 460 | `test_snapshot_guard_stops_internal_access_but_allows_abort` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 486 | `C main` | 待确认：核对内嵌 C 的断言 |
| 500 | `test_apb_clocks_are_held_before_dos_and_unwound_on_failure` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 519 | `C main` | 待确认：核对内嵌 C 的断言 |
| 537 | `test_vendor_path_selection_propagates_errors_before_rate_programming` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 553 | `C main` | 待确认：核对内嵌 C 的断言 |
| 567 | `test_physical_clock_guard_rejects_closed_gates_and_wrong_recipe` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 581 | `C main` | 待确认：核对内嵌 C 的断言 |
| 618 | `test_parent_is_owned_before_top_access_and_child_power_and_released_last` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 698 | `C main` | 待确认：核对内嵌 C 的断言 |
| 726 | `test_mdec_single_read_requires_all_prerequisites_and_verified_power_off` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 778 | `C main` | 待确认：核对内嵌 C 的断言 |
| 829 | `test_runtime_resume_requires_opt_in_and_completed_power_test` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 844 | `C main` | 待确认：核对内嵌 C 的断言 |
| 864 | `test_power_test_never_touches_dos_before_secure_domains_report_on` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 930 | `C main` | 待确认：核对内嵌 C 的断言 |
| 963 | `test_canvas_allocation_failure_preserves_unallocated_sentinels` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 990 | `C main` | 待确认：核对内嵌 C 的断言 |
| 1011 | `test_platform_core_respects_explicit_domain_ownership` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 1035 | `C main` | 待确认：核对内嵌 C 的断言 |
| 1049 | `test_stop_mmio_errors_and_busy_status` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 1075 | `C main` | 待确认：核对内嵌 C 的断言 |
| 1102 | `test_finish_only_after_confirmed_stop_and_no_retry` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 1116 | `C main` | 待确认：核对内嵌 C 的断言 |
| 1137 | `test_vb2_close_keeps_faulted_plane_references` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 1154 | `C main` | 待确认：核对内嵌 C 的断言 |
| 1174 | `test_dos_lease_and_permanent_quarantine` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 1188 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/misc/adla/test_cancel.py`

类型：测试；处置待确认，保留。

原自述：Execute actual pending/finished/scheduled cancellation with controlled lists.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 39 | `C main` | 待确认：核对内嵌 C 的断言 |
| 103 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/misc/adla/test_iova.py`

类型：测试；处置待确认，保留。

原自述：Host tests execute the driver's bitmap IOVA allocator, including rollback.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 61 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/misc/adla/test_lifecycle.py`

类型：测试；处置待确认，保留。

原自述：Execute real error-completion and close paths with controlled DMA/reset events.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 141 | `C main` | 待确认：核对内嵌 C 的断言 |
| 216 | `C main` | 待确认：核对内嵌 C 的断言 |
| 254 | `C main` | 待确认：核对内嵌 C 的断言 |
