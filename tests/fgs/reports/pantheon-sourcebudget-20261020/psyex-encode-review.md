# R8 PSYEX encode-runner review

Reviewed `encode_psyex.py` SHA-256 `61727e5dc3175f47ddf8427dc40516e2d9d6331b4a73b6d7c954a15bcc2bc75a` and `ROUND8_POLICY_CONTRACT.md` SHA-256 `98a6152148a7818cdf60c7a27e8046ee42a34b2249639ce1340bbda0ede9bb74`. No encode or preview was run.

## Disposition

**Block first encode pending three focused corrections.** The two-pass flow, fixture binding, rate calculation, resource bounds, and failure handling are otherwise fit for the contract.

### 1. The contract's app/library hashes are not pinned

Lines 97-103 trust the live `build-artifact-hashes.txt` after checking each artifact against that same live file. A self-consistent replacement/rebuild of the binary, library, hash file, and build receipt would pass because the script has no expected app or library digest. This defeats the explicit build identity in contract lines 49-50.

Add constants and exact assertions for:

- app `f4867ae287fa34cc50f927b7aa52611973adbc7231785117e5d32ce077b2461c`
- library `cd408a2f31f871cf9da924dd943607e2b8aa2e5366e513fc82d959434414f20b`

The existing reviewed build-runner SHA, source-manifest SHA, complete artifact rehash, terminal receipt, and `ldd` resolution can remain. Pinning the two executable artifacts is the smallest sufficient correction.

### 2. Effective pass-2 assertions accept the wrong prediction structure and bitrate

Line 181 stops matching immediately after the slash following `VQ`, so it accepts any logged prediction structure. Line 182 proves VBR but not that the effective target equals `request_kbps`. The source prints both values (`enc_settings.c:1168-1177,1205-1207`). Require exact pass-2 matches for `4 / VQ / random access` and `VBR / <request_kbps>`. Also assert the printed 10-bit/YUV420, 1920x1080/24:1, GOP240/mini-GOP16/key-frame tuple, AQ2/variance2/octile5/curve0, sharpness1, TF1, QP-compress1, noise-normalization1, keyframe-TF1, psy-rd1.00, spy-rd off, and noise-adaptive filtering off. These values are already emitted; checking them catches parser overrides without duplicating later runtime counters.

`sharp-tx`, `hbd-mds`, `complex-hvs`, QM, and automatic filter state are not all printed here. Their literal command, pinned source support, and later admitted runtime/config trace can bind them; the runner need not invent a new probe.

### 3. Loader/resource commands are PATH-dependent and unbound

The encoder is absolute, but lines 115 and 143 execute `ldd`, `nice`, and `taskset` through inherited PATH. Use `/usr/bin/ldd`, `/usr/bin/nice`, and `/usr/bin/taskset`, add them to `identity_paths`, and therefore verify them before each pass and after completion. This makes the recorded private-library resolution and CPU/niceness bounds belong to the actual commands.

## Verified behavior

- Input SHA, full Y4M header, historical exact-lift receipt, 336 frames, 1920x1080, 24 fps, and 10-bit 4:2:0 are checked at lines 104-112. The fixed cap is read and asserted as 9.6765224 Mbps.
- Every public policy flag exists in the pinned source parser. `enable-cdef=-1` and `enable-restoration=-1` are legal automatic sentinels (`enc_settings.c:496-508,1004-1006`). Separate `--pass 1`/`--pass 2` is supported: with one app pass, `app_main.c:233` retains the explicit `config.pass`, and the shared fresh stats file supplies pass 2.
- The run directory is fresh and scratch-only. The environment rejects loader/observation overrides, sets the private library directory, and records exact commands. Nice 10, CPUs 0-7, `lp=1`, and a 130 GiB free-space floor bound resources.
- Pass 1 requires absent stats, successful return, and nonempty output; pass 2 requires the pass-1 hash before and after. Per-pass logs, return codes, UTC intervals, and monotonic durations are preserved. Exceptions rewrite status to `failed`.
- Remux uses the fixed system FFmpeg without re-encoding. Stream codec, dimensions, pixel format, limited BT.709 metadata, 24 fps, reconstruction size, 336 unique cadence-aligned packets, and positions 96:336 are checked. The practical decision uses MKV packet payload sizes and enforces 99-100% of source; lower/over-cap runs remain `rate_gate_failed` for later explicit handling.
- Identity is checked before each pass and after the full run. Calibration changes only the requested TBR; policy values are immutable in the script, and no quality input is read.

One useful nonblocking addition is to assert identical per-position IVF/MKV packet sizes after stream copy and store an identity for `pass1-stats.snapshot`. Both artifacts are already retained and the decisive rate correctly uses MKV, so neither omission changes the present rate result.

## Focused re-review — 2026-10-20

Reviewed `encode_psyex.py` SHA
`9e0f9ccb827112c75b7654d44117f996adcb52fda167e871f4283b9c5f12a1d8`.
The three blocking findings above are resolved:

- Lines 105–106 pin and assert the reviewed app and loaded-library hashes.
- Lines 196–212 require one exact match for each of the 14 effective pass-2
  configuration rows, while the measured command retains the complete literal
  policy.
- Lines 125–128 and 152–157 use absolute, identity-bound `ldd`, `nice`, and
  `taskset`, and assert the private SONAME resolution.

The late cpuinfo provenance correction is also sufficient for this already
built binary. Lines 107–113 pin the audit and 570-file manifest and rehash every
nested tracked file; lines 141–152 carry the supplement into the receipt and
before/after identity chain. Independently checked supplement hashes are
`697dd77268d11f1f8a1a5003f6f6e05e1206d3686904fa3b1f05e5b499a43190`
(audit) and
`2374575a0aba9b941152770a2374ec048eb540868366bbbb46df846896a4a63f`
(manifest). The audit establishes clean commit
`e649baaa95efeb61517c06cc783287d4942ffe0e`, 570 files, the pinned CMake recipe,
and build.ninja's compiled-source binding. Together with fixed final app/library
hashes this supports use without rebuilding. It is correctly described as a
post-build supplement, not a pre-build nested manifest.

One documentation correction remains: `ROUND8_POLICY_CONTRACT.md:21` still
calls the 1,217-file root manifest “complete,” although lines 54–62 later correct
that statement. Call it the “root-tracked 1,217-file manifest”; similarly scope
lines 45–47 to the root checkout plus the later nested audit. This wording defect
does not affect execution.

Erratum to the earlier nonblocking suggestion: IVF and Matroska packet payload
sizes need not be equal because remux can remove AV1 temporal-delimiter OBUs.
Lines 224–232 now do the right thing: retain both packet populations and their
per-position deltas, and consistently apply the practical rate gate to Matroska.
The stats snapshot now also has a retained identity.

**Runner status: accepted for the first encode.**
