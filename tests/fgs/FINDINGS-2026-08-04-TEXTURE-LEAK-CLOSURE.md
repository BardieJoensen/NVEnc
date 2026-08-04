# Source-fit texture needs covariance leak closure — 2026-08-04

> Quality-first offline result. Nothing here was deployed or encoded into the
> library. Production remains r4069 with bilateral separation, residual
> fitting and `modelsrc=off`.

## Decision

The difficult coarse-film result is **not an AV1 AR(3) format ceiling on this
corpus**. The source-fit architecture subtracts retained base grain from its
strength variance but still fits the AR model to the source's *total*
covariance. Playback then adds a full-source texture model on top of a base
that already contains highly correlated temporal texture.

For independent decoder synthesis, both variance and covariance add. The
missing synthesis target is:

```text
variance_synth   = variance_source_temporal - variance_base_temporal
covariance_synth = covariance_source_temporal - covariance_base_temporal
```

The existing strength closure implements the first line. This experiment
implements the second line offline. Across eight grain-positive films, every
covariance difference is positive, every AR system is positive definite, and
every fitted model has a legal AV1 int8 representation at coefficient shift 6
or 7.

The exact normative replay reduces mean played-texture error by **60.2%**. It
improves six titles clearly. Scarface and The Shining are already near the
measurement floor; their small movements are below the replay's finite-seed
uncertainty and are not counted as improvements.

This supports a test-only CUDA/solver prototype with strict fallback. It does
not support enabling `modelsrc`, changing Tdarr routing, or claiming chroma or
per-luma closure.

## Why the previous interpretation was incomplete

Coming to America looked like a compact-model failure:

| layer | lag-1 | lag-2 |
| --- | ---: | ---: |
| source temporal truth | 0.625 | 0.226 |
| temporal texture left in base | 0.928 | 0.795 |
| current decoded synthesis | 0.661 | 0.297 |
| current played total | 0.693 | 0.358 |

The base carries 34.3% of source temporal amplitude (11.8% of its variance),
but that residue is much smoother than the source grain. Adding a
source-shaped synthesis layer therefore pushes played correlation upward even
when played energy is close.
The required independent synthesis target is `0.585/0.151`, not
`0.625/0.226`.

A legal quantized AR model implies `0.584/0.158`. After the real scaling LUT,
overlap, rounding and clipping it delivers `0.569/0.136`; mixed with the
measured base at the exact missing variance, played total becomes
`0.611/0.213`. Axis MAE falls from `0.1002` to `0.0134`.

The remaining under-correlation is a finite-template/pixel-response problem,
not evidence that the AV1 syntax cannot express the covariance target.

## Frozen protocol and integrity

The single-title oracle, unit tests and eight-film corpus were committed and
pushed before the full corpus run:

```text
bfc58fd5  tests(fgs): preregister texture leak oracle
1518e280  tests(fgs): isolate report decoder stdin
```

The exact normative extension and 16-seed protocol were likewise committed
before that pass:

```text
1fe227eb  tests(fgs): add exact texture leak replay
```

Inputs and controls:

- six architecture films plus held-out fine Ju-on and coarse Coming to
  America;
- frames `10,58,106,154,202,250`;
- production flat selection followed by the established `0.8..1.3`
  temporal-static ratio;
- the unchanged bilateral/source-static encoded bases and tables;
- 16 paired deterministic seeds for the current and oracle tables; and
- libaom's normative `gaussian_sequence`, source SHA-256
  `8aec1ca1fae39bf32dd2c63f08bc0a260e333bfcea796c539fd8240796ac5f74`.

Every film-grain table matches the corresponding AV1 bitstream model exactly.
The 195-test Python suite passes. The ordinary solver ridge is `1e-6` of the
mean diagonal on all eight titles; the smallest unregularized covariance
eigenvalue is still positive at `0.0050` of the mean diagonal. No PSD repair,
coefficient clamp or residual fallback is hidden in the result.

Artifacts:

```text
/media/merged-storage/media/test-encodes/
  sourcefit-texture-leak-oracle-20260804/
```

## Exact played-texture result

Error is mean absolute error over horizontal/vertical lag-1/lag-2. The
`current replay` column compares a 16-seed exact replay of the existing table
with its one-seed decoded synthesis and therefore estimates the finite-seed
floor for each title.

| title | current played error | exact covariance-oracle played error | current replay floor | movement |
| --- | ---: | ---: | ---: | --- |
| Casino | 0.0629 | **0.0385** | 0.0070 | improve |
| Coming to America | 0.1002 | **0.0134** | 0.0053 | improve |
| Interstellar | 0.0621 | **0.0218** | 0.0080 | improve |
| Ju-on | 0.0240 | **0.0092** | 0.0085 | improve |
| Scarface | **0.0103** | 0.0115 | 0.0061 | inconclusive / floor |
| Taxi Driver | 0.0546 | **0.0213** | 0.0113 | improve |
| The Deer Hunter | 0.0449 | **0.0145** | 0.0047 | improve |
| The Shining | **0.0137** | 0.0183 | 0.0074 | inconclusive / floor |
| **macro mean** | **0.04659** | **0.01855** | **0.00729** | **-60.2%** |

By the preregistered descriptive scale labels:

| grain group | titles | current mean | exact oracle mean |
| --- | ---: | ---: | ---: |
| coarse | 5 | 0.0587 | **0.0227** |
| fine | 2 | 0.0171 | **0.0103** |
| mixed | 1 | 0.0449 | **0.0145** |

The fine controls matter. Scarface stays at its existing floor, while Ju-on
improves. Covariance subtraction is not a global correlation reduction and
does not erase the analyzer's fine/coarse distinction.

## Per-title texture targets

These are pooled, detrended source-static blocks. The exact replay is lower
than the raw quantized-model prediction because luma-varying scaling, finite
templates, overlap and legal-range clipping affect normalized texture too.

| title | source truth | missing synthesis target | current decoded synth | exact oracle synth |
| --- | ---: | ---: | ---: | ---: |
| Casino | 0.748 / 0.319 | 0.712 / 0.221 | 0.741 / 0.323 | 0.683 / 0.157 |
| Coming to America | 0.625 / 0.226 | 0.585 / 0.151 | 0.661 / 0.297 | 0.569 / 0.136 |
| Interstellar | 0.758 / 0.438 | 0.687 / 0.276 | 0.748 / 0.396 | 0.665 / 0.238 |
| Ju-on | 0.358 / -0.067 | 0.319 / -0.125 | 0.347 / -0.095 | 0.309 / -0.134 |
| Scarface | 0.287 / -0.002 | 0.277 / -0.015 | 0.286 / -0.012 | 0.269 / -0.030 |
| Taxi Driver | 0.800 / 0.420 | 0.759 / 0.310 | 0.792 / 0.428 | 0.740 / 0.290 |
| The Deer Hunter | 0.512 / 0.014 | 0.452 / -0.090 | 0.490 / -0.017 | 0.432 / -0.100 |
| The Shining | 0.669 / 0.228 | 0.647 / 0.174 | 0.653 / 0.195 | 0.631 / 0.151 |

Deer Hunter's negative lag-2 target is a particularly useful control. The
oracle preserves its sign and magnitude rather than merely turning down a
coarseness scalar.

## What this proves, and what it does not

Supported:

- the base and source model must be composed in covariance, not only energy;
- the current architecture systematically double-counts the smooth texture
  left in the base;
- AV1's quantized AR(3) model represents the missing luma covariance on all
  eight tested films, including Taxi Driver and Coming to America; and
- covariance subtraction is much safer than a fixture-derived correlation
  clamp because its target follows each title and preserves fine controls.

Not supported:

- that every possible coarse stock is AV1-representable;
- that the raw covariance fit is already optimal after normative pixel
  response;
- chroma closure (this experiment is luma only);
- per-luma amplitude closure;
- semantic/stochastic admission; or
- a production default change.

The shadow-admission correction still applies: origin labels are not quality
labels. Covariance validity, solver coverage and fallback are output-safety
questions; they do not decide whether arbitrary persistent structure should
be synthesized.

## Recommended next code sequence

1. **Close the normative response offline.** The raw quantized AR fit predicts
   macro played error `0.00755`, while exact pixels deliver `0.01855` and tend
   slightly under the requested covariance. Test a deterministic response
   correction against the exact replay. It must preserve Scarface and The
   Shining rather than trading coarse gains for fine regressions.
2. **Then add a test-only luma covariance path.** Accumulate temporal source
   and base AR normal equations on the existing static mask, subtract them
   over the same rolling window, reject non-positive/ill-conditioned systems,
   and retain the current residual fallback. Keep it behind an environment
   hook and default off.
3. **Re-run the synthetic KAT and eight-film gate.** Require unchanged base
   pixels/bytes within encoder noise, full dav1d decoding, amplitude closure,
   per-luma reporting and exact texture replay.
4. **Keep chroma independent.** U/V need their own static population and
   covariance evidence; luma success is not permission to reuse its mask or
   multiplier.
5. **Blind playback remains the release gate.** Review coarse scale, bright
   flat regions and chroma crawl before considering `modelsrc=on`.

Compression and speed remain secondary. This result identifies a real quality
layer that was missing from the two-operator architecture.
