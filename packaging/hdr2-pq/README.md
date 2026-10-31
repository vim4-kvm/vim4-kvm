# HDR2 product topic series

Apply `0001` through `0009` here, in order with `git am`, on kernel
`f71b5c6289cb3254690e57292327e73514f0715f`. VM worktree:
`~/src/linux-7.3-hdr2-topics`, branch `vim4-hdr2-recovery`.
The first six topics reproduce the a5-tested `851153f2f529f` tree:
**6fdb600add9ca1f0ed8bf12266bee9fee8d6debf**.

Recovery topics `0007` through `0009` follow these six.
`0007` seeds the source monitor after an admitted STREAMON, preventing
cached loss from producing an immediate second recovery event. `0008` samples
present-cable recovery at 50ms while preserving three matching samples,
PLL/PCS checks, DMA exclusion and the 250ms idle/torn-snapshot cadence.
`0009` wakes that qualification immediately after the last DMA lease retires,
and excludes rearming after link shutdown. Their source/stream and link-recovery
fixtures exercise these lifecycle boundaries. This extended tree differs
intentionally from the exact a5 tree; its acceptance is tracked separately from
the six-topic equivalence proof. The final tree is
`0ce3bf8d9a1e57a97bdbaffa67610eceaddba579` at `8bca939d6bbd3`.
The user accepted the paired recovery medians and tails. The nine-topic tree
passed the [formal uhd4 smoke](../../docs/bringup/2026-10-31-uhd4-formal-smoke.md);
the six-topic tree above remains the historical a5 equivalence proof.

`video-recovery.mjs` defaults to 250ms statistics; `HDR2_SAMPLE_MS=50` selects
fine sampling without changing host networking. It also reports keyframe count,
packet arrival and decoder CPU totals. After restarting One-KVM, wait for a real
4K `framesDecoded` increase before starting any separately authorized HDR toggle.
An offer error, closed session, codec change or external viewer invalidates the
affected timing interval. HTTP/MCP availability alone does not prove decoding.

| Topic | Commit | Tests |
|---|---|---|
| HDR profiles and output contract | 05585292e7c03 | HLG LUT/admission, precise PQ gamut, signed offsets, 709/limited NV12 and receiver fixtures |
| Powered PQ shadow diagnostics | 57964b615219d | CRC32 dependency, port samples, inactive debugfs and fixture boundaries |
| Wave5 VUI | 20232cbe8e326 | Actual AVC/HEVC SPS parsing and coherent RBSP failure lifetime |
| Capture byte budget | 35394b9d2eba1 | 192 MiB cumulative REQBUFS/CREATE_BUFS, faults and planes |
| Provenance/retirement trace | 8d9caf01d7750 | Dual export identity, vb2 first member, IRQ/stream ownership |
| Firmware ethernet alias | ce6bc0cc5218a | DT build; RAM-only MAC fixup without saveenv |

HLG and output color share a profile topic so table writers and fixtures remain
consistent at every buildable boundary. HLG is **implemented, without a real
source validation**. The vendor-shaped OETF and existing 709 video tuple are
retained; this does not claim a new mathematical 709 OETF.

`history-a5/` holds the superseded chronological patches for old evidence;
never apply both series. Transfer/gamut, pool budget, layout and fixture repairs
are folded into their owning topics. Each topic passed its host tests, W=1
module builds and actual sparse checks using `~/build/pq-tools/sparse`
v0.6.5-rc1-21-g84ec0658. System sparse 0.6.4 is rejected by this kernel; an
exit-zero make without CHECK lines does not establish sparse validation.
Intermediate modules are never deployed.

Checkpatch `--strict` reports zero errors per topic. Remaining messages are
MAINTAINERS new-file reminders (driver directories already covered; the new
global trace headers still need explicit F entries before external submission), a profile brace warning
(the next shadow topic adds a statement), and TRACE_EVENT continuation/alignment
checks. No suppressions hide these; exact a5 source equivalence is intentional.

Trace events default off: static-key checks plus generation/ticket bookkeeping
and direct-address calculations remain, but there are no trace-buffer writes,
fence, scheduler or DMA-lifetime changes. Enabled tracing emits several events
per frame; collect performance separately. Disabled overhead is not called zero.
`check_retirement.py TRACE` joins allocator and normalized physical address,
fails closed on IOMMU/trace loss, and holds ownership until actual encoder
completion. Capture cleanup alone is not completion. It rejects stale submissions
and early reuse, but does not prove closure of every userspace FD.

`hdr_status` exposes configured/last-written **PQ software shadows**, not HLG
programming or hardware LUT readback. Only reviewed controls are read while a
powered stream lease is held; no LUT address/data ports are read.

The standard `../kernel-edge/build-gstreamer.py` applies all eight locked patches,
including color probing and coded-buffer sizing, and runs their real-function
tests. `build-gst.sh NEW_DIR` delegates without double application. System plugins
are not replaced. `package.py SOURCE OUTPUT NEW_STAGE` seals complete private-aN
or uhd4 builds, refuses existing stages, and records stripped modules/depmod and
file hashes. Keep matching vmlinux for BTF.

`trial-init.c` validates release/build ID and payload ownership before temporary
module/runtime binds. Verify the real service executable and mapped plugin.
`compare_frames.py` defaults to full visible NV21/NV12 with tail padding removed.
Explicit formats permit same-kernel noise comparisons; `--exclude-top N` is a
separate even-row analysis, never a substitute for the full-frame gate.

See the [DMA contract](../../docs/hdr2-dma-contract.md) and historical
[a5 evidence](../../docs/bringup/2026-10-30-hdr2a5-window.md).
