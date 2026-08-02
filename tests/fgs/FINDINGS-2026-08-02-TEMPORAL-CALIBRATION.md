# Temporal-lag calibration and real-film rerun, 2026-08-02

Nothing in this run was deployed.  It changes a test instrument and the
interpretation of existing review clips only.  `modelsrc` remains default-off
and the motion separator remains outside production.

## Question

The first `temporal_drag.py` fitted only the previous-frame direction:

```text
err_n  = base_n - src_n
prev_n = src_(n-1) - src_n
beta   = sum(err * prev) / sum(prev * prev)
```

For a known previous-frame blend, `beta` equals the blend weight.  The reverse
claim was false: a spatial blur on a translating edge also projects onto
`prev`, despite never reading another frame.  That made `beta` a useful arm
separator but not a calibrated temporal-drag detector.

The replacement jointly fits both directions:

```text
err_n = b_prev * (src_(n-1) - src_n)
      + b_next * (src_(n+1) - src_n)
      + residual

lag_asymmetry = b_prev - b_next
```

A previous-frame carry-over loads `b_prev`.  A centred spatial or temporal
blur on a constant-velocity feature loads both directions.  As before, all
fields are averaged into 8x8 boxes first so removal of independent grain does
not manufacture a correlation.

## Labelled controls

`tests/fgs/test_temporal_drag.py` contains the controls and runs entirely from
generated arrays.  No codec or fixture naming is involved.

| control | old previous-only beta | joint previous | joint next | asymmetry |
| --- | ---: | ---: | ---: | ---: |
| unchanged | 0.000 | 0.000 | 0.000 | 0.000 |
| exact 15% previous blend | 0.150 | 0.150 | 0.000 | 0.150 |
| centred 10% previous + 10% next | 0.151 | 0.100 | 0.100 | 0.000 |
| translated edge, spatial horizontal blur only | **0.240** | 0.539 | 0.541 | **-0.002** |

The last row is the labelled negative that invalidated the old interpretation.
The joint fit rejects it while preserving the exact positive controls.  The
suite also includes unchanged content and an exposure/flicker-lag positive.
The latter deliberately demonstrates the remaining semantic limit: the score
detects directional temporal state, not ghosting by name.

Frame-count and relative packet-PTS checks run before file-backed measurement.
The scorer refuses a short, repeated, dropped or shifted paired stream rather
than letting misalignment masquerade as lag.  The endpoints are not evaluated
because the joint model needs both neighbours: 288 input frames produce 286
observations.

## Existing real-film corpus, rerun with the corrected statistic

The exact blinded clips and arm mapping from
`FINDINGS-2026-08-02-MOTION-REVIEW.md` were reused.  Each reference and arm is
a lossless 1920x1080 centre crop with an exact relative timeline.  `A` is
motion for The Shining and Scarface; `B` is motion for The Deer Hunter.

Base results:

| title | separator | joint previous | joint next | asymmetry | asymmetry, >64-motion bin |
| --- | --- | ---: | ---: | ---: | ---: |
| The Shining | motion | 0.14020 | -0.00048 | **0.14068** | 0.13999 |
| The Shining | bilateral | 0.00148 | 0.00133 | **0.00015** | 0.00015 |
| The Deer Hunter | bilateral | 0.00838 | 0.00801 | **0.00036** | 0.00048 |
| The Deer Hunter | motion | 0.14964 | 0.01793 | **0.13172** | 0.12668 |
| Scarface | motion | 0.17423 | 0.05604 | **0.11819** | 0.12108 |
| Scarface | bilateral | 0.02793 | 0.02782 | **0.00010** | -0.00012 |

The bilateral arms sometimes have a non-zero spatial/symmetric component, most
clearly Scarface at about 0.028 in both directions.  Subtracting the directions
removes it.  Every motion arm instead has a large one-sided previous component.
The nearest observed base pair is separated by more than 300x in absolute lag
asymmetry, without choosing a decision threshold from the films.

Finished results show that normative grain synthesis does not hide the signal:

| title | motion asymmetry | bilateral asymmetry |
| --- | ---: | ---: |
| The Shining | 0.14079 | 0.00027 |
| The Deer Hunter | 0.12938 | -0.00055 |
| Scarface | 0.11816 | 0.00013 |

The JSON artifacts are in:

```text
/media/merged-storage/media/test-encodes/review-vmaf-20260802/
  temporal-v2-<title>-<arm>-{base,finished}.json
```

## Finding

The old positive `beta` result was partly ambiguous; the corrected result is
not explained by the tested symmetric spatial-blur mechanism.  On all three
films, the motion separator's base contains a strong directional temporal
component consistent with prior-frame carry-over, while bilateral is symmetric
to within 0.0006 before and after synthesis.

This strengthens the decision to keep motion out of production.  It does not
convert 0.12--0.14 into a visible blend percentage: real processing is not the
single-term model used by the positive fixture, and exposure/state lag also
triggers the statistic.  It also does not replace playback review.  The safe
uses are:

- screen separator changes for temporal regressions;
- sweep motion confidence or disocclusion fallback against asymmetry, bytes
  and the Butteraugli tail together;
- require a known-good bilateral control and a labelled negative in regression
  runs.

Do not set a production threshold from these three films.  First accumulate a
larger real-film bilateral baseline, including cadence changes, dissolves,
flicker and camera flashes; those are the likely non-ghosting tails.

## Verification

```text
python3 -m unittest tests/fgs/test_temporal_drag.py   # 5/5
python3 -m unittest discover -s tests/fgs -p 'test_*.py'  # 61/61
python3 -m py_compile tests/fgs/temporal_drag.py
git diff --check
```
