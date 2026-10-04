# Upstream 9.37 merge into the production line, 2026-10-04

Branch `prod/merge-upstream-9.37-20261004`: merge commit aeb14263 = production
line 06659e92 (d32b6270 core + test-only commits) + rigaya master 0b433672
(9.34 to 9.37, 68 commits). Textual conflicts were limited to
`NVEncC_Options.zh-cn.md` (both sides added sections; kept both) and
`build_deb.sh`/`build_rpm.sh` (both replaced the version lookup; took upstream).

## Build

`tests/fgs/local_gate.sh` pinned-clone recipe (`nvenc-fgs-build:cuda13.3-deps`,
`-Denable_vmaf=disabled -Denable_libvship=disabled`). Candidate sha256
`c6cbd528…`; control build of 06659e92 with the same recipe `b501c76f…`.
The deployed d32b6270 binary (`d158b1e1…`) came from the plain `cuda13.3` image and
reports `libplacebo: no`; the gate recipe reports `yes`. No flow argument uses
libplacebo and the outputs below do not depend on it.

## Encode comparison

The flow's exact NVEncC arguments, run inside the live node image, on seven
paths: h264 WEB-DL (avhw), DV profile 8 HEVC 2160p with `--dolby-vision-rpu copy`,
HDR10+ with `--dhdr10-info copy`, AVC Blu-ray remux with TrueHD + AC3 + 45
subtitle tracks on avsw and on avhw, the same remux through `--vpp-rtgmc`, and an
XviD AVI. Every output packet of every stream was hashed (`ffmpeg -f framemd5`),
and stream metadata compared with ffprobe.

| Path | Result |
| --- | --- |
| WEB-DL, DV, HDR10+, rtgmc | candidate, control and d32b6270 packet-identical in every stream |
| AVC remux avsw / avhw | video alternates run to run between two packet states for d32b6270 itself (avsw: `fb0314ca…` 3 of 5 runs, `cf2f83f4…` 2 of 5); the candidate produced both (1 and 4 of 5); avhw single runs: d32b6270 `fb0314ca…`, candidate `cf2f83f4…`; all audio and subtitle packets identical |
| XviD AVI | same pattern: d32b6270 produced `35d02c6e…` (1 of 4) and `9a26b855…` (3 of 4), the candidate `9a26b855…` (4 of 4) |
| Stream metadata | identical on all paths, including the DOVI configuration record and per-frame HDR10+ (543/543 frames) |

The two-state alternation is the grain-analysis repeat variability recorded as
open work in WORK-TO-PRODUCTION.md, not a merge effect: it reproduces with the
unchanged d32b6270 binary.

Upstream's #805 fix (TrueHD PTS rounding with `--audio-copy`) does not change the
TrueHD packets on this remux; the flow's unlace plugin and validator tripwire stay.

The GMC fallback function and its call site in `rgy_input_avcodec.cpp` are
byte-identical after the merge. No GMC source remains on disk to exercise it.

`local_gate.sh --quick --candidate-nvencc`: 5 passed, 0 failed.

Receipt with hashes, probes and logs: `/opt/docker-apps/logs/nvencc-merge-9.37-20261004`.
Deployed as `nvenc-fidelity/tdarr-node:2.94.02-aeb14263-20261004`; rollback binary
`/opt/docker-apps/build/tdarr-node/nvencc-d32b6270`.
