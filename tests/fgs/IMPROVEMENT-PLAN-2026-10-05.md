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

1. Add a diagnostic trace of each submitted picture, off by default with no disabled-path readback, hashing, allocation or synchronization; copy exact per-picture AV1 grain parameters before submission and read the same owned immutable surface after successful encode completion and unmap, before reuse, respecting the SDK access contract; validate raw/table/output behavior under the existing variability.
2. Repeat production traces on Lost Tapes, Taxi and Gentlemen; begin with three runs per arm and extend only as needed to expose an IVF difference, with a maximum of six new repeats per case before reporting the finite observation. If identical submitted pictures/parameters accompany different IVFs, document NVENC/driver variation and stop that investigation; a bounded upstream divergence may be localized, but an output-changing fix needs the user's OK.
3. Apply the same trace to the kernel candidate, prove stable per-frame submission identity, run CPU and unchanged full gates using regenerated complete Play Dirty histories, then measure alternating production/candidate single-stream and three-stream throughput on a quiet GPU; report library encode-time savings using the supplied 91% 1080p hour share and explicit limits for the remaining 9%.
4. First measure unwanted synthesis on held-out originals, weighted toward 1080p clean digital and animation: grain on clean pictures/shots, frame-to-frame switching or strength jumps, and excess within occupied brightness bands; compare source and synthesized strength per frame in Y/Cb/Cr, report incidence and magnitude, and allow legitimate animation fills as clean-safety evidence while excluding bars.
   The library-file inventory is owned by a separate agent and is excluded from this task.
   Then retain the original amplitude/HF/lag/occupancy census and SDR/HDR separation as supporting evidence, including the historical 0.63 hypothesis where the sample can test it. A confirmed unwanted-grain case outranks fidelity-distance work.
5. Write a bounded fix plan for the largest supported defect with matched-rate controls and kill criteria, then stop for the user's go.

Readback overlap is considered only if the three-stream results show per-stream latency limits aggregate throughput; a measurable small kernel gain alone does not justify another release.

## Pins and placement

Production remains core `aeb14263`, image `nvenc-fidelity/tdarr-node:2.94.02-aeb14263-20261004`; kernel runtime is `6e8fa1fb`, retained on `perf/fgs-prod-filter-kernels-20261004` at documentation head `0a5b5594`. This continuation is `qualify/fgs-prod-kernels-20261005`, descended from that production-based candidate. Trace-only production diagnostics use a separate prod-based branch. Builds use immutable local clones in the pinned `nvenc-fgs-build:cuda13.3` image, with a full clean baseline build and cache reuse only where dependency review proves the reused objects are unaffected.

New scratch is `/tmp/downloads/codex-work/fgs-submission-20261005`, peak budget 140 GiB. Initial free space was 207 GiB there, 58 GiB on home, 44 GiB on opt and 143 GiB on Docker. The private Play Dirty copy is `original-fixtures/play-dirty-source.mkv`, 8,667,928,469 bytes, SHA256 `d4a348ec7afc3dd22a66a492f2c804a49392ba8de1afc5aa244c548f4e15934d`; verified independently at 06:37:49 UTC, mode 0400, original metadata unchanged. All later reads use this copy.

## Decision log

- 2026-10-05 auto: Apply the approved submission-trace identity rule; plain controls are limited to quality/size claims, retention is parked, and Tdarr pause is limited to the authorized timing window.
- 2026-10-05 auto: Copy the space-named Play Dirty original first; the prior dotted-filename search missed this valid file and did not establish absence.
- 2026-10-05 auto: Begin submission comparisons with three repeats on Lost Tapes, Taxi and Gentlemen, extending only to expose a differing IVF and never repeating the prior state-union hunt.
- 2026-10-05 auto: Preserve the initial trace build failure and correct the existing context-lock macro invocation in a new commit, then rebuild all objects from a fresh pinned clone.
- 2026-10-05 auto: Reuse the verified private Play Dirty copy for full histories, with explicit candidate SHA/core pins and tracing disabled.
- 2026-10-05 auto: Prepare task 4 with source-only reviewed native Y/Cb/Cr masks, occupancy and amplitude/HF/lag diagnostics on six pinned originals; keep HDR separate, treat 0.63 as an unverified historical hypothesis, and validate the ruler with generated arrays before any media/GPU execution.
- 2026-10-05 auto: Keep the grain census source-aligned using actual decoded timestamps and frame-offset controls, rather than assuming requested seek times identify the first encoded frame.
- 2026-10-05 auto: Fit SDR and PQ grain response separately, exclude clean animation from natural-grain fits, and use matched-rate plain controls only in the proposed later quality or size experiment.
- 2026-10-05 auto: Reuse the finished immutable production-trace build cache for the candidate because the runtime diff is only FilmGrain.cu and all trace headers, configuration and dependency pins match.
- 2026-10-05 auto: Keep the synchronous trace trial as inconclusive neutrality evidence after six Lost Tapes repeats, and defer diagnostic hashing until drain to reduce its submission-timing disturbance without changing captured bytes or the gate.
- 2026-10-05 auto: Rebuild deferred tracing from a fresh immutable cache clone with tracked host dependencies because the audited include closure contains three C++ units and no CUDA units.
- 2026-10-05 auto: Reuse three completed deployed instrumentation IVFs for the initial task-4 census (32/32/24 frames, 2.78 GiB); extract source display PTS with existing --y4m-timestamp and require independent native-pixel offset checks before scoring.
- 2026-10-05 user: Prioritize synthesized grain absent from the source, temporal switching/jumps and brightness-band excess on held-out 1080p digital/animation originals, and inventory September library audit flags read-only before proposing any fidelity-distance fix.
- 2026-10-05 user: Remove the library-file inventory from this task because a separate agent owns that scan, while retaining the held-out clean-safety and temporal priorities.
- 2026-10-05 auto: Copy four provisionally held-out NVMe originals independently and verify destination hashes; raise the scratch peak budget to 140 GiB after confirming more than 90 GiB of remaining-work headroom beyond the 44.56 GiB copies.
- 2026-10-05 auto: Add Toy Story 5 after source-only Knightfall inspection showed mixed fine texture and plain fills, freeze five titles at10/40/70percent with12second context/evaluation windows, and exclude Insidious mattes from source masks.
- 2026-10-05 auto: Task4 clean-safety priority uses every-frame streaming source-only masks with flat fills retained, exact played-base RMS/nonzeros without a floor, and adjacent source-relative/stationary temporal diagnostics with eligibility coverage; only generated-array controls executed.
- 2026-10-05 auto: Correct the diagnostic to snapshot grain metadata at submission and read the same owned surface only after completed encoding and unmap, because the SDK forbids access while mapped; preserve prior receipts as provisional.
- 2026-10-05 auto: Strip ANSI log escapes before the unchanged exact frame-count check and finish independent decode/hash verification of the completed Play Dirty negative instead of needlessly re-encoding it.
- 2026-10-05 auto: Freeze fifteen held-out windows across five titles plus three original regression windows, keep source selection independent of measured errors, and count all retained raw windows against the 12 GiB cap.
