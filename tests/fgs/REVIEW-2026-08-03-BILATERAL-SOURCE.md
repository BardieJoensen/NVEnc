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
on Casino, Taxi Driver, The Deer Hunter and The Shining. The separator is held
fixed, so this review is not a motion-denoiser gate. It isolates the
architectural change in how AV1 grain texture is measured.

## Integrity

The package contains 16 lossless 1920x1080 10-bit FFV1 centre crops: base and
finished A/B pairs for four titles. Every file:

- was decoded with `libdav1d`, never NVDEC;
- preserves limited-range BT.2020/PQ metadata;
- passed a complete `ffmpeg -xerror` software decode; and
- was generated resumably from an input/command manifest.

The package occupies 4.7 GiB. File sizes are not a comparison metric because
the review copies are lossless and independently grained.

## Why this is the next gate

Source fitting reduces luma lag-1/lag-2 texture error from `0.223/0.343` to
`0.020/0.036` across six films, with corresponding order-of-magnitude U/V
texture gains. Taxi Driver changes from production synthesis `0.564/0.003`
toward source truth `0.804/0.438`, reaching `0.814/0.491`.

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

## Review order

1. Watch each `base` pair first. Look for real-detail or black-level changes.
   Both arms use the same bilateral separator, so motion ghosting is not the
   question.
2. Watch the corresponding `finished` pair at normal speed. Judge coarse/fine
   grain scale before judging strength.
3. Inspect dark weak-grain regions for chroma crawling, coloured blotches,
   lift, pumping, or conspicuous over-graining. Record absolute visibility,
   not only which arm differs.
4. Record title, A/B, timestamp and observation before opening the reveal file.

Independent AV1 grain positions are expected. A paused-frame pattern mismatch
is not a defect by itself.

## Decision boundary

A clean review would make bilateral/source-fit the leading deployable-quality
candidate, but would not itself change the production default. It would still
need a pinned production build, full KAT, complete dav1d validation and a
limited rollout with the original retained.

If visible chroma or dark-band errors remain, do not apply a fixed gain. The
next measurement is a per-plane multi-QVBR temporal transfer study. Coordinate
remapping, unconditional smoothing removal, rectified-block exclusion and the
existing temporal chroma closure have already failed opposite-sign real-film
gates.
