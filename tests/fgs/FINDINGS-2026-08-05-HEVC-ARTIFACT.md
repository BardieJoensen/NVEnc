# HEVC artifact, a retracted negative, and a sampling limit — 2026-08-05

> Offline measurement only. No `NVEncCore/` change, nothing deployed,
> `modelsrc` default-off, Tdarr untouched.

Extends `FINDINGS-2026-08-05-COVARIANCE-ARTIFACT.md` to HEVC, because 4K library
sources are HEVC and the x264 result cannot be assumed to carry over.

## What "HEVC is tested" did and did not mean

The six-film 4K corpus *is* HEVC PQ remuxes, but every clip used throughout the
project is a lossless `ffvhuff`/`ffv1` extraction of one. The analyser therefore
sees the remux's exact pixels: **HEVC content has always been covered.** What
was never covered is **HEVC artifact at delivery rates** — remuxes are
near-lossless (Taxi ~76 Mbit/s) and carry almost none.

Same construction as the x264 run, with `C` produced by x265 at 15000k and
6000k, 10-bit, on Taxi Driver and Interstellar.

## HEVC artifact mimics film grain far more closely than x264's

| cell | `O` grain h1/h2 | `C` artifact h1/h2 |
| --- | ---: | ---: |
| Taxi Driver 15000k | 0.807 / 0.439 | 0.860 / 0.564 |
| Taxi Driver 6000k | 0.807 / 0.439 | 0.872 / 0.613 |
| Interstellar 15000k | 0.803 / 0.514 | 0.911 / 0.751 |
| Interstellar 6000k | 0.803 / 0.514 | 0.890 / 0.773 |

The h1 axis is within `0.05`--`0.11` of the real grain. On x264 the same axis
sat much further away. That similarity is the whole story of what follows.

## Without covariance closure the fit locks onto the artifact, 4/4

| cell | A0 synth → `O` grain | A0 synth → `C` artifact |
| --- | ---: | ---: |
| Taxi Driver 15000k | 0.0999 | **0.0119** |
| Taxi Driver 6000k | 0.1494 | **0.0269** |
| Interstellar 15000k | 0.1779 | **0.0278** |
| Interstellar 6000k | 0.2433 | **0.0149** |

4x to 16x closer to HEVC ringing than to the grain it is supposed to model.
This is the pooled texture statistic, not a per-frame mean, so it is not a
sampling artifact — see the methodological note below for why that distinction
matters here.

`A1` and `A2` beat a plain encode on **4/4** HEVC cells, as they did on 6/6
x264 cells.

## A retracted claim, and why it was wrong twice

On the frozen six-frame set, `A0` measured worse than plain on Taxi Driver
6000k and Interstellar 6000k, and this document's first draft reported that as
the quality-labelled negative the project has been looking for since
`FINDINGS-2026-08-04-SHADOW-ADMISSION.md`.

Densifying Taxi Driver 6000k from 6 to 16 frame pairs reverses it:

| | 6 frame pairs | 16 frame pairs |
| --- | ---: | ---: |
| `A0` worse than plain | 2/6 | **2/16** |
| mean `A0` − plain | +0.0087 | **−0.0113** |
| median | — | **−0.0183** |

`A0` is *better* than plain on average. The apparent harm was entirely which
six frames were sampled.

Interstellar 6000k was densified too rather than assumed, and reverses
identically:

| | 6 frame pairs | 16 frame pairs |
| --- | ---: | ---: |
| `A0` worse than plain | 2/6 | **2/16** |
| mean `A0` − plain | +0.0084 | **-0.0114** |
| median | — | **-0.0335** |

Both cells that looked harmful on the sparse set reverse on the dense one, by
the same margin and the same 2-of-16 frame count.

**No harmful configuration has been demonstrated**, across 6 x264 cells and 4
HEVC cells. That is now the third time in this project that a negative appeared
and dissolved on inspection.

## Methodological limit worth recording

The two over-claims share a cause, and it constrains how every future arm
comparison should be read:

- **Texture axis distances pool blocks across all frames.** `synth_to_o` and
  `synth_to_c` are stable at six frames and support causal statements.
- **Played-error means average six per-frame MAEs.** At six frames their
  sampling sd (`0.031` on this cell) exceeds the effect being claimed
  (`0.011`).

The repo's standing six-frame set is adequate for the texture work it was
designed for and **too sparse for arm-versus-arm played-error comparisons**.
Any such comparison needs a denser frame set, and a 4K three-arm report at 23
pairs exhausts memory, so it must be run as pairs.

## What stands

- HEVC artifact is the harder input, because it resembles grain more closely;
- the unprotected source fit reproduces it almost exactly, 4/4;
- covariance closure moves synthesis from artifact toward real grain on 6/6
  x264 and 4/4 HEVC cells, and every closed arm beats plain on all 10;
- but "fits the artifact" still does not equal "does harm", and no input has
  yet been shown to be made worse by synthesis.

## Artifacts

```text
/tmp/downloads/fgs-covariance-20260805/
  covariance-plain_hevc.json
  Taxi_Driver-6000k_hevc/report-dense2.json     16-pair retraction evidence
```
