# Compressed-base reconstruction and colour-model qualification

The explicit NVENC reconstruction probe is qualified on Linux build `d0ad6818`.
It supplies the actual compressed base for research without a second decoder.
It does not yet select retention or correct a grain model at runtime.
Production remains ordinary `cb903a17`; retention and FEL are off.

## Why the actual base is needed

D31's table-driven controls showed that lossy compression removes residual grain
which the pre-encode model expected to survive. D32 therefore refitted from the
actual grain-off decoded picture. Native luma passed all 96 declared seed checks,
but neither complete colour model passed every check on any seed. Spatial colour
covariance and Cb/Cr correlation remained outside the unchanged 0.08 limits.
This rejects the complete candidates; improved luma alone is insufficient.

D34 then calibrated total displayed variance separately for each actual seed,
using training tiles only and including base/grain cross terms. All valid colour
calibrations met the training variance bound. Spatial covariance still failed:
no seed passed both spatial halves and the mean bound in either depth. One
8-bit calibration rejected nonmonotone evidence. These are constructive
development controls, not a claim of newly damaged production files.

## Reconstructed-picture capture

`--film-grain-recon-probe` is explicit and disabled by default. A bounded manifest
requests at most 16 frames and caps host output and device allocations. The
probe supports progressive NV12/P010, synchronous Linux AV1 and a queried
reconstruction capability. Unsupported configurations fail before encoding.
NVIDIA documents reconstruction registration and the requirement to unmap
before CUDA access in its [NVENC programming guide](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/nvenc-video-encoder-api-prog-guide/#nvenc-reconstructed-frame-output).

Qualification found and corrected two bugs in the new diagnostic:

- Normal pipeline drain could finish successfully with a requested frame missing.
  The common completion path now requires every requested capture and matching
  submitted/received counts; missing frames fail the encode.
- Sparse reconstruction surfaces could contain later reordered pictures. In the
  10-bit control, labels 46/47 initially held pictures 49/50. Keeping a distinct
  reconstruction surface live for every input fixes all declared controls; only
  requested pictures are downloaded. The encoded media stayed unchanged even
  in the failed diagnostic. The observed API display ID is zero in this mode;
  matching uses the locked frame ordinal and timestamp.

Ten final encodes cover 800 frames: 8/10-bit grain tables, reordered AV1, explicit
scene cuts and UHD HDR with lookahead. Both decoders agree in both grain modes
across 1,600 fresh observations. All 45 native captures match grain-off decoding
exactly, totalling 75,970,560 samples. All packet payloads, clocks and metadata
match the controls with the probe on and off. Six negative cases reject duplicate
IDs, host budget overflow, device budget overflow, absent requested frames,
existing output directories and an unsupported codec.

Peak reconstruction allocation was 1,293,926,400 bytes in the declared UHD
lookahead case. This is a measured diagnostic cost, not a qualified automatic
retention overhead. The full CPU pass covers 214 Python tests in 30 suites and
36 C++ programs; the later device-budget parser change has its targeted pass
and the actual failure control. Ordinary mode allocates no probe surfaces.
Tdarr's existing work drained, its pause was released and current limits were
preserved. No experiment restarts automatically.

## Evidence and remaining work

Under the local `colour-recovery-20260922` evidence root, read:

- `roadmap-r3-decoded-base-20260923/report.json` and `synthesis.json`.
- `roadmap-r3-seed-calibration-20260923/manifest.json` and `report.json`.
- `roadmap-r3-reconstruction-20260923/report.json`, `v3/encodes.json`,
  `v3/comparison.json` and `v3/drain-pause.json`.
- `reconstruction-mismatch.json` and `display-trace/` within the reconstruction
  directory retain the failed sparse-buffer evidence.

The qualified binary is `/tmp/downloads/fgs-retention-r1-r2-20260922/build-d0ad6818/nvencc`,
SHA256 `da03376bbeb96a431a628a1fa6ee4836e4df743fbb40694e0f5271844890498a`.
Continue with finite-template colour-shape correction and representability,
then actual automatic call sites. Unsupported real populations, temporal
transitions, unseen quality, storage cost, speed and the Tdarr canary remain
open in R3–R8. The reserved qualification corpus remains unopened.

## Complete model output and bounded seed proposals

D35 applies at most two training-only covariance counterterms to the proposal
shape. Original source evidence remains separate: the adjusted covariance is
an artificial fitting target, never new source evidence. One of 16 10-bit seeds
passes both spatial halves and the mean check; none of the 16 8-bit seeds passes.
Most remaining failures concern spatial Cb/Cr covariance. This is a constructive
feasibility result, with no general model admission.

D36's [manual model writer](MODEL-OVERRIDE.md) carries that passing model into
the existing NVENC video. Independent AOM/dav1d outputs match all 786,432 oracle
samples; the 16 compressed base pictures and other 15 displayed pictures stay
unchanged. Reordered SDR/HDR and reference-reuse controls add 1,472 fresh decoded
observations, ten expected failures and a detected omitted-reference-guard
mutation. A later source-hash binding and grain-free-reference no-op correction
preserve every previously qualified output byte. This is manual IVF research,
not a new automatic encoder path or a Dolby Vision container qualification.

D37's arbitrary finite seed search passes only one of eight fixed banks, after
118 tested seeds. D38 adds a template mean/cross-colour screening proposal.
Six independent AOM/NumPy comparisons and 12 invalid controls verify its math;
actual final source checks remain mandatory. Screening 4,096 seeds takes about
1.9 seconds per control. Of two subsequent 16-candidate banks, the 10-bit one
passes and the 8-bit one falls back. This is not reliable or fast enough for
per-frame deployment. The helper grants no quality bits and has no runtime calls.

Current Tdarr already specifies `--output-depth 10` for SDR as well as HDR.
D39 therefore compares promoted 8-bit originals, promoted 8-bit rounded retention,
and retention rounded directly at native 10-bit precision. It uses declared
constructive controls and actual NVENC reconstruction before any new fitting.
All three now have passing constructive proposals and exact actual-output
serialization. The [subsequent metric calibration](FINDINGS-2026-09-23-GRAIN-METRICS.md)
separates per-picture variation from pooled shape checks and retains every
original failure. Continue D42 and the roadmap.

Read `roadmap-r3-template-correction-20260923/report.json`,
`roadmap-r3-model-output-20260923/report.json` and `hardening-v2/report.json`,
`roadmap-r3-seed-selection-20260923/report.json`, and
`roadmap-r3-template-seed-proposal-20260923/summary.json` in the local evidence root.
