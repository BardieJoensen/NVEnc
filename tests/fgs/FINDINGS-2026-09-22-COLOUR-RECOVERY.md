# Colour recovery and source-fidelity work, September 22

The finite matched-size comparison is complete, including both calibrated SVT
references, native PQ measurements, tighter ordinary-FGS size points and
source-matched still review. The user authorized a Tdarr pause; in-flight jobs
finished, the manual study ran, and the owned pause was released. The final
health check finds two ordinary workers active on the unchanged `cb903a17`
encoder in Tdarr 2.89.01. Automatic retention and FEL remain off.

The proposed joint colour-grain model remains experimental, with no encoder
call sites. A diagnostic reference-plane bug was corrected, revealing useful
real colour-noise samples. This does not qualify integration of the model or
establish a new production defect.

## Implemented work

`78857051` adds experimental joint source/base covariance fitting and quantized
luma/chroma transfer. `f422a063` documents its mathematics and limits in
[JOINT-COLOUR-RECOVERY.md](JOINT-COLOUR-RECOVERY.md).
`1a51dafe` adds a reusable [native PQ comparison tool](../../tools/fgs/README.md#paired-native-pq-errors).
It measures native source-paired luminance and colour errors at explicit
display peaks without first tone-mapping HDR to SDR. It does not render TV
processing or dynamic Dolby Vision metadata; its descriptors are not VMAF,
quality percentages or universal visibility thresholds.

The latest full CPU suite passes **185 Python tests in 26 suites plus all C++
checks**. Subsequent work changed private diagnostics and documentation, with
actual source/decoder and AOM checks below. No new per-file Tdarr check was
added, and routine validation settings and worker limits are unchanged.

## Remaining controls reproduced

Twelve encodes cover three 720-picture HDR windows and the 2,160-picture
Gentlemen jacket window beginning at 33:24. Historical automatic, deployed
ordinary and current automatic arms use the pinned runtime and production
QVBR. Complete grain-on/off decoding, source clocks and the existing
frame/stream metadata checks pass.

| Control | Automatic video bytes | Change versus ordinary at the same QVBR | Automatic grain pictures |
| --- | ---: | ---: | ---: |
| HDR failed-fit witness | 23,976,634 | +22.12% | 0 / 720 |
| HDR later-guard witness | 40,545,058 | +49.69% | 0 / 720 |
| HDR formerly accepted recovery | 25,940,287 | +46.91% | 0 / 720 |
| Jacket window | 31,794,619 | +3.40% | 0 / 2,160 |

The historical timestamps reproduce their distinct fit/recovery categories.
Current automatic guards preserve source input across these windows instead
of allowing the old short synthesis bursts. Source-preserved input still
undergoes lossy AV1 compression. These chosen diagnostic windows are not
whole-title cost estimates or evidence that installed files need repair.

Six further encodes compare existing luma-only automatic retention with plain
NVENC. Luma-only mode emits grain on 0/394/131 of 720 animation/SDR/HDR pictures,
with no one- or two-picture grain-on bursts in those windows. It is a control,
not an enabled automatic policy.

## Completed size and quality comparison

The main tolerance was 3% of automatic retention's complete primary-video
payload. Additional ordinary SDR/HDR points tightened those differences to
**+0.211% and +0.085%**. Audio/container overhead is excluded. Quality uses the
same twelve evenly spaced source-paired pictures per window. SSIMULACRA2 is
higher-is-better; the HDR column uses the recorded 1000-nit Hable SDR proxy,
with native PQ results separately below.

| Arm | Animation SSIMULACRA2 | SDR SSIMULACRA2 | HDR proxy SSIMULACRA2 |
| --- | ---: | ---: | ---: |
| Ordinary FGS, closest size point | 81.119 | 87.801 | 86.622 |
| Automatic retention | 81.189 | 89.041 | 87.840 |
| Plain NVENC | 81.138 | 89.126 | 87.865 |
| Luma-only automatic | 81.189 | 88.301 | 87.874 |
| SVT preset 6, calibrated CRF, no grain | 77.253 | 82.086 | 81.263 |

| Arm | Animation video bytes | SDR video bytes | HDR video bytes |
| --- | ---: | ---: | ---: |
| Ordinary FGS, closest size point | 9,024,786 | 8,559,477 | 38,627,001 |
| Automatic retention | 8,947,415 | 8,541,439 | 38,594,260 |
| Plain NVENC | 8,953,145 | 8,598,313 | 38,669,153 |
| Luma-only automatic | 8,947,415 | 8,400,114 | 37,848,234 |
| SVT calibrated CRF | 8,945,218 | 8,578,453 | 39,563,571 |

The calibrated SVT VBR reference also completed: scores are
76.882 / 80.399 / 80.373, at 8,908,287 / 8,517,712 / 38,629,046 bytes.
Both references use pinned SVT-AV1 4.1.0, preset 6 and tune VQ; CRF additionally
sets variance boost explicitly. Neither uses SVT grain synthesis. This is a
comparison of these settings/windows, not a ranking of everything SVT can do.
HDR VBR used four CPU threads and HDR CRF eight; no speed ranking is inferred.
The SVT CRF HDR point is 2.51% larger than automatic, within the declared band.

Automatic retains source input on all 720 pictures of these deliberately
selected fallback windows and correspondingly resembles plain NVENC. Against
the closer-size ordinary points its displayed score improves by about 1.24
SDR and 1.22 HDR-proxy points; animation is nearly unchanged. These are score
points, not percentages of quality. With synthesis disabled, ordinary scores
are 88.345 SDR and 87.250 HDR-proxy: independent grain phase accounts for part
of the displayed gap. Neither a scalar score nor a grain-off image alone
establishes the perceptual value of regenerated grain.

At the original production QVBR, automatic's video cost was -0.86% / +2.65% /
+19.04% across these three windows. The close-size test changes ordinary QVBR
to separate fidelity from that size difference; it does not eliminate the
same-QVBR cost or predict whole-title/library sizes.

Six selected stills, including large score gaps, and five native-resolution
crops were reviewed. All 30 candidate witness pictures exactly match their
complete-decode frame hashes. Automatic/plain retain source-like fine texture
more closely in the inspected live-action crops; ordinary FGS changes that
texture modestly, with small differences at overview scale. This SVT setting
looks softer or more mottled in some fine-texture crops. No gross alternating
line displacement was evident in these stills. This is not a motion, flicker,
banding, HDR-TV or whole-library visual clearance.

## Native HDR and metadata

Mean per-picture native luminance errors at 1000 nits are:

| Arm | PU21 pixel RMS | PU21 8x8-mean RMS |
| --- | ---: | ---: |
| Ordinary, closest size, grain on | 1.0349 | 0.3423 |
| Ordinary, closest size, grain off | 0.9568 | 0.3323 |
| Automatic | 0.8944 | 0.3213 |
| Plain NVENC | 0.8946 | 0.3217 |
| Luma-only automatic | 0.8991 | 0.3227 |
| SVT CRF | 1.2310 | 0.6030 |

All colour channels and 400/1000/4000-nit runs remain in the reports. The peaks
give identical errors on these selected samples; highlights above 400 nits
remain unqualified. Clipped-pixel counts also include out-of-range/negative
RGB, not just highlights. Grain phase affects RMS and can affect coarse error;
these are descriptive errors, not universal perceptual thresholds.

All 20 comparison arm/window entries have complete 720-picture grain-on/off
decodes and clocks paired to source within 2.1 ms. The NVENC arms pass the
existing frame/stream metadata comparison. The independent software references
retain explicit limitations: both animation SVT arms have 30 one-tick timing
differences and absent chroma-siting tags; the SDR VBR reference also lacks that
tag. Native HDR references have matching range, matrix, transfer, primaries,
dimensions and left siting, but SVT omits Dolby Vision configuration/metadata
on all 720 pictures. It is not a drop-in production replacement. Native PQ
comparison explicitly ignores dynamic metadata in every arm.

The untagged Gentlemen AVC source's limited range was checked in its compressed
headers. Transfer/primaries remain unspecified; all arms use the same stated
SDR interpretation, which does not prove original colour intent.

## Corrected colour-grain evidence

The initial private pixel analysis incorrectly read previous colour from the
encoder's **luma-only** adjacent-source cache. Its zero-real-support conclusion
is invalidated. The original logs/results remain; the reader now fails closed
on that reference by default. Corrected analysis independently decodes previous
colour and checks exact equality for all planes of 20 captured current pictures
and all 20 cached previous luma pictures. Production encoder code was not
changed by this correction.

Five retained source clips were screened with unchanged thresholds. Taxi and
Shining provide real colour-noise support; Bridge supplies one supported
frame/component. Two additional 360-picture Bridge/Shining captures add actual
source/base data to the original three cases. Across those captures, eight
frame/component groups support independent training/holdout missing-noise fits.
Four meet the exploratory 8% variance/generalization bounds. The other four
remain insufficiently consistent; the limits were not widened.

Four stable targets are representable without coefficient clamping. Actual
pinned AOM synthesis, 48 seeds per overlap setting, agrees with predicted
chroma power within 0.24%. Averaged luma transfer differs by up to 8.64%, which
exceeds the exploratory 8% bound in two cases. Finite-template calibration,
intensity-bin support, stronger real coupling, causal stability and actual
integrated temporal transitions still need development/qualification. These
are offline model results, not a new encoder mode that can be deployed.

The earlier forward-gradient selector bias remains documented alongside this
reference-plane correction. Synthetic positive/texture-negative calibration
alone did not validate the real capture contract; independent source pixels
were necessary to expose the second mistake.

## Decision and remaining work

Keep production automatic retention off. The completed comparisons support a
modest source-fidelity benefit in selected live-action fallback scenes, but
current automatic behaves almost like plain NVENC there and has not solved
the grain-compression cost. The recovered colour model must first work across
intensity, finite synthesis and transitions in actual encodes while preserving
all current source/texture/amplitude protections. Then repeat the matched-size
witnesses and pursue longer-title cost and optimization on a useful candidate.
Those implementation/full-title stages are still unfinished; the GPU size/quality
comparison is no longer waiting for an idle Tdarr queue.

`retain-max=0.1` bounds a residual fraction, not file growth. Existing Tdarr
size policy remains 95% for ordinary and 120% for DV/HDR against a source-video
baseline with identical retained audio. Rejection keeps source video. No new
storage/fallback policy or ordinary-encoder speed improvement was deployed.
During the authorized drain, source packet reads dominated the final job
stages; this is an I/O observation, not an encoder throughput measurement.

## Evidence and operational state

Private ledger:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/`.
Start with `README.md`, `handoff.json`, `work-plan.json` and `evidence-index.json`.
Completed comparison evidence is in `matched/`: `report.json`, `crf-report.json`,
`tight-report.json`, their three quality reports and `analysis-{vbr,crf,tight}.json`.

The resumed work is under `resume-authorized/`: pause receipt/controller status,
`corrected-colour/analysis.json`, `reference-cache-fix.json`, `source-fit.json`,
`target-holdout.json`, `quantized-joint/report.json`, witness provenance/review,
health and cleanup receipts. The prior stopped handoff/index and failed still
seek attempts remain recorded. Candidate witnesses use complete short-clip
decoding, exact source timestamps and full-decode hash matching.

Final health verifies the encoder and three companion tools, all 25 plugins,
production flow, worker limits, FEL-original signatures/exclusions and the
inactive/disabled repair coordinator. Tdarr resumed its ordinary queue;
Emby's independent playback watchdog retains its own pause ownership.
Completed media are hash-verified on storage, reusable source/base evidence is
retained, and disposable calibration/witness buffers have cleanup receipts.
No timer, watcher or automatic experiment restart was installed.
