# Pre-registered amplitude response-population gate

Date: 2026-08-04 UTC  
Branch: `fgs/test-automation`  
Authority: offline research only; no encoder, CLI, Tdarr, or routing change

## Why this experiment exists

Two amplitude directions are already measured negatives and will not be
repeated:

- applying the QVBR deadzone independently to every luma bin improves shape
  but worsens the title-wide low bias; and
- independent U/V deadzone fits generalise to held-out pre/post observations
  but regress exact emitted played output.

The earlier sparse luma response Jacobian found a well-conditioned nonlinear
curve response, yet its internally closed table missed the independent
full-block Interstellar oracle by `0.0486..0.0518`.  Increasing the spatial
sample from 16 to 32 blocks per frame/analyser bin did not help.  The failure
moved between adjacent luma bands, identifying population representation—not
ordinary sample count or solver conditioning—as the next falsifiable layer.

## Frozen change

Keep all of the following unchanged:

- production flat/static eligibility;
- the existing 20 analyser luma bins;
- the QVBR synthesis target;
- legal film-grain table quantisation;
- the finite-difference response Jacobian, damping, and two-iteration bound;
- source, clean base, AR coefficients, seed protocol, and external oracle.

Replace only the spatial-hash subset inside each frame/analyser bin.  Build one
fixed feature vector for every eligible clean-base block, averaged over the
adjacent frame pair:

1. clean luma mean;
2. clean luma standard deviation; and
3. legal-range boundary exposure, defined as the mean of
   `1 / (1 + headroom_8bit)`, where headroom is distance to the nearer legal
   output endpoint.

Standardise non-constant features within the bin, choose at most 16
deterministic farthest-first medoids, assign every eligible block to its nearest
medoid, and weight each exact synthesized medoid response by its assigned
population.  Spatial hashing is used only to break exact ties.  The features
do not contain source grain truth, target error, title identity, or candidate
output.

This is deliberately a quadrature/population test, not another strength
multiplier.  It still evaluates normative AV1 synthesis only on a bounded
subset of actual clean pixels.

## Fixed sequence and gates

1. Unit-test deterministic selection, bounds, weights, constant-feature
   handling, and population-weighted response.
2. On the retained Interstellar original table and already-rejected
   32-block/two-seed Jacobian table, compare the 16-representative estimate
   with the existing eight-seed full-block oracle.  Maximum per-band synthesis
   ratio disagreement must be at most `0.020`; otherwise stop.
3. Only if step 2 passes, run the unchanged two-iteration response solver with
   16 representatives and two deterministic seeds.  The independent
   eight-seed/full-block Interstellar audit must close every populated band to
   the existing `0.0442` bound.
4. Only if Interstellar passes, run Taxi Driver and The Deer Hunter without
   changing features, count, thresholds, damping, or iterations.
5. Only if all three labelled cases pass, confirm on the other retained films
   and then on the newer guarded-response corpus.  No training-film threshold
   adjustment is allowed.

Chroma does not inherit a luma pass.  It gets a separate population and exact
U/V played-output gate only after luma generalises.  A luma failure keeps the
independent chroma estimator paused rather than encouraging another per-plane
constant.

## Interpretation

A pass would justify a test-only implementation/timing design; it would not
justify production.  A failure rejects this sparse response-population
architecture at the fixed budget and returns amplitude to perceptual triage or
a post-encode/two-pass design.  In either case, the already-validated source
texture and guarded covariance response remain independent results.

## Resolution

The first Interstellar gate failed.  Maximum sparse-versus-full disagreement
was `0.02115` on the unchanged table and `0.05529` on the changed table, against
the frozen `0.020` bound.  The changed darkest and adjacent bands missed in
opposite directions.  The sequence stopped before a new correction or any
Taxi/Deer/chroma expansion.  See
`FINDINGS-2026-08-04-AMPLITUDE-RESPONSE-POPULATION.md`.
