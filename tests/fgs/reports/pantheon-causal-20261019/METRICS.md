# Full-window metrics

A uses fixed encoded bases; the experimental arm is an offline native synthesis render, not a new AV1 bitstream. Historical A base/existing scores are reused only after fresh pixel-exact native/FFmpeg validation. B uses matched-rate isolated SVT encodes. Rates count video packet bytes, not container size. VMAF/NEG p1 exclude frame0; all other scores include all240. CAMBI is supplementary CPU banding analysis with16 workers; all required full-reference metric paths are GPU. Butter/CAMBI lower is better.

| Case / arm | Mbps | VMAF / NEG | VMAF p1 / NEG p1 | SSIMU2 / p5 | Butter p95(max) | PSNR Y / SSIM | CAMBI FR mean / max |
|---|---:|---:|---:|---:|---:|---:|---:|
| e04 / A base | 9.993245 | 89.91 / 88.92 | 78.22 / 77.01 | 61.70 / 31.05 | 8.46 | 41.96 / 0.9917 | 0.5423 / 3.5752 |
| e04 / A existing | 9.993245 | 89.82 / 88.80 | 78.23 / 76.98 | 59.70 / 30.91 | 8.57 | 40.90 / 0.9913 | 0.2259 / 3.5752 |
| e04 / A reconstruction-aware | 9.993245 | 89.81 / 88.78 | 78.22 / 77.01 | 59.56 / 31.05 | 8.46 | 41.34 / 0.9911 | 0.3114 / 3.5752 |
| e04 / B baseline | 10.027344 | 90.59 / 89.33 | 79.59 / 78.13 | 61.02 / 42.67 | 9.64 | 41.84 / 0.9922 | 0.5881 / 4.2577 |
| e04 / B allocation | 10.066084 | 89.89 / 88.42 | 78.57 / 77.16 | 57.92 / 38.28 | 10.82 | 41.52 / 0.9916 | 0.2810 / 2.8061 |
| e05-1440 / A base | 9.648396 | 94.20 / 92.81 | 81.99 / 80.41 | 54.46 / 33.31 | 7.75 | 40.84 / 0.9910 | 0.4559 / 2.1271 |
| e05-1440 / A existing | 9.648396 | 93.96 / 92.52 | 81.64 / 79.99 | 52.48 / 32.09 | 7.85 | 40.04 / 0.9905 | 0.2877 / 1.7983 |
| e05-1440 / A reconstruction-aware | 9.648396 | 93.71 / 92.20 | 80.58 / 78.50 | 49.20 / 32.63 | 7.97 | 39.83 / 0.9889 | 0.1448 / 2.1005 |
| e05-1440 / B baseline | 9.676331 | 93.57 / 92.03 | 79.92 / 78.39 | 52.87 / 26.23 | 8.84 | 40.08 / 0.9895 | 0.4294 / 2.7392 |
| e05-1440 / B allocation | 9.748665 | 92.54 / 90.84 | 75.61 / 73.90 | 48.49 / 18.82 | 9.93 | 39.65 / 0.9878 | 0.0710 / 1.3427 |
| e05-1420 / A base | 8.996020 | 96.38 / 95.69 | 95.06 / 94.44 | 85.55 / 82.53 | 2.95 | 45.58 / 0.9981 | 3.6483 / 5.7404 |
| e05-1420 / A existing | 8.996020 | 95.92 / 95.16 | 94.67 / 94.03 | 82.03 / 79.23 | 3.54 | 42.62 / 0.9974 | 0.0000 / 0.0097 |
| e05-1420 / A reconstruction-aware | 8.996020 | 96.11 / 95.34 | 94.80 / 94.11 | 81.84 / 79.00 | 4.16 | 43.09 / 0.9966 | 0.0000 / 0.0012 |
| e05-1460 / A base | 7.833230 | 94.77 / 93.98 | 78.47 / 77.48 | 81.65 / 51.14 | 6.06 | 45.25 / 0.9966 | 2.4712 / 5.8224 |
| e05-1460 / A existing | 7.833230 | 94.54 / 93.69 | 78.36 / 77.39 | 79.32 / 45.15 | 6.30 | 43.46 / 0.9959 | 0.3549 / 3.2989 |
| e05-1460 / A reconstruction-aware | 7.833230 | 94.60 / 93.77 | 78.47 / 77.48 | 80.48 / 51.14 | 6.08 | 43.25 / 0.9954 | 0.1631 / 4.0632 |
