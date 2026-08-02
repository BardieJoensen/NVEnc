# QVBR leak transfer and exact AV1 emission audit, 2026-08-02

This executes Phases 0 and 1 of `NEXT-2026-08-02.md`.  It is an offline
experiment against the opt-in `modelsrc=on` candidate.  No default changed and
nothing in Tdarr or the production image was modified.

## Reproducibility

Candidate binary:

- source commit: `1f20fb1c`
- binary: `/home/bardie/.cache/fgs-gate/builds/pin-1f20fb1c-1785626473/build-gate/nvencc`
- binary SHA-256:
  `d119abd866e0689d90c477ca43784fa8fe979c9624cf83751cc739eb0076f06d`

Corpus: the retained 287-frame clips for Casino, Interstellar, Scarface, Taxi
Driver, The Deer Hunter and The Shining, with the matching motion clean bases
from `sourcefit-corpus-20260801`.

Every arm used the same command apart from QVBR:

```text
nvencc --avsw -i SOURCE --codec av1 --output-depth 10 \
  --qvbr Q --max-bitrate 20000 --preset p4 --tune hq \
  --av1-film-grain denoise=auto,chroma=auto,denoiser=motion,modelsrc=on \
  --film-grain-table-out OUT.tbl -o OUT.mkv
```

QVBR 25, 29, 34 and 39 produced 24 arms.  All 24 pass a complete
`libdav1d -xerror` decode.  The QVBR-29 tables are byte-identical to the
retained closure corpus, and the encoded elementary video-stream MD5s also
match it exactly.  This catches the initially attempted but incorrect
`--aq --aq-temporal` reproduction; those options were not present in the
original run.

Artifacts are under:

```text
/media/merged-storage/media/test-encodes/sourcefit-qvbr-sweep-20260802/
```

The checked tools are:

- `strength_selection_report.py --encoded-arm`: one source/mask decode shared
  across all four encoded arms;
- `qvbr_leak_fit.py`: deadzone fit, rate fit, leave-one-out errors and actual
  P-frame qindex/10-bit AV1 qstep extraction;
- `emission_audit.py`: exact luma AV1 synthesis from the parameters actually
  present in each frame, verified pixel-for-pixel against dav1d;
- `av1_grain.py`: luma-only port of the normative fixed Gaussian sequence,
  LFSR, AR recursion, template selection, overlap, LUT interpolation, rounding
  and restricted-range clipping.  The fixed sequence is read from the pinned
  libaom checkout made by `build_aom_reference.sh` at revision
  `18c52422b835ba6cdde1b2342d760c6037a7fd86`.

## Phase 0: the deadzone survives the QVBR sweep

The model is:

```text
post_encode_leak = max(0, pre_encode_leak - theta)
```

All amplitudes use the `production_static` blocks and are relative to source
temporal truth.

| QVBR | mean P qindex | 10-bit qstep | theta | sample SD | range | r(pre, post) |
| ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 25 | 44.145 | 22.198 | 0.13480 | 0.02395 | 0.10913 .. 0.17797 | 0.9797 |
| 29 | 55.697 | 28.685 | 0.15951 | 0.02558 | 0.12660 .. 0.19609 | 0.9777 |
| 34 | 78.742 | 41.371 | 0.18409 | 0.02790 | 0.14331 .. 0.21794 | 0.9761 |
| 39 | 105.007 | 60.257 | 0.20327 | 0.03548 | 0.15629 .. 0.26357 | 0.9638 |

`theta` is ordered at every rate.  Its correlation is 0.99489 with requested
QVBR and 0.99115 with `log2(actual qstep)`.  A linear `theta(QVBR)` fit has a
maximum in-sample residual of 0.00274.  Leaving out one complete rate at a time
and extrapolating/interpolating from the other three has a maximum theta error
of 0.00891.

Taxi Driver and The Deer Hunter approach the 20 Mbit/s cap at QVBR 25.  The
actual P qindex and qstep columns are therefore the safer interpretation than
the requested QVBR label; both still move monotonically with `theta`.

This is not only a good fit to post-encode residue.  It predicts the quantity
the encoder needs: the synthesis target `sqrt(1 - post_leak^2)`.

| QVBR | uncorrected temporal-target MAE | fitted deadzone MAE | leave-one-title-out mean | leave-one-title-out max |
| ---: | ---: | ---: | ---: | ---: |
| 25 | 0.04697 | 0.00494 | 0.00594 | 0.01502 |
| 29 | 0.05321 | 0.00583 | 0.00699 | 0.01808 |
| 34 | 0.05851 | 0.00578 | 0.00693 | 0.02104 |
| 39 | 0.06205 | 0.00545 | 0.00655 | 0.02304 |

Fitting `theta = a + b*QVBR` without each title in turn gives these target
errors across its four held-out rates:

| held-out title | mean | max |
| --- | ---: | ---: |
| Casino | 0.00190 | 0.00350 |
| Interstellar | 0.01930 | 0.02400 |
| Scarface | 0.00036 | 0.00053 |
| Taxi Driver | 0.00589 | 0.01037 |
| The Deer Hunter | 0.00368 | 0.00558 |
| The Shining | 0.00900 | 0.01374 |

**Verdict:** Phase 0 holds.  This is a rate-dependent quantisation transfer,
not the rejected constant gain and not a one-QVBR corpus coincidence.  It
reduces the systematic target error by roughly 8-10x.  The six-film coverage
is sufficient to prototype behind `modelsrc=on`, not to make it a default.

## Phase 1: the apparent emission scatter was a seed-oracle bug

The first table-only audit appeared to reproduce the old `+/-0.09` scatter:
Taxi Driver and The Deer Hunter were predicted 9.7% and 11.5% high while four
other titles were within roughly 3%.  That result was invalid for two reasons:

1. it used a Gaussian substitute and omitted high-bit-depth LUT interpolation;
2. more decisively, it used the random seed stored in the analyser's table.

NVENC's public API does not accept a film-grain seed.  NVENC chooses a seed for
the bitstream, so the `.tbl` seed describes neither the actual 73x82 template
nor its 32x32 patches.  ffprobe exposes the real seed and complete film-grain
parameters as decoded frame side data.

The corrected audit reads those side-data parameters and independently ports
the normative luma synthesis path.  Across six films and seven frame pairs per
film:

- all non-seed model fields in the table match the bitstream;
- **0 of 42** table seeds match the corresponding bitstream seed;
- predicted and dav1d synthesis match on **98,443,264 of 98,443,264 pixels**;
- total mismatches: **0**; maximum absolute pixel error: **0**;
- predicted/delivered detrended amplitude: **1.0000 on all six titles**.

A later audit extended the side-data parser from luma-only fields to both
chroma planes, including scaling curves, AR coefficients and the six chroma
multipliers/offsets.  After accounting for filmgrn1's normative unsigned
parameter biases (`128/128/256`) versus ffprobe's synthesis-space values, the
full table and bitstream models match on all **1,725 of 1,725** QVBR-29 frames.
This turns the original broad sentence into a checked full-model claim.

**Verdict:** there is no second amplitude defect in AV1 emission.  The decoder
delivers the signalled model exactly.  A table-only per-title amplitude oracle
cannot be exact when it uses a seed NVENC replaces; the old scatter was a
measurement bug, not a correction target.  No emission compensation should be
added.

## Decision and next work

The sequencing gate in `NEXT-2026-08-02.md` is satisfied:

1. the deadzone scales with encoding rate and predicts the true post-encode
   target materially better;
2. the emission path is understood and pixel-exact;
3. a leak-aware closure can now be prototyped, but only through the existing
   `sqrt(1 - retain^2)` path and only behind `modelsrc=on`;
4. `modelsrc` remains default-off until a new six-film encode/closure run and
   the independent blinded motion review clear it.

Still open and deliberately not mixed into this experiment: per-block
rectification counts, real-film chroma validation, and the motion perceptual
gate.
