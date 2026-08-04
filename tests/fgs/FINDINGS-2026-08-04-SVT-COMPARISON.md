# NVEnc source-fit versus SVT-AV1 native film grain — 2026-08-04

> Measurement only. Nothing deployed. Production remains r4069 bilateral /
> residual, `modelsrc` default-off.

The last SVT comparison in this project is dated 2026-07-16/17, predates every
source-fit change, and was decided on VMAF and SSIMULACRA2 — the metrics
`FINDINGS-2026-08-02-METRIC-SENSITIVITY.md` and
`FINDINGS-2026-08-03-AMPLITUDE-MATCHED-TEXTURE.md` have since shown are biased
against exactly what FGS does. No August findings mention SVT. This re-runs it.

## Setup

Taxi Driver, the retained lossless 288-frame 4K10 `clip_Taxi_Driver-ref288.mkv`,
which is the project's heavy-35mm-grain stress case.

- **NVEnc**: the pinned bilateral + source-static candidate from
  `sourcefit-texture-final-sixfilm-20260804`, QVBR 29, preset P4, tune HQ.
- **SVT-AV1** `6dbe850` release, preset 6, `--film-grain N
  --film-grain-denoise 1`, CRF swept to match size.

Grain statistics come from `temporal_grain_report.py` on 12 adjacent frame
pairs with the production static-flat selector, masks taken once from the
source. VMAF is the 4K model pair with CUDA extractors, dav1d decode.

Artifacts: `/media/merged-storage/media/test-encodes/svt-compare-20260804/`.

## Size-matched result

NVEnc 30,590,596 bytes against SVT 32,044,274 — SVT carries 4.8% *more* bits.

| | source truth | NVEnc bilateral+source-fit | SVT fg12 CRF25 |
| --- | ---: | ---: | ---: |
| bytes | — | 30,590,596 | 32,044,274 |
| encode speed | — | **26.9 fps** | ~8.8 fps |
| VMAF 4K | — | 86.946 | **92.200** |
| VMAF NEG | — | 86.105 | **91.241** |
| PSNR-Y | — | 38.333 | **42.017** |
| delivered grain amplitude | 1.000 | **0.997** | 0.731 |
| delivered lag-1 | 0.809 | 0.786 | 0.822 |
| delivered lag-2 | 0.441 | **0.413** | 0.529 |
| *synthesis* amplitude | — | **0.864** | 0.267 |
| *synthesis* lag-1 | 0.809 | **0.735** | 0.397 |
| *synthesis* lag-2 | 0.441 | **0.288** | -0.089 |

The two arms are doing different things, and the synthesis rows are where that
shows.

## SVT's grain model has the defect NVEnc just fixed

SVT's synthesized grain reads lag-1 `0.397` and lag-2 `-0.089` against a source
of `0.809 / 0.441`. That is the whitened, over-fine signature of a residual fit
— and it is *worse* than NVEnc's own production residual fit, which measures
`0.564 / 0.003` on this title.

Its delivered texture looks respectable (lag-1 0.822) only because synthesis
supplies just `0.267` of a `0.731` total. Roughly two thirds of the grain SVT
plays is **real grain left in the base**, which has correct texture by
definition. The tell is lag-2: the delivered `0.529` overshoots the source's
`0.441` in the direction of codec ringing, matching the known plain-encode
signature.

SVT's table is also rate-independent. Synthesis measures `0.394 / -0.083` at
CRF 30, `0.394 / -0.083` at CRF 26 and `0.397 / -0.089` at CRF 25 — the
`--film-grain` level sets it and nothing else does. It is not measured from the
content.

Raising the level does not buy a way out:

| SVT arm | bytes | delivered amp | synth lag-1 | synth lag-2 |
| --- | ---: | ---: | ---: | ---: |
| fg12 CRF30 | 16,206,042 | 0.615 | 0.394 | -0.083 |
| fg25 CRF30 | 9,901,504 | 0.583 | 0.599 | 0.085 |
| fg40 CRF30 | 5,687,842 | — | — | — |

Level 25 improves synthesis texture and costs a third of the delivered energy;
level 40 collapses the file to 5.7 MB. There is no setting where SVT both
synthesizes correct grain and delivers it at strength.

## And SVT still wins every full-reference metric

Not by a little, and the plain control makes the point sharper than the FGS
comparison does:

| arm | bytes | VMAF |
| --- | ---: | ---: |
| SVT fg12 CRF25 | 32,044,274 | **92.200** |
| SVT fg12 CRF26 | 27,854,416 | 91.643 |
| **SVT plain CRF30, no grain model at all** | **20,691,034** | **90.376** |
| NVEnc bilateral+source-fit | 30,590,596 | 86.946 |

An SVT encode with no film-grain path whatsoever beats the NVEnc FGS candidate
by 3.4 VMAF at two thirds the size. That is not evidence about grain quality.
It is the retention bias measured directly: FR metrics rank grain *alignment*,
and every arm that keeps real grain outranks every arm that replaces it.

## What this changes

The 2026-07-16 conclusion — "it cannot reach SVT fidelity on heavy grain,
period" — was a VMAF verdict.

- **On VMAF it still holds.** SVT leads by 5.3 points at matched size.
- **On grain modelling it is now false.** NVEnc delivers 99.7% of source grain
  energy with synthesized texture at 0.735/0.288; SVT delivers 73% with
  synthesized texture at 0.397/-0.089. On the axis this project spent two weeks
  building instruments for, NVEnc is ahead, and SVT is roughly where NVEnc's
  production residual path is.

The honest summary is that the two encoders now occupy different points:
SVT keeps real grain and scores well on metrics that reward that; NVEnc
replaces grain with a measured model and scores badly on those metrics while
being the only one of the two whose *model* is close to the source.

Which is better is a perceptual question, and it is the same perceptual
question the source-fit review gate already exists to answer.

## Load-bearing caveat

**Taxi Driver is NVEnc's worst title for this comparison.** Bilateral barely
denoises coarse 35mm grain, so the candidate is 30,590,596 bytes against a
plain encode's 30,678,671 — a 0.3% saving where the six-film corpus average is
23%. On Casino the same arm runs 13.8 MB against a 24.4 MB plain encode.

This comparison therefore sits on the single title where NVEnc's bilateral arm
contributes almost no compression, which flatters SVT's bytes-per-quality
position. A corpus-wide rerun could move the size axis substantially. It would
not move the synthesis-texture rows, which are amplitude- and rate-independent.

Speed is also measured here at SVT preset 6; slower presets would narrow the
3x gap at further cost in wall time.
