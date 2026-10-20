# R9 boundary instrumentation

Private observation of the exact admitted PSYEX R8 output. No production change.
The six-file patch applies to PSYEX 59d1a025 with its separately audited cpuinfo
dependency. The parent scratch source manifest pins all 1,789 files.

The independent implementation review required allocation bounds and removal of
a misleading post-recode quantizer field; both were corrected before build.
The accepted build finished 2026-10-20 14:01:46 UTC. Full build logs, source
manifests and binaries remain in parent/psyex-boundary-r9 under the session root.
completed-build-pins.json binds those final artifacts.

Run ../replay_psyex_boundary.py with off/on, fresh tag, and the pinned app/library
SHA values. A successful replay proves only full336 stream/reconstruction
neutrality. The separate validator must admit trace framing, generation/sample
coverage and exact target reconstruction before any boundary analysis.

See ../ROUND9_BOUNDARY_CONTRACT.md. Source/preloop/postloop snapshots are
diagnostics; no quantizer, final search-route, coded-bit or playback claim.
