# R16 parent integration

Parent-owned scratch for the original-rate TF-off experiment. Worker owns
`worker/psyex-r16-tf0-budget`; reviewer owns `reviewer/round16-*`. No production
changes. Contract is the committed `ROUND16_TF0_BUDGET_CONTRACT.md`.

Reuse the verified R15 decoder validator, parser, stage descriptors and GPU
campaign/control path with explicit R16 provenance. `prepare.py` derives the
new wrappers and requires final runner/replay/binder hashes before completion.
Do not execute drafts. All actual invocations use the unchanged, pinned
`parent/psyex-real-r15/execute.py` wrapper to retain early failures.

Keep receipts, logs, native traces, commands, scripts, metrics and selected
visuals. Raw duplicate decodes and builds remain reproducible, but retain all
live dependencies until investigation completion and archive reconciliation.
This directory is active; do not clean or archive it yet.
