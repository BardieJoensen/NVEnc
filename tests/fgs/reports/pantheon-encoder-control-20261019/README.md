# Pantheon E04: independent encoders at the original bitrate

The user challenged the earlier 14.1 Mbps NVENC result losing texture against a 10.0 Mbps original. This bounded diagnostic tests that exact difficult window with independent encoders and targeted controls. No production or library changes.

## Method

- Untouched AMZN H.264 download; 96 frames preroll, 240 scored frames, 1920x1080 at 24000/1001. Requested start1243.493s; actual reference PTS1243.534–1253.502s.
- Every decoded test-input frame after preroll exactly matches the independently decoded original reference after conversion to10-bit (240 framemd5 matches). Input extraction is not causing this sample’s texture loss.
- Original packet rate rechecked:10.0293586 Mbps. Calibrate actual output packets selected by presentation-frame index, not requested bitrate or packet decode order. All accepted variants within1.5% of original scored-window rate.
- Film grain synthesis disabled in all AV1 controls. Grain-disabled decoding is also explicit. x264 uses grain-preserving tuning; it is an additional H.264 generation, not the original encoder/master.
- Production NVEnc9.38 binary SHA matches earlier provenance. Independent installed software control is SVT-AV1 **1.7.0**, preset4, VQ tune0,10-bit through system FFmpeg6.1.1. This is not a comparison against the newest or best possible software encoder. x264 slow/tune grain uses8-bit matching the source.
- Same campaign.py GPU metrics, patched CUDA vmaf build, HD VMAF/NEG, PSNR/SSIM/CIEDE and GPU FFVship SSIMULACRA2/Butteraugli. Supplementary CAMBI. Frame alignment zero wins in all five variants; each metric arm has240 frames; no VMAF nulls. P1 excludes frame0.

## Results

| Variant | Actual Mbps | VMAF | NEG | VMAF p1 | SSIMULACRA2 | ROI HF amplitude / source | ROI residual ACF1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| nvenc | 10.173 | 91.43 | 90.25 | 81.61 | 61.39 | 62.3% | 0.0488 |
| svt | 10.029 | 91.29 | 90.02 | 77.22 | 62.62 | 68.5% | -0.0904 |
| svt-tf-off | 10.009 | 90.98 | 89.75 | 76.79 | 62.61 | 64.7% | -0.1022 |
| nvenc-noaq | 10.042 | 91.36 | 90.18 | 81.62 | 61.14 | 61.9% | 0.0561 |
| x264-grain | 10.041 | 89.63 | 87.84 | 74.49 | 57.42 | 89.8% | -0.1346 |

Source ROI HF sigma1.8585, residual ACF1=-0.1842, ACF2=-0.0954, ACF3=0.0163. Same background ROI as prior Episode4 tests: x1400,y200,w400,h400; frames120,126,132,138,144. HF in8-bit luma units. Read amplitude together with residual ACF; compression artifacts can also contribute energy. Full-frame values and all three ACF lags are in comparison.json.

## Findings and limits

1. At this matched window rate, installed SVT provides no decisive overall-fidelity win over NVENC. Its residual spatial correlation is closer to the source and its ROI amplitude higher, but both lose texture. These are different encoder configurations, not a universal codec ranking.
2. Disabling SVT temporal filtering does not fix this sample. Disabling both NVENC AQ modes also does not materially improve it. The tested simple settings changes do not justify a season-wide rollout.
3. The x264 grain-tuned baseline retains about90% of ROI HF amplitude and has ACF closer to the source than the tested AV1 configurations, yet scores lower on VMAF and SSIMULACRA2 and higher on CAMBI. More grain energy alone is not proof of accurate grain; higher VMAF alone is not proof of texture preservation.
4. A second H.264 generation at the original rate also loses fidelity. That makes generational loss a demonstrated contributor in a control, but it neither quantifies how much of AV1’s loss it explains nor proves the AV1 results optimal.
5. No tested control is established as a faithful replacement. Do not infer an AV1 standard limit, a uniquely NVENC-specific fault, or that all remaining loss is FGS-related. The independent AV1 control is old; this experiment does not replace an up-to-date encoder comparison or an original-master codec benchmark. Short-window packet-rate matching is not a whole-episode equal-size trial.

## Repair direction

Use the Episode4 overlay and Episode5 grain transitions as explicit regression fixtures. Acceptance must cover texture amplitude and spatial structure, temporal appearance, line detail and banding alongside full-reference scores. The observed mismatch requires tracing denoising, coded base and synthesized grain separately before selecting a production change. A global FGS-off switch, AQ-off switch, simple SVT swap or larger bitrate is not validated as the repair. Original-video restoration remains the only already-verified way to recover the exact available source, but remains unapproved and is not evidence that a satisfactory re-encode is impossible.

Decision (auto): run bounded original-rate NVENC/SVT controls, then temporal-filter/AQ ablations and a same-codec grain-tuned baseline because the first independent control did not resolve the loss. Keep all commands/logs, final and calibration encodes for follow-up. No production code/config changes.

## Artifacts and reproduction

`run.py` uses the local campaign harness and reads inputs.json from scratch. Default scratch `/tmp/downloads/codex-work/pantheon-encoder-control-20261019`; override PANTHEON_CONTROL_DIR. Optional PANTHEON_CONTROL_KINDS comma-separated kinds and PANTHEON_CONTROL_RESULTS filename allow isolated runs. Existing complete variants are cached; use fresh scratch and copy inputs.json for a full reproduction. Calibration and encode logs record every actual command.

Evidence archive: `/media/merged-storage/cold-storage/docker-apps/pantheon-encoder-control-20261019/`. Retains all AV1/H.264 trial encodes, frame134 PNGs, raw metrics, scripts and logs. Lossless preroll/reference/decoded media and FFMS indexes are reproducible and removed after completion.
