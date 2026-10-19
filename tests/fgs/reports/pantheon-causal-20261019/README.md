# Pantheon causal follow-up — 2026-10-19

**A recovers much of E05’s missing shirt HF amplitude and spatial statistics on an unchanged base, but fails quiet-region protection and does not repair E04. B places the main diagnostic texture loss before in-loop filtering; its single allocation intervention fails at matched rate. Neither is a qualified repair. These results do not establish an AV1 limit or make re-encoding impossible.**

This builds on the [completed independent investigation](../pantheon-independent-20261019/README.md), without repeating its encoder sweep. No production binary, configuration, torrent or library file changed. The original 14.1-versus-10.0 Mbps observation remains valid; season-wide savings do not answer it.

## Validity and provenance

Fresh extraction reused the exact fixtures: 96 preroll plus 240 scored frames, 1920×1080 limited-range BT.709, original H.264 downloads lifted exactly to 10-bit. All scored frames matched an independent source seek. E04 is 24000/1001 fps, source PTS 1243.534–1253.502, 10.029359 Mbps. E05 is 24 fps, starts 1420/1440/1460, original rates 9.001411/9.676522/7.772547 Mbps. New scored arms passed the established window-wide alignment checks.

Production remains NVEnc 9.38 r4412, SHA-256 `b30612f9…fce30db`, historical source `f1327e1493e8cad967889af96571e974dd41245b`. SVT is 4.2.0, source `9292ec8e32bce26f781f277ec8739b53426c4300`, rebuilt from the immutable archive. [Full identities](provenance.json).

Prior `lp2` VBR was not byte-repeatable even with the preserved SVT binary. Preserved/rebuilt binaries matched exactly at `lp1`, used for both controlled arms. Instrumented/uninstrumented IVF matched on both fixtures; the final combined patch with both environment switches absent also matched E04. Original-stage pixels match source and final reconstruction matches independent dav1d on every scored frame in both fixtures. [Validation](stage-validation.json).

All required metrics use `campaign.py`, patched CUDA VMAF/NEG/PSNR/SSIM/CIEDE and GPU FFVship SSIMULACRA2/Butteraugli. Supplementary CAMBI uses 16 CPU workers. See [full metrics and tails](METRICS.md), [results](results.json), [reproduction and logged-field definitions](REPRODUCE.md). Rates count scored video packets; these windows are not whole-episode equal-size benchmarks.

## A — reconstruction-aware synthesis

Native dav1d compares synthesis disabled, existing metadata, and an experimental model on **one fixed encoded picture stream** per fixture. The first two arms match independent FFmpeg decoding exactly. Every base sample is checked unchanged before/after synthesis. This is an offline native render, not a rewritten AV1 stream: **new signaling overhead is unmeasured**, and no deployable equal-size bitstream is claimed.

Source-defined flat/stationary 32px tiles exclude diagnostic ROIs, edges, moving structure and persistent HF. Separate source/base marginal spectra estimate positive missing covariance, fitted to AV1 lag3 AR and intensity curves. Raw source-minus-base error is never labeled grain. Nevertheless, spectral subtraction assumes independent stochastic components; it does not uniquely separate grain from artifacts or lost structure.

Training uses frames 16k, immediate neighbors for stationarity, and even checkerboard tiles; evaluation uses frames 8+16k and odd tiles. All thumbnails influence interval detection, so frames are held out from fitting/calibration, not segmentation. The procedure is frozen across all four windows, without retuning after failures.

Historical safeguards reject directional structure and cap synthesis from small source regions, including constant-source zero notches, coupling caps to preencode source retention. This experiment replaces the cap only in offline code with a source lower-quartile amplitude cap while retaining edge/stationarity rejection. **That replacement fails quiet-region protection.** [Historical source audit](grain-safeguards-evidence.txt).

Five-frame diagnostic means, HF amplitude in 8-bit luma units, paired with residual ACF1:

| Region | Source amplitude / ACF1 | Existing model | Reconstruction-aware |
|---|---:|---:|---:|
| E05-1440 shirt | 0.619 / −0.228 | 0.059 / −0.197 | 0.545 / −0.187 |
| E05-1440 background | 1.778 / −0.192 | 1.030 / −0.075 | 1.497 / −0.134 |
| E04 purple | 1.859 / −0.184 | 1.174 / +0.038 | 1.169 / +0.043 |
| E05-1420 shirt | 1.203 / −0.313 | 1.224 / −0.326 | 0.936 / −0.285 |
| E05-1460 shirt | 4.142 / −0.180 | 3.734 / −0.148 | 3.734 / −0.148 |

The primary shirt remains **12.1% low**, missing the provisional 10% amplitude screen; ACF1 error 0.041 passes the provisional 0.05 screen. Its background misses both. E05-1420 regresses relative to existing synthesis. E04’s structured effect remains altered. Around 24:25 strong grain already exists in the source; no synthesis is added at the diagnostic shirt frames.

Across 168 held-out quiet-luma tiles in E05-1460, mean absolute HF-amplitude error rises **0.094→0.277**, with mean added amplitude 0.309. E05-1420 contains no quiet-luma evaluation tiles and cannot establish that safety. Separate U/V checks often improve amplitude error but do not cancel the luma failure. Color-conditioned measurements, isolated synthesis ACF and source correlation are preserved.

Computed temporal evidence: independent seeds give near-zero synthesis correlation; primary shirt output correlation is approximately 0.002 versus source 0.119. Matching original random samples is not required, but temporal appearance remains unproven. Crude thumbnail segmentation creates 72/31/4/21 intervals for E04/1440/1420/1460; only 3/4/4/4 have nonzero models. There is no interval blending. Boundary jumps and fixed-ROI traces are archived; these are not verified scene-cut labels or playback observations.

## B — reconstruction and allocation

Traces capture original/post-TF input, reconstruction immediately after each SB encode before its deblock call, post-DLF/final reconstruction, actual SB qindex, block geometry/skips and final quantized luma coefficients. Pre-DLF is assembled from local SB snapshots. Coefficient counts, magnitudes and qindices are **proxies, not measured block bits**.

| Region | Input HF / ACF1 | Before SB deblock | Post-DLF and final |
|---|---:|---:|---:|
| E04 purple | 1.859 / −0.184 | 1.195 / +0.137 | 1.195 / +0.137 |
| E05 shirt | 0.619 / −0.228 | 0.072 / −0.056 | 0.072 / −0.056 |
| E05 background | 1.778 / −0.192 | 0.624 / +0.082 | 0.624 / +0.082 |

The sampled diagnostic frames survive TF exactly, and their three reconstruction stages are byte-identical. Across each full window TF changes 35 frames; DLF changes 36 E04 and 20 E05 frames. Post-DLF/final match all 240. Thus dominant **local** loss precedes in-loop filtering; TF/DLF are not inactive everywhere. Prediction, transform/quantization and mode/search decisions remain jointly implicated.

E05 shirt frame 120 has 7 nonzero quantized luma coefficients in 4 fully contained transforms/4096 samples; E04 purple frame 132 has 7890 in 107 transforms/126464 samples. Skipped blocks and boundary-crossing transforms are outside these denominators. Prediction and prequantized residuals were not exported, so sparsity cannot establish quantization as the sole cause.

One intervention requests −12 qindex for 64px SBs where at least half the 16px subtiles have source-flat texture and substantial baseline HF loss. It uses all frames/regions, no ROI coordinates. Existing AQ, legal normalization and rate control remain active. Only requested bitrate is calibrated afterward.

| Case | Original Mbps | Baseline Mbps | Intervention Mbps | ROI HF baseline→intervention | VMAF p1 baseline→intervention |
|---|---:|---:|---:|---:|---:|
| E04 | 10.029359 | 10.027344 | 10.066084 (+0.37%) | 1.195→1.180 | 79.59→78.57 |
| E05-1440 | 9.676522 | 9.676331 | 9.748665 (+0.75%) | shirt 0.072→0.096 | 79.92→75.61 |

Flat-texture amplitude errors improve across the window, but edge MSE worsens **10.0%/16.4%**, with worse SSIMULACRA2 tails and Butteraugli. E05 background improves 0.624→0.914, still far below 1.778. CAMBI improves but does not excuse these regressions. B therefore was not expanded to regression windows.

Actual maps explain the tradeoff: E05 shirt frame 120 goes from qindex 80 to 96 while frame base rises to 108. E04 frame 134 changes from uniform 77 to a purple-ROI average 103.0; only 16.6% of that structured ROI qualifies for the flat-texture mask. A relative preference did not ensure lower absolute quantization. This weakens this mask/rate-control strategy, not all texture-directed allocation.

## Limits and next discriminator

Native stills show restored fine shirt texture in A and insufficient E04/B restoration. [Artifacts](ARTIFACTS.md) include synchronized labeled clips, full-frame stills and native crops. Previews convert 10→8-bit; metrics remain 10-bit. **No motion playback or user player/display testing occurred.** Human viewing is needed, particularly at model boundaries and quiet E05-1460 backgrounds.

No production-change proposal is supported. A needs qualified stochastic/structural separation, hard quiet-region protection, temporal state, reconstruction access/two passes, and actual header insertion with overhead/decoder tests. B needs rate-control-aware budgeting and whole-episode qualification. E04 baseline took 67.8 s for 336 frames; the instrumented intervention took 74.4 s excluding map construction. Different tracing overhead prevents a clean production-speed comparison.

Next A discriminator: cross-spectral or motion-compensated coherence in matched-brightness quiet and stochastic regions, retaining hard source-clean constraints, to establish whether a legal frame-wide curve can serve both. Next B discriminator: export prediction/prequantized residuals and inspect fixed-block rate-distortion choices under a fixed frame budget, verifying that the target actually receives lower realized quantization. A’s local gain does not establish preservation of intentional structure; B’s failure says nothing about FGS correctness.
