# R11 independent outcome review

## Disposition

The completed artifacts support a narrow result: **for residual-bearing final EncDec TUs, the first scalar FP quantization is the stage that removes nearly all of the locally recoverable texture; the later full optimizer and noise-normalization stages do not explain the loss.** Face also has a separate large predictor-only/no-quantizer population. Source preprocessing remains material for the shirt, and post-loop filtering remains a separate loss boundary. These observations do not establish a source-budget repair.

Admission is complete and internally consistent: `admitted-1/admission.json` SHA `f9aba0b6...` binds 2,907 accepted-generation tokens, 2,151 final-positive units, actual committed ownership, exact final DQ/EOB/IQM, exact source/predictor/preloop joins, and an all-336 byte-neutral replay. `validation-execution-2.json` SHA `6e22b804...` records return code 0. The analysis receipt is complete, pins analyzer SHA `44b8037c...`, and binds `result.json` SHA `7ba42f09...`. Seven targeted malformed traces were rejected (`fault-run-1/result.json` SHA `3c87bec4...`); those probes are useful structural checks, not exhaustive parser proof.

I independently reparsed the admitted trace and rebuilt all fixed ROI mosaics with:

```text
cd /tmp/downloads/codex-work/pantheon-sourcebudget-20261020/reviewer/round11-outcome
python3 derive.py > run.stdout
```

`derive.py` SHA `7fc34a2b...` produced `derived.json` SHA `4a40383a...`. It uses exact stage-to-stage pixel deltas, avoiding additive interpretations of HF/ACF.

## Observations

The actual path invoked `scalar_fp` 2,187 times. Of its 2,151 positive outputs, `optimize_b` was invoked on every one, but changed q/DQ/EOB in only six units: none in the shirt, one background unit, and five face units. Noise normalization changed none; the final stage changed none. The optimizer changed 0 shirt pixels, 32/45,000 background pixels, and 316/240,000 face pixels. No pixel changed from after-optimizer to final.

By contrast, the fixed-predictor raw-to-scalar comparison changed 16,431/20,000 shirt pixels, 40,821/45,000 background pixels, and 148,495/240,000 face pixels. Full-ROI source-referenced MSE moved as follows:

| ROI | coding input | raw inverse diagnostic | scalar FP | after optimizer/final | post-loop |
|---|---:|---:|---:|---:|---:|
| shirt | 0.313 | 0.495 | 1.528 | 1.528 | 1.507 |
| background | 0.035 | 0.478 | 5.795 | 5.794 | 5.434 |
| face | 0.105 | 4.329 | 8.993 | 8.993 | 8.562 |

MSE-to-source is nonadditive; the direct raw-to-scalar stage-difference MSE is 0.793, 5.286, and 4.633 respectively. The optimizer stage-difference MSE is 0, 0.000225, and 0.002943.

The full-ROI nonlinear descriptors agree with that localization. Shirt HF sigma is 0.606 source, 0.441 coding input, 0.393 raw diagnostic, 0.0937 scalar, and unchanged thereafter. Background is 1.676, 1.665, 1.624, 1.2805, then changes by only 0.000007. Face is 2.701, 2.691, 2.530, 2.4541, then changes by -0.000015. These are whole fixed-ROI values; the analyzer correctly labels pixel-weighted per-TU HF/ACF aggregates as descriptive because those statistics are nonlinear.

The branch populations matter:

| ROI | quantized, EOB>0 | quantized, final EOB=0 | no quantizer | actual qindex |
|---|---:|---:|---:|---|
| shirt | 18,368 px / 24 units | 384 px / 1 | 1,248 px / 2 | 71 |
| background | 42,680 px / 424 | 64 px / 1 | 2,256 px / 32 | 79–87 |
| face | 152,640 px / 1,703 | 4,864 px / 34 | 82,496 px / 686 | 71–115 |

Thus scalar quantization accounts for the decisive loss on exercised support, including final-zero quantized owners. It cannot account for the 34.4% of face pixels whose final owners never invoked the quantizer; those remain a final no-residual/search-decision population. The positive-face aggregate reinforces this separation: raw diagnostic MSE is 0.040 versus scalar 8.880, while absent-residual MSE remains about 14.35.

Representative shirt token 877 / unit 6203 is a 32x32 TU at actual qindex 71. It has 996 nonzero raw coefficients and raw EOB 1024; scalar FP retains six qcoefficients with EOB 165. Optimizer, noise normalization, and final are byte-identical to scalar. Within its shirt intersection, MSE rises from 0.396 raw to 2.488 scalar and HF correlation falls from 0.956 to -0.008. The one changed background optimizer unit and five changed face units slightly alter magnitudes but do not form a common loss mechanism; in the changed background example, optimization actually reduces source MSE.

## Interpretation and limits

This is stronger than an invocation count: the captured scalar q/DQ drives a native inverse with the same actual local predictor, partition, transform, type, qindex and QM, and its final DQ matches the normative decoder exactly after proven storage normalization. It localizes the coefficient loss before `optimize_b` in this admitted R8 stream.

It does not show that FP scalar quantization alone causes the final perceptual failure. The shirt already loses about 27% of source HF at the coding-input boundary; face has a large no-residual population; post-loop filtering changes all three regions. Predictors are held to the original sequential encode, so counterfactual reconstructions do not propagate into later predictors/references or alter mode decisions. Raw inverse is diagnostic and is not a legal encoded reconstruction. One frame and predeclared ROIs do not prove behavior over the whole sequence.

The byte-identical IVF (`26f51de...`) means prior R8 full-window GPU metrics, frozen controls, tails and temporal evidence remain exactly applicable; R11 adds no new regression or quality result. It supplies no entropy cost, packet-rate change, playback observation, or repair feasibility. Raw-nonzero to q-nonzero counts are descriptive and must not be reported as additive texture-loss fractions.

## Smallest next discriminator

Before another full encode, run one all-invoked-TU fixed-decision **scalar-B versus scalar-FP** diagnostic using the captured raw coefficients, exact qindex/tables/QM/scan, predictor and transform. First replay FP and require exact q/DQ/EOB/native-inverse equality with the admitted scalar stage; then substitute only the pinned native B scalar quantizer. Preserve every invoked TU, all frozen ROIs, and the no-quantizer owners unchanged. Report exact coefficient and pixel deltas plus the same whole-ROI descriptors; do not select coefficients or regions from the outcome.

- If B materially restores the quantized-support texture, one matched source-budget real `trellis=0` policy arm becomes justified, with runtime delivery checks because search and feedback can change.
- If B is identical or fails, it rejects that public scalar-policy route. The next local question is finer quantization/representability, while the face still requires a separate no-residual decision discriminator.

This diagnostic is cheaper and more specific than another blind policy encode. It still cannot establish bitrate efficiency or a deployable repair.
