# Bilateral source-fit playback gate — 2026-08-03

## Status

**Blind playback judgement pending. Research only; nothing here has been
deployed to Tdarr.** Production remains r4069 with bilateral separation and
the residual-derived grain model. `modelsrc` remains default-off.

The current review package is:

```text
/media/merged-storage/media/test-encodes/sourcefit-bilateral-review-20260803/blind/
```

It compares production against bilateral separation with source-fitted grain
on Casino, Interstellar, Taxi Driver, The Deer Hunter and The Shining. The
separator is held fixed, so this review is not a motion-denoiser gate. It
isolates the architectural change in how AV1 grain texture is measured.

## Integrity

The package contains base and finished lossless 1920x1080 10-bit FFV1 A/B
centre crops for five titles. Every file:

- was decoded with `libdav1d`, never NVDEC;
- preserves limited-range BT.2020/PQ metadata;
- passed a complete `ffmpeg -xerror` software decode; and
- was generated resumably from an input/command manifest.

The exact file count and package size are recorded after the new Interstellar
pair is generated. File sizes are not a comparison metric because the review
copies are lossless and independently grained.

## Why this is the next gate

Source fitting reduces luma lag-1/lag-2 texture error from `0.223/0.343` to
`0.020/0.036` across six films, with corresponding order-of-magnitude U/V
texture gains. Taxi Driver changes from production synthesis `0.564/0.003`
toward source truth `0.804/0.438`, reaching `0.814/0.491`.

Production lag-2 is negative on four of six titles. It is materially opposite
the positive source on Casino, Deer Hunter and The Shining, while Scarface
turns an effectively zero source value (`-0.002`) into a much stronger
negative (`-0.094`). The defect is therefore not merely grain that is too
fine: production often synthesizes a spurious anti-correlated distance-2
structure, a plausible cause of the electronic-noise appearance this review
is intended to judge.

Whole-title luma delivery also moves from production mean/MAE `0.734/0.266`
to `0.992/0.028` while retaining the production bilateral base and essentially
the same output bytes. Exact luma and chroma emission audits match dav1d
pixel-for-pixel.

The remaining uncertainty is perceptual, not decoder correctness:

- independently synthesized grain cannot be judged by ordinary full-reference
  finished-frame metrics;
- weak chroma bands have large relative errors but very small absolute energy;
- source-fit level compensation can move a small fraction of luma samples by
  one code value; and
- the current hard-bin curve can redistribute strength across sharp luma
  transitions even when title-wide amplitude is correct.

Three currently flagged luma-shape errors all occur in the brightest populated
`0.375--0.500` band: Taxi Driver is low (`0.890`), while Interstellar (`1.278`)
and Deer Hunter (`1.344`) are high. The corpus mean hides these opposite-sign
errors. Chroma V similarly changes from mean under-delivery (`0.895`) in
production to slightly larger mean over-delivery (`1.120`) in the candidate;
three candidate titles exceed `1.17`. U improves overall, but Deer Hunter
worsens from `1.139` to `1.286`.

## Review order

1. Watch each `base` pair first. Look for real-detail or black-level changes.
   Both arms use the same bilateral separator, so motion ghosting is not the
   question.
2. Watch the corresponding `finished` pair at normal speed. Judge coarse/fine
   grain scale before judging strength.
3. Inspect bright flat regions -- skies, walls and faces in key light -- for
   conspicuous over/under-graining. Then inspect dark weak-grain regions for
   chroma crawling, coloured blotches, lift or pumping. Record absolute
   visibility, not only which arm differs.
4. Record title, A/B, timestamp and observation before opening the reveal file.

Independent AV1 grain positions are expected. A paused-frame pattern mismatch
is not a defect by itself.

## Decision boundary

A clean review would make bilateral/source-fit the leading deployable-quality
candidate, but would not itself change the production default. It would still
need a pinned production build, full KAT, complete dav1d validation and a
limited rollout with the original retained.

This review deliberately runs before its earlier stated precondition that the
per-luma and chroma strength report be fully trustworthy. That is acceptable
because playback is the scarce gate and the architecture can be judged now,
but it limits interpretation: bright-band over-graining or chroma instability
confirms known measurement failures. It does not by itself invalidate the
source-fit texture architecture, and it should not displace the coarse/fine
grain and base-fidelity judgement.

If visible chroma or per-luma errors remain, do not apply a fixed gain. The
next measurement is a per-plane multi-QVBR temporal transfer study. Coordinate
remapping, unconditional smoothing removal, rectified-block exclusion and the
existing temporal chroma closure have already failed opposite-sign real-film
gates.
