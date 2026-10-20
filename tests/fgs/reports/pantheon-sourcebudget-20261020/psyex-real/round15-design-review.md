# Round 15 design review — real TF-off / public-QP1 feasibility arm

Reviewed 2026-10-20 before a runner or outcome existed. This review is bound to the pinned PSYEX source at `parent/psyex-coeff-r11/source`, R8 command receipt `worker/psyex-r8/runs/e05-1440/psyex-1x1/command.json`, and admitted R13/R14 results. No encode or metric was run.

## Disposition

The one bundled arm is justified and falsifiable as an **uncapped real-policy feasibility/cost test**. R14 makes it informative rather than wasteful: replacing the captured coding input by original samples at fixed decisions and qindex 1 moved the shirt from 62.79% HF / 0.08207 ACF error to 86.50% / 0.04132, while the corresponding raw arm reached 88.89% / 0.02809. A real arm is now needed to learn whether decision/support changes and the legal feedback loop retain that local opportunity and what its packet cost is. More fixed-decision points would not answer either question.

It is not a clean TF, quantizer, or rate-control contrast. `--enable-tf 0` changes the filtered-reference/GOP decision family, while fixing public QP bounds changes frame quality, SB delta-Q, lambdas, modes, partitions, transforms, filtering, and feedback together. The result can establish only whether this exact bundle preserves under the unchanged screens and its measured cost.

## Blocking terminology / delivery correction

Public `--min-qp 1 --max-qp 1` does **not** request internal qindex 1 and must not be called “q1.” `Source/Lib/Codec/md_process.h:1268-1273` maps public QP 1 to internal qindex 4. Moreover, these bounds constrain rate-control frame QP, not every SB/TU:

- two-pass bounds are mapped through that table in `pass2_strategy.c:1178-1179`;
- the initial frame base is bounded, but variance boost then rewrites the coded base and SB indices in `rc_process.c:1507-1602`; its SB clamp permits qindex 1;
- TPL/AQ adds SB offsets and clamps only to the codec range in `rc_process.c:1623-1658`;
- the live sequence is initialized and applied in `rc_process.c:3690-3730`.

Consequently, the preregistered intervention is **TF disabled plus public QP bounds [1,1]**, with actual normative qindex an outcome to observe. “Near-fine precision delivered” is admissible only after reporting the complete target-ROI effective-q distribution. The trace should cross-check the final EncDec quantizer producer with decoder normative q, DQ/EOB, and committed owner geometry. A mismatch or incomplete target population is delivery failure, not a quality result. Do not impose a post-hoc q threshold; report every value and the fractions above internal qindices 1 and 4.

The static `--qp` default remaining unchanged is acceptable for this bundled public-policy test, but it is not semantically inert: code including `pass2_strategy.c:1611-1624` and `normalize_sb_delta_q()` uses the static value in RC/delta-Q logic. Preserve and report its effective value; do not describe min/max as an absolute TU cap.

## Minimum admission controls

1. Diff both pass commands against admitted R8 and allow only `enable-tf 1→0`, addition of `min-qp 1`, `max-qp 1`, and fresh artifact paths. Keep TBR 10313 and every other explicit policy flag identical. Require fresh pass-1 stats; bind both passes, actual effective log fields, pinned app/library/source/input, before/after hashes, CPU bounds, and successful completion.
2. Measure both full and scored-window IVF and Matroska packet rates, consistently use the established Matroska 96:336 value for the practical ceiling, and retain per-packet remux deltas. The 10,313 kb/s request is not evidence of achieved rate when the quality bounds bind.
3. Require 336-frame cadence/color and exact all-plane agreement among app reconstruction and the established independent decoders. Dynamically reconstruct the coded/display/reference lifecycle: TF-off can change hidden-event population, so no R8/R9 event ordinal, order hint, packet, or OBU may be reused by assumption.
4. Run an observation-replay control whose off/on streams and app reconstructions are byte/sample-identical to the installed arm. Bind displayed source frame 216 (scored frame 120), complete final owners, skips, TX/EOB/support, encoder final q and decoder normative q. Measure coding input versus original rather than infer equality from `enable-tf=0`; other preprocessing remains configured.
5. Only after those checks, apply the unchanged full 240-frame campaign, both prescribed texture boxes and HF/ACF gates, all 12,870 frozen control tiles, quiet/detail/tails/edges/banding/temporal/face summaries, and exact score-input identities. No playback claim follows from these statistics.

## Outcome interpretation fixed in advance

- If both texture regions and all controls pass but scored Matroska rate exceeds **9.6765224 Mb/s**, the arm demonstrates real representability at its measured cost; it is disqualified as a practical repair. That result can justify one subsequently calibrated, independently verified budget-allocation test.
- If the arm fails a texture gate despite complete low-q delivery, it rejects this exact TF-off/public-QP1 bundle. Compare final support, predictors, TX, EOB, loop-filter boundary, and actual q against R8 before choosing a narrower search/RD discriminator. It does not establish an AV1 or finer-precision limit.
- If a local texture gate passes but frozen controls regress, the arm fails candidate qualification regardless of bitrate.
- If delivery tracing finds materially different/higher effective q, incomplete owners, or a stream mismatch, make no preservation-mechanism inference.

The large likely overshoot is part of the question, not a reason to skip the arm. The runner should nevertheless preflight disk space and set explicit bounded wall-time/output-size/resource failure receipts because public-QP1 can greatly exceed the target bitrate.
