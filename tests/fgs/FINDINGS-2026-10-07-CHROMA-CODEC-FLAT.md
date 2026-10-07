# Codec-flat chroma rule: large live-action gain, but it cannot pass the clean-animation guard

Treating flat chroma over grainy luma as codec damage restores colour grain on live action. On fresh held-out windows (Insidious, Marshals, Homegrown) chroma HF rises from 0.08–0.70 of source to 0.62–1.05, amplitude moves toward source, and files get 1.5% smaller (up to 6% on Gentlemen). Every guard fixture stays at zero: monochrome grain, composited graphics, lettering, and variant D's bars, fills and flats. The library-scan detector still grades the animation episodes Clean. But it fails guard (c). In clean-animation census windows, flat colour fills also get chroma grain: Knightfall (an animated film with real luma grain) and, far less, Toy Story 5. None of the signals already in the analyzer separates the two cases: block flatness, the separator residual, whether the luma level is still grained, and temporal persistence. A tighter variant cuts the animation hits by about 30× but gives up most of the live-action gain and still leaves Knightfall at 850–3,600 patches per window. This needs a product decision.

## The rule and its versions (`fix/fgs-chroma-codec-flat-20261007`)

Exactly flat or nearly flat chroma (within the quiet-source limit) is exempt from chroma protection when the co-located luma block is grain-bearing. Grain-bearing means the per-block separator residual, a new luma reduction read back with the existing model statistics, is at least a quarter of the modeled luma grain at that level.

- **Candidate** `e65ea00e`, full from-scratch build, SHA256 `f7572de6c0c138140edb0912fb27ce93e76e3634a9113a4dc7c417e97d86ff25`: the rule above.
- **Tighter variant** `e04ac283` (development build only): additionally requires this frame's luma caps to keep at least half the luma grain at that level.

## Results

| | Variant D | Candidate | Tighter variant |
|---|---|---|---|
| Held-out chroma HF / source (Insidious, Marshals) | 0.08–0.33 | 0.72–1.05 | 0.27–0.89 |
| Held-out chroma HF / source (Homegrown) | 0.33–0.70 | 0.33–0.90 | 0.33–0.81 |
| Held-out bands closer to source (Cb / Cr) | — | 57/61, 53/61 | — |
| Bands > 1.10× source amplitude | 1 (9-patch band) | 1 (same band) | — |
| Fixed-QVBR bytes vs D (held-out / Gentlemen / episodes) | — | 0.985 / 0.938 / 0.996–0.997 | — |
| Guard fixtures (mono SDR/PQ, graphics, lettering) | 0 | 0 | 0 |
| Live-action census windows: luma constant-patch hits | 0 | 0 | 0 |
| Live-action census windows: codec-flat chroma patches grained (RMS median) | 0 (Insidious p70: Cb 1,387) | 284–24,120 per window (0.18–0.48) | 0–19,438 (0.06–0.48) |
| **Knightfall census windows: chroma patches grained** | 0 | **24,428 / 116,117 / 83,668** | 3,594 / 852 / 3,164 |
| **Toy Story 5 census windows** | 0 / 0 / 3 | 3,960 / 225 / 379 | 4 / 18 / 13 |
| Library-scan detector, Amphibia and Lost Tapes episodes | Clean | Clean | — |

Chroma amplitude moves 3–7 points away from source in 14 of 122 held-out chroma bands (mostly Homegrown), while HF moves closer. Combined texture distance improves in 110 of 122. Evidence: scratch `heldout/` (`*-axes-nonflat.json`, reviewed active rectangles), `census/`, `var-c5/`, `guards/`, `anim/`.

## Why no existing signal separates them

| Signal | Live action (Gentlemen, Insidious) | Animation (Knightfall, Toy Story) |
|---|---|---|
| Luma block flat (analyzer's noise test) | Fails for most codec-flat blocks (they sit on textured luma, median sigma 8× the grain model) | — |
| Separator residual ≥ ¼ luma model | Passes | Also passes on Knightfall (real luma grain) and on shaded CG with a small model |
| Luma level still grained after caps | Often protected too (Marshals, Homegrown lose most gain) | Knightfall still passes |
| Flat region also flat in the two previous frames | 0.98 (Gentlemen), 0.82 (Insidious) | 0.92 (Knightfall), 0.66 (Toy Story) |

## Options

1. **Ship the candidate for live action only.** The Tdarr flow already treats animation differently (QVBR 34 vs 30), so it can switch the rule off for animation through a new `--av1-film-grain` option, defaulting to variant D's behaviour. This is a small analyzer option plus one flow argument, not a detector. Live action gets the full gain. Animation keeps variant D exactly. Risk: animation inside live-action libraries, and live action in animation libraries.
2. Ship the candidate everywhere and accept chroma grain on flat colour in animation that carries luma grain (Knightfall-type; 0.2–0.4 RMS median). This breaks your guard (b)/(c) as written.
3. Ship nothing for chroma and keep variant D. Attribution findings and instrumentation stay on the branches.
