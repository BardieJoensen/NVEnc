# Response-critical sparse population does not generalise

Date: 2026-08-04 UTC  
Branch: `fgs/test-automation`  
Authority: offline research only; no encoder, CLI, Tdarr, or routing change

## Decision

Reject the fixed-budget response-population experiment.  Sixteen weighted
clean-pixel representatives per frame/analyser bin do not predict a changed
legal AV1 luma curve accurately enough to drive per-luma strength closure.

Do not:

- loosen the pre-registered bound;
- increase the sample after seeing this result;
- run another Interstellar correction iteration;
- extend this estimator to Taxi Driver or The Deer Hunter; or
- inherit the population or constants for U/V.

The current guarded source-fit **texture** result remains valid and separate.
This is another rejection of a runtime amplitude normalizer, not a rejection
of source-derived AR fitting.

## What changed

The previous spatially hashed sparse Jacobian was well conditioned but missed
the independent full-block result by about `0.05`.  Its internal sample was
not representative of the pixels in adjacent luma bands after the curve
changed.

Commit `cd508ca7` replaces only that sample with deterministic weighted
quadrature.  Each clean block is described by the fixed, target-independent
features pre-registered in
`PLAN-2026-08-04-AMPLITUDE-RESPONSE-POPULATION.md`:

1. adjacent-pair clean luma mean;
2. adjacent-pair clean luma standard deviation; and
3. reciprocal legal-range headroom exposure.

Within each of the existing 20 analyser bins, standardised farthest-first
medoids span the feature population.  Every eligible block is assigned to its
nearest medoid, and exact normative synthesis on each medoid is weighted by
that represented population.  The curve target, response Jacobian, damping,
quantisation, source/static eligibility, and external oracle are unchanged.

The implementation is deterministic, bounded and fail-safe on constant
features.  The complete CPU gate passes: C++ solver/parser tests plus 215
Python tests.

## Frozen Interstellar gate

The first gate used 16 representatives per frame/analyser bin, two
deterministic response seeds and selection salt zero.  It evaluated two
retained tables:

- the original causal source-fit table; and
- the already-rejected 32-block/two-seed Jacobian table.

The independent reference is the existing full-block oracle (four seeds for
the original table and eight for the changed table).  No new table or output
was used as its own validation target.

| source-luma range | original sparse | original full | error | changed sparse | changed full | error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.000--0.125 | 1.13235 | 1.11459 | +0.01776 | 0.97605 | 0.92075 | **+0.05529** |
| 0.125--0.250 | 0.76637 | 0.78751 | **-0.02115** | 0.85091 | 0.89557 | **-0.04466** |
| 0.250--0.375 | 0.85506 | 0.85403 | +0.00103 | 0.84957 | 0.85337 | -0.00380 |
| 0.375--0.500 | 0.87712 | 0.85754 | +0.01958 | 0.87010 | 0.87484 | -0.00475 |
| **maximum absolute disagreement** |  |  | **0.02115** |  |  | **0.05529** |

The pre-registered maximum was `0.020`.  The original table narrowly fails;
the changed table fails by almost three times the bound.  More importantly,
the first two bands move in opposite directions.  A title-wide confidence
margin cannot make that predictor safe.

The probe command also computed a discarded one-iteration proposal because
`delivery_jacobian.py` has no evaluate-only mode.  It was not independently
audited and cannot override the failed baseline-population gate.

Artifacts:

```text
/media/merged-storage/media/test-encodes/
    amplitude-response-population-20260804/
```

## What the failure means

Clean mean, variation and boundary exposure describe clipping risk, but they
do not preserve the changed table's exact within-bin spatial/template
interaction.  The changed darkest-band response is over-predicted while the
adjacent band is under-predicted.  This reproduces the earlier external miss
with a more deliberate population; it does not look like an ill-conditioned
solver or one unlucky spatial hash.

Increasing representatives, seeds, feature dimensions or luma controls after
this result would resume designing a second normative decoder around the
same labelled film.  The previous 16/32-block sensitivity retry and this
pre-registered feature retry are sufficient to stop that direction.

## Consequence for the quality sequence

1. Keep the guarded luma texture path frozen and default-off.
2. Keep local luma deadzone closure and independent U/V deadzones rejected.
3. Do not begin a chroma implementation from this failed luma population.
   Chroma has a smaller block population, two independent curves, and
   plane-specific clipping; it is a harder version of the same problem.
4. Use blinded playback to determine whether the remaining per-luma and
   low-energy chroma amplitude errors are perceptually blocking.
5. If they are blocking, investigate an architecture that observes the
   **post-encode** base—two-pass analysis or safe AV1 film-grain metadata
   rewriting—rather than another pre-encode scalar or sparse response proxy.

No production files, node settings, or Tdarr routes changed.
