# Coarse-band separator, phase 1: a byte lever, not a texture lever

The offline prototype removes the octave of grain below the bilateral's cutoff, capped at what the fitted AR grain model can put back and gated locally so texture is left alone. On known-answer coarse grain it raises the share of grain the separator captures from 0.29 to 0.44 (σ3) and from 0.27 to 0.42 (σ6). But estimated output amplitude does not rise: 0.695 to 0.702 and 0.706 to 0.692, against the +0.1 the plan required. The newly captured grain is grain NVENC was already partly keeping in the base, and synthesis now carries it instead. The useful effect is size. At fixed QVBR, identical plain-NVENC encodes of the prototype picture are 2.0% smaller on Gentlemen and 0.9-4.8% smaller on Play Dirty windows. Structured luma detail drops by 0.06-0.14%, and systematic error at panel edges rises 10-13%. By the plan's stop rule (no texture gain), phase 1 stops here. A CUDA build would buy about 1-5% size on grainy 1080p and no visible texture.

## Prototype (scratch `tools/coarse_band_proto.py`, `tools/proto_eval.py`)

- Fine band: the exact release separator output D1, read from the submission-trace raw dump (`46d6781c`-equivalent traced builds).
- Coarse band: L = d - blur5(d) with d the 2x2 box downsample of D1 luma.
- Per 32-code luma band, the noise power n2 of L comes from the quietest quarter of 16x16 half-resolution blocks. The model power m2 is the band share of an AV1 lag-3 AR fit to the residual the analyzer would see with the whole band removed, measured by passing its synthesized field through the same band operator.
- Per pixel: gain = max(0, 1 - min(n2, m2) / E) with E the 8x8 local mean of L squared, and D' = D1 - up2((1 - gain) * L). Chroma unchanged.
- Validation: on coarse σ3 the replica's release capture is 0.287 against 0.29 measured in attribution. The output-amplitude estimate sqrt(kept + fid² x captured) gives the release 0.695 / 0.706 / 0.920 on coarse σ3 / σ6 / white against the measured 0.68 / 0.69 / 0.91.

## Results

Known-answer (flat panels, frames 48-95; energy relative to the true grain):

| Grain | Captured, release → prototype | Kept by NVENC in the base | Output amplitude (estimate) | Panel-edge systematic error | Plain bytes, prototype / release |
|---|---|---|---|---|---|
| Coarse σ3 | 0.287 → 0.436 | 0.247 → 0.134 | 0.695 → 0.702 | 0.93 → 1.02 | 0.72 |
| Coarse σ6 | 0.275 → 0.424 | 0.300 → 0.173 | 0.706 → 0.692 | 2.84 → 3.21 | 0.84 |
| White σ3 | 0.842 → 0.876 (amplitude 0.92 → 0.94) | 0.004 → 0.002 | 0.920 → 0.937 | 0.95 → 0.97 | 0.45 |

The `coarse_detail` fixture (coarse σ6 over static texture) could not test edges: the release passes that source through unseparated (capture 0), so there is no separator output to compare.

Real 1080p, 192 scored frames per window, plain NVENC at QVBR 30 on both pictures:

| Window | Coarse-band energy removed | Bytes, prototype / release | Structured luma detail (base vs source) | Flat grain HF in the base |
|---|---|---|---|---|
| Gentlemen | 0.2% | 0.980 | 0.9975 → 0.9969 | 0.305 → 0.292 |
| Play Dirty p25 | 0.6% | 0.991 | 0.9953 → 0.9942 | 0.129 → 0.124 |
| Play Dirty p50 | 2.0% | 0.952 | 0.9959 → 0.9945 | 0.142 → 0.129 |
| Play Dirty p75 | 0.5% | 0.963 | 0.9963 → 0.9957 | 0.137 → 0.128 |

On real footage the local gain removes very little, because band energy is mostly texture. Where it does remove grain, the bytes follow.

## Against the phase-1 stop rule

| Criterion | Result |
|---|---|
| Coarse output amplitude up by at least 0.1 | No (+0.007, -0.014): stop |
| White capture at or above 0.90 (amplitude) | Yes, 0.94 |
| Systematic edge at or below 1.5 | Panel edges 1.02 (σ3), but σ6 3.21 (release already 2.84); the detail fixture could not be evaluated |
| At least 2% smaller at fixed QVBR on Gentlemen and Play Dirty | Borderline: 2.0% and 0.9-4.8% |

## Correction to the attribution scratch

The attribution's Play Dirty p25 and p75 stage measurements were taken at the nominal window start, but NVEncC's `--seek` began one second later. They compared misaligned frames (luma MAE 36 and 45). The attribution findings cite only p50 (offset MAE 0.64) and the alignment-independent analyzer traces, so their conclusions stand. This prototype uses each encode's first timestamp.

## Evidence

Scratch `/tmp/downloads/codex-work/fgs-fidelity-20261007/sep2/proto/<window>/` (`proto.json`, `eval.json`, `prod.y4m`/`proto.y4m` and their encodes), `sep2/proto/coarse_detail*` (fixture and traced release encode).
