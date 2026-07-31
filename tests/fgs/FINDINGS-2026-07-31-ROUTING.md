# Heavy-grain routing re-test, 2026-07-31

## Result

`FINDINGS-2026-07-17.md` concluded that the coarsest 35mm stock "is the worst
case for this feature, not the best, and is better served by a plain tuned
encode". That is no longer true.

At an equal VBR budget on real 4K film, FGS retains substantially more grain
than a plain tuned encode, and on lighter-grain coarse stock it does so while
also producing a smaller file:

| title | grainCorr | source HF | plain: MB / retention | FGS: MB / retention |
| --- | ---: | ---: | --- | --- |
| Taxi Driver | 0.811 | 2.46 | 50.7 / **0.805** | 51.0 (+0.6%) / **0.919** |
| Casino | 0.779 | 1.57 | 49.9 / **0.803** | 44.8 (**-10.2%**) / **0.917** |

Plain lands at ~0.80 retention on both titles; FGS lands at ~0.92 on both. Two
different films at different grain levels produce near-identical numbers.

The byte difference between the two titles is a rate-control consequence, not
noise. Taxi's source grain is much heavier (HF 2.46 against 1.57), so its FGS
arm still saturates `--vbr 31700` and the benefit appears as *quality at
matched size*. Casino's arm does not need the full budget, so the same benefit
appears as *fewer bytes at matched quality*.

Campaign in progress: The Shining and Scarface are still running, and the
full-reference metric battery is written only at completion. This section
covers the two titles that have finished.

## Why the old conclusion was correct when written

The 07-17 build's sparse AR estimator sampled a fixed 8x8 lattice in every
32x32 model block. On real film that lattice aliased the spatial correlation
and inflated the fitted AR synthesis gain, and because the strength curve is
divided by that gain once, the encoder signalled roughly half the grain
amplitude it should have. `09dae08c` replaced it with deterministic
block-staggered stratified sampling.

The 07-17 routing conclusion was therefore a measurement of an analyzer defect,
not of the AV1 format or of coarse grain. `FINDINGS-2026-07-29-PERFORMANCE.md`
already superseded it on synthesis amplitude and said explicitly that the
matched-rate confirmation was still missing. This is that confirmation.

## Method

`routing_check.py`, which reuses the `campaign.py` and `matched_rate_sweep.py`
primitives. Per title: one plain tuned encode and one FGS encode at the same
`--vbr 31700`, 288 frames of 4K 10-bit, scored against a lossless ffvhuff
reference built from the same master.

Sources are the preserved lossless FFV1 masters in
`test-encodes/keep-original/`, not library transcodes. `denoiser=bilateral`,
the measured production setting, not the `fft3d` default.

Source grain characterisation over the corpus, from the analyzer's own
`grainCorr` and `noise` diagnostics:

| title | grainCorr | noise (8-bit sigma) | character |
| --- | ---: | ---: | --- |
| Taxi Driver | 0.811 | 5.41 | coarse, heavy |
| Casino | 0.779 | 3.50 | coarse, moderate |
| The Shining | 0.670 | 3.21 | coarse, light |
| The Deer Hunter | 0.570 | 10.80 | mid, very heavy |
| Scarface | 0.302 | 10.80 | fine, very heavy |

These reproduce the values recorded on earlier builds (Taxi 0.811 against 0.823,
Shining 0.670 against 0.696), so the analyzer is stable across the rebuilds.
Scarface is the control: the heaviest grain in the corpus but nearly
uncorrelated, so it separates "FGS fails on lots of grain" from "FGS fails on
coarse grain".

### A harness defect this exposed

`matched_rate_sweep.encode()` hardcodes `--avhw`. Every preserved master in
`keep-original/` is lossless FFV1, which NVDEC cannot decode, so that script
fails outright against this corpus with "codec ffv1(yuv420p10le) unable to
decode by cuvid". `routing_check.py` uses `--avsw`, which is also the
deterministic path for a fixed fixture. The defect remains in
`matched_rate_sweep.py`.

## What this does not establish

Retention is grain *energy*. Energy alone cannot distinguish correctly-sized
grain from wrong-sized grain, which is the entire reason
`FINDINGS-2026-07-30-TEXTURE.md` exists. These pairs should be run through the
texture report before the routing rule is changed in production.

Full-reference metrics are also pending. Per the `matched_rate_sweep.py`
header they are structurally biased against synthesis, because synthesized
grain is a new random realization at different pixel positions, so they are a
counterweight to read alongside retention rather than a verdict.

Netflix reports the same limitation from the other direction: no dedicated
quality model for FGS, PSNR and VMAF "penalized" for exactly this reason, and
validation by internal assessment plus A/B over roughly 300 titles.
