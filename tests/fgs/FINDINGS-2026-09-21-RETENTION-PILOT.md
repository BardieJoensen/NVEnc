# Current-core retention pilot and diagnostic correction

The bounded manual pilot is complete: 15 encodes across three original-source
windows, all-frame decode/clock/metadata checks, source-paired quality samples
and eight inspected comparison sheets. No new ordinary-production encoder
defect was established. Optional retention still needs better colour-grain
recovery and matched-size evaluation; it remains disabled in production.

The actual code correction is diagnostic-only. Commit `c84dbb1f` records late
source-support rejection and synthesis-recovery hold in the source-reason mask.
Those paths could previously reject synthesis while reporting zero reasons,
which correctly caused the strict analyzer to reject the incomplete trace.
The correction does not change model decisions, thresholds or picture data.
The full CPU suite passes, including 180 Python tests in 25 suites and the C++
checks. Fresh before/after outputs have identical decoded pixels at all 2,160
source timestamps with grain both on and off. The only changed model fields
are the previously absent recovery reason on two South Park frames and one
HDR frame. The original incomplete traces remain recorded.

## Builds and scope

All arms used the same pinned Tdarr 2.89.01 image,
`sha256:3ed97a8ac3411f32de346b3d6d50e1be98cd4fbb7d306b15098fae46e01fca6e`,
production QVBR settings and sequential 720-frame requests. Five arms compare
historical automatic `9c1664d4`, deployed ordinary `cb903a17`, combined ordinary
`c84dbb1f`, automatic before the trace correction `c1d3c356`, and current
automatic `c84dbb1f`. Exact binary hashes and commands are in the manifest.
The corrected binary SHA-256 is
`14a8c04426d8eb0c50d0af2a39c02b09755f7b79567e9ce26478ab7dd9d09c8c`.

Automatic arms used `retain=auto,retain-max=0.1`. That bounds retained residual
in the model path; it is not a file-size cap. A rejected model can preserve the
whole source picture as the input to the lossy NVENC encode.

The windows are South Park S23E01 (first actual PTS 78.495 s, QVBR 34),
The Gentlemen S01E01 (2412 s, QVBR 30), and House of the Dragon S03E08
(1625.624 s, QVBR 29, 3840x1920 PQ). They deliberately target historical fallback
decisions and are not a representative library sample. Full-run target PTS
values 88.714, 2422.875 and 1634.591 s recur with the expected historical checks
after excerpt preroll. Joined current checks are recorded at those exact
source pictures; nominal seek/frame arithmetic was not proof of alignment.

Every one of the 10,800 encoded pictures decodes strictly with libdav1d in both
grain modes. All 720 source timestamps per case align within the explicit
2.1 ms container-clock tolerance. Per-frame HDR/colour metadata and stream
properties pass the existing comparator, with deliberate 8-to-10-bit promotion
allowed. This is not Dolby Vision display qualification or FEL work.

The Gentlemen AVC source omits colour tags. Compressed-header evidence across
the window and preroll records `video_signal_type_present_flag=0`; the absent
full-range flag is therefore inferred as zero under Annex E.2.1 of
[ITU-T H.264 (08/2024)](https://www.itu.int/rec/dologin_pub.asp?id=T-REC-H.264-202408-I%21%21PDF-E&lang=e&type=items).
Only this hash-pinned source receives that range normalization. Primaries,
transfer and matrix remain unspecified; shared SDR interpretation is an
analysis assumption, not proof of the source's original colour intent.

## Measured quality and size

Size uses all video packets in each 720-frame window, excluding audio and mux
overhead. Quality uses twelve evenly spaced, exactly source-paired frames per
window. SSIMULACRA2 is higher-is-better; Butteraugli is lower-is-better. These
are measured scores, not percentages of retained quality or VMAF scores.

| Window | Ordinary video bytes | Automatic video bytes | Size change | Displayed SSIMULACRA2, ordinary → automatic | Displayed Butteraugli, ordinary → automatic |
| --- | ---: | ---: | ---: | ---: | ---: |
| South Park | 9,024,786 | 8,947,415 | -0.86% | 81.119 → 81.189 | 0.8810 → 0.8773 |
| The Gentlemen | 8,320,571 | 8,541,439 | +2.65% | 87.591 → 89.041 | 0.6518 → 0.5515 |
| House of the Dragon | 32,420,977 | 38,594,260 | +19.04% | 85.804 → 87.840 | 0.5546 → 0.4857 |

HDR scores and stills use a fixed 1000-nit-to-SDR Hable display proxy, identically
applied to source and output. Native decoding uses the same custom FFmpeg as
validation; distribution FFmpeg supplies zscale only for decoded raw samples.
This is not native HDR or television playback measurement. Metric image,
mapping, tool/sample hashes and every frame score are recorded. Exact duplicate
decoded samples reuse the same measurement with explicit provenance.

Grain-off base SSIMULACRA2 is 81.132 / 88.117 / 86.404 for ordinary and
81.189 / 89.041 / 87.840 for current automatic retention. The displayed
comparison includes both base differences and independent grain phase.
Neither score proves a visible defect or a watchability improvement. Native
stills show modestly closer source texture with retention in the live-action
examples; the animation difference is subtle. No TV playback review was done.
The trial is same-QVBR, not matched-size, and supplies no whole-title cost
forecast, banding clearance or whole-library damage finding.

Combined ordinary output is pixel-identical to deployed ordinary on the two
live-action windows. South Park differs on 305/720 pictures, with +0.054% video
bytes and very close sampled scores. This broader branch includes the earlier
intentional model-hold correction; it is separate from the exact before/after
diagnostic-only comparison. One run per arm, playback admission delays and
shared host activity do not qualify a throughput claim.

## What the precise traces establish

Current automatic retention keeps source input on all 720 pictures in each
window. No synthesized-grain pictures occur in those arms. This is a model
fallback decision, not evidence that the source or deployed output is damaged.

| Window | Held-colour covariance rejection | Local mismatch, all frames | Other observations |
| --- | ---: | ---: | --- |
| South Park | 557 | 641 | Exact target has both reasons; four component-colour rejects; two late synthesis-recovery holds |
| The Gentlemen | 716 | 46 | One covariance fit recovers, then remains source-preserved during recovery hold |
| House of the Dragon | 706 | 0 | Eleven fits recover, all remain source-preserved during recovery hold; one late synthesis-recovery hold |

Counts overlap. Rejected held-colour checks name spatial correlation, which
component-only recovery does not currently qualify. Skipping unused covariance
calculations avoids 557 / 716 / 706 calls respectively; no measured speed gain
is claimed. Removing one rejection does not establish that later checks would
pass or predict any saved bytes.

The historical automatic arms exhibit a two-picture synthesized-grain burst in
South Park and a one-picture burst in HDR. Current recovery guards keep those
sequences source-preserved without those bursts. Deployed ordinary has continuous
synthesis in both SDR windows; HDR has two longer source-only runs, of 30 and
116 pictures, with the same transitions in combined ordinary. This checks these
specific sequences, not every possible temporal transition.

Useful next model work is recovery that accounts for spatially correlated
colour grain while preserving local amplitude and source-support protections.
First reproduce the remaining failed-fit/recovered-but-held/accepted-recovery
HDR controls, then qualify a model change against synthetic coupled-colour
negatives and actual source windows. Keep the current fallback until that model
demonstrates better source fidelity per byte. Matched-size quality and controlled
timing still precede a default or deployment decision. The older 70-command
matrix is preparation, not an automatic job or a current production baseline.

## Evidence, runtime and cleanup

Private ledger:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/manual-pilot-20260921/`.
Start with `closeout.json`, then `manifest.json`, `report.json`, `analysis.json`,
`trace-fix-full-equivalence.json`, `target-reproduction.json`,
`quality-report.json`, `visual-review.json`, `health.json` and `cleanup.json`.
Source hashes, commands, complete frame traces, diagnostics, metadata, quality
sample provenance and inspected PNG sheets remain. The first attempt's
CPU/build/failure evidence is under `manual-pilot-20260916/trace-fix/`.

Completed video controls and the exact corrected binary are preserved at
`/media/merged-storage/validation-fixtures/nvenc-fgs/retention-pilot-20260921/`.
`artifact-locations.json` maps original execution paths to verified archive
paths. Reproducible raw samples and the duplicate build cache are removed after
verification. Original fixtures remain needed for unfinished model and
matched-size studies; production files and source holds were not changed.
September 16 trial videos were already absent when work resumed, so fresh
encodes supplied the before/after proof.

Production remains `nvenc-fidelity/tdarr-node:2.89.01-cb903a17-20260919` with
the qualified ordinary encoder. All four custom tools, production flow, all
25 local plugins and worker limits match prior qualification. The fresh health
check finds ordinary Tdarr unpaused and idle; this work never changed its pause
state. Its independent Emby watchdog remains responsible for playback pauses.
The retired repair coordinator is inactive and disabled. Restored FEL original
signatures and library exclusions match. FEL and production automatic retention
remain disabled. No automatic continuation, timer or download exists.
