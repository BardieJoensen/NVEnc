# Clean-source fix: works, but trips the chroma kill criterion on 4K HDR

The cause of grain on flat picture areas is found and fixed. Production deliberately ignored exactly flat source evidence near black and white (luma ≤20 or ≥232), and allowed up to a quarter code of grain over flat colour. The candidate (v3, binary `4179a32a…`) adds zero grain to every constant test panel, to letterbox bars, and to the retained Insidious, Toy Story, Knightfall and Homegrown witnesses. It barely changes file size (worst so far +1.0%), matches production on the full-reference metrics at equal bytes, and the library-scan detector grades it Clean. But on the 4K HDR Taxi fixture it removes about a third of the chroma grain in the darkest shadows (luma band 0–32: Cb −38%, Cr −35%; whole picture −2% to −4%). That breaks the 10% legitimate-grain kill line. AV1 signals one chroma grain curve per frame, indexed by brightness. Flat chroma at a dark level (bars, and shadow chroma that Taxi's source codec flattened) and grainy chroma at the same level elsewhere in the frame cannot both be honoured. Whether flat black/white areas or dark-shadow chroma grain win is a product decision. The evidence for both options is below.

## Cause (controlled panel test)

1080p synthetic source: a grainy luma ramp (σ 3) with exactly constant 64×64 panels at three grid alignments, chroma grain σ 1.5/1.2, 96 frames, last 32 scored, production flow settings. Added grain is played minus base from the same AV1 stream (dav1d grain on/off), in 8-bit codes.

| Panel / variant | Production added RMS Y / Cb / Cr | Production curve at that level | v3 |
|---|---|---|---|
| luma 16, 20 | 1.9–2.6 / 1.4 / 1.15 | full scaling (167) | 0 / 0 / 0 |
| luma 232, 234 | 2.0–2.4 / 1.4 / 1.15 | full scaling | 0 / 0 / 0 |
| luma 21, 32, 128, 231 | 0 / 0 / 0 | zeroed by `protectSource` | 0 / 0 / 0 |
| letterbox bars at 16 (132 rows) | 1.93 / 1.42 / 1.17 (peaks 10 codes) | full scaling | 0 / 0 / 0 |
| constant chroma over grainy luma | 0 | zeroed | 0 |

`protectSource` returned before any protection when the evidence's luma range sat at or below 20 or at or above 232, and protected only when modeled grain exceeded the source by more than 0.25 code. Mid-level flat patches were already protected at every grid offset. Scripts and receipts: scratch `panel/`, `tools/panel_gen.py`, `tools/panel_measure.py`.

## What changed (three commits on `a1041e3c`)

1. `824638ab`: exactly constant evidence (luma min = max; chroma σ = 0 from integer moments) protects its reconstructed range (±4 codes) at any level, with no small-excess tolerance.
2. `9704aeaf`: that protection is held in a separate `cleanCaps`, combined with production's `sourceCaps` only at curve refit. The first revision had made `hasProtection(0)` true on every letterboxed frame, which opened production's merely-quiet chroma policy and cut Taxi Cr synthesis across luma 57–153.
3. `5bf7c7f9`: the variance-preserving source blend applies only at clean-protected levels. A clean notch takes AV1 scaling points; refit then lowers the curve slightly elsewhere, and blending source grain back at all those levels grew Taxi bytes 7.8%. A scratch diagnostic build showed that blend was the entire cost: notch-only blend gives 0.0%, while a margin of 0 still gave +7.5%.

With no clean protection active, output is production's; production's protection path, gate and curve are untouched. CPU guard test extended for `limitTo`. Only `NVEncFilterFilmGrain.cu` recompiles.

## Clean safety

Constant-patch check: every complete 32×32 Y / 16×16 chroma grid patch in the active picture with exactly constant source; added = played − closer of base or legal-clipped base; no floor. It reproduces the census Insidious full-history witness exactly (Y 11 / Cb 15 frames; 0.831 / 0.639 RMS). Frames where the decoded base differs from the source by more than 8 codes on average (one-frame slips at cuts, identical in both arms) are reported separately. **Policy positives** are changed samples whose decoded grain index (luma value, or the AV1 luma-pair guide for chroma) stays inside the ±4-code protected interval. Positives outside it are NVENC reconstruction errors (for example a moving object smeared across flat black), where AV1 legitimately applies the curve for the decoded level.

| Witness (frames with a positive / max RMS) | Production | v3 | Variant D |
|---|---|---|---|
| Insidious retained witness, full history (16 f) | Y 11f/0.831, Cb 15f/0.639 | **0** | — |
| Insidious p70, full history | Y 45f/0.835, Cb 83f/0.620 | **0** | — |
| Insidious p10, full history | Y 14f/0.635 (all policy) | Y 4f/0.484, **0 policy** | — |
| Insidious p70 window | Y 45f/0.828, Cb 85f/0.634 | 0 | Y 0, Cb 85f/0.634 |
| Toy Story 5 p70 window | Y 48f/0.354, Cr 3f/0.295 | 0 | Y 0, Cr 3f/0.295 |
| Knightfall p70 window | Cr 37f/0.225 | 0 | 0 |
| Homegrown p10 window | Cr 9f/0.202 | 0 | 0 |
| Taxi letterbox bars (18 f) | Y 0.756, Cb 1.016, Cr 0.524 on every bar patch | 0 | Y 0, Cb/Cr as production |

v3 encoded from frame zero through each title's last window: Insidious (103,930 frames), Toy Story 5 (104,600), Knightfall (79,500), Marshals (43,350), Homegrown (31,350). All 15 census windows have **zero policy positives** in every plane. Toy Story, Knightfall and Homegrown are zero outright. Insidious p10 (Y 4 frames, 0.48) and Marshals p40 (Y 1, Cr 4 frames, ≤0.17) show only reconstruction positives beside cut slips and motion smear. Production shows the same reconstruction cases at Insidious p10, plus 14 policy-positive Y frames there. No encode reported a decode break. Receipts: scratch `fullcheck/`, `full/`.

## Legitimate grain

Source-only selection: least-structured quarter of 32×32 patches per source-luma band, with bars and exactly constant patches excluded. Amplitude is the plane-fit residual, HF the calibrated cross-neighbour residual, plus pooled H/V lag-1/2 autocorrelation. Lost Tapes and Gentlemen score 192 frames after a 48-frame warm-up; Taxi scores all 24 frames.

| Fixture, v3 vs production | All-band amplitude Y / Cb / Cr | Worst band (amplitude) | Worst HF | Max lag change |
|---|---|---|---|---|
| Lost Tapes | 0.0% / +0.2% / 0.0% | −0.5% (Y 160–192) | −9.7% (Cb 192–224) | 0.025 |
| Gentlemen | 0.0% / −0.1% / −0.1% | −0.7% (Cb 32–64) | −3.1% | 0.014 |
| **Taxi 4K PQ** | −1.6% / −2.2% / −3.7% | **−38.3% (Cb 0–32), −35.3% (Cr 0–32)** | −64% (Cr 0–32) | 0.40 |
| Taxi, variant D | −1.7% / −0.1% / +0.2% | −4.0% (Y 0–32) | −11.1% (Y 0–32) | 0.058 |

Taxi's source has 32–60 exactly constant 8×8 Cr regions per frame (occasionally Cb), all in the darkest shadows (luma 14–25) over grainy luma. This is most likely the source codec flattening near-black chroma. Its letterbox bars are constant at 10-bit 64. Production's chroma curve keeps Cb synthesis (~40) at luma 0–22 and already spends four of its ten points on a quiet-chroma notch at about 23–57. Any notch at the bars' level merges with it, so a narrower margin does not help (margin 0: Cb −32%). Requiring constant luma as well (variant C) still leaves Cb −30%, because the bars alone cause it.

## Size and artifacts

Fixed-QVBR video bytes, v3 vs production: Taxi 0.0%, Lost Tapes −0.6% (240 f) and +0.58% (full episode), Gentlemen −0.1%, Amphibia episode +0.05%, Insidious full history +1.01%. Variant D: Taxi −0.8%, Lost Tapes −0.6%, Gentlemen −0.1%. No content class exceeds the 2% limit.

Matched rate (both FGS candidates within 1% of production; plain NVENC VBR-matched, Lost Tapes −0.4%, Taxi +0.8%, Gentlemen unresolved at +1.95%), scored with `campaign.score` (vmaf `c4a085f6` CUDA paths, FFVship):

| Fixture | Production VMAF / NEG / SSIMU2 / Butteraugli max p95 | v3 | D | Plain |
|---|---|---|---|---|
| Lost Tapes | 86.25 / 85.32 / 8.60 / 307.8 | 86.33 / 85.39 / 8.67 / 307.9 | same as v3 | 86.60 / 85.70 / 10.19 / 307.8 |
| Gentlemen | 95.51 / 94.33 / 83.42 / 4.18 | 95.53 / 94.35 / 83.44 / 4.15 | same as v3 | 96.58 / 95.35 / 86.33 / 4.64 |
| Taxi | 89.02 / 88.58 / 4.53 / 14.37 | 89.11 / 88.66 / 4.58 / 15.69 | 89.09 / 88.63 / 4.40 / 15.72 | 91.27 / 90.30 / 7.45 / 18.96 |

The candidates match production on mean metrics. Taxi's Butteraugli tail rises 1.3 for both candidates; on 24 frames that is roughly the second-worst frame and is flagged, not concluded. FR metrics cannot judge grain correctness; the grain axes above are the objective.

The library-scan detector (`flatgrain`, dense every 4th frame, scan thresholds) grades both arms **Clean** on the full Amphibia and Lost Tapes episodes (peak 1.99 / 2.06; no story time at level ≥3). Tier-a originals could not be used: copying from the torrent seeding area was refused by the permission system.

## Knightfall temporal jump: unchanged, left as recorded

With full history, v3 emits the same luma curves as production at 477.519–477.602 s, and the dark-band added RMS (base luma < 32) follows the same 0.94 → 0.92 → 0.36 drop. The event comes from a fresh model update, not from clean-source protection. Per the plan it stays recorded for a later slice.

## The decision

| | v3 (strict rule) | Variant D (luma everywhere, chroma as production at black/white) |
|---|---|---|
| Flat panels, bars, black frames: luma | zero | zero |
| Flat black/white areas: chroma | zero | production (about 1 code on Taxi bars; Insidious hair Cb 0.63; Toy Story sky Cr 0.30) |
| Mid-level flat colour (Knightfall, Homegrown) | zero | zero |
| Taxi dark-band chroma grain | −35% to −38% (fails kill line) | preserved |
| Bytes | ≤ +1.0% | ≤ 0% on tested fixtures |

Both are bounded edits to the existing source-safety path. D exists only as a scratch diagnostic build so far; promoting it is a one-condition change to v3 (constant chroma keeps production's active-luma-mean requirement). Neither needs a new framework.
