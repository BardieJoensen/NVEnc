# Native persistent-detail protection — September 23, 2026

The CPU measurement and selector veto are implemented. The bounded GPU collector
and seven-frame encoder diagnostic are implemented but are still being qualified.
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
