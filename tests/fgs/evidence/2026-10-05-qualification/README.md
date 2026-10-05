# Final kernel qualification evidence — 2026-10-05

`gate-evidence.tar.gz` contains 1,551 hashed report/log/build/history members from the successful unchanged full gate and the preserved first attempt, whose historical Butteraugli check ran out of GPU memory. The final command exited zero: 23 passed, zero failed. Candidate CPU tests passed 119 Python tests and nine C++ programs. `gate-archive-receipt.json` pins the archive; every member was verified after packing.

The exact qualified runtime is a1ac278ae22425719fd567931329284f82950cd4, binary SHA256 d1de4e49025114d8c2040d278d83352ebb41e49b4b6e1aed46496a2c6228633b. The pinned source clone, build image, dependency closure and original-copy/full-history receipts are retained. The private canary path view has only the recorded scratch-directory substitutions; no numerical threshold, algorithm or verdict change. Adjacent JSON files retain that path-only proof and header-dependency audit.

Full media/binaries remain under `/tmp/downloads/codex-work/fgs-submission-20261005/`, with exact paths/hashes in the receipts. No media is included in this archive. Complete CPU and release gates are separate from the same-run submission proof in `../2026-10-05-submission/` and from the still-pending quiet throughput measurement. All gates passing is not evidence that untested source classes have no grain defects.
