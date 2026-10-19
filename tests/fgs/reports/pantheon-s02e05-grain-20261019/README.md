# Pantheon S02E05: grain around 24 minutes

Read-only investigation of the user's reported conspicuous grain. Three 240-frame, 1080p24 windows from the untouched AMZN H.264 download versus the existing library AV1, decoded with dav1d grain enabled and disabled. Zero frame offset wins all three alignment checks. This does not reproduce the user's player/display pipeline.

| Window | VMAF on/off | NEG on/off | SSIMULACRA2 on/off | VMAF p1 on/off |
|---|---:|---:|---:|---:|
| 23:40–23:50 | 94.92 / 95.29 | 93.95 / 94.35 | 78.01 / 81.01 | 93.33 / 93.71 |
| 24:00–24:10 | 90.45 / 90.59 | 88.86 / 89.03 | 38.16 / 39.62 | 71.13 / 70.58 |
| 24:20–24:30 | 92.33 / 92.45 | 91.25 / 91.39 | 69.85 / 71.43 | 64.30 / 63.63 |

P1 excludes frame zero. VMAF/NEG, PSNR, SSIM and CIEDE use the patched CUDA vmaf build; SSIMULACRA2/Butteraugli use campaign.py's FFVship GPU helper. All six metric arms contain 240 frames. CAMBI is supplementary. Grain changes penalize full-reference similarity even when their appearance is acceptable: these scores are not standalone grain-quality verdicts.

## Texture evidence

Original screenshots show conspicuous grain at 24:05 and 24:25. The library changes the distribution and structure; this is not uniformly excessive added grain.

Five paired frames (116,118,120,122,124) around each midpoint, HF sigma in 8-bit luma units:

| Time / region | Source HF | Library on HF | Library off HF | Source / on residual ACF, lag 1 |
|---|---:|---:|---:|---:|
| 23:45 shirt | 1.203 | 1.226 | 0.049 | -0.313 / -0.337 |
| 23:45 dark background | 0.624 | 0.836 | 0.017 | -0.312 / -0.338 |
| 24:05 shirt | 0.619 | 0.048 | 0.048 | -0.228 / -0.227 |
| 24:05 background | 1.778 | 0.645 | 0.269 | -0.192 / -0.142 |
| 24:25 shirt | 4.142 | 3.140 | 3.140 | -0.180 / -0.079 |
| 24:25 forearm | 1.685 | 0.296 | 0.296 | -0.233 / -0.000 |

At 24:05 the selected shirt region retains about 8% of the source's HF amplitude, versus 36% in the background. At 23:45 the dark-background amplitude is about 34% higher, while the shirt amplitude is similar; ACF is not identical. At 24:25 the conspicuous shirt texture is present in the coded base: grain-on and grain-off frames are pixel-identical at sampled indices 96,116,118,120,122,124 in the 24:20 window (whole-frame on-minus-off sigma zero). There is added grain on other sampled frames in that window. This alone does not establish inappropriate temporal switching, since scene content changes.

HF/ACF describe high-frequency luma residuals, not pure grain in isolation; edges, motion and existing compression affect them. Exact ROI coordinates and per-frame values are in texture-check.json. These measurements corroborate spatially uneven texture retention; they do not isolate the encoder's denoiser, rate control, grain estimator or decoder as the cause. Decoder grain-off is not an encode with FGS disabled.

## Interpretation of the earlier Episode 4 bitrate result

The user's equal-size question concerns the earlier QVBR22 **FGS-disabled encode**: 14.102 Mbps and VMAF93.36 against a 10.029 Mbps original window. The season-wide 81% storage saving does not answer that objection. FGS cannot be the whole explanation for the FGS-disabled result. The tested NVENC configuration failed to preserve some texture even with more bits; this does not establish a limit of AV1 itself. No alternate AV1 encoder or master-source codec comparison has yet been run. The input is already compressed, and the short encode's bitrate is a measured window rate, not a whole-episode equal-size trial.

The AV1 standard specifies the bitstream and decoding process, not one mandatory encoder search/optimization procedure. AOMedia's grain report describes denoising and modeling followed by synthesis and specifically notes that denoising quality matters for preserving details:
- https://aomedia.org/specifications/av1/
- https://aomedia.org/docs/CWG-C051o_TR_AOMedia_film_grain_synthesis_technology_v2.pdf

## Reproduction and artifacts

Run `python3 run.py` then `python3 texture_check.py` on this host. Scratch defaults to `/tmp/downloads/codex-work/pantheon-s02e05-grain-20261019`; set PANTHEON_AUDIT_DIR to override. run.py reuses only complete results entries, so recreate scratch for a complete reproduction including decoded intermediates. Inputs point to the original download and actual library file. PNGs are exact frame120 extracts, not re-encoded previews. All metrics, screenshots and scripts are archived at `/media/merged-storage/cold-storage/docker-apps/pantheon-s02e05-grain-20261019/`. Reproducible decoded MKVs and FFMS indexes were removed after analysis.

Decision (auto): diagnose three windows around the user's timestamp, preserving source references and paired HF/ACF. No media, production settings, Tdarr flows or services were modified. Prior restoration/bypass proposals remain unapproved.
