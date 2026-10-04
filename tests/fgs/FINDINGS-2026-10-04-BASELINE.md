# Findings — production baseline, 2026-10-04

The production rebuild passes the CPU and quick GPU checks and reproduces the deployed binary’s observed output sets across the tested fixtures. The bilateral filter costs about 0.50 ms per frame on two original 1080p clips and 1.98 ms on the short 4K HDR fixture, making it the strongest measured speed target for the library’s dominant workload. No encoder improvement or release qualification is claimed yet.

## What was measured

This is deployed `aeb14263` versus a fresh build of that same commit, not master. The plan branch starts at production head `6cfb28a5` (documentation only above the deployed merge). Build and binary identities, flow export and source hashes are preserved in the evidence directory. The Docker build followed `local_gate.sh`: CUDA 13.3 build image, release configuration, VMAF/libvship disabled, declared development packages, pinned source and submodules. No moving worktree was built.

The video core uses bilateral FGS, 10-bit AV1, QVBR, quality/HQ, lookahead 32/level 3, spatial/temporal AQ and max bitrate 50000 from `AV1NVENCflow1.json`. The diagnostic IVF outputs omit audio, subtitle and chapter muxing. Raw diagnostics retain color/range but cannot carry encoded HDR/container metadata. Their results do not qualify the Matroska/nonvideo path.

## Baseline checks

- CPU: exit 0; 119 Python tests across 16 suites and nine C++ executables.
- Quick gate: five checks passed, none failed, including all 21 KAT cases, table finalization/failure behavior, lookahead ordering/timestamps/drain, rejection of the adversarial texture model and acceptance of the shipping model.
- Repeated identity: matching raw Y4M/file and pixel MD5, filmgrn1, IVF and grain-off decoded sets on `const_luma`, `const_10bit`, `coarse_luma`, Lost Tapes, Amphibia, Gentlemen and Taxi HDR. All seven have active grain-table entries. Lost Tapes required twelve repeats per binary; the other six have five repeats per binary. This is finite observed-state evidence, not a proof of determinism or equal probabilities.

Lost Tapes produced IVF states `ce0413d0300f5a9775d6352c56d76aa6` and `234dbaecbf54c26b0b361abae33abfbb`: deployed counts 8/4, rebuild 9/3. Raw pixel MD5 stays `5bab36f1c415640f8b78ade8f7a668a0` and filmgrn1 MD5 stays `cdeceddf325f6701d124f593fccbd872`. Packets 7, 9, 13 and 19 differ; the first differing grain-off decoded picture is index 8. The twelve plain-control runs match each other. This localizes an observable difference after the separately measured raw/table exports; it does not capture the submitted surfaces or establish the cause. See the plan’s bounded localization proposal.

The first real raw invocation failed because the harness included `--master-display copy --max-cll copy`, which NVEncC rejects with codec raw. The failed report and original harness remain preserved. A corrected raw-only argument filter passed a two-frame smoke check; all real-source repeats restarted in a new directory. AV1 arguments were unchanged.

## Fresh deployed-binary profile

Nsight Systems 2026.1.3, shared RTX 5060 Ti; one trace per row. GPU durations are divided by declared output frames. They include startup/drain. Host synchronization durations overlap GPU work and are reported separately.

| Original development source | Decode / QVBR / frames | Bilateral GPU ms/frame | All FGS kernels ms/frame | Flat metrics ms/frame |
| --- | --- | ---: | ---: | ---: |
| Lost Tapes, 1080p SDR | avhw / 30 / 240 at 120 s | 0.499229 | 0.955566 | 0.253630 |
| Amphibia, 1080p SDR animation | avhw / 34 / 240 at 350 s | 0.500235 | 0.871542 | 0.252249 |
| Taxi Driver, 4K PQ HDR | avsw FFV1 / 29 / 24 | 1.979050 | 4.342247 | 1.104113 |

Lost Tapes records 502 stream synchronizations, totaling 1.509510 ms/frame of host wait; these must not be added to the kernel durations. Bilateral is 52.2% of its FGS CUDA time, and luma flat metrics alone are 24.7%. Production still has the two routine readback barriers. FFT3D sigma caching is irrelevant to this bilateral flow.

The 24-frame HDR fixture is a finite regression window from the original decoded base, not sustained hardware-decode performance. The shared engine was fully occupied during the Lost Tapes trace. Historical 44% utilization and a suggested 15–20% single-stream throughput gain are not reproduced by this measurement. No wall-clock fps claim is made.

## Matched plain NVENC controls

Every real profile includes ordinary NVENC on the same original input and video settings, removing FGS and selecting VBR to match measured video payload. Failed initial rate matches are retained.

| Source | FGS payload kb/s | Accepted plain target kb/s | Actual plain difference |
| --- | ---: | ---: | ---: |
| Lost Tapes | 2852.233 | 3108 | −0.389% |
| Amphibia | 2693.516 | 2779 | +2.891% |
| Taxi Driver | 22580.156 | 17200 | +0.755% |
| Gentlemen (identity control only) | 1992.312 | 1992 | +2.238% |

These controls support rate accounting and variability checks. They establish no grain-quality preference. A quality experiment must use source amplitude, high-frequency sigma and lag-1/2 autocorrelation together, occupancy-weighted per brightness band and for both color planes. Full-reference scores are only artifact guards.

## Qualification boundary

The unchanged full release gate requires the exact full-history Play Dirty source and its negative/plain/candidate artifacts. Their recorded paths are absent. The user suggested HDD cold storage. The completed offload size scan and September inventories found no recovery candidate; a broader physical filename search was time-bounded and incomplete. No global-absence claim is made. No missing gate is waived, and this baseline report is not a release qualification.

The companion improvement plan ranks the levers, gives confirm/kill measurements, and explains why broad retention should be parked. Any identical-output speed implementation must live on its own production-based branch and pass the repeated-state and full-gate requirements before handoff.

## Evidence

[Compact baseline receipts](evidence/2026-10-04-baseline/README.md), [state-set hashes](evidence/2026-10-04-baseline/identity.json), [build pins](evidence/2026-10-04-baseline/pins.json), and [cold-storage search](evidence/2026-10-04-baseline/cold-storage-search.md). Full evidence remains in the task workspace named by those receipts.
