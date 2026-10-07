# Separator plan: remove only the grain synthesis can put back

The bilateral separator decides what goes into the coded picture and what becomes synthesized grain. It is a fine-scale filter: it takes out almost all fine grain but only about 30% of coarse-grain energy, and the rest stays in the base, where NVENC spends bits on it and still destroys most of it. That is the main reason FGS saves only 0–11% on 1080p with the release, and 4–14% with the codec-flat chroma option (fixed build `725585b8`) (against 30% on the 24-frame 4K HDR Taxi clip). Neither existing alternative helps: FFT3D saves at most 1% and loses luma texture on Gentlemen, and the motion separator costs up to 6.6% more bytes and bleeds the previous frame into the base. This plan proposes a two-band separator whose low-frequency band removes grain only where the local band energy is noise, and only as much as the fitted AR grain model can synthesize back. On 1080p live action it should cut file size by about 3% (0-9% by title) at the same QVBR on top of the codec-flat chroma option, at roughly 0.15 ms of extra GPU time per frame and about 6-7.5 working days to a qualified opt-in build. Its main risk is the one that sank the wider bilateral (r4047) and `psd=on`: real low-contrast texture moving into the grain layer. The gates are built around that. Real 4K HDR coverage is only two 24-frame clips (Taxi, Alien), so this plan qualifies 1080p only and proposes how to cover 4K before enabling it there.

## Evidence

All runs use the production flow's video arguments at QVBR 30 and the release candidate `3efac63c` with the option off (trace-identical to release `46d6781c`). Stage numbers come from the attribution traces (`FINDINGS-2026-10-07-GRAIN-ATTRIBUTION.md`); scratch `sep/` and `floor/`.

**Known-answer luma (removed energy = share of the true grain energy the separator takes out; output = played amplitude / true):**

| Grain | Bilateral removed / output | FFT3D | Motion |
|---|---|---|---|
| White, sigma 3 | 0.85 / 0.91 | 0.98 / 0.98 | 0.77 / 0.84 |
| Coarse, sigma 3 | 0.29 / 0.68 | 0.49 / 0.68 | 0.48 / 0.63 |
| Coarse, sigma 6 | 0.28 / 0.69 | 0.31 / 0.72 | 0.31 / 0.70 |

FFT3D removes more coarse grain at sigma 3, but output amplitude does not move: what leaves the base is not synthesized back. That is the failure the model-matched cap targets.

**Real 1080p (played luma HF / source HF, and fixed-QVBR bytes relative to bilateral):**

| Title | Bilateral | FFT3D | Motion |
|---|---|---|---|
| Gentlemen, luma HF | 0.87 | 0.72 | 0.70 |
| Play Dirty p50, luma HF | 1.02 | 1.00 | 0.66 |
| Gentlemen 3,600 frames, bytes | 1 | 0.996 | 1.005 |
| Play Dirty 10 min, bytes | 1 | 0.990 | 1.066 |
| Lost Tapes episode, bytes | 1 | 1.003 | 1.026 |

**Byte floor.** Plain NVENC of the source pre-denoised with `--vpp-fft3d sigma=2/4/8` stands in for a separator that removes grain everywhere, including the low-frequency part, at the cost of some detail. Fine luma grain left in the decoded picture falls from 0.40 to 0.33 of source on Gentlemen and from 0.25 to 0.18 on Play Dirty. Luma detail in the most-structured quarter of patches stays within 1% in amplitude (HF 0.98 to 0.96 on Gentlemen, 0.77 to 0.69 on Play Dirty). Chroma detail drops more (Gentlemen Cb HF 0.90 to 0.74). Bytes relative to plain NVENC:

| Title | Plain | FGS bilateral (release) | FGS, codec-flat chroma on (`725585b8`) | fft3d 2 | fft3d 4 | fft3d 8 |
|---|---|---|---|---|---|---|
| Gentlemen 3,600 frames | 1 | 0.975 | 0.961 | 0.902 | 0.875 | 0.854 |
| Play Dirty 10 min | 1 | 0.890 | 0.864 | 0.884 | 0.849 | 0.811 |

## Design

Keep the production bilateral as the fine band and add one coarser band, both spatial (no motion compensation, so no drag).

1. **Fine band (unchanged).** The current two-pass 5x5 bilateral with the per-block sigma map produces `D1`. Fine grain stays exactly as today; white-grain known-answer capture is already 0.92 and must not drop.
2. **Coarse band.** Downsample `D1` 2x2 (box), take the band `L = D1_half - blur(D1_half)` (the octave below the bilateral's cutoff, wavelengths of about 4-8 px), and estimate its noise power `n2` in that band from the same flat training blocks the analyzer already uses.
3. **Model-matched cap.** The analyzer emits one frame late, so the previous frame's fitted AR coefficients are available before the separator runs. From them compute the synthesized grain's power in the same band, `m2`. Remove at most `min(n2, m2)`: the base loses only band energy the AR lag-3 model can put back. If the model cannot represent coarse grain, nothing extra is removed and the result equals today's.
4. **Local gain, not a frame-wide shape.** Per pixel, `gain = max(0, 1 - min(n2, m2) / E_local)`, with `E_local` the local band energy over an 8x8 half-resolution window, and subtract `(1 - gain) * L`, upsampled, from `D1`. Where the band carries structure (`E_local` much larger than the noise), the gain stays near 1 and nothing is removed. This is the difference from `psd=on`, which applied one spectral shape to every block and hit detail on film with little flat area. The existing coherence mask additionally fades removal on directionally coherent blocks.
5. **Same downstream path.** The analyzer fits `source - D` as today, so the fit now sees the coarse component. Template-gain normalization (`1f20fb1c`) already keeps signalled strength consistent for correlated models. Every source-safety rule (constant-patch caps, clean-source blend, codec-flat chroma option) runs unchanged on the new residual.
6. **Opt-in engine.** A new `denoiser=` value (working name `bilateral2`), with production's `bilateral` untouched, so the release stays trace-identical until the flow switches. Chroma uses the same scheme on the half-resolution planes.

## Expected file-size saving

Relative to the live-action baseline the flow will run (codec-flat chroma on), the pre-denoised plain encodes are:

| Title | fft3d 2 | fft3d 4 | fft3d 8 |
|---|---|---|---|
| Gentlemen (digital, fine to medium grain) | -6.1% | -9.0% | -11.1% |
| Play Dirty (35 mm, coarse grain) | +2.4% | -1.7% | -6.1% |

These are upper bounds for a grain-only separator, because the pre-filter also takes detail, mostly chroma (Cb HF in structured patches down 8-18%) and, on Play Dirty, some luma (structured HF down 5-10% across strengths 2-8). A separator that removes the low-frequency grain without that detail should land between the strength-2 and strength-4 points.

**Expected 1080p saving: about 3-6% at the same QVBR on live action with fine to medium grain (Gentlemen-like), and 0-2% on coarse film like Play Dirty, where FGS with the chroma option already saves 13.6% against plain NVENC.** Across both, plan on about 3%, with 0-9% as the range. This is two titles; the prototype phase re-measures it on the held-out windows and stops the work if the saving is under 2%.

The texture side matters as much as bytes: on the known-answer coarse grain, output amplitude is stuck at 0.68 with every existing separator, and real 1080p luma texture is already 0.87-1.02 of source with bilateral. The gain to expect is coarse-grain fidelity plus the byte saving above, not a large change on fine-grain digital footage.

## Cost

| Item | Estimate |
|---|---|
| Offline prototype (numpy on the submission-trace raw dumps already in scratch; KAT capture, structured-patch detail, bytes via plain NVENC of the prototype base) | 1-1.5 days, under 1 GPU hour |
| CUDA: 2x2 downsample, half-resolution band and local energy (one kernel), model band power on host from the AR coefficients, upsample-and-subtract fused into the existing bilateral output pass | 2-3 days |
| Tests: KAT checks for the new engine, a moving coarse-grain-over-detail fixture (the static `coarse_detail` cannot show substitution on motion), CPU tests | 1 day |
| Qualification: full gate, held-out texture, census, base-fidelity canary, drag probe, fixed-QVBR bytes, flow tests for the switch | 1.5-2 days, about 8-10 GPU hours shared |
| **Total to a qualified opt-in build** | **about 6-7.5 working days** |
| Runtime per 1080p frame | bilateral today is 2 passes x (128 + 54) us = 0.36 ms; the coarse band adds about 0.25x that plus resampling, about 0.15 ms. Tdarr's single stream is latency-bound at about 8.3 ms/frame, so up to about 2% throughput if not hidden. 4K: about 0.6 ms. |
| Memory | two half-resolution work planes per frame (about 1.5 MB at 1080p 10-bit) |
| Host synchronization | none added; the model band power uses coefficients already on the host |

## Risks and how each is gated

| Risk | Earlier evidence | Gate |
|---|---|---|
| Substitution: low-contrast real texture (skin, fabric, foliage) moves into the grain layer | r4047 wider bilateral: synthesized grain up, base smoothed by the same amount, fidelity down at unchanged total energy | Base-fidelity canary (`grain-base-canary.sh`, Casino, grain-off decode vs source): no worse than bilateral. Structured-patch detail ratio (most-structured quarter per band, luma amplitude and HF): within 1% of bilateral on every held-out window |
| Detail damage on real film with little flat area | `psd=on`: real-film fidelity fell monotonically with shaping strength | Local gain (step 4) plus the KAT systematic-edge check (<= 1.5 RMS, as `fgs_kat.py`) and the new moving coarse-over-detail fixture |
| Removing grain the model cannot synthesize (coarser than AR lag 3) | Attribution: coarse output amplitude 0.68 with all three existing separators; removed energy only turns into texture if the model can represent it | Model-matched cap (step 3); known-answer coarse output amplitude must rise, not just base energy fall |
| Temporal instability from per-frame band gains | Flicker work 2026-09-12 | Flicker regression and periodic stages of the full gate, unchanged thresholds |
| Clean sources and animation | Clean-source rules, codec-flat chroma guard (c) | Constant-patch census zero, library-scan detector Clean on the animation episodes, guard fixtures zero. The band of a constant patch is zero by construction |
| Metrics that reward lost grain | Plain wins every FR metric while up to 2.2x larger; SSIMULACRA2 prefers grain-destroying encodes | FR metrics are informational only. Decisions rest on grain axes vs source, base fidelity, detail ratio, drag and bytes |

## Coverage limit: 4K HDR

Real 4K HDR evidence is two 24-frame clips: Taxi (coarse 35 mm, PQ) and Alien (PQ). The known-answer set adds synthetic PQ grain, but synthetic coarse PQ grain already behaves differently from real footage (AR rejection on 53-88% of synthetic frames, none on Taxi or Alien). Two clips of 1 second each cannot qualify a separator change for 4K, where FGS already saves about 30% and a regression would cost the most.

Proposal: qualify and enable `bilateral2` for sub-4K live action only (the flow already routes 4K separately, before the animation check). Before any 4K enablement, add two or three longer 4K HDR live-action windows (several minutes each, grain-heavy and clean) from verified originals, chosen and frozen before any result, outside the reserved corpus. Choosing those titles is your call.

## Phases and stop points

1. **Prototype (offline).** Stop if, on the known-answer set, coarse output amplitude does not rise by at least 0.1 (from 0.68) while white-grain capture stays at or above 0.90 and systematic edge stays at or below 1.5, or if the prototype base saves under 2% at fixed QVBR on Gentlemen and Play Dirty.
2. **CUDA build, opt-in.** Trace-identical to the release with the default engine; CPU tests and the full gate pass with the default.
3. **Qualification with `denoiser=bilateral2`.** The gates above, plus fixed-QVBR bytes on held-out 1080p live action and matched-bitrate controls against production and plain NVENC. Kill if the gain is confined to one title, if any texture axis worsens while another improves, or if base fidelity drops.
4. **Flow.** Sub-4K live action only, through the same flow variable mechanism as the codec-flat chroma option.
