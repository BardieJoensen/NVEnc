# Coding-source pixel neutralization

Removing every measured coding-source sample substitution is a valid failed
repair arm at the original rate. The experiment establishes that these sparse
pixel changes affect the bitstream and reconstruction, but removing them does
not recover the severe E05 texture deficit under this fixed libaom policy.
It does not disable all temporal filtering/analysis or hold later coding choices
fixed. No codec-wide or implementation-wide limit follows.

The same reviewed private binary runs both arms. Disabled off reproduces the
installed PSNR IVF exactly. Enabled on retains TF/GF/TPL/show-existing analysis
and substitutes the original lookahead-source pointer immediately before actual
encoding. All363 selected/effective event pairs bind to all336 untouched input
frames and independent bitstream headers. Every selected-stage field equals off;
32 events have the same sparse sample differences before intervention. On has
zero changed effective samples on every Y/U/V plane and no distinct-source
pointer. Both streams contain363 coded plus127 show-existing headers, with the
same keyframe schedule. This proves realized sample neutralization and the
observed source-selection control; it does not prove all internal analysis state
or downstream decisions remain identical.

The scored actual MKV video packet rate is **9.6256032 Mbps**,99.4738% of original
9.6765224 and99.8601% of parent9.639088. No rate calibration was needed; requested
TBR11671 and preserved first-pass stats are unchanged. Three independent decoder
paths agree on all336 full frames, and all240 scored frames match exactly.
The enabled instrumented pass2 took373.697s versus371.444s for instrumented off.
These diagnostic replay times include tracing and reuse existing pass1 stats;
they are not measured end-to-end candidate costs. The installed baseline's
measured both-pass cost remains391.652s/336frames.

| Five-frame midpoint average | Original | Parent PSNR | Original pixels at coding input |
|---|---:|---:|---:|
| Shirt HF amplitude | 0.619353 | 0.098604 | 0.097788 |
| Shirt ACF absolute error | 0 | 0.113094 | 0.074420 |
| Background HF amplitude | 1.778495 | 0.909357 | 0.915182 |
| Background ACF absolute error | 0 | 0.106166 | 0.098892 |

Both frozen amplitude±10%/ACF≤.05 gates still fail. Source-HF correlation improves
from.0890→.1031 in shirt and.5009→.5052 in background. Full240-frame traces retain
the broad suppression pattern. Face/edge and quiet-region averages improve
slightly, while all-tile MSE6.4634→6.4922 and p9521.4488→21.6763 worsen;
6445/12870 tiles have worse MSE and6291 worse HF error. Quiet positive HF residual
falls from one tile(max.01801) to none(max0), but this is a frozen-tile numerical
screen, not comprehensive proof of no new perceptible noise.

VMAF94.00→94.01 and NEG92.50→92.50 do not capture a repair. VMAF p182.2309→82.1870,
SSIMULACRA2 mean54.81→54.79 and PSNR40.70→40.69 worsen slightly; Butteraugli
p957.76→7.68 and SSIMULACRA2 p526.85→26.87 improve. CAMBI mean/max
.381026/2.309536→.383783/2.332228 worsen. These small mixed changes are reported,
not collapsed into a single winning score.

[Machine result](aom-neutralization-result.json), [control](aom-neutralize-control.json),
[patch](aom-source-neutralize.patch), [reproduction](REPRODUCE.md) and
[review record](REVIEW.md) preserve commands, hashes, actual packet rates, all
frozen tile pairs, GPU frame metrics and temporal traces. Native10-bit comparison
clips for shirt/background/face validate every panel over all240 frames. Parent
inspected the shirt still and trace plot; no actual motion playback was observed.

Next hypothesis: after the now-tested source boundary, distinguish initial
scalar quantization, later coefficient optimization and already-selected skip
choices using fixed-TU observations and separate counterfactual reconstructions.
The public no-trellis option changes FP→B scalar quantization too, so it cannot
serve as a clean pruning-only discriminator. Any live optimizer bypass is a
separate coding-policy intervention with downstream feedback.
