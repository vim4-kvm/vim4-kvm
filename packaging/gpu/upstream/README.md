# Mesa review queue (not sent)

2026-10-30: compiler work is paused. Builder default stays GCM; the repaired full
series stays opt-in. These two mail patches are prepared against Mesa 26.2.6,
not submitted, posted or pushed. Before sending, rebase and test against Mesa's
then-current main branch and check whether the issue is already fixed there.

1. `0001-panfrost-move-safe-loop-invariants-before-local-sche.patch`: GCM only,
   with existing speculation restrictions. Review live ranges and register cost.
2. `0002-panfrost-stop-same-block-branch-offsets-at-the-block.patch`: independent
   layout bug fix and generic unit test. It does not depend on the private uniform
   backedge change, and omits the brace fix to that private test. Can be reviewed
   independently of GCM. Tests cover self, forward and cross-block offsets.

Apply with `git am` in this order; patch 2 also applies independently. No author
or license changes to existing source. Review evidence: [loop repair](../../../docs/gpu-loop-repair.md)
and [hardware results](../../../docs/bringup/2026-10-30-gpu-repair-window.md).
Original 0004/0005 remain experimental, not in this upstream queue. The fixed
probe passes; divergent/helper-invocation/CTS coverage remains insufficient to
promote that transformation. Experimental unrolling is also outside the queue.
The readiness busy-poll kernel candidate showed no gain and is not queued.

`kernel-0001-default-gpu-cooling.patch` is the separate default-DT cooling change
from the GPU branch, retaining its author and license; the private pm-test DTS
cleanup is omitted. It is for a kernel queue,
not `git am` into Mesa. Its T7/VIM4 DTS baseline must first be matched to the
target upstream tree; it is not claimed to apply to an arbitrary Linux release.
Review/build/schema and hardware binding evidence: [GPU parity](../../../docs/gpu-parity-plan.md).
The 10ms polling and temporary PM QoS boost changes remain platform experiments
pending wider power/lifecycle review, not in this submission-ready queue.
