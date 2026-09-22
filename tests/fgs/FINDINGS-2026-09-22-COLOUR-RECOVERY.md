# Colour recovery and source-fidelity work, September 22

The control/model stage and new native HDR diagnostic are complete. The
equal-size study is **partially complete and stopped for ordinary Tdarr queue
priority**. No new ordinary-mode encoder defect was established, and no
experimental behaviour was deployed. Automatic retention and FEL stay off.
There is no automatic restart, scheduler or pending experimental container.

## Implemented work

`78857051` adds experimental joint source/base covariance fitting and quantized
luma/chroma grain transfer. `f422a063` documents the independent evidence and
integration limits in [JOINT-COLOUR-RECOVERY.md](JOINT-COLOUR-RECOVERY.md).
These helpers have no encoder call sites. Current footage has insufficient
source-supported independent colour noise to qualify this proposed recovery;
the existing spatial-correlation rejection remains intact.

`1a51dafe` adds a reusable [native PQ comparison tool](../../tools/fgs/README.md#paired-native-pq-errors).
It measures source-paired native HDR error in luminance and all three colour
channels, with separate coarse-picture descriptors and explicit display peaks.
It does not tone-map HDR to SDR before measurement. It also does not render TV
tone mapping or dynamic Dolby Vision metadata, and its scores are not VMAF,
quality percentages or universal visibility thresholds.

The final CPU suite passes: **185 Python tests in 26 suites and all C++ tests**.
Five new end-to-end native-PQ checks cover identity, independently calculated
PQ level shifts, chroma errors, malformed/unequal inputs and display limits.
None of this adds a check to normal Tdarr per-file validation.

## Remaining controls reproduced

Twelve encodes cover three 720-picture native HDR windows and a 2,160-picture
jacket window beginning at 33:24 in The Gentlemen S01E01. Historical automatic,
deployed ordinary and current automatic arms use the pinned runtime image and
production QVBR. All pictures pass strict libdav1d decoding with grain on/off,
source clock alignment and the existing frame/stream metadata checks. The
untagged AVC source's limited-range inference is independently recorded from
its actual compressed headers; colour primaries/transfer remain unspecified.

| Control | Current automatic video bytes | Change versus ordinary, same QVBR | Synthesized-grain pictures in current automatic |
| --- | ---: | ---: | ---: |
| HDR failed-fit witness | 23,976,634 | +22.12% | 0 / 720 |
| HDR later-guard witness | 40,545,058 | +49.69% | 0 / 720 |
| HDR formerly accepted recovery | 25,940,287 | +46.91% | 0 / 720 |
| Jacket window | 31,794,619 | +3.40% | 0 / 2,160 |

Exact historical target timestamps reproduce the distinct failed fit,
recovered-but-held and previously accepted recovery categories. Current
recovery guards keep these automatic windows source-preserved instead of
allowing the historical short synthesis bursts. A source-preserved input still
undergoes lossy AV1 compression. These selected windows do not predict a
whole-title cost or establish damage in an installed library file.

Six further encodes compare existing `chroma=off` automatic retention with
plain NVENC across the original animation/SDR/HDR windows. Luma-only mode emits
grain on 0/394/131 of 720 pictures; its grain-on runs have no one- or two-picture
bursts here. It gives modest savings against full automatic retention, not a
demonstrated improvement over the deployed mode. It is not enabled as an
automatic policy.

## Completed approximate size matches

The predeclared tolerance is 3% of automatic retention's complete primary-video
payload. Audio and container overhead are excluded. Quality scores use twelve
evenly spaced, source-paired pictures and the same metric image. SSIMULACRA2 is
higher-is-better. Grain-off scores and Butteraugli are retained separately in
the evidence; synthesized grain phase affects pixelwise comparisons.

| Window / arm | Video bytes | Gap from automatic | Displayed SSIMULACRA2 |
| --- | ---: | ---: | ---: |
| South Park / automatic | 8,947,415 | 0% | 81.189 |
| South Park / ordinary FGS | 9,024,786 | +0.865% | 81.119 |
| South Park / plain NVENC | 8,953,145 | +0.064% | 81.138 |
| South Park / luma-only automatic | 8,947,415 | 0% | 81.189 |
| The Gentlemen / automatic | 8,541,439 | 0% | 89.041 |
| The Gentlemen / ordinary FGS | 8,320,571 | -2.586% | 87.591 |
| The Gentlemen / plain NVENC | 8,598,313 | +0.666% | 89.126 |
| The Gentlemen / luma-only automatic | 8,400,114 | -1.655% | 88.301 |

Automatic retention preserves source input on every picture of these windows.
Its scores and sizes are correspondingly close to plain NVENC. The animation
result is very close across all four modes. Ordinary SDR is 2.6% smaller, so
its lower score cannot be attributed entirely to the mode. These deliberately
selected fallback windows do not establish an advantage across the library.
The untagged SDR source uses the same stated colour assumption for every arm;
that is not proof of the original colour intent.

SVT-AV1 4.1.0, preset 6, tune VQ, no film grain is an additional **base-encoder
reference**, using an already-installed pinned FFmpeg 8.1 container. Two
size-calibrated VBR references are encoded and scored. The independent CRF /
variance-boost comparison is unfinished: animation is calibrated to -0.025%
of the target bytes but its GPU scores did not run. SDR/HDR CRF calibration and
HDR VBR calibration remain open. Do not rank SVT from the short-window VBR
allocation result or interpret this as qualification of SVT's grain analyser.

Every completed reference has all 720 decoded clocks paired to source within
the predeclared 2.1 ms tolerance. The stricter metadata comparator records 30
one-tick timing differences in the animation VBR reference; its chroma-siting
tag is also absent. These limitations remain explicit. The HDR reference must
retain explicit left chroma siting before native display comparison.

## Native HDR measurements completed without GPU use

The HDR automatic, plain and luma-only outputs are already within 2.2% of
each other, so their native PQ comparison could finish while ordinary workers
owned the GPU. Twelve source-paired pictures were measured at 400/1000/4000
nits. Mean per-picture luminance error is:

| Arm | Video bytes | PU21 pixel RMS | PU21 8x8-mean RMS |
| --- | ---: | ---: | ---: |
| Automatic | 38,594,260 | 0.8944 | 0.3213 |
| Plain NVENC | 38,669,153 | 0.8946 | 0.3217 |
| Luma-only automatic | 37,848,234 | 0.8991 | 0.3227 |

Colour-channel measurements show similarly small differences. The three peaks
give identical recorded errors on these samples; fidelity for highlights above
400 nits remains unqualified. No perceptual significance is assigned to
these small differences. **Ordinary FGS at matched HDR size is still missing**;
its earlier same-QVBR output is 19% smaller and cannot substitute for that arm.

## Resources, failures and unfinished work

The two private SVT containers yielded when ordinary Tdarr started Landman.
As Tdarr continued into subsequent episodes, the paused experiments were
stopped and their memory released. The quality wait reached its bounded idle
timeout. No ordinary worker was paused. There are no remaining experiment
containers or automatic retries.

An earlier pair of experimental writers collided on one progress temporary
filename and interrupted an HDR attempt. Retry code uses process-specific
temporary files and separate stage status files. The failed commands/logs and
unqualified-output cleanup receipt remain. The earlier offline selector's
forward-gradient bias and corrected synthetic calibration also remain recorded;
neither defect was in the production encoder or validation flow.

The next manual work is to finish the HDR production/SVT size matches, the
remaining SVT CRF references, and their source/metadata/quality review. For
model integration, obtain real source-supported colour-noise positives and
qualify quantization, intensity support, texture protection and transitions.
Full-title cost trials and optimization follow a demonstrated fidelity-per-byte
benefit. They have not been run or silently waived.

`retain-max=0.1` remains a residual-fraction bound, not a file-size budget. The
existing Tdarr size policy is unchanged: 95% for ordinary and 120% for the
DV/HDR route, relative to a source-video baseline with identical retained audio.
An unsuccessful size check keeps source video. No new size/fallback policy was
introduced by these trials.

## Evidence and resumption

Private ledger:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/`.
Start with `README.md`, `handoff.json`, `work-plan.json` and `evidence-index.json`.
The current encoder branch includes the three commits above; the current
runtime remains qualified ordinary `cb903a17` in Tdarr 2.89.01. Final health
checks pin all four tools, all 25 plugins, the production flow, worker limits,
FEL-original signatures/exclusions and the disabled repair coordinator.

Completed controls and dependent pixel captures are verified and archived at
`/media/merged-storage/validation-fixtures/nvenc-fgs/colour-recovery-20260922/`.
`artifact-locations.json` resolves original execution paths; partial attempts
and reproducible raw buffers have separate retirement receipts. Duplicate
build caches/source copies are removed. Original media, source protections
and unresolved model evidence remain. Resume only after checking the current
runtime/source identities and ordinary workload; exact commands and remaining
gates are in the private handoff. Nothing starts merely because Tdarr becomes
idle.
