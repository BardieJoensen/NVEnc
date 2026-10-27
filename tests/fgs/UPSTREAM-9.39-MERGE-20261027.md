# Upstream 9.39 merge into the FGS release line, 2026-10-27

Branch `prod/merge-upstream-9.39-20261027`: merge commit d1d4f77e = production line
`prod/merge-upstream-9.38-20261008` (7a3336c6; runtime f1327e14) + rigaya master 33f54186
(tag 9.39, 29 commits after ce3890cc). No textual conflicts.

Upstream content: the RTGMC search-prefilter repair path rewritten as staged passes (upstream
reports bit-identical output; it only matters for presets that use the repair, such as
`preset=slower`), the prefilter cache pool that grew with stale SourceTwin entries (f541c6f5,
measured upstream on `--vpp-kfm`), RTGMC attached-data release on the CUDA side (c22dd59e),
retouch, shimmer-repair, degrain and KFM speedups and fixes, the raw output thread that could exit
with frames still queued (9e441bdb), and `cltask` thread control.

One manual resolution: the auto-merge placed the fork's `wait_for_push()` (1bc791b7) inside
upstream's new post-loop drain in `WriteThreadFuncRawVideo`, where `thAbort` is always set, so it
was dead code. Upstream's event wait replaces it and the function now equals 9.39. The flow's mkv
mux does not use the raw-output thread. The fork's degrain causal/cache changes and the DV P7
profile mapping are unchanged by the merge.

## Build

Pinned clone, gate recipe (`nvenc-fgs-build:cuda13.3-deps`, `-Denable_vmaf=disabled
-Denable_libvship=disabled`): NVEnc 9.39 (r4443), sha256
`904b9c1b04887cc600d575d23e51718d22eb74b63325f3557af56790f467e8e3`.

Put the pinned clone on SSD (`PIN_ROOT=…`). The default `~/.cache/fgs-gate/builds` is a symlink
into cold storage on the HDD pool since 2026-09-28; during the LUKS precopy the final link sat
in disk wait for over 20 minutes and was abandoned.

## Tests

- `tests/fgs/run_cpu_tests.sh`: 119 Python tests and all C++ programs pass.
- `local_gate.sh --quick --candidate-nvencc`: 4 passed, 1 failed. The failing stage is
  `test_training_lookahead.py`, sub-tests `count=1` (8 and 10 bit): a one-frame y4m input exits
  with `Invalid fps: 0/1001`. The production binary f1327e14 fails the same two sub-tests the same
  way today, although it passed this stage on 2026-10-08, so it is not a merge effect. The avsw
  reader estimates the average frame rate from frame durations, and one frame gives 0. Every
  production input has many frames.

## Qualification against production f1327e14

The flow's current (v49) NVEncC argument template, run inside the live node image
`3.01.00-f1327e14-20261016` with each binary mounted. Clips were cut once from the original downloads:
Gentlemen S02E08 WEB-DL (h264, avhw), HotD S03E08 DV P8 2160p (`--dolby-vision-rpu copy`), HDR10+
(hdr10plus_tool `regular.mkv`, `--dhdr10-info copy`), Bad Guys 2 AVC remux with TrueHD/AC3/PGS on
avsw, on avhw and through `--vpp-rtgmc order=tff`, The Young Ones S01E06 1080i25 remux (real woven
TFF, the flow's RTGMC path: avsw, no timestamp passthrough) at 30 s and 180 s, a Felicity XviD AVI,
and the pinned lossless Gentlemen clip (`gentlemen-source-33m-150s.mkv`, 3,600 frames).

| Case | Packets (all streams) | Frames, libdav1d errors | Old fps | New fps | Peak VRAM MiB | Peak RSS MiB |
|---|---|---|---|---|---|---|
| WEB-DL h264 avhw | identical | 635 / 635, 0 | 152-155 | 152-154 | 917 / 917 | 859 / 860 |
| DV P8 2160p | identical | 293 / 293, 0 | 47.5 | 46.7 | 2605 / 2605 | 1859 / 1855 |
| HDR10+ | identical | 259 / 259, 0 | 615 | 629 | 292 / 292 | 443 / 443 |
| AVC remux avsw | identical | 499 / 499, 0 | 147 | 143 | 833 / 843 | 1068 / 1070 |
| AVC remux avhw | identical | 499 / 499, 0 | 152-154 | 152-154 | 917 / 917 | 939 / 940 |
| AVC remux, rtgmc | identical | 998 / 998, 0 | 159 | 155 | 3295 / 3315 | 1174 / 1184 |
| Young Ones 1080i, 30 s | identical | 1534 / 1534, 0 | 159.1-160.4 | 154.7-156.4 | 3295 / 3315 | 1165 / 1158 |
| Young Ones 1080i, 180 s | identical | 9052 / 9052, 0 | 164.0-164.3 | 160.0-160.3 | 3295 / 3315 | 1185-1193 / 1202-1217 |
| XviD AVI | identical | 739 / 739, 0 | 538 | 524 | 221 / 211 | 488 / 489 |
| Lossless Gentlemen, 150 s | 2 of 2 matched pairs identical | 3600 / 3600, 0 | 147.8-151.7 | 146.4-151.8 | 843 / 833-843 | 1592 / 1592 |

- **Output:** packet-identical in every stream on every path. Stream metadata, per-stream start
  times and durations (A/V offsets) are identical. RTGMC output is progressive (idet 0 woven on the
  Young Ones outputs) and lossless RTGMC output (HEVC `--lossless`) is identical too, so the
  deinterlacer itself did not change on the flow's preset.
- **Lossless Gentlemen:** both binaries produce more than one packet state run to run. Under the build's
  CPU load the first old and the first new run each gave a different state; the next two old/new
  pairs were identical. This is the known grain-analysis repeat variability, not a merge effect.
  Scores against the lossless source (1,800 frames, CUDA VMAF + FFVship): common state VMAF 96.04,
  NEG 94.88, PSNR-Y 49.19, SSIMULACRA2 85.67, Butteraugli 0.623 (max p95 4.06); the candidate's other
  state 96.05 / 94.88 / 49.20 / 85.69 / 0.623 (4.05); production's other state
  96.05 / 94.88 / 49.20 / 85.68 / 0.623 (4.03).
- **Speed:** on the RTGMC path the candidate is consistently about 2.5% slower (interleaved runs:
  180 s clip 164.0-164.3 → 160.0-160.3 fps, 30 s clip 159.1-160.4 → 154.7-156.4 fps), with
  +20 MiB VRAM and about +20 MiB RSS. On the other paths the differences are within run-to-run
  noise (interleaved WEB-DL and avhw remux within ±1%; lossless Gentlemen means 149.4 and
  147.9 fps over four runs each). RTGMC alone with HEVC lossless output ran 294 → 299 fps in one
  run each, so the cost appears only when RTGMC shares the GPU with FGS analysis and the AV1 encode.
- **Fixed issues on our paths:** none visible. Peak VRAM does not grow from 30 s to 180 s with
  either binary (3295 MiB old), so production's RTGMC preset does not show the cache-pool growth
  that f541c6f5/9292f401 fix (measured upstream on KFM). The raw-output fix does not apply to the
  mkv mux.
- **Candidate image** `nvenc-fidelity/tdarr-node:3.01.00-d1d4f77e-20261027` (f1327e14 image +
  this nvencc, sha-checked): WEB-DL, DV, Young Ones RTGMC, XviD and avsw remux outputs
  byte-identical (all streams) to the mounted-binary runs.

## Verdict

The output is identical on every flow path and nothing regresses functionally. Production gains
nothing it uses today: the fixes cover KFM, `preset=slower` RTGMC and raw output. RTGMC jobs (12
in the Tdarr 2.94/3.0x job reports, all The Young Ones) run about 2.5% slower. Not deployed: the
deployment rule was a clean pass, and this has a measurable RTGMC slowdown plus a quick gate that
is not green (pre-existing). Deploying gives the same encodes and keeps the line current for the
next merge; the user decides.

Receipt: `/opt/docker-apps/logs/nvencc-merge-9.39-20261027` (binary, build/test/gate logs, packet
hashes, per-run fps/RSS/VRAM, comparisons, scores, candidate Dockerfile). Work dir:
`/tmp/downloads/codex-work/nvenc-939-20261027`.
