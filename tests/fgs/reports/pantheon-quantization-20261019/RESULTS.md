# Measured results

All rates are actual video packet bytes over the 240 scored frames. Texture values are the established five-frame midpoint summaries, not whole-window means. Screens are provisional, not perceptual acceptance. Baseline scores are reused only after byte-identical output verification.

| Case / arm | Mbps | vs source | VMAF / NEG | VMAF / NEG p1* | SSIMU2 / p5 | Butter2 / max p95 | PSNR Y / SSIM | CAMBI FR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| e04 / baseline | 10.02734 | -0.02% | 90.59 / 89.33 | 79.59 / 78.13 | 61.02 / 42.67 | 1.476 / 9.64 | 41.84 / 0.9922 | 0.5881 |
| e04 / qp4 | 121.21537 | +1108.61% | 98.84 / 98.24 | 96.24 / 95.25 | 91.01 / 86.58 | 0.342 / 3.81 | 54.25 / 0.9998 | 0.0000 |
| e04 / qp8 | 59.45063 | +492.77% | 97.55 / 96.61 | 94.61 / 93.65 | 84.53 / 80.10 | 0.684 / 4.52 | 48.32 / 0.9990 | 0.0000 |
| e04 / budget5 | 10.59857 | +5.68% | 74.25 / 72.50 | 54.67 / 52.84 | 24.69 / -13.80 | 2.488 / 25.49 | 39.11 / 0.9749 | 2.3132 |
| e05-1440 / baseline | 9.67633 | -0.00% | 93.57 / 92.03 | 79.92 / 78.39 | 52.87 / 26.23 | 1.738 / 8.84 | 40.08 / 0.9895 | 0.4294 |
| e05-1440 / qp4 | 129.78461 | +1241.23% | 99.36 / 98.81 | 97.24 / 96.13 | 89.77 / 84.90 | 0.357 / 4.43 | 53.90 / 0.9998 | 0.0000 |
| e05-1440 / qp4-tx32 | 131.04721 | +1254.28% | 99.37 / 98.81 | 97.16 / 96.04 | 91.35 / 87.12 | 0.343 / 4.33 | 54.45 / 0.9998 | 0.0000 |
| e05-1440 / budget1 | 9.69348 | +0.18% | 92.75 / 91.07 | 77.24 / 75.45 | 47.09 / 11.46 | 1.883 / 9.56 | 39.61 / 0.9869 | 0.3248 |

*VMAF/NEG p1 excludes frame 0 only. Other measures include all 240 frames. Lower Butteraugli/CAMBI is better. SSIMULACRA2 can be negative. See results.json for SSIMU2 p1, CIEDE2000, timing, controls and full precision.

| Case / arm | HF source → output | ACF1 source → output | HF correlation | Provisional ROI screen |
|---|---:|---:|---:|---|
| e04 / baseline | 1.8585 → 1.1947 | -0.1842 → 0.1371 | 0.4038 | fail |
| e04 / qp4 | 1.8585 → 1.8481 | -0.1842 → -0.1775 | 0.9587 | pass |
| e04 / qp8 | 1.8585 → 1.7485 | -0.1842 → -0.0982 | 0.8128 | fail |
| e04 / budget5 | 1.8585 → 1.8810 | -0.1842 → -0.1915 | 0.9646 | pass |
| e05-1440 / baseline | 0.6194 → 0.0718 | -0.2278 → -0.0562 | 0.0336 | fail |
| e05-1440 / qp4 | 0.6194 → 0.5037 | -0.2278 → -0.1299 | 0.6630 | fail |
| e05-1440 / qp4-tx32 | 0.6194 → 0.5931 | -0.2278 → -0.1799 | 0.8050 | pass |
| e05-1440 / budget1 | 0.6194 → 0.6344 | -0.2278 → -0.2128 | 0.8291 | pass |

QP4 uses realized qindex 16 at the diagnostic ROI; QP8 uses 32. E05 qp4-tx32 and budget1 include a global 32-pixel transform cap. Budget maps hold the SB-aligned diagnostic rectangle at 16 for all 336 input frames. E04 budget5 is 5.68% above source and is **not a matched-rate result**. E05 budget1 is +0.18%. Both budget attempts fail whole-window quality. These are ten-second windows, not episode equal-size benchmarks.
