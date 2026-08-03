# Hard-bin strength-grid isolation, 2026-08-03

> Offline research only. No encoder default, Tdarr flow, image or production
> binary changed. Production remains r4069 with bilateral separation and the
> residual-derived model; `modelsrc` remains default-off.

## Question

The source-fit analyser assigns each block to one of 20 equal-width luma
intervals:

```text
bin = floor(block_mean * 20 / 2^bit_depth)
```

`fit_strength_points`, however, emits the 20 solved values on an endpoint grid
from 0 through 255. If each hard-bin estimate belongs at its interval centre,
the 8-bit positions should instead span 6.4 through 249.6. This experiment
isolates that coordinate mismatch from strength, AR texture, separation and
encoding.

## Isolation

`strength_grid_replay.py` deep-copies a `filmgrn1` table and applies the affine
mapping

```text
x' = 6.4 + x * 243.2 / 255
```

to luma point coordinates only. Scaling values, luma/chroma AR coefficients,
chroma curves, random seeds and timing remain unchanged. The parsed output is
validated before use. CPU tests cover the endpoint mapping, field isolation
and a complete `filmgrn1` round trip.

Three labelled titles were replayed first:

- Interstellar: mandatory non-regression case near black;
- Taxi Driver: dark, coarse-grain case; and
- The Deer Hunter: largest existing within-luma slope.

Both original and remapped tables were applied to the exact same saved
detail-aware motion clean base with pinned r4165 candidate binary SHA-256
`46256276d961dd25549b4bd8164ce7ded88512e83fef4662982414b6bb165b81`.
Encoding was AV1 10-bit, QVBR 29, 20 Mbit/s maximum, P4 and tune HQ.

Artifacts are under:

```text
/media/merged-storage/media/test-encodes/strength-grid-20260803/
```

## Safety controls

All six AV1 streams pass a complete `libdav1d -xerror` decode. Grain-disabled
decoded frame MD5 is identical between the two arms for every title:

| title | grain-off decoded MD5 |
| --- | --- |
| Interstellar | `71c3371890ccaefc93d2e6c9d21efd88` |
| Taxi Driver | `ba25fd4b626b3b194cc09641cdbb99bd` |
| The Deer Hunter | `172cdfa9c44ea0b6f1e4907959f1811b` |

Encoded byte counts are also exactly equal within each pair: 12,063,199,
27,172,126 and 30,152,197 bytes respectively. AV1 grain is out of loop, so
this is the expected result and proves the clean picture/compression path did
not move.

## Exact post-encode result

Variance-weighted production-static closure on seven fixed frame pairs:

| title | original total | centred total | change |
| --- | ---: | ---: | ---: |
| Interstellar | **0.9967** | 0.9551 | -0.0416 |
| Taxi Driver | **0.9720** | 0.9578 | -0.0142 |
| The Deer Hunter | **0.9450** | 0.9404 | -0.0046 |

All three regress globally. Interstellar alone is sufficient to reject a
universal coordinate remap.

The band result explains why the idea looked plausible offline but fails as a
fix. It redistributes grain between luma ranges:

| title | source-luma band | original total | centred total |
| --- | --- | ---: | ---: |
| Interstellar | 0.000--0.125 | **1.0624** | 0.9548 |
| Taxi Driver | 0.000--0.125 | **1.0382** | 0.9419 |
| Taxi Driver | 0.125--0.250 | 0.9463 | **0.9702** |
| Taxi Driver | 0.250--0.375 | 0.9485 | **0.9646** |
| Deer Hunter | 0.000--0.125 | **0.9301** | 0.9007 |
| Deer Hunter | 0.125--0.250 | 0.9124 | **0.9477** |
| Deer Hunter | 0.250--0.375 | **1.0837** | 1.1133 |
| Deer Hunter | 0.375--0.500 | **1.2501** | 1.2736 |

The darkest populated band dominates all three titles. Moving the curve right
reduces that band enough to outweigh improvements elsewhere; on Deer it also
worsens already-excessive brighter grain.

## Decision

Reject the coordinate-only remap. Do not implement it in C++, expose an
option, or extend the hardware campaign to the remaining films. The exact
replay overrides the earlier approximate raw-block prediction.

This does not prove that the current population/curve estimator is correct.
It proves that coordinates cannot be changed after hard aggregation and still
be expected to fix delivery. NVEnc currently differs from the libaom reference
in coupled ways: it hard-bins variance and takes the square root after
averaging, whereas libaom contributes each block's standard deviation
fractionally to adjacent endpoint-grid controls and solves a regularised
system.

The next quality experiment is therefore an offline observation-level solver,
not another table-wide multiplier or coordinate shift. It must use continuous
source-block luma, per-block temporal strength observations, endpoint-grid
linear weights and regularisation, then quantize and replay the resulting
table. Interstellar, Taxi Driver and Deer Hunter remain the mandatory first
gate. A candidate fails if it improves one band by moving the opposite error
into another, even when its title aggregate looks better.
