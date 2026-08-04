# Deterministic seeds do not close the binned luma response

Date: 2026-08-04 UTC  
Branch: `fgs/test-automation`  
Authority: offline research only; no encoder, Tdarr, routing, or production change

## Decision

Stop the deterministic-seed two-pass experiment at its pre-encode replay
gate.  The independently measured maximum luma-band error is `0.03935`, above
the frozen `0.02000` bound.  No pass-2 encode was made, and Taxi Driver, The
Deer Hunter, and chroma were not run.

Actual NVENC seeds remove a real source of expectation noise, but they do not
repair the response solver's loss of within-bin information.  Do not loosen
the bound, add an iteration, or treat the solver's internal near-pass as the
result.

## Isolated tooling

Commit `01238ad9` adds research-only seed replay to the existing offline
tools:

- `delivery_jacobian.py --response-seed-mode stream` reads the actual
  pass-1 side-data seed for each selected frame;
- `emission_audit.py --expected-stream-seeds` independently replays a
  proposed table with those same seeds; and
- both modes fail closed unless exactly one measured seed is requested.

The historical oracle-seed defaults are unchanged.  The complete CPU gate
passes: C++ solver/parser tests plus 218 Python tests.

## Frozen Interstellar result

The solver used the exact grain-disabled pass-1 base, every eligible block on
the seven frozen frame pairs, their actual seeds from the 288-frame pass, the
existing quantized response Jacobian, and two iterations.  Its targets are
the exact post-encode missing amplitudes.

| source-luma range | target | solver replay | internal error | independent replay | external error |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.000--0.125 | 0.969529 | 0.990229 | **+0.020699** | 0.949295 | **-0.020234** |
| 0.125--0.250 | 0.816071 | 0.816454 | +0.000382 | 0.855425 | **+0.039354** |
| 0.250--0.375 | 0.825927 | 0.829566 | +0.003639 | 0.829376 | +0.003449 |
| 0.375--0.500 | 0.879952 | 0.881831 | +0.001879 | 0.883983 | +0.004031 |
| **maximum absolute error** |  |  | **0.020699** |  | **0.039354** |

The internal result already narrowly missed the gate.  The separate emission
audit then failed it materially, so the frozen sequence stopped before any
second encode, seed-identity claim, base hash, decode test, or played-total
measurement.

## Why the two replays disagree

`delivery_jacobian.py` synthesizes all selected blocks, but then averages
their variances inside the analyser's 20 luma bins and assigns that one mean
response back to every block in the bin.  The independent audit retains each
block's actual response when accumulating the four fixed reporting bands.
These statistics are not equivalent where a reporting boundary cuts an
analyser bin.

Interstellar exposes the error at the `0.125` boundary.  Analyser bin 2 spans
normalized luma `0.100--0.150` and contains blocks on both sides:

| bin-2 population | blocks | candidate synthesis sigma |
| --- | ---: | ---: |
| all bin-2 blocks | 1772 | 4.295615 |
| reporting band 0.000--0.125 | 1463 | 4.069401 |
| reporting band 0.125--0.250 | 309 | 5.235606 |

The darker and brighter subsets have very different realized responses on
the actual encoded pixels, largely because restricted-range clipping is
pixel-dependent.  Replacing both with the pooled `4.295615` response moves
the adjacent reporting bands in opposite directions.  Bin 7 similarly
straddles `0.375`, but its two subsets are close (`5.273736` versus
`5.373219`) and the resulting error is small.

This corrects the inference in the pre-registration.  The earlier four-seed
solver versus eight-seed audit disagreement was not evidence that seed
expectation was the *only* remaining fault.  Both paths visited every block,
but the solver discarded within-bin response before producing its luma-band
estimate.

## Reproducibility

Artifacts:

```text
/media/merged-storage/media/test-encodes/
    postencode-strength-closure-20260804/Interstellar/
        pass1-original-table.mkv
        actual-seed-corrected.tbl
        actual-seed-solver.json
        actual-seed-corrected-audit.json
```

SHA-256:

```text
5b2a46a3afcd9a5133af7d8c64000ec81c9cfe28338cea92f9e640193a7e789d  pass1-original-table.mkv
d981ea912b4b0411738a73129907c8132a0f826871620567a7c9e0e88a0d188d  actual-seed-corrected.tbl
f76f1996505cb2a98e3bd91068851d50366540db706b41d71961751767ddb70f  actual-seed-solver.json
788c96b5b43bdfd1a01267aae78a7ac35e0d0ca7eb664dfcfe0b69a00853e8ed  actual-seed-corrected-audit.json
```

## What this points to next

The next technically justified amplitude experiment is an exact per-block
response accumulator: keep the same finite-difference table controls and
normative synthesis, but accumulate each synthesized block directly into its
fixed luma reporting band instead of routing it through a 20-bin mean.  In the
current full-population offline gate this needs no additional synthesis work;
it removes a lossy aggregation that is now measured to dominate the error.

That would still be a two-pass research architecture, not production code.
It must be pre-registered separately, pass Interstellar without tuning, and
then generalise to held-out films before luma closure is credible.  Chroma
remains blocked behind luma and will require its own plane-specific response
and amplitude estimator.

The guarded source-fit luma **texture** result remains valid and independent.
This failure concerns per-luma amplitude closure only.
