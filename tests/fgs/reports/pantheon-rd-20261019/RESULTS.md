# Measured results

Rates use240 scored video-packet positions after96 preroll frames. Runtime covers all336 input frames; x264/x265 includes both passes. Instrumented SVT lp1, x264 four threads, and x265 pool4/frame-threads2 are different execution policies, so these are observed costs rather than a controlled encoder speed ranking.

| Case / arm | Mbps | Source multiple | Encode seconds | VMAF / NEG | VMAF p1* | SSIMU / p5 | Butter / max p95 | CAMBI full-ref mean / max |
|---|---:|---:|---:|---|---:|---|---|---|
| e04 / budget1 | 10.00999 | 0.998 | 66.932 | 85.42 / 83.88 | 70.649 | 44.18 / 15.75 | 1.927 / 15.73 | 1.87410 / 5.43649 |
| e04 / high2x | 23.81770 | 2.375 | 94.025 | 94.41 / 93.12 | 87.802 | 68.70 / 58.98 | 1.202 / 7.77 | 0.22448 / 2.90143 |
| e04 / q32-tx32 | 59.27086 | 5.910 | 63.330 | 97.56 / 96.62 | 94.776 | 84.87 / 80.36 | 0.679 / 4.56 | 0.00000 / 0.00011 |
| e04 / x264-2x1 | 20.16340 | 2.010 | 29.799 | 94.56 / 92.96 | 90.525 | 72.56 / 67.99 | 1.198 / 5.11 | 0.42804 / 3.48970 |
| e04 / x264-search11-4x1 | 40.17652 | 4.006 | 76.684 | 96.61 / 95.21 | 93.623 | 84.26 / 80.20 | 0.740 / 3.36 | 0.00015 / 0.00793 |
| e05-1440 / budget0 | 10.01947 | 1.035 | 72.151 | 92.96 / 91.29 | 77.442 | 47.96 / 14.23 | 1.857 / 9.91 | 0.27561 / 1.85942 |
| e05-1440 / budget1 | 9.61704 | 0.994 | 72.892 | 92.88 / 91.22 | 76.708 | 47.75 / 14.40 | 1.866 / 10.12 | 0.31011 / 2.50319 |
| e05-1440 / high2x | 18.15288 | 1.876 | 83.812 | 95.02 / 93.48 | 83.904 | 58.52 / 38.33 | 1.543 / 8.66 | 0.10220 / 1.12995 |
| e05-1440 / q32-tx32 | 68.43754 | 7.073 | 68.717 | 98.62 / 97.75 | 94.212 | 84.47 / 80.42 | 0.688 / 5.47 | 0.00000 / 0.00000 |
| e05-1440 / x264-2x0 | 19.25284 | 1.990 | 34.952 | 95.98 / 94.21 | 89.332 | 66.72 / 60.66 | 1.421 / 6.12 | 0.60844 / 3.70672 |
| e05-1440 / x264-aq1-2x1 | 19.35914 | 2.001 | 32.856 | 94.94 / 93.07 | 88.724 | 67.34 / 61.75 | 1.411 / 6.66 | 0.13353 / 1.36328 |
| e05-1440 / x264-aq2-2x1 | 19.34029 | 1.999 | 32.481 | 90.78 / 88.64 | 86.047 | 63.49 / 55.93 | 1.500 / 11.29 | 0.00237 / 0.13115 |
| e05-1440 / x264-nodeblock-3x0 | 28.97162 | 2.994 | 76.827 | 96.79 / 95.17 | 91.583 | 76.43 / 73.81 | 1.084 / 4.59 | 0.00063 / 0.04771 |
| e05-1440 / x264-search11-2x0 | 19.36834 | 2.002 | 58.649 | 95.16 / 93.23 | 88.833 | 67.63 / 63.13 | 1.399 / 6.26 | 0.07703 / 0.65450 |
| e05-1440 / x264-search11-3x1 | 29.01377 | 2.998 | 74.287 | 96.85 / 95.20 | 91.838 | 76.70 / 74.08 | 1.065 / 4.48 | 0.00215 / 0.07469 |
| e05-1440 / x264-search11-4x1 | 38.68522 | 3.998 | 94.102 | 97.71 / 96.26 | 93.038 | 81.79 / 79.61 | 0.860 / 3.53 | 0.00001 / 0.00188 |
| e05-1440 / x264-search8-3x0 | 29.00634 | 2.998 | 40.432 | 96.73 / 95.07 | 91.521 | 76.17 / 73.13 | 1.096 / 4.88 | 0.00501 / 0.31058 |
| e05-1440 / x265-grain-2x1 | 19.25875 | 1.990 | 219.569 | 96.30 / 94.38 | 88.314 | 62.82 / 55.08 | 1.502 / 6.55 | 0.00000 / 0.00000 |

*VMAF p1 excludes frame0 as explicitly recorded by the established harness. Complete per-frame data and minima remain in the archive. Q32 controls use application-reported execution time; other rows use measured wall time.

## Frozen midpoint texture screen

HF relative error must be within10% and ACF1 absolute error at most0.05. These necessary numerical screens are not perceptual qualification. Correlation, controls, temporal evidence, tails and human playback remain separate.

| Case / arm / ROI | HF error % | ACF1 error | Source HF correlation | HF + ACF pass |
|---|---:|---:|---:|---|
| e04 / budget1 / purple | +2.563 | 0.002833 | 0.9251 | True |
| e04 / high2x / purple | +2.457 | 0.001767 | 0.9232 | True |
| e04 / q32-tx32 / purple | -5.622 | 0.085961 | 0.8136 | False |
| e04 / x264-2x1 / purple | -1.180 | 0.062288 | 0.6623 | False |
| e04 / x264-search11-4x1 / purple | +3.800 | 0.007079 | 0.8602 | True |
| e05-1440 / budget0 / shirt | -0.764 | 0.039336 | 0.7505 | True |
| e05-1440 / budget0 / background | -55.473 | 0.172045 | 0.2712 | False |
| e05-1440 / budget1 / shirt | -0.905 | 0.036961 | 0.7510 | True |
| e05-1440 / budget1 / background | -59.873 | 0.189630 | 0.2280 | False |
| e05-1440 / high2x / shirt | -1.877 | 0.046549 | 0.7388 | True |
| e05-1440 / high2x / background | -49.488 | 0.188774 | 0.4082 | False |
| e05-1440 / q32-tx32 / shirt | -52.032 | 0.264434 | 0.3148 | False |
| e05-1440 / q32-tx32 / background | -6.874 | 0.033776 | 0.8834 | True |
| e05-1440 / x264-2x0 / shirt | -30.563 | 0.001290 | 0.1888 | False |
| e05-1440 / x264-2x0 / background | -7.998 | 0.051542 | 0.6769 | False |
| e05-1440 / x264-aq1-2x1 / shirt | -18.944 | 0.048105 | 0.2427 | False |
| e05-1440 / x264-aq1-2x1 / background | -7.464 | 0.050674 | 0.6902 | False |
| e05-1440 / x264-aq2-2x1 / shirt | -6.037 | 0.078871 | 0.4233 | False |
| e05-1440 / x264-aq2-2x1 / background | -7.199 | 0.049301 | 0.7040 | True |
| e05-1440 / x264-nodeblock-3x0 / shirt | -4.360 | 0.066486 | 0.4311 | False |
| e05-1440 / x264-nodeblock-3x0 / background | +0.346 | 0.025608 | 0.8160 | True |
| e05-1440 / x264-search11-2x0 / shirt | -15.841 | 0.047883 | 0.2672 | False |
| e05-1440 / x264-search11-2x0 / background | -3.971 | 0.043459 | 0.7041 | True |
| e05-1440 / x264-search11-3x1 / shirt | -5.247 | 0.057362 | 0.4344 | False |
| e05-1440 / x264-search11-3x1 / background | +0.221 | 0.020969 | 0.8181 | True |
| e05-1440 / x264-search11-4x1 / shirt | +0.821 | 0.035571 | 0.5860 | True |
| e05-1440 / x264-search11-4x1 / background | +2.751 | 0.003576 | 0.8806 | True |
| e05-1440 / x264-search8-3x0 / shirt | -2.534 | 0.057680 | 0.4358 | False |
| e05-1440 / x264-search8-3x0 / background | +2.561 | 0.022002 | 0.8118 | True |
| e05-1440 / x265-grain-2x1 / shirt | -39.664 | 0.195111 | 0.2514 | False |
| e05-1440 / x265-grain-2x1 / background | +0.005 | 0.027010 | 0.7029 | True |

Full control summaries, signed quiet-region HF tails, source/evidence hashes, banding/source comparisons and runtime scope are in results.json. The archive retains all240 texture traces, metric frames, packet lists, decoder checks and source-defined tile measurements. No playback observation is implied.

`budget0` SVT rows are calibration evidence, not decisive matched-original-rate comparisons; use `budget1` for that contrast.
