# Bilateral separation with source-fitted grain — 2026-08-03

> Quality-first research checkpoint. Nothing here was deployed to Tdarr.
> Production remains on the conservative r4069 bilateral/residual path;
> `modelsrc` remains default-off, PSD remains absent, and no motion-test
> environment variable is set in production.

## Question

The integrated source-fit campaign established that fitting the AV1 AR model
from source flat blocks fixes the residual fit's incorrect spatial grain
structure, but its large compression result used an experimental motion separator
that has not cleared perceptual disocclusion review. This experiment isolates
the architectural grain-model change from that separator risk:

```text
production:       denoiser=bilateral, modelsrc=off
bilateral-source: denoiser=bilateral, modelsrc=on
```

The candidate therefore keeps the production base operator and changes where
the grain model is measured. Compression is secondary in this gate.

Harness support is commit `ebd98ffa`. The six-film run used the pinned binary:

```text
/home/bardie/.cache/fgs-gate/builds/pin-603c2eea-1785764448/build-gate/nvencc
SHA-256 8bff5e6dbbfc2a66590a822bcefaa4d123ab7293361eaf4e8c83d8ef786f0ab0
```

Artifacts are retained under:

```text
/media/merged-storage/media/test-encodes/sourcefit-bilateral-quality-20260803/
```

## Safety and isolation

- all six direct AV1 streams passed complete `libdav1d -xerror` decoding;
- every quality pair passed exact frame-count and relative-PTS validation;
- all quality crops retained matching limited-range BT.2020/PQ metadata;
- the complete CPU gate passed 113/113 after the arm was added; and
- Taxi Driver's exact normative emission audit found zero mismatches in
  14,815,232 synthesized pixels, zero maximum pixel error, matching table and
  bitstream models on all seven frame pairs, and predicted/delivered amplitude
  of exactly `1.0000`.

The last result localises any remaining amplitude error upstream of AV1
emission. It is not a mux, decoder, random-seed or normative-synthesis error.

Switching `modelsrc` does not produce a byte-identical grain-disabled luma
payload. A deterministic fixture check found that about 1.7% of luma samples
move by at most one 8-bit code; chroma is unchanged. This is not a changed
bilateral separation result. `kernel_fgs_level_compensate` deliberately adjusts
the coded luma base according to the signalled strength LUT so that clipping
the later synthesized grain does not lift black levels. A different correct
grain curve therefore produces a slightly different compensated base. The
grain-disabled decoded base is scored below instead of being assumed equal.

## Grain texture: the architectural fix survives bilateral

`temporal_grain_report.py` used the same source-selected, temporal-static
blocks for both arms. Lag-1 and lag-2 are amplitude-independent spatial scale
descriptors: a residual fit that whitens coarse film grain drives them toward
zero, while a correct source fit follows the source.

Mean absolute luma synthesis error across the six films:

| arm | lag-1 MAE | lag-2 MAE |
| --- | ---: | ---: |
| production residual fit | 0.2231 | 0.3434 |
| bilateral source fit | **0.0202** | **0.0357** |

Per-title values make the change concrete:

| title | source lag-1 / lag-2 | production synthesis | bilateral-source synthesis |
| --- | ---: | ---: | ---: |
| Casino | 0.774 / 0.388 | 0.514 / -0.077 | **0.762 / 0.379** |
| Interstellar | 0.758 / 0.442 | 0.503 / 0.008 | **0.792 / 0.500** |
| Scarface | 0.285 / -0.002 | 0.144 / -0.094 | **0.317 / 0.024** |
| Taxi Driver | 0.804 / 0.438 | 0.564 / 0.003 | **0.814 / 0.491** |
| The Deer Hunter | 0.531 / 0.040 | 0.319 / -0.237 | **0.526 / 0.047** |
| The Shining | 0.681 / 0.257 | 0.452 / -0.102 | **0.711 / 0.317** |

This is the primary quality result. The source-fit architecture fixes the
fine-versus-coarse grain problem without requiring the motion separator.

Production lag-2 is negative on four of six titles. On Casino, Deer Hunter and
The Shining it has the wrong sign relative to a positive source; on Scarface it
turns an effectively zero source (`-0.002`) into a material negative
correlation (`-0.094`). Calling production merely "over-fine" understates the
failure: it often synthesizes a spurious anti-correlated distance-2 structure.
That is a plausible mechanism for grain that reads as electronic noise rather
than film texture, and makes source fitting a structural correction rather
than a tuning preference.

## Luma strength: corpus closure is good; shape is still open

Equal-frame amplitude means overweight low-grain frames. The decision uses
the variance-weighted production-static closure population instead:

| title | production played total | bilateral-source played total |
| --- | ---: | ---: |
| Casino | 0.683 | **0.955** |
| Interstellar | 0.728 | 1.060 |
| Scarface | 0.851 | **0.998** |
| Taxi Driver | 0.684 | **0.992** |
| The Deer Hunter | 0.776 | **0.968** |
| The Shining | 0.683 | **0.980** |
| **mean** | **0.734** | **0.992** |
| **MAE to 1.000** | **0.266** | **0.028** |

Measured base-plus-synthesis variance predicts played total within 0.009 on
every candidate title. This independently agrees with the exact Taxi emission
audit.

The corpus aggregate does not close the per-luma question. All three flagged
candidate bands are the brightest populated `0.375--0.500` band:

| title/band | blocks | played total | direction |
| --- | ---: | ---: | --- |
| Taxi Driver 0.375--0.500 | 233 | **0.890** | low |
| Interstellar 0.375--0.500 | 34 | **1.278** | high, thin population |
| The Deer Hunter 0.375--0.500 | 258 | **1.344** | high |

The source-fit architecture is therefore right at corpus level but does not
yet justify claiming accurate luma-shaped strength on every film.

## Chroma: texture fixed, amplitude not cleared

Real-film U/V use the same source-luma flat/static mask mapped exactly to
16x16 4:2:0 blocks. Source fitting also fixes chroma spatial scale:

| plane | production lag-1 / lag-2 MAE | bilateral-source |
| --- | ---: | ---: |
| U | 0.1915 / 0.1979 | **0.0249 / 0.0241** |
| V | 0.3124 / 0.2908 | **0.0447 / 0.0354** |

The current chroma report's amplitude field is an equal-frame diagnostic, not
the variance-weighted shipping gate used for luma. It nevertheless exposes a
real open issue:

| plane | arm | mean played total | MAE to 1.000 | observed high titles |
| --- | --- | ---: | ---: | --- |
| U | production | 0.866 | 0.181 | Deer Hunter 1.139 |
| U | bilateral-source | 1.024 | **0.073** | Deer Hunter **1.286** |
| V | production | 0.895 | 0.129 | Deer Hunter 1.072 |
| V | bilateral-source | 1.120 | 0.126 | Taxi 1.173, Deer 1.234, Shining 1.245 |

Texture improves by roughly an order of magnitude, but V amplitude does not.
Its mean actually inverts from production under-delivery (`0.895`) to
candidate over-delivery (`1.120`), with three titles above `1.17`; the slightly
smaller MAE hides that directional change. U genuinely improves overall, but
its worst title, Deer Hunter, worsens from `1.139` to `1.286`.
The existing temporal leak closure intentionally rewrites only the luma
strength statistics. Chroma still uses the spatial source-minus-base estimate,
so it is now the most direct analyser-quality gap. Do not hide this with a
fixed chroma multiplier; the title and plane spread is already large enough to
repeat the fixture-threshold mistake.

## Base fidelity

Grain-disabled candidate output is production-equivalent on the six-film
quality crops:

| metric | production mean | bilateral-source mean | delta |
| --- | ---: | ---: | ---: |
| VMAF | 84.1141 | 84.3046 | +0.1905 |
| VMAF p1 | 79.2270 | 79.4576 | +0.2306 |
| PSNR-Y | 42.2441 | 42.2386 | -0.0055 dB |
| SSIMULACRA2 | 26.1549 | 25.9614 | -0.1935 |
| SSIMULACRA2 p5 | 15.4831 | 15.3414 | -0.1417 |
| Butteraugli 2-norm | 2.4852 | 2.4907 | +0.0055 |
| Butteraugli max p95 | 10.4883 | 10.5771 | +0.0888 |

Deer Hunter is the largest single-title movement: VMAF +0.863 and
SSIMULACRA2 -0.740. That is small enough to clear continued research, not a
substitute for perceptual review.

Full-reference metrics on the finished grain-on frames are much worse
(mean VMAF -4.67, SSIMULACRA2 -27.63, Butteraugli +1.08). This is the known
stochastic-grain trap: source grain and correctly shaped decoder synthesis are
independent fields at different pixel positions. Those numbers must not be
reported as evidence that source-fitted grain is perceptually worse. Base
fidelity, energy closure and amplitude-independent texture answer separate
questions.

The audit's fixed-energy follow-up now isolates the previously open scale term.
On The Shining's bit-identical base, source-fit coarse grain loses `0.84` VMAF
to production-fine grain at matched production-like energy and `1.48` at
matched candidate-like energy. PSNR-Y is flat at the higher level. VMAF
therefore penalises coarser grain more strongly at equal energy; see
`FINDINGS-2026-08-03-AMPLITUDE-MATCHED-TEXTURE.md`. The static luma-only
factorial explains about 61% of the dynamic stream's finished VMAF gap. The
remainder is not a quality finding and the playback gate remains necessary.

## Compression and timing

The six candidate streams total 116,099,448 bytes:

- 23.06% smaller than the 150,902,000-byte plain corpus;
- only 0.248% larger than the 115,812,295-byte production corpus.

That is the intended trade for this quality-first arm: it retains production's
compression rather than motion's experimental 46.4% saving. Its six encodes
finished in 91.1 seconds versus 135.2 seconds for the retained production run,
but the binaries contain different performance commits, so the 0.674 ratio is
not attributed to source fitting and is not a speed finding.

## Parallel separator lead rejected offline

Before returning to bilateral, an aligned-pixel photometric confidence was
tested on the labelled motion-occlusion fixture after paired SAD admission.
Known-bad versus control separation was weak: raw absolute difference AUC was
about 0.63, detail-region variants remained about 0.63, and normalising by
block SAD reduced it to about 0.58. A threshold above 24 8-bit codes rejected
10.9% of labelled bad samples but still rejected 1.44% of controls. That is not
enough evidence for another CUDA admission gate, so no implementation was
written.

## Decision

1. Keep production unchanged and keep `modelsrc` default-off.
2. Promote **bilateral + source fit** to the leading quality architecture. It
   fixes luma and chroma grain scale while retaining the trusted separator and
   production-sized output.
3. Do not promote it to Tdarr yet. Per-luma strength and chroma amplitude are
   still open, and finished-output full-reference metrics cannot clear the
   perceptual gate.
4. Next, add a variance-weighted U/V closure using the same fixed source-luma
   masks, then test a per-plane temporal source/base strength estimate offline.
   Implement chroma temporal closure only if it closes all six films without a
   fixed corpus multiplier.
5. Run the blind production-versus-bilateral-source playback comparison for
   Taxi Driver, Interstellar, Deer Hunter, Casino and The Shining. Judge grain
   scale and real detail first; explicitly inspect bright flat regions,
   dark-band lift and chroma crawling. Because per-luma and chroma strength are
   still open, observations in those known failure regions confirm the
   measurement gaps rather than deciding the architecture alone.
6. Before any universal production default, rerun the general-content corpus
   with plain, production and bilateral/source-fit arms. Include clean digital,
   animation and the known Drag Race/Stormester separator failures. Passing the
   synthetic clean KAT is necessary but does not establish real-content safety.

   **Completed later on 2026-08-03:** the gate does not clear a universal
   default. See `FINDINGS-2026-08-03-GENERAL-SOURCEFIT-GATE.md`. Source fitting
   remains the leading real-film architecture, but every tested content class
   produced a grain model and the general-content guard rails worsened. Keep
   `modelsrc` default-off while a semantic admission layer is investigated.
