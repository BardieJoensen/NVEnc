# Opt-in codec-flat chroma: qualification of both modes

With the option off, the new build is frame-for-frame identical to the release. With it on, the first full gate run exposed a real defect: a small flat graphic over grainy picture (constant luma and colour, under 64 px, off the 32-pixel block grid) borrowed its block's "grain-bearing" verdict and got colour grain, breaking your guard against grain on composited graphics. The fix (`74d3d744`) judges each 16x16 region by its own luma. The fixed build keeps most of the gain: held-out live-action colour texture is 0.42-1.04 of source (variant D 0.08-0.70), closer than D in 53/61 Cb and 52/61 Cr bands, and files are 1.2% smaller on the held-out windows, 1.4% on Gentlemen and 3.0% on Play Dirty, never larger. Guard fixtures, small graphics and luma checks are all at zero, and the animation episodes still grade Clean. Three gate stages flag with the option on, all by design: the Gentlemen periodic detector sees the intended colour restoration (reviewed below; it follows the source, no new jumping), and two synthetic or animation fixtures assert the very rule the option relaxes (flat colour over noisy luma stays clean). One held-out band remains above 1.10x source amplitude, at variant D's own level. <<GATE2_SUMMARY>>

## What is qualified

- NVEncC `fix/fgs-chroma-codec-flat-20261007`: option `559b80c0` (`--av1-film-grain ...,codec-flat-chroma=on|off`, default off; help text and all three `NVEncC_Options` files), region fix `74d3d744`.
- Release candidate built from scratch in `nvenc-fgs-build:cuda13.3` from a clean pinned clone of `74d3d744`: SHA256 `725585b8e458d12d9fb1709c231f7d6b5846d69148dcc2a2646725356437605b`, r4412 (scratch `fgs-submission-20261005/bin/nvencc-optcand-725585b8`). Option-on runs use the wrapper `nvencc-optcand-725585b8-on`, which appends the option to every `--av1-film-grain` (source `tools/optwrap-725585b8.c`).
- Flow patch, prepared and not applied: `/opt/docker-apps/scripts/apply_flow_v43_live_action_codec_flat_chroma_patch.py` with `tests/test_tdarr_flow_live_action_chroma_patch.py` (both untracked). The bucket router sets `fgsChromaOpt` to `,codec-flat-chroma=on` only for files under `/tv-shows/` or `/movies/` whose show or movie NFO is readable and has no animation genre, using the router's own NFO lookup, before the 4K override and every bucket decision. Everything else gets an empty string: animation roots, animation NFOs, missing NFOs, paths outside the roots, any 4K animation. Both NVEncC argument strings (encode and bitrate sample) carry the variable. Tests: 12 path classes, buckets unchanged against the unpatched router, idempotent patch, rendered arguments, misplaced-block rejection, tracked export untouched. All docker-apps flow tests pass. `--install` exists as in v42 and was not run.

## Option off: identical to the release

Same-run submission trace (schema 2), release `46d6781c` against `725585b8` with the default: all 1,496 frames identical (submitted pictures and grain parameters) on the 21 KAT fixtures and the real fixtures Amphibia, Gentlemen, Lost Tapes, Silo partial and Taxi HDR. The earlier option build `3efac63c` was also identical. CPU tests pass on the pinned clone (119 Python, all C++).

## The defect the gate found, and the fix

`protectSource` checks each 32x32 block and its four 16x16 quiet-source regions. The exemption read the whole block's separator residual and luma mean even for a region, so a quiet region sharing a block with grainy picture inherited the block's verdict. A fixture of six flat graphics (constant Y, U and V; 24-56 px; unaligned) over grainy panels shows it (scratch `smallgfx/`):

| Build | 24x24 | 40x40 | 48x24 | 56x56 | 36x60 | 28x44 |
|---|---|---|---|---|---|---|
| Option off | grained (below evidence size, unchanged since D) | 0 | 0 | 0 | 0 | 0 |
| `3efac63c` option on | grained | U/V 1.41 | 1.41 | 0 | 1.41 | 1.42 |
| `725585b8` option on | grained (as off) | 0 | 0 | 0 | 0 | 0 |

The residual kernel now also reports each region (no extra synchronization; same readback), the region's own luma level indexes the model, and exactly constant luma is never grain-bearing. My 32-aligned guard fixtures could not show this.

## Option on: results of the fixed build

| Check | Result |
|---|---|
| Held-out chroma HF / source (Insidious, Marshals, Homegrown; 9 windows) | 0.42-1.04 (D 0.08-0.70; unfixed rule 0.33-1.05). Luma unchanged |
| Held-out bands closer to source than D | Cb 53/61, Cr 52/61 |
| Held-out bands above 1.10x source amplitude | 1 of 183: Insidious f55, luma 224-256, Cr, 9 patches, 1.22x (D 1.23x, production 1.13x) |
| Guard fixtures (monochrome SDR/PQ, composited graphics, lettering) | zero in every plane |
| Small unaligned flat graphics | zero (as option off) |
| Census windows, luma constant-patch policy hits | zero in all 15 |
| Live-action census: codec-flat chroma patches now grained (guard c report) | 92-17,413 per window, median RMS 0.06-0.37 |
| Library-scan detector, Amphibia and Lost Tapes episodes | Clean |
| Fixed-QVBR bytes vs D | held-out 0.988 (every window 0.953-0.996), Gentlemen 3,600 frames 0.986, Play Dirty 10 min 0.970, episodes 0.997-0.999 |
| Submission trace vs the unfixed rule `f7572de6` | KAT, Silo and Taxi identical; Amphibia, Gentlemen, Lost Tapes change in grain curves (pictures only alongside) |

Two held-out windows lost much of the unfixed gain (Insidious f55 Cb 1.04 to 0.42, Marshals f55 0.93/0.99 to 0.63/0.72). The analyzer trace of Insidious f55 shows why: one flat-colour region about every five frames whose own luma is not grain-bearing (for example crushed black against clipped white) is now protected as variant D protects it, and D's constant-chroma rule caps that region's whole luma span, about 210 Cb levels. That over-breadth (capping the span rather than the levels present) predates this work; changing it would change variant D and is left as a follow-up.

## The remaining band above 1.10x

Insidious f55, luma 224-256, Cr: source 0.23, fixed build 1.22x, variant D 1.23x, production 1.13x, unfixed rule 1.84x. The Cr curve is frame-wide and luma-indexed, and its top points are interpolated from sparse top bins (0-36 training blocks; measured sigma 0.10-0.28 against about 0.37 in the mid-tones). Variant D already applies it at luma 236-255. After the fix the option no longer adds anything here, so this is the release's existing behaviour. It is still above your 10% rule, so it is your call whether that rule binds the release's own top-of-curve behaviour.

## Gate stages flagged with the option on

First full run with the option on (`3efac63c`, `reports/full-gate-optcand-on-559b80c0`): 21 pass, 3 fail. <<GATE2_TABLE>>

**Periodic grain (Gentlemen, live action): the intended colour restoration.** The detector compares decoded grain per frame against the pinned variant D positive. With the fixed build, red/blue texture, amplitude and correlation change on 502-1,881 frames, all on frames whose chroma curves changed. Luma curves and AR coefficients are identical on all 3,600 frames. No frame approaches the 2.0 mesh ceiling (peak red 1.55, blue 1.67; positive 0.82/0.78). The flagged luma frame (141.46 s) is display luminance from rounded and clipped R/G/B in a dark scene: Y grain is unchanged there and only chroma grain is new. The adjacent-frame flags are grain on/off transitions on the same schedule as the positive (37 transitions in both), whose steps are larger only because chroma amplitude is larger, and two source pulses. At 117.29 s and 118.00 s the source's own chroma noise jumps (U/V 1.54/1.65 and 1.40/1.51 against 0.7-0.9 around them) and the candidate follows it. Through 118-121 s the candidate tracks source chroma noise better than D (correlation 0.84 vs 0.79, level 0.85 vs 0.64 of source) with frame-to-frame change no larger than D's. Relative frame-to-frame change p99 equals the positive's (red 0.99 vs 1.00, blue 1.00 vs 0.98). This is intended and is not new jumping.

**Mixed-source (synthetic) `interior`, `chroma_only`, `islands`: the option's definition.** These cases set chroma exactly constant over luma that keeps its sigma-3 noise ("Source chroma is clean while co-located luma remains noisy") and require no chroma grain there. That is the exact pattern you chose to treat as codec damage in live action. The option grains it at the background chroma level (1.1-1.6), and the flow keeps the option off everywhere else.

**Flicker `losttapes_colour` (animation): the reason the flow excludes animation.** An exactly constant U patch in Lost Tapes gets chroma grain (SD 0.40-0.49 against a 0.3 limit). Option off passes this case.

## Evidence

Scratch `/tmp/downloads/codex-work/fgs-fidelity-20261007/`: `optoff2-trace-regions.txt`, `opton2-trace-regions.txt`, `smallgfx/`, `heldout/*-axes-nonflat-fix.json`, `var-fix/` (census, guards), `anim/*-fix*`, `floor/size-fix-*`, `periodic/` (re-encodes with grain tables, display measurements), `band/` (analyzer traces). Gate reports in `fgs-submission-20261005/reports/full-gate-optcand-on-559b80c0/` and `full-gate-optcand-on-74d3d744/`.
