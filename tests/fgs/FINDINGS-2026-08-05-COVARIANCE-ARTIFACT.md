# Covariance closure is what stops the analyser fitting codec artifact — 2026-08-05

> Offline measurement only. No `NVEncCore/` change, nothing deployed,
> `modelsrc` default-off, Tdarr untouched.

Executes the protocol frozen in `PLAN-2026-08-05-COVARIANCE-ARTIFACT.md`
(commit `24cb2071`), written before any number below was measured.

## Result: the hypothesis is supported

`FINDINGS-2026-08-05-NEGATIVE-SPECIMEN.md` raised and declined to claim that
the covariance closure may discount codec artifact structurally, because
artifact lives largely in the encoded base whose covariance the closure
subtracts. It does.

| frozen prediction | held |
| --- | ---: |
| `synth_to_c`: A0 < A1 <= A2 (further from artifact) | 5/6 |
| `synth_to_o`: A0 > A1 >= A2 (closer to real grain) | 5/6 |
| **A0 to A2 movement, both axes** | **6/6** |

The single miss is Tuner at 2000k, where A1 and A2 tie to `0.0003` on both
axes — not a reversal. The A0-to-A2 direction is unanimous.

## The measurement

`O` is a lossless 288-frame clip from a 1080p AVC remux in `long-term-seeding`;
`C` is an x264 encode of it at the frozen rates. Arms differ only in closure
strength. All layers sit on one `O`-derived mask.

| cell | A0→O | A1→O | A2→O | A0→C | A1→C | A2→C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train to Busan 5000k | 0.2184 | 0.1004 | **0.0893** | **0.0468** | 0.1648 | 0.1759 |
| Train to Busan 2000k | 0.3101 | 0.1833 | **0.1483** | **0.1276** | 0.2544 | 0.2894 |
| Tuner 5000k | 0.1569 | 0.0358 | **0.0163** | **0.1136** | 0.2348 | 0.2543 |
| Tuner 2000k | 0.3421 | 0.1565 | 0.1568 | **0.0776** | 0.2632 | 0.2629 |
| Quiz Show 5000k | 0.2437 | 0.1024 | **0.0950** | **0.0584** | 0.0829 | 0.0902 |
| Quiz Show 2000k | 0.2010 | 0.0614 | **0.0475** | **0.1067** | 0.2463 | 0.2601 |

## What this actually says

**Without covariance closure, the source fit synthesizes codec artifact — on
6 of 6 cells.** A0's synthesis is closer to `C`'s x264 texture than to `O`'s
real grain in every title at every rate. On Train to Busan at 5000k it is
4.7x closer to the artifact (`0.047` against `0.218`).

**With full closure that inverts on 5 of 6.** A2 resembles the original's grain
rather than the artifact; only Quiz Show at 5000k stays marginally
artifact-side (`0.0950` to grain against `0.0902` to artifact), effectively a
tie.

The played result against the original improves on 6/6:

| cell | played axis error to `O`, A0 → A2 |
| --- | --- |
| Train to Busan 5000k | 0.2539 → 0.1502 (−40.8%) |
| Train to Busan 2000k | 0.3543 → 0.2490 (−29.7%) |
| Tuner 5000k | 0.2400 → 0.1735 (−27.7%) |
| Tuner 2000k | 0.4097 → 0.3306 (−19.3%) |
| Quiz Show 5000k | 0.2667 → 0.1340 (−49.7%) |
| Quiz Show 2000k | 0.3091 → 0.1171 (−62.1%) |

The artifact also behaves as expected with rate, which validates the
construction: `C`'s texture grows more correlated as bitrate falls — Train to
Busan h1 `0.484` → `0.613`, Tuner `0.682` → `0.798` — while `O`'s grain is
fixed at `0.253` and `0.443`.

## This corrects yesterday's conclusion

`FINDINGS-2026-08-05-NEGATIVE-SPECIMEN.md` concluded that "the architecture is
safer on recompressed input than feared". That is true of the configuration it
tested and **misattributed**. Every arm in that run used
`NVENC_FGS_TEST_TEXTURE_LEAK=response` — the protected configuration. The
safety came from one specific mechanism, not from the architecture as a whole.
Run with source fitting alone, the same pipeline fits the artifact on every
cell measured here.

The covariance closure was built and justified as a *texture-accuracy* result
(`FINDINGS-2026-08-04-TEXTURE-LEAK-CLOSURE.md`, −76.6% played-texture error).
This is a second, independent reason to keep it, and one nobody was looking
for: it is also what keeps the analyser off codec structure.

## The negative the project has been missing

`FINDINGS-2026-08-04-SHADOW-ADMISSION.md` closed by asking for a
quality-labelled negative — "an interval where source fitting demonstrably
synthesizes persistent picture/codec structure that temporal truth says is not
noise". **A0 on x264 input is that specimen**, with ground truth, on six cells
across three titles and two rates.

It is not the shipping configuration, which weakens it as an admission gate
test: a gate is meant to reject harmful *inputs*, and this is a harmful
*setting*. But it is the first configuration in this project demonstrated to
fit non-grain structure against a known original, and it can serve as the
labelled negative any future admission rule must reject.

## Limitation, stated plainly

**There is no plain-encode arm in this experiment.** The comparison is between
closure strengths, so it establishes that A0 fits the artifact and that A2 is
closer to the original — not that A0 is worse than not running FGS at all.
Calling A0 harmful in the absolute sense requires that control, and it is the
obvious next measurement.

Also: three titles, two rates, one preset, luma only, and `C` is x264 rather
than a real distributor encode. The retained Tuner AMZN WEB-DL was used to
calibrate the rate but is 1920x1040 letterbox-cropped, so it cannot pixel-align
with its 1080-line remux and was not used as a specimen.

## Integrity

- 18 AV1 streams, all passing complete `libdav1d -xerror` decoding;
- frame counts equal across arms in every cell;
- the runner aborts if the encoder logs `ignoring`, so each arm's hooks are
  confirmed active;
- `artifact_axis()` mirrors `temporal_grain_report`'s mask construction exactly
  — production flat blocks from the source, the `0.8..1.3` static subset, then
  `(n − n+1)/sqrt(2)` — because the tool forces `libdav1d` for arms and an
  H.264 `C` cannot be passed as one;
- `C` built with the system ffmpeg, since the CUDA/dav1d build carries no
  libx264; measurement still runs through the CUDA build.

Artifacts: `/tmp/downloads/fgs-covariance-20260805/`.
