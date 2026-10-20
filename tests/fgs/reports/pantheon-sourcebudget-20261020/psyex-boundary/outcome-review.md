# R9 boundary-observation independent outcome review

Reviewed 2026-10-20, read-only. Principal identities:

- admission `f6a7a6d3221f15fb789419a43cd3f1b61372ffb99e325cd1ee131962ed5be7fc`
- record metadata `fe3b060e1b21c6c99c9f3366a2fed6b894efbc4197c8dd17404049d55ca61915`
- analysis `b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5`
- fault receipt `d9cd01c47cbdacf7e7a4025f83b148dff688b9711d439c344ea72d153fcc9539`

## Admission and validity

Admission is sound for the stated single-frame boundary question. Off and on replays retain exact R8 full-336 IVF and reconstruction streams. The on trace contains one accepted generation with 510 uniquely owned visible SBs, one pre-loop record, one post-loop record, and one terminal record (513 total). All visible Y/U/V samples are owned exactly once; original frame 120 equals input picture 216; post-loop equals the admitted R8 app reconstruction for picture 216. The corrected raw `show_existing_frame=6` is consistently treated as an uninterpreted 3-bit DPB-slot member, with activation unknown.

All 858 frozen frame-120 controls are present. The population is 120 edge, 480 flat-texture, 258 other, and zero quiet; 840 are in the legacy outside-only subset. Therefore this frame provides no quiet-group observation. Null groups are retained explicitly rather than silently dropped. The visual artifacts are hash-bound, have correct native geometry and labeled fixed-ROI strips, and convert 10-bit luma to rounded 8-bit-equivalent display values once. They are inspection aids; rounding can hide sub-code-value differences and they are not color, motion, playback, or exact-10-bit evidence.

The fault receipt exercises all preregistered structural classes: nine corrupt traces are rejected, while a plausible in-range post-loop change survives structural parsing and is shown to differ from the required R8 post frame. The synthetic mutations are deleted and rejection errors are generic `AssertionError`, so the receipt demonstrates the result by case/hash rather than preserving independently inspectable corrupt inputs or assertion sites. This is adequate corroboration, not new encode evidence.

## Observations

Values below are for the exact single frame and fixed coordinates, in 8-bit-equivalent sample units.

- Whole-frame coding input already differs from original: luma MSE `0.1758`, HF sigma `1.3454 -> 1.3059`, and only `44.36%` of luma samples are exactly equal. Coding-input-to-pre-loop is the larger pixel transition (luma MSE `3.2583`); pre-loop-to-post-loop is smaller (`0.3239`).
- Post filtering improves whole-frame luma MSE relative to original from `3.5989` to `3.4146`, while HF sigma falls further from `1.0634` to `0.8846`. Lower sample error and texture preservation therefore move in different directions.
- **Shirt:** HF sigma is `0.6063 -> 0.4413 -> 0.09367 -> 0.05454` (coding input retains 72.8% of source; pre-loop 15.4%; post-loop 9.0%). Source HF correlation is `0.8965` at coding input but only `0.0082/0.0178` at pre/post. Most loss is present before post filtering. Post filtering further lowers HF, but ACF1 error improves markedly from `0.1965` pre-loop to `0.04362` post-loop and MSE slightly improves (`1.5282 -> 1.5069`).
- **Background:** HF sigma is `1.6764 -> 1.6655 -> 1.2805 -> 0.8478`. Coding-input change is negligible by the texture descriptors; both coding/reconstruction and post filtering contribute material loss. ACF1 error rises `0.00093 -> 0.1419 -> 0.1903`.
- **Face:** HF sigma is `2.7008 -> 2.6912 -> 2.4541 -> 2.1504`. Again coding input is close to source, while pre-loop and post-loop each remove energy. ACF1 error rises `0.00101 -> 0.06155 -> 0.13982`.
- Across all 858 frozen tiles, mean absolute HF error is `0.0761` at coding input, `0.4371` pre-loop, and `0.5890` post-loop. Mean ACF1 error is `0.0251`, `0.2307`, and `0.2551`. The outside-only results are very similar (`0.0743/0.4352/0.5895` HF), so the aggregate transition is not produced solely by the 18 non-outside tiles. Edge, flat-texture, and other groups all show additional post-loop HF loss; exact magnitudes differ.

## Interpretation and limits

The evidence localizes loss to multiple boundaries. It rejects a filter-only account for the shirt: substantial alteration exists in packed coding input, and the dominant additional loss is already present in pre-loop reconstruction. It also rejects an account in which post filters are immaterial everywhere: the background, face, whole-frame, and frozen groups lose additional HF/ACF fidelity across pre-loop to post-loop. These filters simultaneously reduce MSE, so their effect cannot be characterized as uniformly harmful.

This observation does not isolate temporal filtering, input preparation, prediction, partitioning, coefficient selection, quantization, or a particular post filter. It does not show which search candidates survived final commit. One selected frame cannot establish whole-window prevalence, temporal behavior, practical repair, or subjective visibility. Exact stream identity lets prior R8 quality evidence identify the output, but does not turn this boundary analysis into a 240-frame result.

## Narrowest next discriminator

Use the same byte-neutral observational replay to export the **final committed target-frame TU/block map** at accepted generation only: visible geometry/ownership, final mode and transform, skip/skip-mode, EOB, and realized qindex, joined to fixed shirt/background/control coordinates and the already admitted coding-input/pre-loop samples. Require complete visible ownership including block/TU skips, an explicit unsupported-state failure, exact off/on IVF+reconstruction identity, and consistency of an assembled final reconstruction with the admitted pre-loop plane.

This is narrower and more informative than another policy encode. It tests whether the dominant coding-input-to-pre-loop loss corresponds to final skipped/zero-EOB regions, quantized nonzero transforms, or both, and whether the R8 aggregate policy counters describe decisions that actually survive final commit. It must not attribute the earlier original-to-coding-input shirt loss; that remains a separate input-preparation boundary question. If the final map shows pre-loop loss concentrated in skipped/zero-EOB ownership, the next causal test should target that final decision. If nonzero transformed regions dominate, a coefficient/quantizer-stage discriminator is warranted. Post-filter substage tracing should follow only if the repair decision specifically turns on the additional background/face filtering loss.
