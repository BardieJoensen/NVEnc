# Round7: realized finer quantization, initially unconstrained rate

Primary question: can a substantial actual quantizer reduction change the
observed skip/transform/coefficient losses enough to preserve the E05 texture?
This is an end-to-end coding-policy contrast, not a fixed-predictor ablation.
No qmax sweep or original-budget redistribution is part of this first arm.

Use R3 `aom-psnr-1x2`, request11671kbps, as the comparator. Keep the exact336-frame
original fixture,96 preroll/240 scored positions, PSNR, variance AQ, **objective
delta-Q**, four threads/nice10/CPU0–7, GOP/lookahead/TF settings and color. Add
only `-qmin 0 -qmax 8`. Explicit qmin0 is a proven no-op: FFmpeg defaults its
generic field to−1 and leaves libaom's minimum0; explicit0 writes the same value.
Qmax8 maps to base qindex32, against observed target base69 and exercised
shirt65/background69–73. It is not a guarantee of per-TU qindex≤32.

Worker owns `worker/aom-qmax-r7/encode_qmax.py`, README, previews and installed
encode outputs. Parent owns repo integration, private replay, dynamic admission,
scoring, decision and Git index. Reviewer owns independent reports. Two children
maximum, no recursion, no production changes, preserve others' files. Existing
R6 build/source/evidence remains unchanged; no new build is initially needed.

## Before interpreting the intervention

- Bind the exact successful R3 receipt, original input, validity/history,
  installed FFmpeg/ffprobe/libaom and commands before/after execution. Normalize
  only passlog/output argument positions and the single qmin0/qmax8 pair.
- Fresh first-pass statistics must exactly equal the admitted208496-byte
  SHA256 `aa3f8940549354587cd0f417108b257999f3f303871d397f3dbeb7dd1da55d81`.
  Preserve a snapshot and require unchanged stats through pass2. Mismatch is an
  unexpected coupling/validity failure, not quality evidence.
- Retain both pass times, UTC start/end, complete commands, logs, hashes,
  failure receipts, remux execution and full/scored actual packet populations.
  Accept a successfully encoded above-cap stream as an **unconstrained
  diagnostic**; requested rate and container size are not measured video rate.
- The private same-binary off and trace replays must both exactly reproduce this
  installed arm, using its actual stats and command. Parse the new stream's
  complete reference/display history independently; do not inherit R3 target
  packet, event, order hint, refresh flags or population counts.
- Bind original input216/scored120, actual coding source, packed final OBU,
  decoded display, final generation, all visible ownership, source/predictor/
  residual and final inverse/pre-loop/post-loop exactly. Require all parsed coded
  base qindices≤32, and separately report actual exercised TU quantization.
- Delivery requires, separately for shirt and background, exercised-pixel mean
  qindex≤40 and at least90% of exercised pixels≤48. Report every value above32,
  full ROI status/skip/transform fractions, and the changed exercised population.
  Empty populations fail. These gates never describe skipped pixels as having
  received finer quantization or establish whole-ROI preservation.

Failure of intended delivery is an intervention failure before quality inference.
Unexpected encoder states, missing coverage, incompatible input or insufficient
storage stop execution/admission for a focused correction. Keep failure evidence.

## Quality and cost

After delivery and all336/all240 exact decoder/color/alignment checks, run the
required `campaign.py` GPU paths with serialized GPU use. Reuse all frozen source
tiles, quiet/detail controls, five-frame primary windows, full240-frame
HF/ACF/correlation/temporal evidence, full-reference means/tails and CAMBI.
Report both scored-window and complete-window packet rates and measured two-pass
wall time. Inspect exact native visual artifacts; still inspection is not playback.
No pooled score can compensate for failed texture or clean-region requirements.

Only demonstrated preservation justifies a later separately declared source-budget
redistribution attempt. Practical rate remains≤9.6765224Mbps for this E05 window
and≤10.029358641Mbps for E04; decisive matched-rate comparisons require99–100%
of original and pairwise1%. E04, full-episode and actual playback qualification
remain necessary before any production proposal. No threshold is relaxed here.

Read-only resource preflight requires at least130GiB free on staging, checks active
jobs and keeps CPU use bounded; GPU scoring is serialized. Expected encode
duration is minutes, with slower execution possible under the precision bound.
Preserve commands, source/binary identities, useful traces and media. Archive and
remove reproducible intermediates through the established workflow at completion.
