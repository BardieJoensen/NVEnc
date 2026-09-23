# Native measurements and bounded diagnostic selection

D48 and D49 implement complete native moment measurements, comparison, bounded
seed selection and an eight-picture window policy in reusable C++ helpers.
They advance R3; they do not approve source populations or enable retention.

`NVEncFilmGrainNativeMoments.h` measures the native-Y 25-variable covariance,
both 26-variable colour covariances, common-colour covariance and 49 spatial
Cb/Cr cross moments on the existing disjoint tile halves. A displacement-product
integral preserves each pair's exact shifted support. A central autocorrelation
is not an equivalent replacement on nonstationary pictures. Means and native
layout/range checks share the previously qualified variance conventions.

`NVEncFilmGrainMomentComparison.h` retains the original full spatial result
alongside D42's separate research policy. Each picture must pass mean,
native-Y spatial and all-component variance checks. Every sliding eight-picture
window must also pass all spatial and colour-cross checks. This is the recorded
D42 policy, not a relaxation of the original source-admission contract.

The first training-pass seed among at most four supplied seeds is selected.
Failure on its independent check half rejects the trial; it cannot cause a
search for another seed. The window helper rejects invalid layouts, missing
ordinals, segment changes, individual failures, insufficient tails and reuse
after completion. It holds seven pictures until an eight-picture comparison
passes. Later failure is terminal: an already compressed partial base cannot
be relabelled as original-source fallback.

The explicit `select=true` development synthesis adapter now runs calibration,
complete native measurements and this seed policy in one process. Shape and
pre-encode retention remain supplied. No production call site invokes it.

## Evidence

- D48: 98 native 8/10-bit source, base and final pictures match independent
  NumPy measurements: 784 complete matrices and 9,604 cross values. Maximum
  absolute difference is `7.993605777301127e-14`, within the predeclared
  `1e-9 + 1e-10 * abs(reference)` arithmetic tolerance. An additional 1,250
  optimized/direct sums agree exactly on nonstationary integer fields.
- D48 includes 32 new grain-on dav1d observations. Their pictures match the
  previously qualified AOM oracle identities; this is not a new AOM decode.
- D49: 162 comparisons and 128 known-negative comparisons preserve the
  independent Python results. Both changing-picture controls preserve all 32
  selected seeds and strengths and all 18 sliding-window results.
- Fresh synthesis reproduces 420 calibration steps and all 42 candidate
  pictures exactly. These compare to existing decoder-qualified identities;
  D49 makes no new AV1 decoder claim. Temporary 66,060,288 raw bytes were hashed
  and retired after verification.
- Invalid/nonfinite and zero-variance evidence, check-half seed-search leakage,
  bounded attempts, sequence changes and an isolated dropout hidden by a
  pooled-only average have explicit regression coverage.

Full CPU suite passes: 214 Python tests in 30 suites and 42 C++ programs.

The first D49 harness incorrectly assumed every self comparison was valid.
Quiet zero-variance base pictures have undefined normalized covariance and
correctly reject. The harness was corrected to compare invalid results as such;
the implementation was unchanged, and the failed attempt remains in the ledger.

D49's 32 process calls took 5.40 seconds including input reads, synthesis,
calibration, complete moments and candidate selection. This is a finite CPU
substep measurement, not complete encoder throughput. D48's standalone native
measurements took 3.87 seconds versus 12.19 seconds for the independent NumPy
calculations; neither timing justifies a production speed claim.

Continue with in-process source/base shape fitting and automatic live integration.
The whole-picture source/coverage problem, retained-fraction choice, temporal
qualification and R4–R8 remain open. Production stays ordinary `cb903a17`,
retention/FEL off; reserved qualification footage remains unopened.

Local evidence: `roadmap-r3-native-moments-20260923` and
`roadmap-r3-native-selection-20260923` under the current ledger root, including
manifests, exact commands, independent comparisons, synthesis hashes and the
CPU suite log. No experiment is scheduled or restarts automatically.
