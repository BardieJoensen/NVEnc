# Residual retention, reopened and closed (2026-11-06)

**Verdict: doesn't work.** No retain value beats production FGS (retain=0) on base detail at equal size once colour is counted, so retention stays parked. A per-class route doesn't help either, and neither raising the 0.5 auto cap nor resuming roadmap R3–R8 is warranted. The user reopened this on 2026-11-06 after a 10-second sweep showed retain=auto ahead on full-reference (FR) metrics.

## Method (frozen before results)

- **Windows:** 14 windows from 7 development titles, at 30% and 65% of runtime. Each is a 12 s keyframe-aligned stream copy of the original download, which serves as both encoder input and reference.
  - WEB fine grain: Black Doves S02E04.
  - Moderate 35mm: Brokeback Mountain, Coming to America.
  - Older 35mm: Life of Brian, Breakfast at Tiffany's.
  - Digital clean: Nightcrawler.
  - Animation control: Dark Knight Returns P1.
  - The reserved corpus (Bear S04E10, Pantheon S02E08, Transformers) was not opened.
  - The pre-declared dark-window rule shifted 5 windows by 60 s.
- **Encoder:** production nvencc f1327e14 with production args.
- **Variants:** prod, plain (no FGS), and retain 0.5, 0.75 and 0.9, each at QVBR 26/30/34. retain=auto at q30 with a debug log. prod q40 as the labelled detail-loss negative. 238 encodes in total; every one has the source frame count and zero alignment offset.
- **Primary measurement:** base detail, decoded with grain off, against the source.
  - Luma: Gaussian lowpass on both sides (sigma 3 primary, 1.5 secondary). Top-decile structured 16×16 patches give `amp` (amplitude ratio) and `err` (normalised structure error).
  - Chroma: the `chroma_base_detail.py` measure, generalised to the active area.
  - Equal-size values are interpolated against log rate at the prod q30 size (S1) and the retain=0.5 q30 size (S2).
- **Secondary measurements:** HF sigma plus residual acf, Butteraugli p95 (FFVship, verified to apply grain), and vmaf_p1.
- **Controls passed:**
  - Source vs itself gives amp 1.0 and err 0.
  - The q40 negative is worse than q30 on all 14 windows.
  - Adding iid grain at source strength moves amp_Y3 by 0.00002 and err_Y3 by about 0.0008.

## Results

- **Luma structure gains a little.** At S1, retain=0.5 has lower err_Y3 than prod on 13 of 14 windows. Prod would need a median of about +10% bits to match it (range −8% to +19%; Black Doves window 1 loses).
- **Colour is lost, even with more bits.** At fixed QVBR 30, retain=0.5 is 3–13% larger than prod on grainy windows, yet its structured Cb/Cr amp/peak is lower on 12 of 14 windows. On 6 of 14 it falls below the gate margin (prod − 0.002), worst on Brokeback window 2 (Cb −0.009). At equal size the loss grows to −0.012 Cb and −0.018 Cr at retain 0.9.
  - This is the direction the 2026-10-07 blind review found visible (dull lips), at a smaller size.
  - The first guess was that chroma follows a higher frame quantiser. The 2026-11-07 follow-up below disproves it.
- **Grain energy drops.** At equal size, HF ratio is 0.06–0.10 below prod. acf moves inconsistently.
- **Artifact tails get slightly worse.** Butteraugli p95 is worse on 10 of 14 windows (+0.1 to +0.5). vmaf_p1 improves by 0.2–2.8, which is the known FR bias toward pixel-aligned grain.
- **retain 0.75 and 0.9 are worse than 0.5:** less luma gain at equal size, more colour loss, lower grain, worse tails. They converge on plain. Raising the auto cap would not help.
- **Plain at equal size** loses luma structure vs prod on most film windows and smooths grain to an HF ratio of 0.38–0.72.
- **retain=auto** chose 0.5 on 12 of 14 windows, matching the earlier sweep, and costs within 1 point of retain=0.5. Its size cost vs prod at q30 by class: WEB +12%, moderate 35mm +7%, older 35mm +8%, digital +3%, animation +0.5%.
- **Animation:** every variant is within noise, so retain does nothing there.

## Independent check

A fresh-context Opus read of the raw data and instrument code reached the same answers. Its notes:

- **Chroma at equal size:** all 48 chroma deltas (12 grain windows × 4 numbers) are negative, and 9 of the 12 windows go past the gate margin.
- **Luma error vs amplitude:** err_Y partly rewards source-aligned retained grain, estimated at up to about 0.0006 of the gain. amp_Y is grain-robust, and its gain cannot be bought with prod bits at any tested rate, because the denoiser sets prod's ceiling.
- **Chroma has no lowpass:** chroma is scored without one. That affects plain vs prod, not retain vs prod.
- **retain=auto is more than 0.5:** it also switches on denoiser detail protection and chroma source protection (`NVEncFilterFilmGrain.cu` around lines 2252 and 2575), and it still loses more than 0.002 Cr on 3 windows.
- **Strongest case for retain:** a consistent, grain-independent luma structure gain. The colour loss looks like a bit-allocation side effect and is about 5× smaller than the visible lips gap, so it may not be visible. But it fails the release gate, and fixing colour first would be a new experiment.

## Answers

- **(a)** No class qualifies. The luma gain (about +10% bits, less than one QVBR step at the measured 13% per step) comes with structured-colour loss that the release gate would reject on half the windows.
- **(b)** No. Higher retain is worse on every primary measurement.
- **(c)** No route is worth it, and R3–R8 should not resume. The loss happens in how NVENC allocates bits once retained residual is in the luma. Per-region retention would put the same residual in front of the same rate control.

## Reopen if

A different encoder, or an NVENC release whose block-level decisions keep chroma when luma carries retained grain. A frame-level chroma QP offset is not enough (see the follow-up). When one appears, re-run this window set with the same instrument.

## Evidence

`/tmp/downloads/codex-work/fgs-retention-reopen/` holds the scripts, `results.json` (all rows plus the window manifest), `summary.md` and `controls.json`. The compact copy is in `reports/retention-reopen-20261106/`.

## Follow-up 2026-11-07: chroma QP offset (no change to the verdict)

The user approved one flag-only test. Production nvencc honours `--chroma-qp-offset` for AV1: it writes `delta_q_u_ac`, and V follows U. On the 12 grain windows (dkr dropped), prod and retain=0.5 were each run at offsets 0/−2/−4 and QVBR 26/30/34, then compared at equal size against prod@0 and prod at the same offset. Follow-up checks at q30 added offsets −16 and −32, plus a near-lossless (`--cqp 4`) input check on 6 windows. 240 encodes. Evidence: [reports/retention-chromaqp-20261107/](reports/retention-chromaqp-20261107/) (`summary.md`, `extra_summary.md`).

- **Reproducibility:** the offset-0 arms repeat the 2026-11-06 run.
  - Size moves by up to 2.96% (bat1), so NVENC is not bit-exact run to run.
  - err_Y3 moves by at most 0.00011, chroma amp by at most 0.002 and Butteraugli p95 by at most 0.41.
  - The size tolerance was raised from 0.5% to 3%, the matched-size tolerance in RETENTION-CONTRACT. The structure tolerance is unchanged.
- **The frame quantiser is not the cause.** Retain raises the median frame `base_q_idx` from 59 to 62 (bd1, q30), so an offset of −4 fully offsets that for chroma AC. Yet at equal size, retain still fails the chroma margin on 7–10 of 12 windows at every offset, for both comparators. The luma gain is unchanged (err_Y3 −0.0006 to −0.0009, better on 11 of 12).
- **Chroma reaches the encoder unchanged.** At near-lossless, retain minus prod chroma is ≤0.0002 on 5 of 6 windows (ca2 −0.0015), and luma err_Y3 is 0.002–0.007 better. Explicit retain touches only luma (`NVEncFilterFilmGrain.cu` around lines 2702–2726). The loss therefore happens inside NVENC's block-level coding, plausibly chroma-from-luma prediction or partitioning on noisier luma. This is not verified.
- **Larger offsets don't help either arm.**
  - At fixed q30, prod@−16 costs +9% bits and prod@−32 costs +34%.
  - Chroma err improves (0.266 to 0.255), but chroma amp/peak falls, luma err rises (0.0200 to 0.0223) and Butteraugli p95 worsens.
  - retain@−16 (+15.5%) loses to prod@−16 (+9.3%) on chroma err while costing more.
- **Production alone:** offsets −2/−4 are neutral at equal size (chroma within 0.0006, luma +0.0001 to +0.0003 worse). Nothing to ship.
