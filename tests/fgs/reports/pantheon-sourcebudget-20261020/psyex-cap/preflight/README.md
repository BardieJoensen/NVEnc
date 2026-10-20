# R18 parent execution preparation

Parent owns this directory, the private build and execution harness. The worker
owns `worker/psyex-r18-cap/source` and its source patch. No production changes.
Do not mutate previously built source or completed receipts; revisions use fresh
directories and explicit identities.

Order: reviewed source and build wrapper; private build; cap-disabled second-pass
neutrality against R16; fresh unchanged first-pass statistics; cap-enabled second
pass without observers; same policy with independent cap/boundary/coefficient
observers. All controls must pass before quality interpretation. New syntax and
native decoder binding must follow the new stream rather than reuse old ordinals.

The first policy run may exceed the source budget; that is diagnostic cost.
Original-rate practicality and every quality gate remain unchanged. The policy
touches selected q/lambda and whole-frame delta-q resolution; feedback and
unselected damage must be measured across the entire scored window.

Source/build: nice10, CPU0–7, parallel4 build; encoder lp1. GPU benchmarks are
serialized. Fresh scratch allowance40GB, staging floor120GB. Preserve source
patches, logs, failed attempts, receipts, native evidence and useful outputs for
final archival. Duplicate reconstructions/build objects are reproducible but
remain active dependencies until admission and the investigation finish.

Invoke each preparation, pinning, preview or encode script through the pinned
R15 `execute.py` wrapper (SHA256
`93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858`)
with a fresh outer receipt and exact script hash. This preserves failures that
occur before an inner output directory exists. Build shell execution records
its own failure log and also receives a parent execution receipt.
The launch free-space gate is160GiB (build shell uses160GB), conservatively
covering the120GB staging floor plus40GB additional allowance.
