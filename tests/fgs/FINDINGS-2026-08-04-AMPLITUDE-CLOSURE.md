# Per-luma and independent-chroma amplitude closure — 2026-08-04

> Quality-first research result. Nothing here was deployed. Production remains
> r4069 with bilateral separation, residual fitting, `modelsrc=off`, and the
> existing Tdarr route. Both encoder experiments are hidden environment-only
> paths, default off, and unavailable through the public CLI.

## Decision

Do not promote either amplitude closure.

- Per-luma luma closure reduces the six-film populated-band MAE, but moves the
  whole-title bias in the wrong direction and improves only one title
  materially.
- The independent U/V transfer fits the baseline multi-QVBR observations very
  well, but that fit does not survive emitted-table construction and played
  output. A dense exact audit shows U worse at title and luma-band level. V is
  effectively flat in absolute title error and worse by every other reported
  measure.
- Do not tune the constants on these six films. Errors change sign by title,
  plane and luma range; another corpus-derived scalar would only move the
  failure.

The source-fitted AR architecture remains the leading grain-*texture* result.
This is a rejection of two amplitude estimators, not of source fitting.

## Experiments

### Per-luma luma closure

The accepted source-fit path already estimates adjacent-frame source and
pre-encode base variance. The existing experimental closure pools that evidence
over the whole title window. `NVENC_FGS_TEST_LUMA_LEAK=local` instead applies
the same QVBR deadzone independently in each populated luma bin:

```text
pre_bin  = sqrt(V_base_bin / V_source_bin)
post_bin = max(0, pre_bin - theta_y(QVBR))
target_bin = V_source_bin * (1 - post_bin^2)
```

It does not change the separator, AR observations, model admission, base or
public defaults.

### Independent chroma amplitude

The chroma study first measured the exact same bilateral/source-static control
at QVBR 25, 29, 34 and 39. U and V received separate one-parameter deadzones;
no title multiplier was fitted:

```text
theta_U(q) = 0.0644564334 + 0.0057399549 q
theta_V(q) = 0.2772047404 + 0.0005557562 q
```

`NVENC_FGS_TEST_CHROMA_LEAK=independent` applies each transfer per source-luma
bin to that plane's adjacent-frame source/base variance. The temporal-static
selection remains luma-derived because the earlier plane-specific selector did
not improve absolute error. Chroma AR fitting continues to use the accepted
full spatial-flat population; strength observations and AR observations remain
separate.

The first hardware attempt mistakenly used deadzones fitted on the motion
separator. It failed and was discarded as a confounded transfer: the preserved
base variance is separator-specific. The final constants above come only from
the matching bilateral separator.

## Per-luma luma result

Six bilateral/source-static QVBR-29 clips compare the existing title-wide
closure with the local-bin experiment. `total` is played grain amplitude
against adjacent-frame source truth on the fixed production-static mask.

| title | title-wide | per-luma |
| --- | ---: | ---: |
| Casino | 0.9332 | 0.9304 |
| Interstellar | 1.0136 | **1.0095** |
| Scarface | 1.0023 | 1.0020 |
| Taxi Driver | 0.9872 | 0.9867 |
| The Deer Hunter | 0.9455 | 0.9443 |
| The Shining | 0.9830 | 0.9741 |

| scope | title-wide MAE / max | per-luma MAE / max |
| --- | ---: | ---: |
| six title aggregates | **0.02786 / 0.06684** | 0.02933 / 0.06958 |
| 24 populated luma bands | 0.05502 / 0.16152 | **0.04985 / 0.13028** |

The local calculation redistributes strength in a useful direction in some
bins, reducing band MAE by 9.4% and the worst band by 19.3%. It lowers every
title, drives the already-low corpus mean lower, and regresses all four titles
that were already below target. This is not closure: it
trades a smaller shape error for a larger systematic amplitude deficit.

All six streams pass complete `libdav1d -xerror` decoding. Encoded size and AR
texture are effectively unchanged, as expected for a strength-only film-grain
table change.

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-luma-local-20260804/
```

## Why the chroma fit looked ready offline

The multi-rate baseline study compares the predicted synthesis fraction with
post-encode temporal truth. The plane-specific one-parameter model generalises
well under leave-one-title-out testing:

| plane | model | ratio MAE | max ratio error | max absolute sigma error (8-bit) |
| --- | --- | ---: | ---: | ---: |
| U | pooled | 0.0060 | 0.0306 | 0.0309 |
| U | leave one title out | 0.0068 | 0.0351 | 0.0355 |
| V | pooled | 0.0211 | 0.1569 | 0.0155 |
| V | leave one title out | 0.0230 | 0.1646 | 0.0159 |

The large relative V tail is nearly grain-free content; its absolute error is
small. These figures answer a limited question: given measured pre- and
post-encode leak, what synthesis *target* follows? They do not prove that the
rolling, smoothed, point-reduced and quantised AV1 table delivers that target.

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-bilateral-qvbr-20260804/
/media/merged-storage/media/test-encodes/sourcefit-bilateral-chroma-qvbr-20260804/
```

## Dense exact played-output result

The final hardware A/B uses the same pinned binary and source-static bilateral
architecture at QVBR 29. Only independent chroma closure changes. Each control
and candidate stream was audited on 23 adjacent frame pairs rather than the
historical six or seven:

```text
10,22,34,...,250,262,274
```

`chroma_emission_audit.py` replays the exact normative AV1 chroma synthesis on
the selected clean pixels. Across 24 title/plane/arm reports it covers 633,232
blocks and 324,214,784 chroma pixels. The table model matches the stream in
every report, and the local replay matches dav1d with zero pixel mismatches.

The decision metric is played total against source temporal truth. Ratios and
absolute 8-bit sigma error are both mandatory because near-zero chroma grain
can produce an enormous ratio with negligible visible energy.

| plane / scope | control ratio MAE | candidate | control sigma MAE | candidate |
| --- | ---: | ---: | ---: | ---: |
| U, six titles | **0.02923** | 0.03723 | **0.03424** | 0.04772 |
| U, 27 luma bands | **0.08368** | 0.09564 | **0.08369** | 0.08621 |
| V, six titles | **0.07097** | 0.08372 | 0.02068 | **0.02055** |
| V, 27 luma bands | **0.24083** | 0.27576 | **0.05310** | 0.05609 |

V's `0.00013` title-level absolute improvement is not a usable win: its band
error worsens, its ratio error worsens, and the title changes have opposite
signs. U is unambiguously worse.

The title decomposition shows the trade rather than hiding it in a mean:

| title | U control -> candidate | V control -> candidate |
| --- | ---: | ---: |
| Casino | 0.961 -> 0.928 | 0.974 -> 0.923 |
| Interstellar | 0.973 -> 1.029 | **0.913 -> 0.998** |
| Scarface | 0.978 -> 0.985 | 1.055 -> **1.257** |
| Taxi Driver | 0.983 -> 0.940 | **1.097 -> 1.025** |
| The Deer Hunter | 0.984 -> 1.029 | 1.010 -> 1.055 |
| The Shining | **0.947 -> 0.981** | **1.150 -> 1.087** |

The estimator fixes Interstellar, Taxi and The Shining V while creating a much
larger Scarface V excess and smaller opposite regressions elsewhere. That is
exactly the pattern a fixed per-plane transfer must not ship.

The candidate totals 116,148,916 bytes against 116,156,604 for the exact
control (`-0.0066%`). There is no compression claim. All six candidate streams
pass complete `libdav1d -xerror` decoding.

Artifacts and machine-readable comparison:

```text
/media/merged-storage/media/test-encodes/sourcefit-chroma-control-static-20260804/
/media/merged-storage/media/test-encodes/sourcefit-chroma-independent-bilateral-20260804/
  emission-dense-comparison.json
  emission-dense-comparison.txt
```

## Measurement correction found during the audit

The old `temporal_grain_report.py` result was directionally negative too, but
its source-luma mask was not analyzer-exact. It decoded luma directly to gray,
which expands limited-range values, then selected flat blocks in that converted
domain. On Scarface frame 10 it selected 837 blocks instead of the exact 982.

Commit `50da8a40` now:

- extracts the stored Y/U/V plane before gray output conversion;
- measures in an explicit sample domain, defaulting to the 10-bit analyzer
  domain; and
- records that depth in JSON.

On the 23-pair Scarface V control/candidate, the corrected tool selects exactly
the same block counts as `chroma_emission_audit.py`. Its equal-frame aggregate
is `1.069 / 1.266`; the audit's block-variance-pooled aggregate is
`1.055 / 1.257`. The small remaining difference is the documented aggregation
choice, not a population or decoder discrepancy.

Historical reports produced before this fix remain internally paired, but
their absolute population is not production-exact and should be regenerated
before quoting thresholds. The six/seven-pair provisional audit also changed
direction on some summary rows when expanded to 23 pairs. Sparse frames remain
useful for diagnosis, not for an amplitude shipping verdict.

`chroma_amplitude_compare.py` makes the exact comparison reproducible. It
rejects any dav1d mismatch or table/stream mismatch, retains zero-target bands
for absolute-error reporting, and leaves their undefined ratios unset.

## Build and source isolation

The final chroma hardware A/B came from the retained pinned clone, not the live
tree:

```text
commit  7548182a364174a877d21557ee9410a932ca5493
binary  /home/bardie/.cache/fgs-gate/builds/
        pin-ed2829b39d519e2bfc163a5ce5334759c453348d-1785807218/
        build-gate-static/nvencc
SHA256  1d9f3471ca9935a5ca064e5ee2ad9e55597e10f628de8c2e3885a9f05cd1056c
```

The ordinary path does not enable either closure. The CPU solver and parser
tests pass, as do all 182 Python tests, with the test hooks present. Focused
tests additionally cover separate U/V constants, zero-target reporting and
native-plane extraction.

## What follows

1. Keep both closure hooks default-off and research-only. They are retained to
   reproduce the negative result, not as dormant production options.
2. Stop scalar deadzone tuning. The multi-QVBR fit's success at target
   prediction and failure at played delivery prove that another coefficient is
   not the missing architecture.
3. Keep evaluating bilateral/source-fit for texture quality. Its order-of-
   magnitude lag-1/lag-2 improvement is independent of these strength failures.
4. Use the prepared blind comparison to decide whether the remaining low-
   energy chroma errors are visible. If they are not, do not let dramatic
   near-zero ratios block the source-texture improvement.
5. If amplitude is perceptually blocking, a future proposal must jointly model
   observations and the realised AV1 curve response and must clear held-out
   full replay. The prior continuous-observation and sparse/Jacobian response
   gates already failed that requirement, so there is no currently validated
   runtime-normalisation design to implement.

Quality work should now return to the source-fit perceptual gate and admission,
not speed or another fixture-derived amplitude lever.
