# Forward/backward motion-cycle investigation — 2026-08-03

> Investigation only. Nothing here is enabled in NVEncC or deployed to
> Tdarr. `modelsrc` remains default-off and the centred-motion hook remains
> test-only.

## Question

The paired centred separator can reject a one-sided match by admitting both
temporal references at the lower of their SAD affinities. It cannot reject two
wrong vectors that agree. This investigation tests the next proposed signal:
follow each current-to-reference motion vector, sample the reverse vector at
its endpoint, and reject a reference when the two do not close a cycle.

The falsifiable requirement was deliberately stronger than "cycle error exists
on film": after the existing paired SAD gate, cycle error had to remain higher
on a labelled disocclusion than on unaffected controls. Otherwise it would add
work and reject useful temporal samples without detecting the failure it was
designed for.

## Method

`motion_cycle.py` joins exact degrain block traces for frames `t-1`, `t` and
`t+1`. For each previous and next reference it evaluates:

```text
cycle_error = |v(t -> reference) + v(reference -> t)|
```

The reverse field is sampled bilinearly on the overlapping 16-pixel block
grid. This avoids turning block-grid quantisation into a false cycle error.
Border samples clamp to the edge, matching the renderer's mirrored reference
coordinates.

Two specimens were used:

1. `coarse_detail_occl`, whose moving opaque foreground provides exact
   visibility ground truth. A current background pixel hidden by foreground
   in the selected reference has no valid static-background correspondence.
2. The Shining frame 268, the independently selected high-motion real-film
   sample used by the earlier confidence investigation.

Both used the checked-in, default-off centred hook, paired confidence,
`motion-refs=1`, `modelsrc=on` and the measured `thsad=640`. Each trace was
generated from a full or 33-frame pre-rolled window; a five-frame trimmed
fixture run was rejected because scene analysis had not warmed up and disabled
both references.

Artifacts and machine-readable reports are under:

```text
/media/merged-storage/media/test-encodes/motion-cycle-20260803/
```

## Result 1: cycle error is real before admission, but SAD is the detector

Across 15,708 direction records in the occlusion fixture:

| signal | ROC AUC for known disocclusion |
|---|---:|
| current-reference SAD | **0.943** |
| paired maximum SAD | **0.898** |
| forward/backward cycle error | 0.571 |

The mean cycle error is 1.864 pixels on known-disocclusion records and 0.591
on controls before admission. That is a real enrichment, but it is weak beside
the signal already available to the renderer. The paired `thsad=640` gate
rejects 1,061 of 1,246 labelled records (85.2%) while retaining 11,939 of
14,462 controls (82.6%).

## Result 2: the surviving wrong matches close their cycles

After paired SAD admission, the relationship reverses:

| admitted subset | records | mean cycle error | fraction `> 0 px` |
|---|---:|---:|---:|
| known disocclusion | 185 | **0.284 px** | **3.2%** |
| fixture control | 11,939 | 0.437 px | 11.7% |

At least 95% of the surviving labelled disocclusions have exactly zero cycle
error. These are symmetric zero-vector or repeated-texture matches: a wrong
match followed by the same wrong match in reverse is cycle-consistent by
construction. This is the specific limitation the experiment needed to
expose. A positive cycle threshold cannot catch them.

## Result 3: a zero-error rule is unusable on real film

The Shining's paired-SAD-admitted records have this cycle distribution:

| statistic | cycle error |
|---|---:|
| median | 1.700 px |
| p90 | 6.325 px |
| p95 | 7.438 px |
| p99 | 10.244 px |

Of 13,608 admitted direction records, 78.1% are above zero, 45.1% are above
2 pixels and 26.9% are above 4 pixels. Therefore the only threshold that could
touch the fixture's zero-cycle failures would also reject most real temporal
references. The signal is not merely incomplete; at the point where it would
be inserted, it orders the labelled failure and real content in the wrong
direction.

## Decision

Do **not** implement a motion-cycle gate in CUDA. The existing stricter paired
SAD admission is the useful part of this line of work. Forward/backward cycle
consistency is redundant before that gate and cannot see the symmetric wrong
matches left after it.

The next separator experiment should operate on the aligned pixel samples,
where an occluded or repeated-texture reference can still be an intensity
outlier despite having low SAD and a closed vector cycle. A robust three-sample
operator (current, aligned previous, aligned next) is the next defensible
candidate. It must be tested first on `coarse_detail_occl`, then on the six-film
source-referenced gate. The current paired mean remains test-only until such a
candidate improves base fidelity without giving back source-fit grain texture.

## Verification

- `motion_cycle.py` has CPU tests for exact inverse flow, a deliberately broken
  reverse field, endpoint sampling and tie-correct ROC AUC.
- The complete CPU gate passes: **101 Python tests**, plus the C++ film-grain
  solver and parser tests.
- Trace-only runs did not modify the encoder or public options.
