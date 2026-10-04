# Findings — FGS filter kernels, 2026-10-04

Film-grain filtering and analysis used 12.2–13.8% less GPU processing time on the original 1080p Lost Tapes and Amphibia clips, saving about 0.12 ms per frame. A 24-frame 4K HDR Taxi Driver fixture used 7.5% less. The change targets the 1080p hardware-decode workload that accounts for 91% of library GPU hours. Complete Tdarr throughput has not been measured. The candidate did not cover every known production output state within the declared repeat bound, so it is not release-qualified.

## Change and provenance

Branch `perf/fgs-prod-filter-kernels-20261004` descends from production head `6cfb28a5`, with core commits `3f4d5290` and `6e8fa1fb`. Only `NVEncCore/NVEncFilterFilmGrain.cu` changes at runtime.

The bilateral kernel stores exact integer code values as floats once in its shared tile and unrolls the existing 5×5 tap traversal. The flat-metric kernel specializes full 32×32 blocks, using constant dimensions and mask/shift indexing; partial blocks retain the existing general calculations. The block mapping, sample/reduction order at source level, source evidence, min/max fields, barriers, fallback rules and host pipeline remain intact. The two routine stream synchronizations remain at lines 2004 and 2273 of the candidate CU. FFT3D caching, frame-copy changes and deferred emission are not part of this candidate.

The final measured binary was built from an immutable local clone of `6e8fa1fb1a2b06e64b8c4a19af392bc5adfe5c5e` in the pinned CUDA 13.3 build image. Its SHA256 is `be7a50a1681fc5aa9a7133533f081d4e3253b2c74bc639605358f69d591ababe`. It reports 9.37 r4366 with the same relevant features as production. A copied immutable build cache was reused only for this CU-only runtime diff; configuration and dependency hashes were unchanged, Meson regenerated the revision, and Ninja rebuilt the changed CUDA object. No live worktree was built. The deployed comparator is the exact `c6cbd528…` binary extracted from the current node.

## Before and after

Three alternating paired Nsight Systems traces per source, using the production video settings and original-source development fixtures. Values below are medians in GPU milliseconds per output frame, including startup/drain. Percentages are reductions between arm medians, not medians of paired percentage changes. FGS totals sum only `kernel_fgs_*` CUDA activity durations; flat metrics include luma flat statistics and the unchanged chroma source-statistics kernel. These sums exclude copies, CPU work and the NVENC engine.

| Original source | Frames / decode / QVBR | Production FGS kernels | Candidate FGS kernels | Reduction | Bilateral before → after | Flat metrics before → after |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Lost Tapes, 1080p SDR | 240 / avhw / 30 | 0.955358 | 0.838507 | 12.23% | 0.500220 → 0.469404 | 0.253035 → 0.168184 |
| Amphibia, 1080p SDR animation | 240 / avhw / 34 | 0.873852 | 0.753702 | 13.75% | 0.500182 → 0.469841 | 0.254048 → 0.164573 |
| Taxi Driver, 4K PQ HDR | 24 / avsw FFV1 / 29 | 4.483887 | 4.148085 | 7.49% | 1.983576 → 1.867869 | 1.106058 → 0.883139 |

The isolated bilateral-only step saved 3.10% and 3.42% of FGS kernel time on the two SDR clips. Full-block specialization supplies most of the additional saving. Keep those isolated receipts separate from the final combined measurements; GPU load changed between campaigns.

All three paired comparisons have lower total FGS kernel time in every candidate trace, with separated before/after ranges. The GPU remained shared with live work. Host synchronization time overlaps device work and is not added to these numbers. The 24-frame HDR sample demonstrates only that short fixture, not sustained HDR decoding or throughput. The two SDR clips are a range within the supplied 91% bucket; no unsupported title/class weights are assigned. That 91% describes whole-job GPU hours, not the FGS share of those hours, so multiplying these kernel savings by 0.91 would not establish a library-wide time saving. There is no justified 15–20% end-to-end throughput claim from these measurements.

Ordinary NVENC controls use the same original inputs and video settings, with FGS removed and VBR tuned to actual FGS payload rate. Accepted controls match within −0.389% for Lost Tapes, +2.891% for Amphibia, +0.755% for Taxi and +2.712% for Gentlemen. Later failed control states and successful retuning receipts are preserved separately. Silo and the corrected 21-case KAT control campaign remain pending; the first KAT attempt inherited a VBR rate cap that was inactive under canonical CQP, and its capped/overflowed attempts cannot count as matched controls. Controls establish rate accounting and repeat behavior, not a grain-quality preference.

## Output identity and regression checks

The final compiled binary matches production on raw-base, filmgrn1, IVF and grain-off decoded state sets across all 21 KAT fixtures, with five repetitions per arm. This is the completed KAT identity result; it does not establish real-source identity or a passing quick/full gate. Five real-source fixtures also match within their first five-repeat campaign. Across all compatible historical and current evidence, candidate admission still lacks one known Taxi state and the earlier Gentlemen state. Both cases reached the predeclared twelve unprofiled runs per binary without those states. The [strict audit](evidence/2026-10-04-filter-kernels/identity-summary.json) admitted 687 runs with zero evidence/scope errors; no candidate-only state was found, but known-state coverage did not pass. Whole raw-file/pixel and grain-off decoded MD5 are retained as additional checks. Raw exports are separate invocations, not captures of the submitted NVENC surfaces.

Production's known Lost Tapes states are `ce0413d…` and `234dbae…`. The Taxi profile set is currently unequal: production produced IVF MD5 `3fbd02014b8bac6da53d77e3e2195f95` twice and `d3cf4137a98a02a37a478c5c08ce9cdd` once; the candidate produced only the first state in three traces. All six used filmgrn1 MD5 `83c169e521a6f7a0c8aa8d7eb2bf77e9`. Admission must include both observed production states, including this profiler evidence; a single matching hash is insufficient. No nondeterminism fix is included or cause claimed.

Gentlemen now has two production states as well, with an unchanged table. Its plain NVENC control also varies with FGS disabled: the same arguments and source produce two decoded-picture states, differing from frame zero. This proves FGS is not necessary for that observed variability; it does not establish identical submitted surfaces or identify a driver cause. See the [plain-control receipt](evidence/2026-10-04-filter-kernels/gentlemen-plain-variability.md).

The existing Silo source fixture, 1918×802, adds 25 usable partial-width blocks and 60 tiny bottom-edge blocks that the canonical KAT dimensions do not exercise. It is a lossless original-source conversion and uses avsw; it is not presented as a hardware-decode performance sample.

CPU tests pass on final core: 119 Python tests and nine C++ executables. Independent source review and an exhaustive integer geometry check found no indexing, shared-initialization or barrier defect. Those checks are not substitutes for compiled GPU bit identity. The fifteen available release stages are running under an explicitly partial label. The amplitude stage is absent because its pinned source/history inputs are missing; the required `--full` run has not passed.

## Release status and operation

Release requires all three: matching known production state sets, matched plain controls, and the unchanged full gate including the complete-history Play Dirty amplitude negative/control/candidate witnesses. None can substitute for another. The first condition is currently unmet; the other checks are incomplete. The user is reacquiring the original. Its exact SHA must match before it is independently copied into scratch and all three full histories are regenerated. The new manifest must name this candidate binary's actual SHA. Historical missing artifacts and every failed result remain recorded.

The external canary helper hardcodes four temporary directories under `/tmp`. A scratch-only view changes only those four directory literals to this task's `/tmp/downloads` workspace; both launchers and all metric, threshold, frame, control and verdict code remain identical. The exact diff and reverse-byte/AST proof accompany the gate receipt. No global helper or local_gate.sh change is required.

After all qualification conditions pass, use the existing `/opt/docker-apps/build/tdarr-node/Dockerfile.fidelity` release procedure with the exact qualified binary, matching core/SHA labels and a new immutable image tag. Validate the packaged binary and approved flow before the user replaces the node. Verify the actual binary SHA and `fgs.encoder.*` labels; the base image also carries stale inherited labels that must not be treated as encoder identity. Retain the current `nvenc-fidelity/tdarr-node:2.94.02-aeb14263-20261004` image as rollback and verify its `c6cbd528…` binary when restoring it. This session deploys and pushes nothing.

Principal risk is a compiled-output change or unrecognized interaction with existing repeat variability. Raw/table equality is encouraging, but incomplete IVF-state coverage leaves that risk unresolved. The host pipeline and surface lifetime are unchanged. These finite fixtures do not prove every possible input, and the measured stage saving must not be advertised as a complete-library throughput percentage.
