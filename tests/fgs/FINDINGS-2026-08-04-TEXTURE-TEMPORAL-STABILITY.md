# Guarded texture response at model-update frames

Date: 2026-08-04 UTC  
Branch: `fgs/test-automation`  
Authority: research only; no production or routing authority

## Question

The guarded response selector improves mean decoded luma texture on twelve film
scenes, but a good whole-scene mean can hide a visibly unstable model.  This
check asks whether the candidate develops large texture errors or abrupt error
spikes when the encoder emits a new film-grain table.

It does **not** test strength closure, chroma amplitude, semantic admission, or
subjective flicker.  Those remain separate gates.

## Frozen inputs and method

The check used the four genuinely unseen 288-frame film-positive scenes from
the response-selector validation:

- Quiz Show 31%;
- Life of Brian 31%;
- Drunken Master 31%;
- Jerry Maguire 31%.

All outputs came from the same pinned `40b987ff` binary documented in
`FINDINGS-2026-08-04-TEXTURE-RESPONSE-SELECTOR.md`.  The three arms were the
existing same-build static source fit, dynamic covariance, and guarded
response encodes.  Nothing was re-encoded or retuned for this check.

Frames were predeclared from the guarded candidate's emitted-table updates.
Every requested frame retained at least eight production-selected flat/static
source blocks, so no frame was discarded after measurement.  For each frame
`n`, `temporal_grain_report.py` measured

```text
(frame[n] - frame[n + 1]) / sqrt(2)
```

on the same source-derived blocks and reported the mean absolute error across
decoded-total `h1`, `h2`, `v1`, and `v2` relative to source temporal truth.
Commit `6224a670` added the per-frame distribution without changing the
existing aggregate calculation.

Reports:

```text
/media/merged-storage/media/test-encodes/
    sourcefit-texture-response-margin-newfilms-20260804/
        */temporal-update-stability.json
```

## Per-scene result

Each cell is `mean / p95 / maximum` per-frame luma-axis error.  Lower is
better.

| unseen scene | static source fit | dynamic covariance | guarded response |
| --- | ---: | ---: | ---: |
| Quiz Show | 0.0636 / 0.2068 / 0.2241 | 0.0298 / 0.0552 / 0.0658 | **0.0237 / 0.0418 / 0.0432** |
| Life of Brian | 0.0524 / 0.0932 / 0.1011 | 0.0266 / 0.0483 / 0.0610 | **0.0187 / 0.0300 / 0.0340** |
| Drunken Master | 0.0214 / 0.0325 / 0.0325 | 0.0168 / **0.0266 / 0.0276** | **0.0156** / 0.0267 / 0.0277 |
| Jerry Maguire | 0.0353 / 0.0742 / 0.0933 | 0.0271 / 0.0525 / 0.0539 | **0.0246 / 0.0432 / 0.0443** |

Guarded response has the lowest mean, p95, and maximum on three scenes.  On
Drunken Master it has the lowest mean while dynamic wins p95 and maximum by
only `0.0001`.  Most importantly, guarded response improves all three
distribution statistics over static source fit on all four scenes.

Pooling all 58 predeclared frame pairs:

| arm | mean | standard deviation | median | p95 | maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| static source fit | 0.0441 | 0.0399 | 0.0310 | 0.1011 | 0.2241 |
| dynamic covariance | 0.0256 | 0.0142 | 0.0205 | 0.0522 | 0.0658 |
| **guarded response** | **0.0211** | **0.0106** | **0.0187** | **0.0413** | **0.0443** |

The guarded candidate therefore improves the tail as well as the mean.  The
result is not a mean-versus-flicker trade.

## Closely spaced updates

Quiz Show contains consecutive update pairs at 27/28 and 109/110.  Guarded
errors were `0.0408 -> 0.0303` and `0.0413 -> 0.0364`.  Jerry Maguire contains
196/197 and a reset sequence at 218/219/220; guarded errors were
`0.0398 -> 0.0320` and `0.0205 -> 0.0271 -> 0.0138`.

The largest adjacent change in these deliberately inspected clusters is
`0.0133`.  Jerry's emitted response weight changes from zero to `0.75` at
frame 197 and from zero to `0.85` after the 218/219 resets at frame 220, yet
neither transition creates a measured tail spike.  Quiz's inspected reset
clusters stay at weight zero and consequently bound the selector's fail-closed
path rather than a non-zero transition.

This is evidence against objective update pumping in the sampled windows.  It
is not a substitute for later continuous playback review: random synthesis can
look objectionable in motion without exceeding an ACF error threshold.

## Decision

The temporal/update gate passes for continued default-off development.  Freeze
the current guarded **luma texture** path while the independent amplitude
layers are investigated; do not retune the `0.01` selector margin on these
twelve scenes.

This does not make the candidate production-ready.  Remaining blockers are:

1. per-luma luma-strength closure;
2. an independent real-film chroma-amplitude estimator, especially for V;
3. semantic film-grain admission;
4. QVBR generalisation of the exploratory confidence margin;
5. final base-fidelity/conventional metrics and perceptual playback review.

No Tdarr configuration or production binary was changed.
