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

