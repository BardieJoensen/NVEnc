# Measured retention evidence and numerical target correction

D64 connects actual native source, rounded input, NVENC reconstruction, emitted
model and decoded picture measurements to finite selector evidence. It completes
this evidence plumbing and fixes an experimental numerical false rejection.
It does not complete automatic retention: detail/quiet and regional eligibility
remain separate requirements, and R3–R8 remain open.

## Numerical correction

The previous fixed-order PSD predicate could discard a tiny positive pivot
before eliminating its larger correlated direction. A valid 10-bit Cb
source/reconstruction pair consequently failed both folds, although independent
eigenvalues established PSD. The predicate now eliminates the largest diagonal
first and checks the complete trailing block when it reaches numerical rank.
The supplied target, coefficients and numerical tolerance are unchanged.
No invalid target is regularized or clipped into a successful fit.

Analytic tiny-variance/permutation controls and 516 independent matrix checks
pass, including 96 indefinite negative controls. All 64 measured frame targets
agree on both spatial folds for all components. Twenty model syntax/feedback
controls also pass. The exact retained 8/10-bit fitting inputs produce unchanged
coefficients, pair moments and fit diagnostics after the fix.

The reconstructed-picture library is rebuilt as `libfgsnative.so-v8`, SHA
`6be9b20b057b4f48af329ffebf0a9aeaee42d451687de4114dbcd5232651d1b3`.
Ten CPU replays through the live encoder adapter cover 160 pictures, 1080p/UHD,
both source/model transition directions and all-source intervals. Their models,
decisions, readiness and complete encoded bytes are identical to the earlier
GPU/decoder-qualified controls. This reuses prior decode evidence by exact byte
identity; it is not a new GPU or decoder count.

The affected helper is absent from production revision `cb903a17`; no production
hotfix or library repair follows from this development-only false rejection.

## Measurement and association

The new references measure every native rounding sample, full-resolution Y,
both chroma components, disjoint spatial folds, means and common-colour
relationships. Current source/reconstruction pair targets retain the oriented
cross matrix. Quantized syntax and causal/spectral feedback remain distinct
from pixel fidelity. The evidence join rejects mismatched original, pristine,
rounded, reconstructed or decoded content, model, frame clock or fraction.

Across the 64 constructed frames, 50,331,648 native rounding samples agree
exactly. There are 64 fresh dav1d observations linked to existing independent
AOM/oracle evidence. Original strict single-picture checks still reject frame
zero of both 10-bit runs; all 36 separate eight-frame windows pass. The window
result does not erase those single-picture failures.

Only actually measured check bits are supplied. Detail and quiet checks remain
unknown; native-Y classification and complete regional proofs are not invented
from a successful fit. Source populations stay fixed across fractions and the
census uses the actual reconstructed-picture lookup. All four measured 16-frame
selector replays therefore preserve the whole source. This validates rejection
behaviour, not real-source admission or useful automatic partial retention.

The complete CPU suite passes **232 Python tests in 33 suites and 49 C++
programs**. Current ordinary Tdarr is unchanged; retention and FEL stay off,
the reserved corpus remains unopened and nothing starts automatically.

## Next implementation

Measure quiet-region and decoder-range safety using the complete native
picture, then join those facts to the same candidate identity. Extend independent
detail evidence while retaining motion/persistent-grain counterexamples and
source fallback. Passing a constructed constant scene cannot approve an
arbitrary real scene. Full runtime selection, temporal qualification, unseen
compressed-output quality and measured quality/bytes/speed remain R3–R8 work.

Private evidence is in `roadmap-r3-measured-candidates-20260924/` under the local
colour-recovery evidence root. Read `report.json`, `refit-pivoted-report.json`,
`library-v8-report.json`, `model-target-report.json`, `psd-control-report.json`,
`measured-plan-report.json` and `cpu-tests-final.log`. The September 27 recovery
note describes the earlier interruption; this report supersedes its pending
fitter/library and commit steps. The failed initial numerical comparison remains
available separately. Keep retained source/capture data needed by the next stage.
