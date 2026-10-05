# Submitted pictures and repeat variability — 2026-10-05

The provisional diagnostic observed no kernel-candidate change in the submitted picture bytes or grain parameters on five original-source fixtures, including 1080p SDR, partial picture blocks and 4K HDR. Production's submitted inputs also remain identical across six repeats on Lost Tapes, Gentlemen and Taxi. However, the diagnostic has not reproduced both known Gentlemen output states, so its output-neutrality check remains incomplete; these results do not yet establish where the untraced variation occurs.

Production tracing is commit `118acfb0`; candidate tracing is `a2a5d88d`, descended from the production-based kernel branch. Their only runtime difference is `NVEncFilterFilmGrain.cu`. Both were built from independent pinned clones in the pinned CUDA 13.3 image. The exact deployed comparator remains binary SHA256 `c6cbd5280440c62b51c3b43ced4570dad40295748d42f562a867ac6a525be72b`.

**Provisional diagnostic limitation:** the SDK forbids client access to a mapped input surface; this first diagnostic used such access and therefore cannot establish the final supported identity proof. A correction retains submission metadata and reads the same immutable owned surface after output completion and successful unmap, before reuse; all checks below must be repeated with that correction.

The first trace snapshots the mapped NVENC input immediately before submission, after producer completion, and copies the actual picture's grain object bytes. It hashes full pitch, visible Y/UV and padding separately, plus initial and per-picture grain objects and flags. Hashing/writing occurs after successful drain; retained snapshots have a 2 GiB limit. Tracing off performs no capture, allocation, hashing or synchronization. See [the trace contract](SUBMISSION-TRACE-20261005.md).

| Original fixture | Production traced repeats | Candidate traced repeats | Submitted picture and grain comparison |
| --- | ---: | ---: | --- |
| Lost Tapes, 240 frames, 1080p SDR | 6 | 3 | All bytes identical |
| Gentlemen, 240 frames, 1080p SDR | 6 | 3 | All bytes identical |
| Taxi Driver, 24 frames, 4K PQ | 6 | 3 | All bytes identical |
| Amphibia, 240 frames, 1080p SDR | 2 | 2 | All bytes identical |
| Silo, 24 frames, 1918×802 SDR | 2 | 2 | All bytes identical |

The production neutrality batch also checks one raw export per arm and three same-command AV1 repeats for the deployed binary, trace build with tracing off, and trace build with tracing on. Raw-base and filmgrn1 hashes match for Lost Tapes, Gentlemen and Taxi. In that batch Lost Tapes and Taxi have matching observed IVF sets. Gentlemen has states `0ff816e7…` and `73707cd1…` without capture, but only `73707cd1…` with capture, including three additional production trace runs. A finite missing state neither proves an output change nor proves neutrality. The existing Gentlemen plain-NVENC receipt already shows that FGS is unnecessary for variation; it does not replace the requested same-run localization evidence.

The first implementation hashed and wrote before each submit. It also produced only one known SDR state across six production repeats; that inconclusive evidence is preserved. Deferring hashes removed that work from submission, but the readback/wait can still affect scheduling. There is no traced pair with differing IVFs in the completed real-source sample, so no driver cause or FGS nondeterminism fix is claimed. No output-changing correction is included, and the missing neutrality result is not silently treated as a pass.

Evidence is in `/tmp/downloads/codex-work/fgs-submission-20261005/`: `reports/deferred-trace-real-summary.json`, the three linked complete reports, exact commands, per-frame traces and IVF/decoded hashes. Historical synchronous-capture results are in `reports/synchronous-trace-summary.json`. The same provisional diagnostic also matched all 21 KAT fixtures over two repeats per binary. The unchanged full release gate and throughput results are separate checks and remain pending.
