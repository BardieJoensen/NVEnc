# Kernel candidate qualification

The kernel candidate now passes the new same-run input-identity rule and the complete existing release gate. Production and candidate submit identical pictures and grain parameters on all 21 KAT fixtures and five original-source fixtures, including 4K HDR and partial-block geometry. All 23 full-gate checks and 119 Python / nine C++ CPU tests pass. This establishes the tested output identity; the decision to spend a release on its small kernel saving still depends on the separate quiet-GPU throughput measurement.

## Exact candidate

- Local branch: `qualify/fgs-prod-kernels-20261005`, descended from production `aeb14263` through the October 4 kernel branch.
- Qualified runtime commit: `a1ac278ae22425719fd567931329284f82950cd4`.
- Candidate binary: `/tmp/downloads/codex-work/fgs-submission-20261005/bin/nvencc-kernels-trace-unmapped`, SHA256 `d1de4e49025114d8c2040d278d83352ebb41e49b4b6e1aed46496a2c6228633b`.
- Exact deployed comparator: `c6cbd5280440c62b51c3b43ced4570dad40295748d42f562a867ac6a525be72b`, production core `aeb14263c94bde5e3434920ce6281aa3285852fb`.
- Immutable build image: `nvenc-fgs-build:cuda13.3`, ID `sha256:031ff1820c81f1c8888deff7bd1654a17e4885bfac3d04105ad55da9e34fd9ff`.

The binary was built from an immutable pinned clone, not a live worktree. Later branch commits contain reports and evidence, not encoder changes. The current candidate includes opt-in submission tracing; default-off execution performs no tracing readback, hashing, allocation, synchronization or I/O. It does retain two null-pointer checks per picture, whose cost belongs in the final end-to-end timing comparison.

The algorithmic change remains the bilateral shared-tile/tap work and full-block flat-metric specialization. Border calculations, traversal/reduction order, source guards and both normal per-frame readback synchronizations remain. There is no readback overlap, FFT3D caching, retention work or quality-changing fix.

## Identity and variation

The SDK-compliant schema-2 trace snapshots the exact picture grain object before submission and reads the same owned surface after completed encoding and unmap, before reuse. Full-pitch, visible and padding hashes and picture parameter bytes match stably across repeated production/candidate runs. The five real fixtures include Lost Tapes, Amphibia, Gentlemen, TaxiHDR and Silo; the latter covers 1918×802 partial blocks. All 21 KAT cases have two runs per traced arm, as do the five real cases.

The production instrumentation check preserves the initially incomplete three-arm IVF-state result and combines already required compatible production-trace repeats for the actual deployed-versus-traced comparison. Raw/table hashes and the observed IVF sets match. Lost Tapes and Gentlemen each produce distinct IVFs from identical traced inputs: variation is downstream of submission, inside NVENC/driver behavior. No further driver investigation or rare-state hunt is justified. IVF and decoded hashes are informational for this FGS-only candidate. See [the short variability findings](FINDINGS-2026-10-05-SUBMISSION-VARIABILITY.md) and [trace contract](SUBMISSION-TRACE-20261005.md).

## Full gate and retained failure

The exact Play Dirty original was independently copied and verified before any measurement: 8,667,928,469 bytes, SHA256 `d4a348ec7afc3dd22a66a492f2c804a49392ba8de1afc5aa244c548f4e15934d`. The original was never modified. The negative, plain-reference and final candidate histories were regenerated or independently finalized from that private copy, each with 183,661 strictly decoded frames. These plain controls are required by the existing amplitude gate, not an additional identity/timing control campaign.

The first complete gate attempt passed 22 checks but its historical r4047 Butteraugli canary ran out of GPU memory under unrelated ASR/LLM load. That failure remains in the evidence. After that load cleared, the **entire unchanged** `local_gate.sh --full` command was rerun and exited zero with **23 passed, 0 failed**, including the historical negative controls, candidate base fidelity, periodic/flash/colour cases, mixed sources, complete-history amplitude, source variance and source training.

The harness is pinned to the candidate clone. The existing private path view changes only scratch-directory literals in the external canary helper; algorithms, inputs, thresholds and verdicts are unchanged. The new clean-region measurements reveal production coverage gaps outside the current fixtures; passing this gate does not invalidate those findings.

## Retained kernel measurements, not end-to-end gains

The CUDA source is byte-identical between the October 4 measured runtime `6e8fa1fb` and current `a1ac278a`: SHA256 `2de02e359a8b9f1fb73847cf24ff0bf04945290671239dd44d04aa14c0256a67`. The previous three alternating paired Nsight runs therefore remain evidence for the unchanged kernel implementation. They do not measure the final binary's whole video-stage throughput.

| Original source | Production → candidate FGS GPU ms/frame | Reduction |
|---|---:|---:|
| Lost Tapes, 1080p SDR, avhw/QVBR30 |0.955358 → 0.838507|12.23%|
| Amphibia, 1080p SDR, avhw/QVBR34 |0.873852 → 0.753702|13.75%|
| Taxi Driver, 4K PQ, FFV1/QVBR29, 24 frames |4.483887 → 4.148085|7.49%|

These are summed FGS GPU kernel durations, excluding copies, CPU work and NVENC. The HDR window establishes only that short fixture. Lost Tapes is animation, so the final quiet throughput matrix uses verified Marshals digital live action and Amphibia animation to cover two content classes. No 15–20% throughput claim follows from these kernel figures.

## User-operated release and rollback

Do not deploy solely because this gate passes; use the final timing recommendation to decide whether a standalone release is worthwhile. No image has been built, swapped or pushed by this qualification work.

1. Use the exact qualified runtime/binary above. If rebuilding, follow `local_gate.sh`'s immutable pinned-clone recipe in the pinned build image and verify the resulting artifact; a changed binary hash needs its own artifact parity/qualification receipt.
2. Copy `/opt/docker-apps/build/tdarr-node/Dockerfile.fidelity` into a private release staging context. Preserve its official Tdarr 2.94.02 application digest, retained runtime base, Opus, `fgs-scan`, `packet-audit`, `dovi_tool`, plugins and flow. Supply the qualified `nvencc`; update only its final checksum, encoder core/hash labels and immutable candidate image tag. Do not change the earlier source-runtime checksum assertions or reuse stale production labels.
3. Validate the built image's encoder hash/version and unchanged tool/flow pins, then run the existing release image/flow qualification and source canary. Keep `NVENC_TRACE_SUBMISSION` unset for ordinary operation. Only the user may authorize the image swap under the existing drain/ownership recipe.
4. Roll back by restoring `nvenc-fidelity/tdarr-node:2.94.02-aeb14263-20261004` in the existing release procedure, then verify deployed binary `c6cbd528…`, the original node limits and flow. Retain that image and the qualified artifacts until the release decision and rollback window are closed.

The currently deployed image was read-only verified after the full gate as ID `sha256:3bf0fe28f70cda3305b9476e4f87ca013c37e1467f4b2d27e73482fb56107773`, unchanged from the production receipt.

## Evidence

The [qualification bundle](evidence/2026-10-05-qualification/gate-evidence.tar.gz) contains both complete gate attempts, CPU/build pins and regenerated full-history receipts; its manifest hashes every member. [Submission evidence](evidence/2026-10-05-submission/README.md) retains the repeated exact inputs and neutrality receipts. The [October 4 kernel findings](FINDINGS-2026-10-04-FILTER-KERNELS.md) retain the profiler numbers under their original contract. New quality findings and the unimplemented proposal are [clean-source safety](FINDINGS-2026-10-05-CLEAN-SOURCE-GRAIN.md), [grain axes](FINDINGS-2026-10-05-GRAIN-AXES.md) and [the fix plan](CLEAN-SOURCE-FIX-PLAN-2026-10-05.md).
