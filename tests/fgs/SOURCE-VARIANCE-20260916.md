# Source variance prototype, September 16

Status: **experimental, not qualified or deployed**. The deployed ordinary core
is `2fa6cfd0`, binary `ef4799f6e7110e1057d8f728586d45e382b1ce3aa75c035403da35f05ca4b946`.
Normal workers remain paused under the separately owned fidelity hold.

The ten broader default-mode trials found a remaining source-support gap after
the held-model amplitude correction. In Severance S02E02 at 2232.439 seconds,
the source's left fluorescent panel has native eight-bit-equivalent spatial
sigma 0.977; the new encode adds synthesis sigma 13.865 there. The panel is
only about two dozen pixels high, and full 16x16 cells cross its boundaries.
Near-white code values and weak but nonzero variance are also excluded by the
existing quiet-source test. This is not evidence against the qualified repairs
or a claim that all flagged files are damaged.

This prototype reuses each source tile for 8x8 luma statistics, then caps gross
model excess relative to the region's total source variance. That variance
includes texture and is a conservative upper bound, not a noise estimate.
Existing source-residual restoration, bounded AV1 curve fitting, temporal hold
and release remain in use. No new GPU source pass, kernel or synchronization is
added; the metrics readback is larger and must be measured. Chroma keeps its
existing eligibility, including its clipped-luma exclusions.

The trial attack is above both three codes and `2 * source_sigma + 1`; the
target is `1.5 * source_sigma + 0.5`. These are unqualified engineering margins,
not visibility thresholds. Small correlated genuine-grain samples may still
trigger protection; source quality, grain preservation and byte/runtime cost
must be checked before accepting this policy.

CPU source/curve checks pass. The new end-to-end fixture separately checks thin
near-white regions, weak non-flat regions and preserved genuine background
grain, in both depths and CQP/QVBR. Its retained deployed-build negative control,
candidate results, broader real witnesses, prior full GPU gate, HDR controls
and whole-source trials remain pending. Do not publish a new positive baseline
merely because this prototype changes output.

Live evidence is in
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/`:
`amplitude-scope-pilot-review.json`, the Severance pilot's `native-witness-v2/`,
and `source-variance/`. The canonical handoff remains the fidelity worktree's
`tests/fgs/WORK-TO-PRODUCTION.md`. No automatic-retention campaign has started.
