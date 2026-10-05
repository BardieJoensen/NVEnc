# Approved continuation — 2026-10-05

The user approved the October 4 plan with a new identity rule: compare the actual submitted picture and grain parameters within each encode. A rare IVF state missing from a finite sample no longer blocks an FGS-only change. The kernel candidate saves about 0.12 ms of GPU work per 1080p frame; this continuation measures whether that saves library encoding time and identifies the largest remaining grain defect.

## Approved changes and scope

- Matched-bitrate plain controls are required for quality or size claims only; do not run them for identity or timing work.
- The user deliberately replaces historical IVF-state-union admission with stable, identical per-frame NVENC submission traces between production and candidate; IVF/decoded hashes are informational.
- Preserve October 4 receipts as results under their historical contract, rather than rewriting them as passes under the new rule.
- R3–R8 retention is parked; preserve its branch and negative evidence and do no further work on it.
- The exact Play Dirty original used spaces in its filename and was already present; the prior dotted-name search missed it.
- Only task 3 may pause Tdarr, using the existing owned-pause procedure, for at most two hours total including drain and restoration; leave the Emby watchdog alone.
- No deployment, push, torrent action, library mutation, reserved-corpus access, FEL or review clips.

## Ordered work

1. Add a diagnostic trace immediately before NVENC submission, off by default with no disabled-path readback, hashing, allocation or synchronization; record submitted surface layout/pixels and exact per-picture AV1 grain parameters, and validate that instrumentation preserves raw/table/output behavior under the existing variability.
2. Repeat production traces on Lost Tapes, Taxi and Gentlemen; begin with three runs per arm and extend only as needed to expose an IVF difference, with a maximum of six new repeats per case before reporting the finite observation. If identical submitted pictures/parameters accompany different IVFs, document NVENC/driver variation and stop that investigation; a bounded upstream divergence may be localized, but an output-changing fix needs the user's OK.
3. Apply the same trace to the kernel candidate, prove stable per-frame submission identity, run CPU and unchanged full gates using regenerated complete Play Dirty histories, then measure alternating production/candidate single-stream and three-stream throughput on a quiet GPU; report library encode-time savings using the supplied 91% 1080p hour share and explicit limits for the remaining 9%.
4. Measure production grain against original SDR/HDR sources: amplitude, HF sigma and lag-1/2 autocorrelation, occupancy-weighted brightness bands and each of Y/Cb/Cr; validate masks, reference-self and single-variable controls, reassess the historical amplitude exponent, and rank defects by reach and size.
5. Write a bounded fix plan for the largest supported defect with matched-rate controls and kill criteria, then stop for the user's go.

Readback overlap is considered only if the three-stream results show per-stream latency limits aggregate throughput; a measurable small kernel gain alone does not justify another release.

## Pins and placement

Production remains core `aeb14263`, image `nvenc-fidelity/tdarr-node:2.94.02-aeb14263-20261004`; kernel runtime is `6e8fa1fb`, retained on `perf/fgs-prod-filter-kernels-20261004` at documentation head `0a5b5594`. This continuation is `qualify/fgs-prod-kernels-20261005`, descended from that production-based candidate. Trace-only production diagnostics use a separate prod-based branch. Builds use immutable local clones in the pinned `nvenc-fgs-build:cuda13.3` image, with full object rebuilds when headers change.

New scratch is `/tmp/downloads/codex-work/fgs-submission-20261005`, budget 80 GiB. Initial free space was 207 GiB there, 58 GiB on home, 44 GiB on opt and 143 GiB on Docker. The private Play Dirty copy is `original-fixtures/play-dirty-source.mkv`, 8,667,928,469 bytes, SHA256 `d4a348ec7afc3dd22a66a492f2c804a49392ba8de1afc5aa244c548f4e15934d`; verified independently at 06:37:49 UTC, mode 0400, original metadata unchanged. All later reads use this copy.

## Decision log

- 2026-10-05 auto: Apply the approved submission-trace identity rule; plain controls are limited to quality/size claims, retention is parked, and Tdarr pause is limited to the authorized timing window.
- 2026-10-05 auto: Copy the space-named Play Dirty original first; the prior dotted-filename search missed this valid file and did not establish absence.
