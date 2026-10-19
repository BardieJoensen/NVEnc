# Pantheon library quality audit — 2026-10-19

The sampled Season 2 library encodes average **94.20 VMAF / 93.26 VMAF-NEG**, with substantial scene variation. **S02E04 is the main concern:** its textured scene around **20:49** is visibly smoothed compared with the original. These results do not justify a blanket fidelity pass for the series.

All 16 library episodes are 1920×1080 AV1. Season 2 has eight matching original H.264 AMZN WEB-DLs in long-term seeding. Season 1 originals were not found in the downloads or merged-storage search, so its fidelity remains unmeasured. All 24 Season 1 sample decodes completed with the expected 240 frames.

## Season 2 results

Each row pools three 240-frame windows, starting at 20%, 50% and 80% of that episode's runtime. These are sample results, not whole-episode scores. VMAF p1 excludes frame zero of each window; higher is better for VMAF/NEG and SSIMULACRA2. Butteraugli max-norm p95 is lower-is-better and flags localized differences.

| Episode | VMAF | NEG | VMAF p1 | SSIMULACRA2 | Butteraugli p95 |
|---|---:|---:|---:|---:|---:|
| S02E01 | 93.33 | 92.50 | 87.66 | 72.67 | 8.71 |
| S02E02 | 95.13 | 94.06 | 91.92 | 75.45 | 4.53 |
| S02E03 | 94.07 | 93.21 | 89.59 | 73.36 | 4.95 |
| S02E04 | 91.95 | 90.85 | 69.61 | 59.89 | 10.09 |
| S02E05 | 93.94 | 92.87 | 88.77 | 62.16 | 6.88 |
| S02E06 | 95.69 | 94.67 | 85.56 | 75.39 | 5.97 |
| S02E07 | 95.77 | 95.08 | 90.97 | 73.35 | 8.07 |
| S02E08 | 93.69 | 92.85 | 87.60 | 77.91 | 4.66 |

Across 5,760 scored source frames: PSNR-Y **43.38 dB**, SSIM **0.9959**, SSIMULACRA2 **71.27**, Butteraugli max-norm p95 **7.42**. The combined VMAF p1 is **77.14**, largely reflecting Episode 4's weak scene. Season 2 occupies **4.588 GiB vs 24.089 GiB** for the original downloads, an **81.0% container-size reduction**. All eight retain a 5.1 E-AC-3 track alongside default Opus stereo; this is a stream-metadata check, not an audio fidelity measurement.

## Findings

- **S02E04, 20:43.493–20:53.503:** window VMAF **84.50**, NEG **83.32**, SSIMULACRA2 **46.55**, Butteraugli p95 **11.19**. The inspected content frame near 20:49.082 scores **64.26** VMAF. Source and library show the same scene and moment; texture is substantially reduced in the library. Multi-frame alignment selects zero offset. Grain-off VMAF is **84.49**, so the loss remains in the coded base; this audit does not isolate the production processing stage responsible.
- A five-frame texture check around that Episode 4 frame finds background high-frequency sigma **1.8585 → 0.6584** in 8-bit luma units, retaining **35.4% of the source amplitude**. Residual ACF at lags 1/2/3 changes from **−0.1842/−0.0954/+0.0163** to **+0.0146/−0.0675/−0.0483**. Energy and spatial structure both differ. This is a selected 400×400 background patch across five frames, not a season-wide grain statistic.
- **S02E01 near 33:41:** visual inspection shows softer rock texture and fine detail. Its 80% window averages **90.22 VMAF**; the inspected content frame scores **87.38**.
- **S02E05** also has lower SSIMULACRA2 than most episodes (**62.16** pooled), despite **93.94 VMAF**. Treat the differing metrics as complementary evidence, not interchangeable pass/fail ratings.
- CAMBI averages **0.128 source / 0.154 library** with grain enabled, versus **2.024** on the grain-disabled base. S02E05's 20% window has **1.132 vs 0.019 source**. Banding is therefore scene-dependent; the overall mean alone should not be read as “no banding.”
- Grain synthesis changes decoded pixels in **23/24** scored windows. Turning it off raises average VMAF only **0.14**. Full-reference scores penalize uncorrelated synthetic grain and do not by themselves establish whether grain synthesis is perceptually correct. The targeted HF/ACF check supports the specific Episode 4 texture-loss observation.

## Method and validity

The installed `tests/fgs/campaign.py::score` runs SSIMULACRA2/Butteraugli through FFVship CUDA and VMAF/NEG, PSNR, SSIM and CIEDE2000 through the patched CUDA vmaf build at **c4a085f6**. The existing `/opt/docker-apps/scripts/library-fidelity/libvsorig.py` feeder supports decoded ffvhuff pairs and adds CAMBI with 16 CPU threads; CAMBI is the only CPU image-quality metric in this run. Tool hashes and image ID are in `provenance.json`.

Reference and library windows are independently decoded frame-accurately; AV1 uses dav1d with explicit grain-on/off control. Resolution, frame rate and duration match for every Season 2 pair. Sixteen-frame alignment checks over ±3 frames choose zero for all 24 windows. All VMAF/NEG and FFVship runs contain exactly 240 frames; no null VMAF/NEG/VIF frames occur. The low Episode 4 score occurs on content, not initialization frame zero.

CIEDE2000 here is a logarithmic score (higher is better), not raw ΔE. Twenty-four pixel-identical frames in S02E01 produce infinity, represented as JSON null. Their equality was verified by decoded frame hashes. `ciede_finite_mean` reports only finite scores, alongside `ciede_perfect_frames`; original metric JSON is preserved. No VMAF null-frame check was relaxed.

Scope: 48 windows / 11,520 unique sampled library frames across both seasons, with full-reference metrics for Season 2 only and both grain states when they differ. This is not a full-runtime corruption scan, audio test, subtitle-sync test, or assessment of unsampled scenes. No media files, production encoder settings or live services were changed.

## Evidence and reproduction

Compact evidence: `summary.json`, `results.json`, `inventory.json`, `texture-check.json`, and `provenance.json`. Raw per-frame metrics, execution log and the four inspected PNG frames are archived at `/media/merged-storage/cold-storage/docker-apps/pantheon-quality-20261019/`.

Run `python3 run.py` using the installed tooling to recreate the audit in `/tmp/downloads/codex-work/pantheon-quality-20261019/`, then `python3 texture_check.py` and `python3 summarize.py`. Set `PANTHEON_AUDIT_DIR` to another scratch directory for a fresh run, or to the archive to summarize existing raw results. The runner caches completed results: use a fresh directory when library files or tools change. Sample MKVs are removed after scoring; retained JSON and inventory establish exactly what was measured.

Auto decisions: use the established three-window campaign sampling scheme; score grain-off separately only when pixels differ; retain missing-original Season 1 as decode-only; verify and separately report infinite exact-match colour scores; add a targeted HF-plus-ACF check for the weakest observed textured scene. These are diagnostic choices, not changes to a production plan.
