# Per-scene target-quality zones (2026-11-06)

Prototype: `tests/fgs/target_quality.py`. It detects scenes, merges them to 2-10 s, probe-encodes
each at several QVBR values with the production args, and scores each probe with a grain-aware
metric. It then interpolates a per-scene QVBR (clamped to 20-40) and runs one continuous encode
with `--dynamic-rc` zones. Encoder: production NVEncC 9.38 r4412 in `tdarr-node`.
JSON reports: `/tmp/downloads/codex-work/target-quality-zones/{bd,anime}`.

## Grain-aware metric

The metric compares the probe decoded without grain synthesis against the denoised base that
NVEncC encodes (`--codec raw` with the same `--av1-film-grain` args).

- Two raw runs are bit-identical.
- A raw run with 100 extra lead-in frames differs only at 69 dB Y-PSNR.
- On a 10 s clip at QVBR 30:
  - grain-free decode vs base: 48.5 dB;
  - grain-on decode vs base: 42.8 dB;
  - grain-free decode vs original: 42.1 dB.

So the metric is valid. Standard-VMAF dips to 84-86 in the two worst Black Doves scenes are grain
mismatch: those scenes score 95 on the grain-aware metric. Per-scene scores only span about 92-99,
so probe noise is a large share of the differences between scenes.

## Matched-size results

Values are worst / p10 / mean of the per-scene means.

### Black Doves S02E04, 600-900 s (grainy live action)

Fixed QVBR 30 is 119.0 MB; zones (target 95.4) are 118.7 MB.

| metric | fixed q30 | zones |
|---|---|---|
| grain-aware VMAF | 92.35 / 94.50 / 95.80 | 93.14 / 95.07 / 95.75 |
| standard VMAF | 84.26 / 86.39 / 89.89 | 84.22 / 86.75 / 89.81 |
| SSIMULACRA2 | 43.65 / 46.27 / 54.89 | 42.81 / 46.90 / 54.66 |
| Butteraugli max p95 | 6.71 | 7.39 |

- Chosen QVBR ranged 25-40 (median 31); 5 scenes hit the 40 clamp.
- The grainy close-up at 693 s got QVBR 25.5 and gained about 2 VMAF and 4.5 SSIMULACRA2.
- Every other scene paid for it.

### Kusuriya no Hitorigoto 54, 300-600 s (anime)

Fixed QVBR 30 is 54.6 MB; zones (target 96.9) are 54.3 MB.

| metric | fixed q30 | zones |
|---|---|---|
| grain-aware VMAF | 95.81 / 96.64 / 97.13 | 95.47 / 96.21 / 96.90 |
| standard VMAF | 94.43 / 95.95 / 96.85 | 94.09 / 95.72 / 96.62 |
| SSIMULACRA2 | 81.5 / 84.6 / 87.4 | 74.0 / 78.5 / 85.5 |

Zones are worse on every metric. Butteraugli p95 rose from 3.48 to 5.14.

## Runtime

For 5 min of Black Doves, a plain encode takes 93 s. The zoned route spends about 490 s on analysis:

| stage | time |
|---|---|
| scene detection | 15 s |
| base | 124 s |
| probes | 3 x ~55 s |
| probe scoring | 3 x ~58 s |

The final zoned encode then takes 68-86 s. That is about 6x a plain encode, or roughly 85 min instead
of 14 for a 45-min episode. Probe-predicted size ran 5-10% low, so matching size needed 2-3 extra
final encodes.

## Confound: every zone change forces an IDR and an encoder reset

In `NVEncCore/NVEncPipeline.h` (around line 3235), the dynamic-rc path calls
`NvEncReconfigureEncoder` with `resetEncoder = 1` and `forceIDR = 1`.

With zones, keyframes rose from 31 to 58-60 in 5 min. Each reset also restarts lookahead and rate
control. This likely explains the anime loss, and it handicaps zones everywhere. A rate-control-only
reconfigure without reset or IDR has to be tested before the approach can be judged.

## Native NVEncC outline

| piece | location |
|---|---|
| `--dynamic-rc` parsing | `NVEncCmd.cpp:822` |
| validation | `NVEncCore.cpp:5704` (`CheckDynamicRCParams`) |
| capability check | `NVEncCore.cpp:2397` |
| zone application | `NVEncPipeline.h:3213-3284` |

A native `--target-quality` mode would:
1. detect scenes from the lookahead or decoded luma;
2. estimate complexity from lookahead costs or a short probe pass over frames already in the
   pipeline;
3. emit zones internally.

The hard parts:
- a grain-aware GPU metric inside the encoder;
- probe cost and VRAM, which are shared with Tdarr;
- the IDR on every zone change;
- FGS analyzer continuity;
- keeping shared `rgy_` code compatible with QSVEnc/VCEEnc (use `ENCODER_NVENC` guards).

## Follow-up: zones without IDR/reset (branch `exp/zones-noidr`, 336f23ae)

`f1327e14` (the production binary's source) was rebuilt with the zone reconfigure set to
`resetEncoder = 0; forceIDR = 0`. NVENC accepts that and the output decodes.

- The unmodified rebuild matches production: same size and identical decoded frames.
- Keyframes are back to 31, the same as fixed q30.
- Zone QVBR changes now take effect sluggishly. Only 29 of 63 Black Doves scenes reach within 15% of
  the bitrate the IDR run gave each scene.

Results at matched size (worst / p10 / mean over scenes):

| clip | run | MB | grain-aware VMAF | VMAF | SSIMULACRA2 |
|---|---|---|---|---|---|
| Black Doves | fixed q30 | 119.0 | 92.35 / 94.50 / 95.80 | 84.26 / 86.39 / 89.89 | 43.65 / 46.27 / 54.89 |
| Black Doves | zones, no IDR | 118.9 | 92.97 / 94.82 / 95.74 | 84.47 / 86.68 / 89.86 | 43.82 / 47.56 / 54.99 |
| Kusuriya 54 | fixed q30 | 54.58 | 95.81 / 96.64 / 97.13 | 94.43 / 95.95 / 96.85 | 81.5 / 84.6 / 87.4 |
| Kusuriya 54 | zones, no IDR (+0.75) | 54.57 | 95.54 / 96.46 / 96.98 | 94.20 / 95.82 / 96.70 | 76.1 / 79.9 / 86.2 |

**Verdict:** the IDR was a minor confound. Without it, zones are within noise on grainy live action
and still lose on anime, at about 6x runtime. NVENC QVBR already adapts per frame, so per-scene QVBR
only moves bits around. A native `--target-quality` built on zones is not worth building. Results
are in `/tmp/downloads/codex-work/target-quality-zones/noidr/`.
