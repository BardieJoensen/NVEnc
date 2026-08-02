# Cheap per-luma delivery response is not sufficient, 2026-08-02

This executes the implementation gate left by
`FINDINGS-2026-08-02-LEAK-CLOSURE.md`.  It is an offline test of the opt-in
`modelsrc=on` candidate.  No encoder default, Tdarr configuration or production
image changed.

## Question

The exact multi-seed oracle proved that per-luma scaling curves can close all
26 populated real-film bands, but it has inputs the analyzer hot path does not:
decoded base pixels and several normative AV1 grain realizations.  The proposed
implementation was allowed to proceed only if a cheap response model built from
the rolling analyzer's existing 20-bin weights and quantized table parameters
predicted the same correction.

`delivery_response.py` tests that premise.  For each of the 24 measured frame
pairs per title it:

1. reconstructs production's exact source-selected static blocks;
2. uses the quantized table model and one deterministic normative seed per
   frame;
3. measures a constant-luma response for every legal 8-bit code value;
4. weights that response with the analyzer's 20 source-luma block bins; and
5. compares against the retained two- or four-seed, actual-base-pixel oracle.

The reference reports and tables are under:

```text
/media/merged-storage/media/test-encodes/sourcefit-leakclose-20260802/
```

The decisive recorded run is:

```text
Taxi_Driver-delivery-response.json
Taxi_Driver-delivery-response.txt
```

It can be reproduced with:

```text
python3 tests/fgs/delivery_response.py \
  --emission .../Taxi_Driver-emission-lumabins2.json \
  --qvbr 29 --fixed-seed-clean-pixels \
  --json-out .../Taxi_Driver-delivery-response.json
```

## Result

The existing-quantity `uniform_20bin` model predicts 23 of 26 bands within 5%
and has a 2.9% mean absolute relative error, but the failures are exactly the
dark/sparse bands where an incorrect correction is most damaging:

| title / luma band | 20-bin uniform | + clean block mean | + clean pixel histogram | one seed on clean pixels |
| --- | ---: | ---: | ---: | ---: |
| Interstellar, 0.000--0.125 | +11.7% | +2.3% | +2.7% | not run |
| Taxi Driver, 0.000--0.125 | **+27.7%** | **+7.8%** | **+6.6%** | **+0.7%** |
| The Deer Hunter, 0.000--0.125 | +9.5% | +3.6% | +2.8% | not run |

The clean-block mean would require one small additional accumulator per source
bin and fixes two of the three failures.  Taxi remains outside the gate.  Even
giving the estimator the complete clean-pixel luma histogram does not close it.

This is not a harmless prediction miss.  On Taxi's darkest band the true
expected synthesis ratio is 0.9839 and the target is 0.9676.  If each estimator
were used to normalize the curve, the residual target errors would be:

| response model | post-correction target error |
| --- | ---: |
| existing 20-bin occupancy | -0.2101 |
| clean block mean | -0.0699 |
| complete clean-pixel histogram | **-0.0596** |
| one fixed seed on the actual clean pixels | -0.0066 |

The accepted exact per-luma experiment used a maximum absolute band error of
0.0442.  The histogram model therefore still fails the already-measured gate;
using it would turn a small dark-band excess into a much larger deficit.

## What the failure localizes

Seed averaging is not the missing information.  One deterministic seed over
the actual clean blocks predicts the multi-seed oracle within 0.7% on Taxi.
The lost term is the interaction among the clean pixels' spatial arrangement,
the luma-dependent scaling curve, restricted-range clipping near black, and the
per-block plane removal used by the measurement.  Counts, a mean, and even an
unordered histogram cannot represent that interaction.

Closing it in the encoder would require an actual pixel-aware synthesis
response pass after the table is quantized, or a similarly rich surrogate.
That is no longer the proposed cheap use of rolling statistics.  It adds a
second pass and a second implementation of normative behavior to a hot path
whose emitted synthesis is already known pixel-exact.

## Decision

**Do not implement the per-luma delivery normalizer in CUDA.**  The stated
cheap-estimator gate fails on the most important title and the failure would
produce a large wrong-direction amplitude regression if acted on.

- Keep the rate-dependent leak closure and source model as opt-in research;
  `modelsrc` remains default-off.
- Do not promote the six-film mean of 0.995 played total as production
  clearance: Interstellar still reaches 1.087 while Deer Hunter remains 0.924.
- Keep the exact per-luma result as an existence proof, not an encoder design.
- The next compression work belongs upstream in the separator.  The current
  motion arm saves 46.4% but fails the calibrated temporal-drag gate; a
  confidence/disocclusion fallback can now be ranked directly against
  bilateral using drag, localized artifact tails and bytes.
- Real-film chroma closure remains separate and open.

Nothing in this result is approved for Tdarr production.
