# Fixed-energy fine-versus-coarse grain replay, 2026-08-03

> Metric-sensitivity experiment only. Nothing here was deployed to Tdarr.
> Production remains r4069 with bilateral separation and residual-fitted
> grain; `modelsrc` remains default-off.

## Question

The bilateral/source-fit quality run changed both grain energy and spatial
texture. On The Shining its grain-disabled production and candidate bases are
decoded-pixel identical, yet enabling production grain changes VMAF by only
`-0.245` while source-fitted grain changes it by `-3.011`. The audit could not
tell how much of that gap came from the candidate's stronger delivery and how
much came from its coarser, source-like AR model.

`amplitude_matched_texture.py` removes that ambiguity. It replays the two luma
AR models at matched decoded energy on one common base, then repeats at two
amplitude levels.

## Isolation

Both levels use:

- the same 288-frame, lossless 1920x1080 10-bit Shining base;
- the same pinned NVEncC binary and QVBR-29/P4 encode settings;
- the production and source-fit models covering the same source time, 6.0 s;
- one static table interval, one flat luma curve and no chroma synthesis;
- the same table seed and the same emitted AV1 seed on all 288 frames; and
- complete software decode with `libdav1d -xerror`.

The decoded grain-off stream is byte-identical between arms:

```text
SHA-256 edbb9a7df52bfebe24b5702083c72ae6088ae6190b1b3cd0cf242fbbe9ee4de6
```

The encoded arms are also exactly the same size at each level (`2,203,369`
bytes). Every non-grain-scale parameter, luma point location, timeline and
range flag is identical. Chroma scaling is empty in both. The active luma AR
model and the scalar needed to match its realised energy are the treatment.

This is intentionally not a perceptual-quality comparison. It is a controlled
test of how the metrics respond to grain scale.

## The treatment is large and the amplitude match is tight

Decoded luma texture:

| model | lag-1 | lag-2 | high-frequency spectral fraction |
| --- | ---: | ---: | ---: |
| production residual fit, fine | 0.465 | -0.094 | 0.1285 |
| bilateral source fit, coarse | 0.689 | 0.285 | 0.0623--0.0602 |

The coarse model moves energy toward lower spatial frequencies and removes the
production model's negative lag-2. This is the intended architectural change,
not a marginal coefficient perturbation.

The two matched levels are:

| level | fine sigma | coarse sigma | coarse / fine |
| --- | ---: | ---: | ---: |
| production-like | 0.7953 | 0.7989 | 1.0045 |
| candidate-like | 1.0906 | 1.0866 | 0.9963 |

The first differs by `+0.45%`; the second by `-0.37%`. At the higher level,
PSNR-Y actually moves `+0.012 dB` for coarse versus fine, consistent with the
coarse arm carrying fractionally *less* energy. An energy excess cannot explain
the VMAF result below.

## Result: VMAF prefers fine grain at fixed energy

Coarse minus fine, higher is better:

| reference / level | VMAF | VMAF NEG | VMAF p1 | PSNR-Y | SSIM |
| --- | ---: | ---: | ---: | ---: | ---: |
| source, production-like | **-0.838** | -1.015 | -0.797 | -0.011 | -0.001772 |
| common clean base, production-like | **-0.796** | -1.224 | -1.635 | -0.035 | -0.001805 |
| source, candidate-like | **-1.475** | -1.764 | -1.426 | +0.012 | -0.003248 |
| common clean base, candidate-like | **-1.358** | -2.070 | -2.717 | +0.036 | -0.003314 |

The answer is unambiguous: **VMAF's multiscale features penalise the coarser
source-fit model more heavily even when luma energy, base pixels and seed are
controlled.** The effect grows with grain strength, from about `0.8` VMAF at
the production-like level to `1.4--1.5` at the candidate-like level.

Scoring against the source and against the common clean base gives nearly the
same texture penalty. It is therefore not an accident of the source reference's
particular grain realisation.

This closes the open statement in `TESTING-SUITE.md`. VMAF is biased toward
finer grain at equal total energy. It remains useful as a base-fidelity guard
rail and must not be used to choose an AV1 grain texture model.

## Factorial decomposition

The two levels form a small 2x2 control:

| texture / amplitude | source VMAF | common-base VMAF |
| --- | ---: | ---: |
| fine / low | 91.043 | 98.768 |
| coarse / low | 90.205 | 97.972 |
| fine / high | 90.840 | 98.412 |
| coarse / high | 89.365 | 97.053 |

Against the source:

- raising amplitude while texture stays fine costs `0.203` VMAF;
- changing texture at low amplitude costs `0.838`;
- changing texture at high amplitude costs `1.475`; and
- the production-like fine/low to candidate-like coarse/high movement costs
  `1.678` VMAF (`1.715` against the common base).

The actual dynamic Shining streams differ by `-2.766` VMAF (`92.474` to
`89.708`) on a bit-identical base. This static, luma-only factorial explains
roughly 61% of that gap. It does **not** explain the remaining `~1.1` points.
Likely remaining variables are the rolling AR sequence and per-luma strength
shape; the replay deliberately removed both. Chroma cannot explain luma-only
VMAF.

Do not turn the unexplained remainder into a quality claim. It is a metric
accounting question, not evidence that source-like texture looks worse.

## Decision

1. The large finished-frame VMAF loss is not a blocker for source fitting.
   A material part is now proven to be a scale bias in the metric itself.
2. The result does not prove the coarse arm looks better. Lag closure says it
   is statistically closer to source; blinded playback still decides whether
   that improvement is perceptually clean.
3. Keep judging the architecture with base fidelity, per-plane energy closure,
   lag-1/lag-2 and playback. Keep VMAF on the grain-disabled base as a guard
   rail.
4. Do not spend another review cycle trying to make finished-frame VMAF endorse
   correct grain. It is structurally the wrong objective.

## Reproduction and artifacts

Harness commit: `aff2a6c9`.

```text
python3 tests/fgs/amplitude_matched_texture.py \
  --nvencc /home/bardie/.cache/fgs-gate/builds/pin-603c2eea-1785764448/build-gate/nvencc \
  --coarse-scale 94

python3 tests/fgs/amplitude_matched_texture.py \
  --nvencc /home/bardie/.cache/fgs-gate/builds/pin-603c2eea-1785764448/build-gate/nvencc \
  --fine-scale 44 --coarse-scale 128 \
  --work /media/merged-storage/media/test-encodes/sourcefit-amplitude-match-20260803/high
```

Reports and retained media:

```text
/media/merged-storage/media/test-encodes/sourcefit-amplitude-match-20260803/report.json
/media/merged-storage/media/test-encodes/sourcefit-amplitude-match-20260803/high/report.json
```
