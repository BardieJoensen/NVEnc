# R17: quantization isolated on the real TF-off choices

Status: completed and independently reconstructed. Lower quantization restores
most observed scalar loss, but the fixed-choice shirt still misses its local
amplitude and structure criteria. This is a single-frame diagnostic, not a legal
encode or a practical candidate.

The [evidence manifest](psyex-q4/outcome/manifest.json) freezes 60 files
(2,442,230 bytes), including scripts, receipts, native results, still panels and
rejected preparation. The two larger native array/mosaic files remain in active
scratch with exact hashes. Read the [independent review](psyex-q4/outcome/reviewer/round17-outcome/REVIEW.md)
together with its [interpretation correction](psyex-q4/outcome/reviewer/round17-outcome/ADDENDUM.md).

The [contract](ROUND17_FIXED_Q4_CONTRACT.md) uses R16 frame216/scored120, preserving
predictors, partitions, transforms, scans and quantization matrices. All2870
tokens join the admitted owners. On all2169 invoked tokens, current-q scalar
q/DQ/EOB/inverse and raw inverse reproduce the captures exactly through direct C
and runtime dispatch before any new reconstruction. The independently bound
frame-header luma DC delta is0. Nativeq4 then replaces only FP table rows0/1/6,
with direct/runtime equality on every token. Packed64 transforms keep their
native1024-coefficient support. The701 uninvoked owners receive no intervention.

| Frame120 ROI/stage | HF/source | ACF error | Source-HF correlation | MSE |
|---|---:|---:|---:|---:|
| Shirt original | 100% | 0 | 1 | 0 |
| Shirt raw fixed-choice inverse | 86.735% | .03792 | .85378 | .19326 |
| Shirt scalar/preloop | 21.013% | .34788 | .05472 | 1.47524 |
| Shirt q4 | 86.080% | .05612 | .83228 | .21869 |
| Background q4 | 99.605% | .00492 | .98810 | .19733 |
| Face q4 | 93.543% | .02525 | .92133 | 4.25032 |

These single-frame values do not pass the required five-frame/full-window gates.
The shirt falls outside even the local±10% amplitude/.05 ACF limits. Background
falls inside those local descriptor limits; source-clean, line-detail, banding,
temporal and player/display acceptance remain untested by this diagnostic.

## What remains after q4

All20000 shirt pixels had invoked positive-EOB quantization at actualq71 in R16.
After q4, its16x16 and32x32 strata retain98.67% and99.95% of their own source HF.
The4624pixels using64x64 transforms (23.12%ofshirt) retain28.93%; the raw inverse
on that stratum retains29.50%. Complete-mask additive SSE assigns86.03% of q4
shirt error and96.56% of raw shirt error to those64x64 pixels. This is an SSE
partition, not an additive HF fraction or proof of one rejected search decision.

Background's1040 uninvoked pixels contribute66.91% of its remaining q4 SSE.
Face's81472 uninvoked pixels contribute99.19% of its q4 SSE. Those populations
are explicitly unchanged. They cannot be counted as q4 failures or successes.

Across all traced invoked tokens, nonzero coefficients rise20974→203490 and
EOB changes on2154tokens; q4 has positive EOB on all2169, including39 whose
baseline final EOB was zero. Coefficient counts are not coded-bit estimates.
No entropy coding or packet rate exists for R17. The diagnostic took3.594s
inside the runner (3.706s including the outer wrapper); this is not encode speed.

Whole-ROI metrics use the unchanged descriptor helper. Irregular strata use its
existing3x3-valid-mask high-pass and pair-valid ACF method. Complete-pixel SSE,
eroded descriptor support and valid pair counts are recorded separately. The
reviewer reconstructed every saved mosaic from token-indexed arrays and the
original trace, then independently reproduced all ROI/population/TX measurements.
All316 dependency identities remained unchanged.

## Review, corrections and next decision

The parent rejected four worker runner drafts before native execution for
scaling, schema, stage-comparison, DC provenance and incomplete-output errors,
then implemented the runner using established interfaces. One rejected draft's
exact source was not preserved; its hash alone is not inspectable source.
The final runner passed preflight and completed the native experiment once.

The worker's header extractor needed overlap and line-coordinate corrections.
Its accepted v4 binds event314/coded210, packet209's second header, and exact
physical DC line22349/zero-based index22348. The independent review also corrected
its own false cleanup comments and an initial assumption that the ROI trace
covered the entire frame. Full ROI coverage is exact; the trace covers345792pixels.
No metric formula or acceptance criterion changed.

The parent inspected native-size grayscale original/raw/scalar/q4 panels:
restored grain is visible, with residual smoothed patches on the shirt.
This was still inspection only.

Another fixed-choice quantizer point is low value. Raw HF is not a strict upper
bound on all quantized HF, so this does not prove numerical or codec impossibility.
The reviewer proposed a local64→four32 split. The parent selects a real spatial
absolute-cap experiment next to measure delivered precision, changing encoder
decisions and actual bit cost, which local reconstructions cannot supply.
R15 already proves legal preservation when decisions change at high rate.
The local split remains a discriminator if a real cap retains the deficient
64x64 support. Original-rate practicality and all quality gates remain unchanged.

## Reproduction and artifact provenance

The accepted runner is
`parent/psyex-q4-r17/experiment.py`, SHA256
`cb0e9a59adfde606ec489095ba71874bf476f5775e5d4223a6cb477fb44f19a6`,
under `/tmp/downloads/codex-work/pantheon-sourcebudget-20261020`.
Its [receipt](psyex-q4/outcome/parent/psyex-q4-r17/result-1/receipt.json)
records all 316 dependencies before and after; the
[outer receipt](psyex-q4/outcome/parent/psyex-q4-r17/experiment-execution.json)
records the exact executed command and runtime.

For a deliberate rerun, preserve the original absolute dependency paths and use
fresh output and receipt names:

```bash
root=/tmp/downloads/codex-work/pantheon-sourcebudget-20261020
"$root/analysis-venv/bin/python" "$root/parent/psyex-real-r15/execute.py" \
  "$root/parent/psyex-q4-r17/NEW-execution.json" \
  "$root/parent/psyex-q4-r17/experiment.py" \
  cb0e9a59adfde606ec489095ba71874bf476f5775e5d4223a6cb477fb44f19a6 \
  "$root/parent/psyex-q4-r17/NEW-result"
```

The [render script](psyex-q4/outcome/parent/psyex-q4-r17/render.py) and
[panel manifest](psyex-q4/outcome/parent/psyex-q4-r17/stills-1/manifest.json)
document native-size grayscale output and rounding. The
[shirt panel](psyex-q4/outcome/parent/psyex-q4-r17/stills-1/shirt-4panel.png)
orders original, raw, scalar and q4 left to right. These panels are diagnostics,
not a player/display assessment. Active scratch dependencies remain in place
until the investigation reaches a stopping condition and can be archived safely.
