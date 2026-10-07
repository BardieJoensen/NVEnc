# Where the grain goes missing

Two causes dominate, and neither is the analyzer's fit. On real 1080p SDR footage most of the colour-grain loss comes from source-safety caps: the 8-bit sources contain hundreds of exactly flat chroma blocks per frame (codec-flattened colour inside grainy pictures). Each one zeroes the frame-wide chroma grain curve over its brightness range, so the source's chroma noise is blended back into the base and NVENC codes away about half of it. Lifting those caps on Gentlemen restores chroma texture (HF 0.52 → 0.96–1.12 of source) and makes the file 6.4% smaller, but every such flat chroma patch then receives grain, which the clean-source rule forbids. For luma, and for chroma on known-answer grain, the bilateral separator is the main cause. It removes only a high-passed part of the grain (all but ~8% of fine grain, but only ~29% of coarse-grain energy). The low-frequency rest stays in the base, where NVENC discards most of it. The fit itself is faithful: it reproduces what it measures to within 2% on fine grain and 9–15% short on coarse grain. One fit-stage defect is large where it applies: the anti-ripple AR certification rejects coarse grain models in PQ on 53–88% of frames.

## Method

The debug-only traces added on `research/fgs-fidelity-attribution-20261007` (`08d4996f`, `fc7f4bab`) give each stage directly. `NVENC_TRACE_SUBMISSION_RAW` dumps the exact picture NVENC receives (the separator output, after any source blend). `NVENC_FGS_TRACE_ANALYZER` dumps the analyzer's own per-bin residual (it fits `source − denoised` on flat blocks), its solved model, the uncapped and final curves, and which safety rule capped which plane. Stages are measured per plane and luma band: amplitude, HF sigma and H/V lag-1/2 (`stage_axes.py`). The known-answer set has six flat panels with white or Gaussian-correlated grain (lag-1/2 0.77/0.36, Taxi-like) at σ 3 and 6, with independent chroma grain, in SDR and PQ. Real windows were frozen before any result (`WINDOWS-FROZEN.json`): Gentlemen, Lost Tapes, Taxi 4K PQ, and Play Dirty (native-1080p coarse film) at 25/50/75%. Encodes use the production flow arguments; the binary is the shipped bundle plus tracing.

## Ranked causes

| # | Cause (stage) | Evidence | Size |
|---|---|---|---|
| 1 | **Chroma source caps** (analyzer curve decision) | Gentlemen 279–306 constant-chroma blocks per frame zero 165–207 of 256 Cb/Cr levels; Play Dirty 421–797 per frame | Gentlemen chroma HF 0.52 → 0.96/1.12 with caps off; Play Dirty 0.82–0.87 → 1.09. Bytes −6.4% / −5.6% with caps off. Cost: 2,149 Cb and 3,083 Cr constant patches in 192 Gentlemen frames get grain (≤0.58 RMS) |
| 2 | **Separator high-pass** (bilateral) | Coarse SDR luma: residual 0.29 of true energy, lag-2 −0.02 vs +0.34; 0.36 left in base, of which NVENC keeps 0.22. Fine grain: residual 0.92 amplitude, lag-1 −0.11 | Coarse output amplitude 0.68–0.69 (luma), 0.73–0.75 (chroma); fine 0.91–0.95. Taxi luma 0.66, Gentlemen luma HF 0.87 |
| 3 | **AR certification rejects coarse PQ models** (fit) | `rejected=1` from the anti-ripple stability/decay check; recovery hold follows | Synthetic coarse PQ: no synthesis on 51/96 (σ3) and 84/96 (σ6) frames. Not seen on the 24-frame Taxi; library incidence unknown |
| 4 | Coarse-grain fit shortfall (template gain / AR quantization) | Synthesized 0.49 vs measured 0.54 (σ3), 0.45 vs 0.53 (σ6) | 9–15% amplitude on coarse grain only |
| 5 | Curve fit, quantization, rendering | White grain: synthesized = measured within ±2% in every plane and band | Negligible |

NVENC's coding of the base is not an independent cause: it destroys grain that the separator or a cap left in the base, which is where synthesis should have carried it.

## FGS versus plain NVENC at the same QVBR

Production flow arguments, release binary `46d6781c`:

| Original | Frames | FGS / plain bytes |
|---|---|---|
| Gentlemen (1080p digital) | 3,600 | 0.975 |
| Lost Tapes (1080p animation with grain overlay) | 16,272 | 0.980 |
| Amphibia (1080p clean animation) | 17,193 | 1.002 |
| Play Dirty (1080p coarse film), 10 min | 14,385 | 0.890 |
| Taxi (4K PQ coarse film) | 24 | 0.702 |

On 1080p SDR, FGS currently saves 0–11%, much less than on 4K HDR. Causes 1 and 2 keep grain in the base, where it costs bits.

## What this means for the brief

The largest real-footage loss is a fit-stage decision (cause 1), but its fix conflicts with the accepted clean-source invariant: a frame-wide chroma curve cannot both grain codec-flattened constant chroma and leave constant chroma clean. Cause 2 is the separator, which the brief routes to a costed plan. Cause 3 is a fit-stage fix with no conflict, but it is smaller and HDR-specific. Evidence: scratch `/tmp/downloads/codex-work/fgs-fidelity-20261007/` (`kat/`, `real/`, `caps/`, `size/`, each with traces and `stages.json`).
