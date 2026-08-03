# Continuous strength-observation gate, 2026-08-03

> Offline research only. No encoder default, public option, Tdarr flow or
> production image changed. Production remains r4069/bilateral and `modelsrc`
> remains default-off.

## Question

The coordinate-only replay proved that moving an already-aggregated hard-bin
curve is not a valid fix. This experiment tests the coupled estimator change
that the coordinate replay deliberately omitted.

NVEnc currently:

1. assigns one block variance to one of 20 hard luma bins;
2. averages variance inside each bin;
3. takes the square root; and
4. smooths the 20 resulting values.

The libaom reference contributes every block standard deviation fractionally
to the adjacent endpoint-grid controls and solves a regularised least-squares
system. `strength_observation_replay.py` reproduces that observation/solve
structure offline with temporal source and clean-base measurements.

Two luma-only variants were tested:

- `fractional-global`: the current entry-wide QVBR leak closure, with curve
  energy normalised to the input table so only shape changes;
- `fractional-local`: the same unit conversion, with the existing QVBR
  deadzone applied to each block's base/source temporal ratio.

AR coefficients, chroma, random seeds, parameter shifts, table timing, clean
base and encoder settings remain fixed.

## Held-out design

Interstellar is the mandatory first gate because restricted-range clipping
near black defeated every prior cheap curve correction. The seven scoring
pairs at frames `10,58,106,154,202,250,275` were excluded from fitting.

The first run used one deterministic interior pair per table entry. One
predeclared sampling-sensitivity retry used two pairs per entry. Neither retry
overlapped the held-out frames. Both used the exact saved detail-aware motion
base and pinned r4165 candidate binary SHA-256
`46256276d961dd25549b4bd8164ce7ded88512e83fef4662982414b6bb165b81`.

Artifacts:

```text
/media/merged-storage/media/test-encodes/strength-observation-20260803/
```

The complete Python gate is 111/111, including constant and linear solver
controls, held-out frame selection, bounded local closure and AV1 point-limit
quantisation.

## Domain-migration check

Before blaming source-versus-clean luma coordinates, the exact
production-static blocks were measured across all seven diagnostic frame
pairs:

| title | mean clean-source block mean (8-bit codes) | p95 absolute | blocks changing a 20-bin index |
| --- | ---: | ---: | ---: |
| Interstellar | -0.122 | 0.249 | 0.954% |
| Taxi Driver | -0.258 | 0.569 | 0.664% |
| The Deer Hunter | -0.426 | 1.194 | 0.823% |

Denoising moves fewer than 1% of block means across a hard-bin boundary on
every title. Source-versus-clean block-luma migration is therefore not large
enough to explain the opposite title/band failures. Respectively 8.1%, 7.9%
and 12.9% of selected clean pixels fall outside their source block's bin, but
that is ordinary within-block range rather than a shifted block population.

## Safety controls

Every alternate stream:

- has the same byte count as the original Interstellar replay: 12,063,199;
- passes a complete `libdav1d -xerror` decode; and
- has the same grain-disabled decoded MD5 as the original:
  `71c3371890ccaefc93d2e6c9d21efd88`.

The experiment changes only displayed luma grain.

## Held-out result

Production-static played-total amplitude:

| arm | one pair/entry | two pairs/entry |
| --- | ---: | ---: |
| original hard-bin curve | 0.9967 | 0.9967 |
| fractional-global | 1.0072 | 1.0026 |
| fractional-local | 1.0182 | 1.0150 |

The aggregates look superficially acceptable, but the required luma-band gate
rejects both candidates:

| source-luma band | original | global, one | global, two | local, one | local, two |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.000--0.125 | 1.0624 | **1.0479** | **1.0500** | 1.0871 | 1.0871 |
| 0.125--0.250 | **0.9539** | 0.9444 | 0.9443 | 0.9482 | 0.9477 |
| 0.250--0.375 | **0.9767** | 1.0361 | 1.0207 | 1.0198 | 1.0134 |
| 0.375--0.500 | **0.9122** | 1.2095 | 1.1266 | 1.1998 | 1.1195 |

The fractional-global solver mildly improves Interstellar's dominant darkest
band but moves the opposite error into the brighter populations. Doubling fit
coverage reduces that extrapolation but still leaves a 0.1266 error, worse
than the original 0.0878. Per-block local leakage also raises the darkest band
and is rejected independently.

## Decision

Do not implement either observation solver in CUDA and do not extend the
hardware run to Taxi Driver or Deer Hunter. Interstellar was the mandatory
non-regression gate and both variants fail it. Doubling the only allowed
sampling retry changes the result materially without clearing the gate, so
the offline population is not stable enough to justify a rolling hot-path
implementation.

This is not evidence that hard variance bins are ideal. It is evidence that a
libaom-style curve solve and luma-local leak arithmetic do not, by themselves,
fix post-encode delivery. The exact response work already established the
missing coupling: curve controls interact through clean-pixel population,
overlap and restricted-range clipping. Reintroducing that normative response
inside the analyser was separately rejected as too complex and failed its
held-out bound.

The amplitude branch is therefore paused rather than tuned further. The next
quality code experiment returns to the independent separator problem: a
robust current/aligned-previous/aligned-next operator. The motion-cycle audit
showed that vector-cycle thresholds cannot see the surviving symmetric wrong
matches; an aligned-sample outlier operator is the remaining direct way to
reject a single occluded reference before it is averaged into the clean base.
