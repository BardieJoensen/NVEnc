# R15: real source-off and public-QP1 feasibility diagnostic

Primary question: can a legal PSYEX encode with disabled temporal filtering and
demonstrably finer target-block quantization preserve E05 texture when coding
decisions and references can change, and what are its actual packet and runtime
costs? This is one bundled feasibility test. It does not isolate TF causality,
hold decisions fixed, or promise a source-budget repair.

Use the unchanged admitted R8 app/library and E05 336-frame original fixture.
Keep the entire R8 policy except `--enable-tf 0 --min-qp 1 --max-qp 1`.
Keep static QP at its existing source default; do not add `--qp 1`, disable AQ,
change matrices or tune other settings. Keep requested bitrate 10313 kbps.
Run fresh first and second passes: TF-off can change first-pass statistics.
Public QP1 maps to frame qindex4, not the R13 internal qindex1. Variance/TPL and
normalization can change SB/TU q; bounds do not prove the actual intervention.

This initial arm may overshoot rate only as a diagnostic. Practical acceptance
still requires actual scored-window video packet rate at or below the untouched
original's 9.6765224 Mbps. Decisive matched-rate comparisons must be within1%
and at or below the cap. Container sizes, requested rates, coefficient counts
and q values are not substitutes for measured packets.

Required delivery/admission:

- Freeze literal commands, scripts, binary/library/source/input versions and
  hashes, logs, monotonic encoding times, tools and before/after identities.
  Record all requested/effective settings, including the static QP default.
- Verify all336 frame counts, cadence, original fixture identity, color tags
  and exact reconstruction agreement through independent decoder paths used
  by admitted R8. Verify all240 scored samples and metadata on metric inputs.
- Reuse the exact R11 observer in separate neutral off/on pass2 replays bound
  to this arm's fresh stats. Require whole output/reconstruction identity to
  the unmodified arm. Bind target display216 dynamically through actual frame
  events and show-existing mappings; do not retain R8's hidden-event indices.
- Measure coding-input identity and actual final forward quantizer state on
  every target/control TU; join final DQ/EOB/QM/ownership to the decoder map.
  Classify skips separately. If old observer cannot represent a new state,
  stop admission and diagnose; do not weaken guards or infer values.
- Score against untouched originals using campaign.py and required CUDA/GPU
  metric paths. Preserve five-frame HF plus ACF/correlation; all frozen
  full-window tiles, quiet/source-clean protection, line/edge errors,
  full-reference scores and tails, banding and temporal evidence. No selected
  ROI can stand in for full-window preservation.

All existing gates remain unchanged. Numeric screens and stills are
provisional; actual player/display observation is separate. If preservation
passes at elevated rate, original-budget feasibility is still mandatory. If
it fails, inspect observed source/support/TX/q/filter behavior to select the
next discriminator; failure rejects only this bundle, not AV1 or all precision.
No similar rerun without a changed, evidenced hypothesis.

Worker owns fresh `worker/psyex-r15-real` runner/replay preparation. Parent owns
integration, validation/scoring scratch, contracts and Git index. Reviewer
owns fresh `reviewer/round15-*`, forms independent outcome before receiving the
parent conclusion. No recursion or production changes; preserve other work.
Bound encoder CPU affinity to0–7 with lp1/nice10, serialize GPU metrics, check
active jobs and storage first, retain >120GB staging free. Initial new media
budget10GB; estimate/check before any validation expansion. Stop and report
failed identity/delivery controls or unexpected resource growth, preserving
partial receipts. No speculative successful delivery or playback claims.
