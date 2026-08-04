# Source-fit admission and model-failure fallback — 2026-08-03

> Quality-first research result. Nothing here was deployed. Production remains
> r4069 with bilateral separation, residual model fitting, and the existing
> Tdarr route. `modelsrc` remains default-off.

## Decision

**Do not change the flow routing yet, and do not enable source fitting over the
existing FGS route.** The source-derived model remains the leading architecture
for admitted photochemical grain, but a title/genre rule is not a safe proxy for
admission. In particular, a blanket animation bypass would discard a meaningful
13.57% saving on the textured Legend of Korra control, while a blanket
source-fit route would synthesize poorly representable texture on both held-out
animation controls.

The next code experiment is now better defined: keep the source fit when its
quantized AV1 model passes its safety checks; when it does not, fall back to the
already-proven residual model on the same bilateral base. The current fallback
restores the original frame. That is quality-safe, but it gives back essentially
all compression on long rejection runs.

## Held-out animation result

`general_content_gate.py` was extended with two original H.264 sources at the
flow's animation operating point, QVBR 34. Each arm contains 600 frames and all
14 grain-on/off outputs passed a complete dav1d decode.

| title | production bytes vs plain | production base VMAF vs plain | source-fit bytes vs candidate control | source-fit base VMAF vs control |
| --- | ---: | ---: | ---: | ---: |
| Phineas and Ferb | -3.87% | -0.7405 | +0.50% | +0.1068 |
| Legend of Korra | **-13.57%** | -1.4025 | +0.40% | +0.0424 |

The production comparison does not prove perceptual damage: source-referenced
base VMAF still confounds correct grain removal with picture loss. It does show
that the animation bucket is not one homogeneous routing class. Rick and Morty
saved only 4.2% in the first gate, Phineas saves 3.9%, and Korra saves 13.6%.
That spread rejects an NFO-only bypass rule.

Finished source-fit VMAF moved -0.2874 on Phineas and -1.0906 on Korra relative
to candidate-control. Those are guard rails, not a grain ranking: the two arms
synthesize independent textures and VMAF has a measured preference for finer
grain at fixed energy. Full SSIMULACRA2/Butteraugli scoring was deliberately
not used to turn the same confound into more decimals.

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-animation-gate-20260803/
```

## Admission report: useful axes, no deployable threshold

`sourcefit_admission_report.py` now scans every grain-table interval and reports
three questions independently: temporal/film-like evidence, AV1 model fidelity,
and coverage. `routing_verdict` is deliberately null.

| title | measured entries | cross-frame corr | source lag-1 / lag-2 | model lag-1 / lag-2 | anisotropy mismatch |
| --- | ---: | ---: | ---: | ---: | ---: |
| Phineas and Ferb | 26/27 | 0.141 | 0.236 / 0.179 | 0.227 / 0.321 | 0.030 |
| Legend of Korra | 14/27 | 0.161 | 0.658 / 0.638 | 0.672 / 0.621 | **0.092** |

Korra demonstrates why the axes cannot be collapsed. Its scalar horizontal/
vertical lags are close, but the AV1 model misses directional structure and
only half the table entries have sufficient static-flat evidence. Phineas has
good directional agreement but overstates lag-2 by +0.141. "Texture exists"
does not imply "this texture is film grain" or "AV1 can represent it."

The exploratory conjunction from the first 12 titles still rejects both
held-out animations: all six films had cross-frame correlation <=0.127 and
anisotropy mismatch <=0.032, while Phineas fails the first axis and Korra fails
both. This is encouraging held-out negative evidence, not a router. The bounds
were chosen after seeing the first corpus, there are only two held-out
negatives, and no held-out film-positive title has passed them yet.

## Silo's +26% is a model-failure fallback, not the grain table

`sourcefit_transfer_isolation.py` generated residual-fit and source-fit raw
bases, then encoded the complete 2x3 factorial: either base with no table, the
residual table, or the source table.

| isolated change | encoded-byte delta |
| --- | ---: |
| source base vs residual base, no table | +26.39% |
| source base vs residual base, residual table fixed | +26.36% |
| source base vs residual base, source table fixed | +26.37% |
| source table vs residual table, residual base fixed | -0.03% |
| source table vs residual table, source base fixed | -0.02% |
| combined source/source vs residual/residual | +26.34% |

All six fixed-base encodes passed complete dav1d decoding. The direct gate's
+26.13% is reproduced, and the decomposition is decisive: the table is
negligible; the changed base explains the whole movement.

Two same-arm raw repeats are sample-exact across all 1,658,880,000 luma/chroma
samples per run. This rules out a CUDA race or run-to-run state movement. Across
arms, however, 39.90% of luma and 31.88% of chroma samples differ. Chroma cannot
be changed by `kernel_fgs_level_compensate`, so the earlier explanation that the
Silo base delta was only one-code level compensation was wrong.

The debug trace and code path localize it:

| trace | residual fit | source fit |
| --- | ---: | ---: |
| reliable frames | 600/600 | 300/600 |
| regularization-rejected frames | 0/600 | 400/600 |
| copied-source fallback frames | 0/600 | 300/600 |

The source fit repeatedly needs a realized-template strength correction above
the conservative 1.25x bound. The analyzer safely holds the last valid model
for at most eight frames. Persistent rejection then reaches
`NVEncFilterFilmGrain.cu:2412-2415`, clears the grain parameters, and copies the
original source over the already-denoised output. This protects quality: a
denoised base with no synthesis would destroy grain. It also restores original
luma and chroma complexity, which is why Silo grows.

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-silo-transfer-20260803/
```

## Architectural correction

Source fitting is separator-independent only while it produces a valid model.
On persistent failure, the current safety fallback deliberately changes the
base operator from "bilateral clean base" to "unaltered source." This is not a
reason to remove the safety copy. It is evidence that the two-operator
architecture needs a third, explicit failure layer:

1. bilateral separator produces a clean base;
2. source fit is preferred when its quantized model passes correlation and
   realized-gain bounds;
3. residual fit is the conservative synthesis fallback when source fitting is
   rejected; and
4. restoring the original remains the last resort only if neither model is
   valid.

This ordering preserves the source-fit texture win on film, preserves grain
when AV1 cannot safely carry that model, and avoids silently treating a model
rejection as a routing decision. It must remain behind `modelsrc=on` until Silo,
the six films, the general corpus, KAT, CPU tests and complete dav1d validation
all pass.

## Residual-model fallback experiment

Commit `8439bd0e` implements that ordering behind `modelsrc=on`. It collects a
second compact statistics buffer from the already-produced bilateral residual.
When the source-derived model is rejected, the analyzer tries the deployed
residual solver before allowing the existing original-frame fallback. The
emitted model's origin is carried through the hold/hysteresis state and printed
as `fallback=0|1`; this avoids claiming that a held source model is a fallback,
or vice versa.

The implementation was built from a fresh pinned clone. The quick GPU gate
passed all 18 KAT fixtures, rejected the labelled bad texture model, and
accepted the shipping control. The CPU/parser suite passed 160 tests, including
new cases for source rejection with a valid residual model and for both models
being invalid.

Repeating the Silo raw 2x3 isolation changes the result decisively:

| isolated change | before fallback | with residual fallback |
| --- | ---: | ---: |
| source base vs residual base, no table | +26.39% | **-0.19%** |
| source table vs residual table, residual base fixed | -0.03% | +0.003% |
| combined source/source vs residual/residual | +26.34% | **-0.19%** |

All 600 source-fit frames now report `reliable=1`. Source regularization is
still rejected on 400 frames, as expected, but the emitted model is explicitly
the residual fallback on 463 frames and the source model on 137. The difference
between rejection count and emitted-origin count is the intentional model
hold/hysteresis. No frame reaches the original-copy fallback.

The two raw bases now have sample-identical chroma. Only 88 of 1,105,920,000
luma samples differ (0.00000796%), by 1--3 ten-bit codes, all at input luma
232--234. This is the bounded level-compensation difference that was previously
hidden by the much larger original-frame fallback.

The direct QVBR 29 gate agrees. Source fit is 0.016% smaller than candidate
control; base VMAF is 94.1637 versus 94.1636 and base PSNR is 47.1281 versus
47.1282. All grain-on and grain-off outputs pass complete dav1d decoding. The
finished VMAF delta (-0.5893) is not a grain-fidelity verdict because the two
arms synthesize independent, pixel-misaligned grain fields.

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-silo-fallback-20260804/
/media/merged-storage/media/test-encodes/sourcefit-silo-fallback-gate-20260804/
/home/bardie/.cache/fgs-gate/reports/20260803T235133Z/
```

This closes the Silo size regression and validates the failure-layer mechanism
on one real title. It does **not** validate source fitting for production or
create a routing threshold. Grain delivery/texture on Silo and the six-film
architecture corpus remain the next gates.

## Silo texture by emitted-model origin

The direct Silo stream was split into intervals where the emitted table came
from the source solver and intervals where it came from residual fallback. The
same source-selected production-flat/static masks were used for both arms.

| interval | arm | synth amplitude | synth lag-1 / lag-2 | played total |
| --- | --- | ---: | ---: | ---: |
| source-origin | residual control | 0.801 | 0.158 / -0.110 | 0.937 |
| source-origin | source fit | **1.031** | **0.524 / 0.275** | **1.142** |
| source-origin | source truth | 1.000 | 0.502 / 0.276 | 1.000 |
| fallback-origin | residual control | 0.885 | 0.153 / -0.089 | 0.998 |
| fallback-origin | source arm (fallback) | 0.873 | 0.168 / -0.089 | 0.991 |
| fallback-origin | source truth | 1.000 | 0.451 / 0.234 | 1.000 |

The failure layer behaves as intended: fallback intervals reproduce the
residual arm's texture and delivery closely instead of copying the source or
dropping synthesis. Accepted source-model intervals reproduce spatial texture
nearly exactly, but their played total is 14.2% high because the coded base
still contains about 46% of temporal grain amplitude. This is not a fallback
defect. It is evidence that the six-film leak-transfer calibration does not
close Silo's accepted intervals accurately enough to treat `modelsrc=on` as a
general-content switch.

Across the default mixed-origin sample, source fit moves luma synthesis
lag-1/lag-2 from `0.156/-0.108` to `0.348/0.093` against source
`0.427/0.188`, while played total moves from `0.937` to `1.054`. U/V played
totals are `1.033/1.075`; V reaches `1.142` in the darkest populated luma
band. These are useful quality bounds and reinforce the decision not to change
the flow route yet.

## Six-film non-interference result

The pinned fallback binary was run through direct QVBR 29 encoding, raw clean
base generation and complete dav1d decoding on Casino, Interstellar, Scarface,
Taxi Driver, The Deer Hunter and The Shining.

| title | analysed frames | source regularization rejects | emitted fallback frames |
| --- | ---: | ---: | ---: |
| Casino | 287 | 0 | **0** |
| Interstellar | 288 | 1 | **0** |
| Scarface | 287 | 0 | **0** |
| Taxi Driver | 287 | 0 | **0** |
| The Deer Hunter | 288 | 0 | **0** |
| The Shining | 288 | 0 | **0** |

Interstellar's one transient rejected estimate is absorbed by the existing
model hold. The residual fallback is never emitted on the admitted film
corpus, so the architectural source-fit result is not diluted.

All six outputs are decoded-identical to the pre-fallback candidate. Four have
byte-identical elementary AV1 streams. Casino and The Shining move one
redundant scaling point along an equal-valued plateau in the text table; their
grain-disabled and grain-enabled decoded-frame MD5s both match exactly. The
previous six-film texture, delivery and base-fidelity results therefore carry
over without statistical inference: the pixels are the same.

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-bilateral-fallback-20260804/
```

The fallback code is now validated as a non-interfering failure layer, not as a
production admission rule. The remaining architectural blocker is admission:
deciding when a source-derived model represents film-like, AV1-representable
texture and when to choose residual fitting from the start. Silo also keeps the
per-content leak-closure question open for any admitted non-film material.
