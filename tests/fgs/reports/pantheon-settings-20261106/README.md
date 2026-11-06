# Pantheon S02 texture: encoder settings sweep (2026-11-06)

**Verdict: (c) NVENC limit at acceptable cost.** No setting tested recovers the lost background texture in the S02E04 20:43 scene. The remaining options are keep-original, or accepting the loss; that is the user's call.

## Method

- **Encoder:** production nvencc f1327e14, production args, production series bucket QVBR 34 with FGS.
- **Windows:** four frozen windows taken from the original AMZN H.264 downloads, each with 96 frames of preroll and 240 scored frames, zero alignment, 240/240 frames per metric.
  - p04a: E04 at 1243.5 s, the known scene.
  - p04b: E04 at 1865.2 s. The contract said 50%, which coincided with p04a, so the worker used 75%.
  - p01: E01 at 2021 s.
  - p05: E05 at 1440 s.
  - E08 is reserved and was not used.
- **Variants:**
  - prod ladder at QVBR 38, 34, 30, 26 and 22;
  - plain (FGS off) at 34, 30 and 26;
  - retain 0.5 and 0.9 at 34 and 30;
  - aq-strength 1, aq-strength 15 and AQ off, each at 34;
  - tune uhq at 34;
  - tf-level 4 at 34.
- **Comparison:** every variant is compared with the prod ladder at equal size, on:
  - HF ratio and acf for the whole frame and for the known ROI;
  - grain-off base detail, using the instrument from `retention-reopen-20261106`;
  - Butteraugli p95, vmaf_p1 and CAMBI.

## Results

- **The scene needs more bits than the original to approach its texture.**
  - Prod at q34 reproduces the library exactly: 3.31 Mbps, ROI HF 0.38 of source.
  - Reaching ROI HF 0.6 takes 8.3 Mbps, and q22 at 12.5 Mbps reaches only 0.71. The original window is 10.03 Mbps.
  - Earlier controls agree: at the original's rate NVENC keeps 62%, SVT-AV1 1.7 68%, and x264 tune grain 90% (`pantheon-encoder-control-20261019`).
- **No knob gains texture at equal size.**
  - FGS off and retain 0.5/0.9 lower grain-on HF (mean ROI −0.06 to −0.28). Base amp_Y moves only +0.001 to +0.003.
- **AQ flags are no-ops under QVBR with lookahead.** On p04a, aq-strength 1, aq-strength 15 and AQ off give packet- and md5-identical output to prod. Elsewhere the differences are at most 0.4%.
- **tune uhq and tf-level 4 are an efficiency gain, not a texture fix.**
  - Each is 12–16% smaller at q34. At equal size, Butteraugli p95 is better (−0.4/−0.9) and vmaf_p1 is higher.
  - Problem-scene ROI HF drops by 0.18–0.25.
  - Not pursued here: speed and grain qualification would be a separate item.
- **E01 near 33:41 is not a texture-loss case:** frame HF is about 0.96 of source at q34. The loss is concentrated in E04's scene.

## Options for the user

- **Keep-original for E04:** the verified candidate costs +2.43 GB and sits in cold storage at `pantheon-fix-20261019`.
- **Pantheon keep-original allowlist entry:** stops future re-encodes. The proposal is in `pantheon-fix-20261019/`.
- **Accept the loss.**

Files in this folder: `summary.md` holds the per-window tables, `results.json` and `rows.json` hold all rows, and `manifest.json` holds the windows. The scripts are here too.
