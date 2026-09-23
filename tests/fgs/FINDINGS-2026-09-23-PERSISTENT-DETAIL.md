# Native persistent-detail protection — September 23, 2026

The CPU measurement, bounded GPU collector and seven-frame encoder diagnostic
are qualified on the declared controls. The current trial build is `04bd03aa`,
SHA `385790542b0b9a069dcaf3025bd1ab8e62652ba145e0823d6c820250be972da7`.
They do not select a new output model or change production. R3–R8 remain open.

Persistent source structure, including persistent grain, is protected as detail.
On each native Y64/C32 tile, compare the actual rounded candidate with current
source along two older source-only directions: means of the oldest three and
next four frames. Native luma is essential: averaging 2×2 pixels can entirely
hide alternating scanlines. The mean check is also available on one-pixel
borders, which have no spatial contrast anchor.

The frozen exploratory limits are 2% projected contrast change and 0.125 8-bit
code units of coherent removed RMS or mean error. Source/history correlation
must be at least 0.5 and history/history correlation at least 0.8 for an anchor.
These are development limits, not perceptual guarantees or HDR-light thresholds.
No R1 source classification or 8% variance/0.08 covariance model bound changed.

The complete Shining development frames 30 and 210 cover 12,240 native tiles,
including every border pixel, 24,883,200 source samples and 149,299,200 candidate
samples. All 73,440 C++/NumPy candidate comparisons pass. At retention 0.5, the
anchored detail conflicts number 4/11 Y, 80/78 Cb and 16/49 Cr for the two frames.
At 0.75 they number 0/0 Y, 5/6 Cb and 0/1 Cr. Full source has zero measured loss.
The 0.75 Y measurements do not change R1's existing luma proposal limit.
These are pre-fallback development candidates, not newly identified library defects.

All seven declared synthetic families add 1,344 C++/NumPy comparisons, including
lost persistent grain, lost/sharpened texture, fast motion and quiet copies.
A necessary projection check cannot establish that a residual is grain, recover
arbitrary moving structure or replace the other artifact/detail checks. Missing
anchors remain unknown. The selector evidence requires the complete canonical
native grid and exact current frame, clock, epoch, population, component,
retention and model/base identity. Its only effect is to remove clearance;
a passing projection cannot create or repair a full detail/model pass.

GPU qualification uses NV12, YV12, native planar 10-bit and P010, nonzero pitch
padding, interleaved offsets, one-pixel borders, invalid histories and native
code errors. The collector reads seven older complete source frames, has no
internal allocation/synchronization and caps each call at 512 tiles. The
optional encoder diagnostic uses a bounded seven-frame cache, explicit stream
ownership and complete invalidation on reset, discontinuity or failed update.
Ordinary mode allocates no new history or measurement buffers.

To request the diagnostic, add `"persistent_detail": true` to the existing
explicit joint-probe manifest. It writes native moment records for the requested
frames, with their source-history identities and fixed binary field offsets.
It neither changes the encoded picture/model nor approves retention.

Evidence lives in `roadmap-r3-persistent-detail-20260923/` (complete CPU study),
`roadmap-r3-persistent-gpu-20260923/` (GPU qualification) and
`roadmap-r3-persistent-integration-20260923/` (encoder lifecycle) under the
[local evidence root](/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/).
Read each final report before treating the corresponding GPU/runtime stage as
qualified. Actual selection/model integration and moving output qualification
remain the next work; these necessary measurements do not complete R3.

## GPU and encoder evidence

The final collector passes 321 cases: 82,944 valid tiles, 1,293 rejected tiles,
159,740,208 native samples, 432 one-pixel borders and 4,815 rejected invalid
calls. Mean/covariance error versus the independent reference is at most
2.85e-14/1.37e-12. All 690 candidate-component veto replays match the independent
reference. Native integral sums make covariance centering exact before
normalization; the earlier raw floating-average formulation produced a tiny
negative variance on constant borders. Its failed example is retained. The
strict PSD check and quality bounds were preserved. The reserved record word
is initialized so binary evidence contains no indeterminate padding.

The collector takes about 3.61 ms per full UHD candidate in this run, excluding
history copies, allocation, upload/download and encoder work. This is not an
end-to-end throughput or deployment-cost result.

Thirty-eight GPU history controls verify 7,182 native plane copies, startup,
rolling order, reset, cuts, skipped/repeated frames, clocks, incomplete updates,
stream ownership and the memory cap. The encoder comparisons cover 3,040
encoded frames across SDR, HDR, ordinary/automatic modes and explicit scene
cuts. The first revision adds 2,432 direct AOM/dav1d decoded observations, with
grain enabled and disabled. The corrected build preserves all their encoded
packet payloads, clocks and stream metadata; decoder evidence is reused only
after that exact equality and is not counted twice. Each runtime revision also
checks 53,305,344 native samples and 126 original-source plane matches.

The public AOM API control `AV1D_SET_SKIP_FILM_GRAIN` is used for grain-disabled
comparisons. The tested system FFmpeg AOM wrapper did not suppress grain when
asked to export its metadata; that attempted control is retained as invalid
comparison evidence. `tests/fgs/aom_decode_hash.cpp` now provides an explicit
finite comparison against the pinned AOM 3.14.1 library.

All owned GPU pauses are released and current Tdarr limits preserved. The
reserved qualification corpus remains unopened. D27 continues the application
of the new veto alongside independent detail/model checks: flat independent
grain has no persistent contrast anchor, so absence of that anchor cannot serve
as its own admission or replace complete independent evidence.

## Applying the veto alongside independent evidence

D27's actual flat-grain runtime captures have 32,768 source-supported colour
pixels per component yet no persistent contrast anchor. Mandatory anchors
would block them despite that separate source evidence. Source support alone
still does not prove a complete candidate or synthesized picture.

The default helper remains strict. An explicit `UseIndependentCandidateChecks`
mode may preserve already complete, independently established candidate,
detail, model, native-range and whole-picture coverage checks when missing
anchors are the only unresolved projection result. Its changed-sample count
must agree with the native measurement. It never creates or repairs check bits.
Observed losses, invalid/stale/partial evidence, failed/unmeasured checks,
insufficient independent blocks and R1 quiet/rejected/border restrictions still
reject. Unknown samples and use of independent evidence remain reported.
This is a host-policy integration prerequisite, with no new encoder output call
sites or population/model admission. The full CPU suite passes 214 Python tests
in 30 suites and 32 C++ programs.

D26's cleanup receipt removes 2,676,847,441 bytes of completed scratch. Duplicate
native planes are mapped by hash to the retained v2 captures. Current build,
active model-work inputs, ordinary comparison outputs and one small AOM control
remain available; protected originals and reserved sources are unchanged.
