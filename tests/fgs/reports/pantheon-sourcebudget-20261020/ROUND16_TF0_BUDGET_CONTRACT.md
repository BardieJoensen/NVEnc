# R16: TF-off policy at the original packet budget

Primary question: does the admitted R8 PSYEX policy with only temporal filtering
disabled preserve E05 texture under normal rate allocation at the original
packet budget? R15 proves numerical preservation is possible for this source
policy at abundant precision, but its 19.6777x rate is disqualified. R16 supplies
the missing practical policy comparison before a spatial allocator is built.

Use unchanged admitted R8 source/app/library and the untouched E05 336-frame
fixture. Relative to R8, change only `--enable-tf 1` to `--enable-tf 0`, fresh
output/statistics paths, and the bitrate request needed for measured-rate
calibration. Do not add min/max QP bounds or static QP, alter AQ/QM/psy/search,
change filter controls, use grain, or change thread/GOP settings. TF-off is a
bundled reference/search/source policy; it is not an isolated input-pixel
ablation. Observe the actual coding input and final quantizers.

The scored 96:336 video-packet rate must be in 99–100% of the untouched original
9.6765224 Mbps for the decisive matched comparison. This interval is also within
1% of R8's 9.6279048 Mbps. Lower-rate results remain under-cap observations but
are not substituted for the predeclared matched comparison.

Start at the unchanged 10313 kbps request. If calibration is needed, target
99.7% of the original by multiplying the previous request by target/actual and
rounding to integer kbps. Change only the request. Use fresh two-pass statistics
for each request; do not assume R15's first pass is reusable after removing QP
bounds. Preserve every receipt and measured packet result. Initially allow at
most three requests; if the rate controller does not reach the interval, report
the observed response to the parent before choosing a better calibration
method. This is rate calibration, not a quality-settings sweep.

Admission and unchanged acceptance:

- Freeze literal commands, source/app/library/input and script hashes,
  before/after identities, effective QP setup, logs and both encoding times.
- Verify complete packet counts/cadence/color and exact all336 samples across
  app reconstruction, dav1d, libaom and NVDEC. Bind all240 metric inputs exactly.
- Derive the new coded/display/reference lifecycle independently from syntax;
  never assume R15's event indices or populations remain valid.
- Neutral encoder observation off/on and independent native decoder observation
  must reproduce the unmodified arm. Join all traced target/control owners,
  actual final forward q, DQ/EOB/IQM, source/predictor/preloop and skips.
  Reuse unchanged observers only when their explicit target/state guards hold.
- Use campaign.py and required GPU metrics; retain the same five-frame
  HF±10% and ACF-error≤0.05 screens, source correlation, all12870 frozen control
  tiles, quiet positive tails, edge/face errors, full-reference scores/tails,
  banding and full-window temporal evidence. Keep regressions visible.
- Numerical success remains provisional. No actual playback or full-episode
  qualification is implied. No production proposal follows from a failed arm.

Predeclared interpretation: a numerical pass under the cap advances to E04 and
regression-window qualification before the minimum human playback request. A
failure with original-identical coding input, sufficient realized residual
support, and loss localized at coarse scalar quantization motivates the
absolute-cap allocation route. Coarse q alone is not sufficient evidence.
If skip/no-residual or missing support dominates, trace that decision instead.
Do not infer an AV1 limit or rerun an unchanged failed policy.

Worker owns fresh `worker/psyex-r16-tf0-budget` runner/replay preparation; parent
owns `parent/psyex-tf0-r16`, integration, decoder/metric admission and Git index.
Reviewer owns `reviewer/round16-*` and forms its outcome before the parent's.
No recursion, production or unrelated edits. All agents preserve others' work.
Encoder CPU0–7/lp1/nice10; parent decoder CPU8–11; GPU jobs serialized. Check
active jobs and mounts/free space first. Initial validation allowance20GB;
retain >120GB staging free. Preserve partial receipts on identity, unsupported
state or resource failures, and report the smallest needed correction.
