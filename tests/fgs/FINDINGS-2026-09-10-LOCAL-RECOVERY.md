# Local grain recovery and Tdarr acceptance

Status: **development controls qualified; final build, full-source acceptance
and Tdarr canary in progress**. This report does not close the broader
[work through production](WORK-TO-PRODUCTION.md).

Evidence directory:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/auto-retention-production-20260910`.
Scratch and decoded controls:
`/tmp/downloads/fgs-auto-retention-production-20260910`.

## Demonstrated defects and recovery

The preceding `02a6c86b` iteration protected quiet regions at distinct
brightnesses, but averaging all patches at one brightness could still hide a
small quieter region. New source-labelled controls reproduced this in luma,
Cb and Cr, including motion, medium grain, PQ and HLG. These are demonstrated
optional-mode control failures, not additional identified library damage.

The local guard now keeps six source-strength populations within each fine
brightness bucket. Source/base variance and covariance describe the total
predicted played-out grain. A rejected model first gets an independent luma
strength refit, within AV1's 14-point limit. This keeps the AR coefficients,
shared scaling shift and colour curves unchanged. Failed attempts are
transactional. Quiet borders can use a narrow zero-strength plateau without
removing grain from unobserved brightnesses. Conflicting local strengths at
one brightness retain the source; one global curve cannot represent them.

Colour components get independent local energy checks. Approximately white
colour grain with sufficient current observations and negligible measured and
signalled luma coupling can preserve only its source component. All-zero
scalings preserve AV1's paired Cb/Cr point-count requirement. Coupled, spatially
correlated or insufficient colour evidence uses whole-frame source retention.
The original model stays in the temporal cache; source-component restoration
has its own stricter, three-frame recovery requirement.

A separate correlated-luma control exposed under-strength grain after the
quiet border was repaired. A retained noisy base and its removed residual are
correlated, so removed-residual variance alone is an incorrect independent
synthesis target. Source-flat 32x32 patches now require an adjacent source
picture with stable local level and independently changing noise. Their
source/base moments supply the synthesis target. Strength-population labels
use the independent previous sample so ordinary sampling variation does not
create artificial populations. The first correlated picture is preserved
while that temporal witness is unavailable.

The coarse check pools this evidence across its actual brightness interval.
Requiring four samples separately in every fine bucket had left some coarse
bins comparing against the old residual target and rejected otherwise valid
recovery. The corrected check still needs four independent observations in
the coarse interval. Fine population checks remain separate vetoes.

## Controlled evidence

Prototype 7 is pinned in `recovery-7-build.json`; its binary SHA-256 is
`e25e677942c28c042f10a740fe764e018783dcb12c878bb9032fdafcefe2e000`.
The cached build label is historical; identify this prototype by its binary
and source hashes. A separately identified final build is required for the
remaining acceptance stages.

The 19 picture controls, 23 local-grain controls, 16 controlled cases at both
retention ceilings, eight texture-residual checks and nine strength/transition
controls pass their decoded quality checks. Every tested output is scanned
for synthesis stability; both grain-on and grain-off output are decoded.
The local controls include positive and negative luma-colour coupling and
uniform-grain controls around the strength-group boundaries.

The quiet/noisy brightness control drops from 2,909,640 bytes with the prior
whole-source fallback to 311,130 bytes, a reduction of 89.31%, at the same QP.
Quiet-region decoded checks still pass. Same-brightness conflicts continue to
preserve source rather than claiming this saving.

In the coarse directional control, the median decoded flat-grain sigma ratio
improves from about 0.778 to 0.871 without changing QP. The complete output is
1,191,873 bytes versus the preceding cost-study reference's 1,202,403 bytes
(-0.876%). The newly preserved startup picture adds 18,284 measured video
packet bytes. Excluding that one measured startup difference, the earlier
processing optimization still saves 2.396%.

The first cost check retained the old rule comparing a two-second clip with
no protected startup picture, and failed its 1% saving threshold by 1,494 bytes.
`startup-cost-accounting.json` records the resolution. The cost regression now
separately measures this first packet only when exactly frame zero is retained
and the reference has no source fallback. Full file sizes remain reported.
The rejected prototype with 47 fallback frames still fails this check. No
Tdarr size limit or picture-quality bound was relaxed. The original failed
qualification record remains intact; its resolved cost evidence is separate.

On the 150-second Gentlemen interval, ABBA means were 45.669 seconds for
`02a6c86b` and 45.569 seconds for prototype 7 on the shared server. Output grew
from a mean 47,338,406.5 bytes to 49,602,274 bytes (+4.782%). Whole-source
fallback increased from 98 to 1,162 of 3,600 frames. This is additional source
preservation with no measured slowdown in this bounded run, not a universal
performance guarantee. All real-clip grain-on/off decodes, timelines and
synthesis scans pass; fixed/default-mode decoded pixels remain unchanged.

## Coverage and limits

These measurements establish the named controls and intervals. Sparse or
structured regions cannot certify the whole picture. The correlated-grain
check depends on source-flat, temporally independent evidence; the local
colour recovery eligibility is intentionally narrower. Existing syntax and
feedback guards remain in force. Encoding quantization still applies to
preserved source pixels. Ordinary fixed retention does not allocate the new
analysis buffers or run these additional checks.

Grain texture remains an approximation. An additional source/output spatial
correlation audit of prototype 6 (`correlated-texture-6.json`) found remaining
lag-four correlation of about 0.14 in the repaired Gaussian-grain border
controls, compared with approximately zero in the source. This difference
was also present in the preceding optional encoder; amplitude recovery does
not solve every covariance/texture difference. It is not evidence of another
unstable ripple or of additional damaged library titles. Aggregate amplitude
checks must not be described as complete grain-texture or perceptual fidelity.

## Production acceptance still required

Complete retained sources for The Gentlemen S01E01, South Park S23E01 and
House of the Dragon S03E08 are independently hashed in
`full-source-preflight.json`. Their actual video arguments are pinned in
`full-source-manifest.json`. Complete candidate/baseline size, metadata,
timeline and decode qualification remains a required foreground step.

The Tdarr builders now support upgrading the already deployed source-size and
Dolby Vision guard layout. Both original and already-preserving FEL policies
are handled explicitly; unknown guard settings and routing are rejected.
The 12 routing tests and preparation from the actual current flow pass.
`prepared-flow-checks.json` pins that source flow. These prepared graphs have
not activated a candidate or changed the ordinary validation budget.

The exact 10% measured-baseline budget continues to need a complete matching
baseline. Rejected or unlisted pilot sources are retained; no hidden QP rise
or substitute lower-quality encode is introduced. The existing ordinary
flow keeps fixed retention and its source-relative saving rules. Final
runtime, bundle and canary evidence must be recorded before this acceptance
work is complete. Background repair/audit services, their pause ownership,
Emby yielding and the hold on new recovery downloads remain in force.
