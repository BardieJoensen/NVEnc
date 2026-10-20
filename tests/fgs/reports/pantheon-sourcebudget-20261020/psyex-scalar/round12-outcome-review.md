# Independent R12 outcome review

## Disposition

The diagnostic is admissible. The outer execution returned 0, the inner receipt is `complete`, and `result.json` is `admitted_diagnostic`. The admitted result SHA-256 is `9caf06214e249306788a6e58a22d134ed86284b4183fb38f815d8ccf236029d9`; `native-arrays.npz` is `aaee0f9c89623023e5c0d541c38241092950e99e3f48e46de4544bc5caf9799c`. The exact-baseline control covers all 2,187 invoked TUs and preserves all 720 non-invoked owners. All baseline, raw, same-q B, and FP-q32 C/native pairs are exact. The observed actual-q population is `{71,75,...,115}` and the generated q32 FP table is bound in the result. Inputs before and after match, including revised contract `3898232c...`, experiment `87eb15f8...`, and native library `07fe2554...`.

I independently reconstructed every arm from the admitted arrays and R11 trace geometry/predictors, reloaded original and coding-input luma, and reimplemented the descriptor calculations. Every full-ROI parent metric agrees within `1e-12`. Reproduction and derived evidence are in `reviewer/round12-outcome/derive.py` (`7f36790a...`) and `derived.json` (`b4800406...`). The small-lag ACF warnings in the run log concern undersized TU intersections; the admitted full-ROI values are finite.

## Observations

Across 233,536 coefficient positions, same-q B is more destructive than baseline FP: nonzeros fall from 20,706 to 15,167 (-26.8%), coefficient L1 from 22,074 to 16,336, DQ L1 from 8,708,209 to 6,443,220, and positive-EOB units from 2,151 to 2,132. It changes 1,902/2,187 TUs and 189,781/242,752 invoked pixels. FP-q32 instead has 81,299 nonzeros, DQ L1 15,308,588, and positive EOB in every invoked TU; all 2,187 TUs change.

| ROI / stage | HF/source | ACF1 absolute error | source HF correlation | MSE |
|---|---:|---:|---:|---:|
| shirt coding input | 72.79% | .03534 | .89655 | .31279 |
| shirt raw inverse | 64.82% | .06621 | .77270 | .49534 |
| shirt FP baseline | 15.45% | .19652 | .00818 | 1.52822 |
| shirt B same-q | 12.44% | .11520 | .00907 | 1.57844 |
| shirt FP-q32 | 41.39% | .39301 | .24932 | 1.13211 |
| background FP baseline | 76.38% | .14186 | .53894 | 5.79478 |
| background B same-q | 60.22% | .13709 | .46995 | 6.29775 |
| background FP-q32 | 96.76% | .03221 | .85610 | 1.67544 |
| face FP baseline | 90.87% | .06154 | .78707 | 8.99316 |
| face B same-q | 85.11% | .09422 | .77017 | 9.54305 |
| face FP-q32 | 93.35% | .03035 | .89323 | 5.09285 |

Same-q B therefore does **not** restore useful joint amplitude and structure. In the shirt it improves ACF error relative to FP, but loses still more HF amplitude, leaves source correlation effectively zero, and increases MSE. Background and face likewise lose amplitude, correlation, and MSE quality. A representative 32x32 shirt TU at q71 drops from FP EOB 165 / 6 nonzeros / DQ L1 995 to B EOB 3 / 3 nonzeros / DQ L1 559. This is stronger pruning, not a preservation mechanism.

FP-q32 is materially different. It improves amplitude, correlation, and MSE, and the single-frame background and face satisfy the existing numerical HF/ACF screens. The shirt does not: HF remains only 41.39% of source and ACF error worsens to .393. Its representative shirt TU rises to EOB 605 / 108 nonzeros / DQ L1 6,872, showing that the negative shirt result is not failure to exercise the finer scalar arm. The q32 result rejects this fixed q point as a joint shirt-preservation answer; it does not reject finer quantization generally.

The stage references matter. Shirt coding input already retains only 72.79% of source HF, and the unquantized local inverse retains 64.82%. Background and face coding inputs remain at 99.35% and 99.64%. Thus scalar loss is large in the shirt, but neither B nor q32 can be treated as the sole source of shirt loss. The raw arm is an unquantized local reference, not a mathematical upper bound for nonlinear descriptors.

## Causal reach and limits

These results isolate native scalar/reconstruction alternatives only for the 2,187 actually invoked TUs under fixed source, predictor, partition, transform, QM, and clipping. They do not cover the 720 non-invoked owners. They omit a subsequent optimizer for the counterfactual arms, reference feedback, filtering, entropy cost, and mode/skip changes. They are one frame and three fixed ROIs; there are no source-declared quiet tiles in this frame and no full-window, temporal, banding, tail, rate, legal-encode, repair, or playback evidence.

The B result also cannot justify a public `--trellis 0` arm: this pinned PSYEX exposes no such CLI/API option. A real B-policy test would require a private policy intervention and would bundle changes to optimizer/search decisions.

## Next discriminator

The cheapest bounded closure is one predeclared near-fine-limit native FP replay, such as q1, through the already verified helper—no sweep. Its stopping rule should be fixed in advance: if its coefficient/inverse surface converges to the raw arm, the fixed-decision scalar precision curve is closed; if it does not, report the native quantizer floor. This takes seconds and distinguishes “q32 was insufficiently fine” from “even effectively lossless scalar replay reaches the already-observed raw local surface.” It still cannot establish a repair or budget feasibility.

After that single closure, further local q points have little value. The evidence points to upstream coding-input loss and decision/skip policy for the next real mechanism test. Neither a same-q B encode nor a real q32 arm is justified by R12, especially given the prior high-rate qmax arm and the hard source-rate cap.
