# R16 midpoint refinement and observations

Parent-owned scratch. The initial three rate calibrations are immutable under
`worker/psyex-r16-tf0-budget`. The revised contract is
`tests/fgs/reports/pantheon-sourcebudget-20261020/ROUND16_RATE_REFINEMENT.md`.
Only the requested bitrate and fresh output/statistics paths vary. The
acceptance interval remains 9.579757176–9.6765224 Mbps of actual scored packets.

The corrected runner is in `worker/psyex-r16-calibration-refine`; the parent
owns it after rejecting the worker drafts. `repair_refine.py` records the
correction. Rejected drafts are retained as development evidence. The new
replay comes from accepted R16 replay 03118968, not the rejected R8 replay.

Use the existing pinned `parent/psyex-real-r15/execute.py` wrapper:

```
analysis-venv/bin/python parent/psyex-real-r15/execute.py OUTER.json SCRIPT SHA [arguments...]
```

The first real request is `r16-refine-tbr10042 10042`, with explicit
`--low-receipt/--low-receipt-sha` referencing original request10014
(02bc2093…) and `--high-receipt/--high-receipt-sha` referencing request10070
(690beb60…). Later requests require the immediately preceding refinement
receipt and its hash. The validator reconstructs the bracket and midpoint;
equal endpoint rates are permitted. At most three new requests are allowed.

`preview-execution.json` and `validator-controls-execution.json` are completed
no-encode controls. Everything under `SYNTHETIC-NOT-ENCODED` is synthetic
validator evidence, never a measured encode or admissible quality result.
The four valid and five corrupted cases behaved as prescribed.

`prepare.py` derives the observation/scoring wrappers from frozen R15 sources.
Its arguments are encoder5804a1…, replay8491a3…, binder5d30f9…. The exact full
hashes and generated files are in `derived-pins.json`. The independent release
and wrapper reviews are in `reviewer/round16-refinement-*-review.md`.

After a measured matched result, invoke `observe_selected.py` through the outer
wrapper with tag, command-receipt SHA, encode-outer path and encode-outer SHA.
It runs decoder validation, syntax binding, neutral encoder/decoder replays,
admission and stage analysis sequentially. A changed syntax target requires
private observer retargeting before continuing. Run `score_r16.py` only after
admission, using tag, admission path, command SHA and admission SHA.

Keep all current evidence and dependencies. No production change or playback
acceptance is implied. Archive and clean only at an authorized stopping point;
see `parent/psyex-real-r15/ARCHIVAL_NOTES.md`.
