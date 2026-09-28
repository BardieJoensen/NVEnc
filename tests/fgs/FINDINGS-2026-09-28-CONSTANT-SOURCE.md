# Exact reconstruction of constant source planes

D78 closes a demonstrated blind spot in D76's necessary energy/mean veto.
Adding opposite constant offsets to different native tiles creates false block
edges. Tile detrending removes the offsets, while both checkerboard-half means
can cancel. Six component/depth examples pass the old aggregate checks.

The new check measures whether each original plane is truly constant and
whether every visible reconstructed sample equals its original. A constant
source requires an exact match. Both measurements share the existing integer
mean scan, include borders and exclude padding. They do not require a grain
classification, change the variance/mean bounds or introduce a quiet noise
allowance. Nonconstant source/detail and local-artifact limits remain separate.

The report names `native_variance_means_constant_v2` and includes
`constant_source` and `actual_matches_source` flags. This explains a rejection
even when the old moments appear unchanged. The same terminal model/readiness
failure applies. Ordinary and model-only paths do not call the new measurement.

CPU tests pass 14 native positives and 134 loss/mean/quiet/layout negatives,
including 18 new component/depth/geometry step controls. Six sequence failures
verify that a bad constant reconstruction cannot publish a model or complete.
Independent NumPy checks agree across 102 measured frames and 598,622,208
samples, including the six previously missed examples and actual D76 captures.
All 20 source-bound native replays preserve their existing decisions, moments,
models and readiness. All nine accepted complete IVF outputs remain exact.
The full suite passes 267 Python tests in 37 suites plus 54 C++ programs.

The tiny 20-pixel quiet-transition rejection recorded in D76 remains rejected;
this change addresses false acceptance, not its conservative quiet policy.
The ordinary recovery findings in D77 remain separate. R3/R4 and later
qualification are unfinished. Production, retention/FEL settings, protected
sources and reserved footage are unchanged.

Local evidence: `roadmap-r3-constant-source-reconstruction-20260928/` under the
handoff root, especially `plan.json`, `targeted-tests.json`, `full-cpu.json`,
`independent-report.json` and `replay-report.json`. Full encoder build and the
bounded actual GPU regression are pending at this CPU checkpoint.
