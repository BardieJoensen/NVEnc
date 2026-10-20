# Independent R14 outcome review

## Disposition

R14 passes its admission controls and establishes that source-sample processing is a material contributor to the shirt loss. It also rejects source replacement plus q1 as sufficient under the retained predictor, partition, transform, and residual-support decisions. The next discriminator should therefore observe decision/support changes before committing to a combined real TF-off plus precision arm.

I independently reconstructed every reported stage from the R11 trace, R13 arrays, and R14 arrays. The reconstruction verifies all 2,907 owners, 2,187 invoked TUs, 720 unchanged owners, gap-free coefficient/pixel/source offsets, original-source identity, scan-derived EOB, fixed predictors, and every reported original/coding-input ROI descriptor and support distance.

Derived evidence:

- `reviewer/round14-outcome/derive.py` SHA-256 `27a8d56479d81c605d0fb5768985a8d395c3c3156dc0afd32dd3e5b0019f7ca0`
- `reviewer/round14-outcome/derived.json` SHA-256 `537d299719d7b71664eef524e71c04e800057255379a706ab1b08bafca2176fb`
- Reviewed result `0dcfb0f808ae9a34d0c707de828a4dd5ad88cc23a2bda3c0971585a0476008b8`; arrays `c8bdbaf904334a00c710ae89d34d65272af0b50be5898b2c18c8679226821592`.

## Admission observations

Both receipts are complete and bind unchanged inputs before/after. The baseline control confirms all 2,187 captured-source forward transforms, raw inverses, and new-library q1 results exactly reproduce R11/R13 before the intervention. Every new forward, quantizer, and inverse direct-C/runtime pair agrees.

The substitution changes 83,721/242,752 invoked source pixels (34.49%). No invoked TU has padding in this target frame, so all substituted samples are visible. It changes 111,666/233,536 raw coefficients (47.82%) and 74,829 q1 coefficients (32.04%). All 2,187 original-source arms retain positive q1 EOB; q1 EOB equals raw in 1,605 and is shorter in 582. These are substantive, realized changes rather than a null intervention.

## Measured local outcome

| ROI/stage | HF/source | ACF1 error | Original MSE |
|---|---:|---:|---:|
| Shirt captured-input q1 | 62.79% | 0.08207 | 0.51353 |
| Shirt original-source q1 | 86.50% | 0.04132 | 0.23243 |
| Shirt original-source raw | 88.89% | 0.02809 | 0.22239 |
| Background original q1 / raw | 97.03% / 97.43% | 0.00727 / 0.00378 | 0.46630 / 0.44578 |
| Face original q1 / raw | 93.90% / 93.90% | 0.02205 / 0.02118 | 4.28870 / 4.27152 |

Original samples recover a large part of the shirt amplitude and move ACF below the unchanged `0.05` screen. They do not reach the HF ±10% screen: q1 remains at 86.50%, and the unquantized fixed-TX inverse reaches 88.89%. The q1-versus-raw gap is now small relative to the source substitution, but still measurable.

On shirt invoked support, original-source q1 MSE is `0.14196` versus `0.44178` for captured-input q1. Unchanged owners retain MSE `1.59165`; they now contribute 42.73% of the full shirt q1 squared error despite covering only 6.24% of its pixels. The corresponding unchanged-owner shares are 89.21% for background and 99.51% for face. This is why background/face full-ROI MSE remains high even though their invoked original-source raw reconstructions are close to source.

As an explicitly non-codec oracle, replacing unchanged owners with exact source while retaining R14 invoked pixels gives shirt HF/ACF of 91.44%/0.02993 for raw and 89.12%/0.04251 for q1. The raw oracle crosses the two texture screens; q1 narrowly misses HF. This calculation does not establish a legal transform, bit cost, or attainable encoder state. It only shows that the unchanged-owner population is large enough to affect the decision.

## Causal reach

The supported update is that observed source preprocessing is necessary to explain a substantial part of the shirt loss, while fixed residual support and geometry still prevent joint recovery. R14 does not isolate a public TF flag, because a real source-policy change can alter references, search, partitions, and rate. It also does not show that q1 is affordable or that a coarser budget-feasible precision would retain this gain.

No bitstream was produced. There is no rate, full-window, quiet/tail/banding/temporal, playback, or repair conclusion. The exact-uninvoked calculation is diagnostic only and must not be described as an upper bound for nonlinear metrics or as legal synthesis.

## Next discriminator

Decision-support observation is more informative than immediately launching a combined TF-off plus precision candidate. Use one source-processing-off search replay at the existing policy and requested budget, with neutral instrumentation that records:

- the final invoked/uninvoked owner map and committed TX/q state;
- for each source-predeclared shirt owner that was uninvoked in R14, whether a legal residual-bearing candidate was evaluated, its native reconstruction, and its RD margin to the selected no-residual decision; and
- complete output/rate identity for an instrumentation-off control and actual packet rate for the changed arm.

Do not force a transform or choose a candidate from its texture score. If source-off search grows support and its committed/raw local reconstruction crosses the fixed screens, then one real source-off plus independently delivered absolute-precision allocation at the original packet ceiling is justified as a bundled feasibility test. If legal residual candidates remain absent or fail locally, further precision allocation is not the next useful action; the remaining target is search/objective/partition policy.

