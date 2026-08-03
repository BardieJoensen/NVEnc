# Sparse pixel-aware delivery response, 2026-08-03

> Offline research only.  No encoder default, Tdarr flow or production image
> changed.  `modelsrc` remains default-off.

## Question

The integrated six-film gate left opposite per-luma strength errors even
though source-derived AR fitting fixed grain texture.  Cheap response models
cannot predict AV1 delivery on dark film: luma-bin occupancy, clean-block mean
and even a complete clean-pixel histogram lose the spatial interaction among
the scaling curve, overlap, detrending and restricted-range clipping.

One deterministic normative seed evaluated on every actual clean block did
predict the multi-seed oracle.  This experiment asks two separate questions:

1. can a bounded subset of actual clean blocks preserve that accuracy; and
2. does multiplying the quantized curve by the predicted correction actually
   deliver the target?

The second question is mandatory.  A response estimate can be accurate for
the current table while still failing to predict a changed table.

## Inputs and reproducibility

The causal source-fit arm from the integrated campaign was used because paired
centering failed its base-fidelity gate.  Seven frame pairs per film were held
fixed at frames `10,58,106,154,202,250,275`.  AV1 synthesis used the pinned
libaom Gaussian sequence with SHA-256:

```text
8aec1ca1fae39bf32dd2c63f08bc0a260e333bfcea796c539fd8240796ac5f74
```

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-integrated-20260803/
  reports/emission/
  reports/sparse-normalized/
```

Entry points:

```text
tests/fgs/emission_audit.py
tests/fgs/delivery_response.py
tests/fgs/delivery_normalize.py
```

`emission_audit.py` was first extended to accept both the labelled multi-arm
and single-stream closure-report schemas.  The repository CPU gate now uses
test discovery rather than a stale hand-written module list; it currently
runs 95 Python tests plus the C++ solver and parser tests.

## Exact emission remains closed

Fresh audits of all six causal streams show:

- every signalled non-seed model field matches the table;
- the local normative synthesizer matches dav1d with zero pixel mismatches and
  zero maximum error;
- direct predicted/delivered amplitude is exactly 1.000 on every film; and
- all streams had already passed complete `libdav1d -xerror` decoding.

The luma-shape error is therefore upstream of bitstream emission.  It is not a
mux, decoder, random-seed or hidden AV1-gain defect.

## Sparse current-response gate

For every frame pair and populated 20-bin analyser luma bin, one normative
seed was evaluated on at most N actual clean 32x32 blocks.  Sixteen
deterministic spatial selections expose sensitivity instead of reporting one
lucky subset.  The table below reports the worst absolute *linearized* target
error across bands and selections.

| title | 8 blocks | 16 blocks | selected fraction at 16 |
| --- | ---: | ---: | ---: |
| Casino | 0.0281 | **0.0204** | 11.9% |
| Interstellar | 0.0439 | **0.0427** | 20.2% |
| Scarface | 0.0114 | **0.0098** | 13.8% |
| Taxi Driver | **0.0516** | **0.04295** | 10.9% |
| The Deer Hunter | 0.0369 | **0.0242** | 11.5% |
| The Shining | 0.0196 | **0.0156** | 6.1% |

Eight blocks fail on Taxi Driver.  Sixteen blocks pass the previous 0.0442
existence bound on all six films while evaluating 6.1--20.2% of the selected
block pairs.  This establishes a practical sampling floor for further work;
it does not clear a correction algorithm.

The harness now names these values `linearized_post_correction_target_error`.
The earlier shorter name implied a corrected table had been replayed, which
was stronger than what the calculation proved.

## Exact corrected-table replay rejects one multiplication

A concrete table was built from selection zero at 16 blocks per frame/bin.
Only the luma scaling curve changed; AR coefficients and the coded clean base
were held fixed.  Eight-seed exact replay then measured the quantized proposed
table on all selected blocks.

| title | one-pass maximum band error | result |
| --- | ---: | --- |
| Taxi Driver | 0.0386 | pass |
| The Deer Hunter | 0.0266 | pass |
| Interstellar | **0.1226** | fail |

Interstellar's failure is its darkest 0.000--0.125 band.  The sparse estimate
of the current table was accurate, but multiplying the curve assumed delivery
would scale linearly.  Restricted-range clipping near black violates that
assumption.

A three-pass limit was fixed before continuing.  Exact darkest-band error
converged monotonically:

```text
0.1226 -> 0.0824 -> 0.0533
```

The third pass remains above 0.0442, so the bounded multiplicative solver is
rejected.  A fourth pass is not retroactively allowed merely because the miss
is small.  The other Interstellar bands finish within 0.0387.

## Decision

The result separates the architecture into a measured success and an open
algorithm:

- **Keep the pixel-aware response direction.**  Sixteen sampled blocks per
  frame/luma bin measure the difficult current response accurately enough,
  including Taxi Driver.
- **Reject the simple multiplicative update.**  It is not a valid local model
  near clipped black and fails the predeclared iteration bound.
- **Do not implement a runtime normalizer yet.**  No CUDA response pass or
  public option follows from this result, and nothing is approved for Tdarr.
- **Keep source-derived AR fitting as the primary grain-quality result.**  It
  remains the change that fixes coarse-versus-fine texture by about an order of
  magnitude; this experiment concerns amplitude closure only.

## Next quality experiment

Estimate the local response slope on the same sparse pixels after the table is
quantized.  The offline prototype should evaluate a bounded perturbation of
each populated luma factor, solve a damped local response model, quantize once,
and re-evaluate.  It passes only if Interstellar, Taxi Driver and Deer Hunter
all close within 0.0442 in at most two correction steps without worsening AR
texture or changing the clean base.

If that gate fails, abandon runtime delivery normalization and put the next
code effort into separator admission: forward/backward motion-vector cycle
consistency with current/spatial fallback, ranked on base Butteraugli tails,
VMAF/SSIMULACRA2, temporal drag and grain texture.  Speed remains secondary
until either quality path clears.
