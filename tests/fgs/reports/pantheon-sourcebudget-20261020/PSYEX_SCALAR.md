# R12: changing the scalar rule fails; q32 helps only part of the problem

At fixed R11 predictor, partition, transform and matrix, native scalar B at the
same actual qindex worsens texture amplitude and original-referenced MSE in all
three prescribed E05 frame120 ROIs. Native scalar FP at qindex32 improves several
measurements, especially background, but the shirt still has too little texture
and the wrong spatial structure. Neither local result is a repair candidate.

The [contract](ROUND12_SCALAR_CONTRACT.md), [compact result](psyex-scalar-result.json),
[reproduction](psyex-scalar/README.md), and [independent outcome review](psyex-scalar/round12-outcome-review.md) bind the result.
No encoded bytes changed, so there is **no new measured bitrate or encoding-speed
claim**. R8 still fails at 9.6279048 Mbps, 99.49757% of original, and 370.335769 s
for both passes over 336 frames. The R12 diagnostic subprocess took 11.484 s;
that measures offline analysis, not re-encoding cost.

## Exact controls

All 2,187 invoked TUs reproduce captured FP qcoeff, DQ, EOB and native inverse
exactly. Native raw inverses also match. All generated FP table rows match the
captured baseline rows at q71–115, supporting the zero luma-DC offset used by
the native lookup. Every baseline, same-q B and q32 quantizer/inverse operation
is independently executed through direct C and initialized runtime kernels;
all outputs agree exactly.

The helper links the existing R11 codec objects read-only. It does not change
encoder state, R11 source/build, reference frames, CDFs or encoded output. Every
linked object, source, compiler/link command and dependency is hash-bound before
and after. Original and coding-input frames remain separately identified.

The q32 control changes the three FP rows only. For shirt q71, DC/AC dequant is
255/297; q32 uses 109/122. Matrix/IQM, scan, transform scale and native predictor
remain fixed. B uses its captured zbin/round/quant/shift rows; it is a bundled
scalar-algorithm contrast, not one rounding parameter.

All 720 owners without final quantization retain their actual predictors.
Invoked support is 18,752/20,000 shirt pixels, 42,744/45,000 background pixels
and 157,504/240,000 face pixels. Native coefficient/pixel arrays and offsets
are preserved for every invoked TU; all fixed ROI intersections are reported.

## Observations

| ROI / measure | Original | Raw local inverse | FP baseline | B, same q | FP, q32 |
|---|---:|---:|---:|---:|---:|
| Shirt HF amplitude | .60632 | .39301 | .09367 | .07542 | .25097 |
| Shirt ACF1 error | 0 | .06621 | .19652 | .11520 | .39301 |
| Shirt HF source correlation | 1 | .77270 | .00818 | .00907 | .24932 |
| Background HF amplitude | 1.67639 | 1.62379 | 1.28049 | 1.00946 | 1.62212 |
| Background ACF1 error | 0 | .00464 | .14186 | .13709 | .03221 |
| Background HF source correlation | 1 | .96899 | .53894 | .46995 | .85610 |
| Face HF amplitude | 2.70085 | 2.53031 | 2.45413 | 2.29866 | 2.52115 |
| Face ACF1 error | 0 | .02238 | .06154 | .09422 | .03035 |
| Face HF source correlation | 1 | .92130 | .78707 | .77017 | .89323 |

FP→B MSE worsens 1.5282→1.5784 on shirt, 5.7948→6.2977 on background and
8.9932→9.5431 on face. q32 improves these to 1.1321, 1.6754 and 5.0929, but
shirt gradient error barely changes (.9520→.9417), and ACF error worsens.
Amplitude improvement alone would misclassify that shirt result.

Whole-ROI values are primary. The detailed result retains invoked, uninvoked,
final-positive and quantized-zero populations, support-aware intersection
descriptors and unweighted tails. Nonlinear HF/ACF summaries are not additive
loss fractions. Coefficient counts and magnitudes are not entropy-bit costs.

## Review, scope and decision

Independent reconstruction from native arrays and R11 geometry reproduces every
full-ROI metric within 1e-12. All admission controls pass. Same-q B reduces
nonzeros from 20,706 to 15,167 across 233,536 coefficient positions; q32 increases
them to 81,299. These demonstrate delivery, not coded-bit cost.

Design review required C/runtime equality on every new arm: baseline FP equality
alone would not validate different inputs. The implementation was revised before
any trace execution. A second review caught a baseline-table dictionary alias;
the baseline mapping is now frozen before adding q32 and matches the separate
baseline-control file exactly. Preparation-only build1 and the reviewed pre-fix
driver are preserved; native build2 is authoritative.

A source audit also corrected a suggested public `--trellis 0` follow-up: that
option is absent from this PSYEX version. Any real B-rule intervention would
require scratch source work and verified search/final delivery. This failed
local B result supplies no reason to run that intervention.

These are local single-frame diagnostics. They retain sequential native
predictors and do not propagate changed reconstruction. Original shirt texture
already differs from coding input, selected transform support is retained,
and 34.37% of face support never invokes final quantization. There are no quiet
controls in the frozen frame120 population. Full-window noise, banding, temporal
and playback gates are not evaluated by this diagnostic. Parent inspected
native-size rounded-luma stills only.

Accept the negative same-q B result. q32 rejects only that precision point;
it does not establish a finer-quantization or codec limit. The remaining
discriminator is whether a substantially finer native scalar point approaches
the raw local reconstruction, before changing upstream source processing or
selected decisions. The practical ceiling remains at or below original rate.

The [R13 contract](ROUND13_FINE_CONTRACT.md) selects only qindex1 for that
closure, with exact new-arm C/runtime controls and distances to raw. Then stop
local scalar sweeps and select an upstream or decision-policy experiment.
