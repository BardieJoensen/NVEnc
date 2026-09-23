# Per-picture grain variation and compressed 10-bit models

R3 remains open. D39 qualifies three constructive compressed-picture models;
D40/D41 show why the exploratory per-picture spatial score needs calibration.
Neither result authorizes automatic retention. Production remains `cb903a17`,
retention and FEL off. The reserved qualification excerpts remain unopened.

## Actual 10-bit output

Tdarr already specifies 10-bit AV1 for SDR. D39 therefore compares the same
8-bit source promoted to 10-bit, colour retention rounded at 8-bit before
promotion, and retention rounded directly at 10-bit. Each control has sixteen
different source pictures; only the final picture receives the proposed model.
The retained fractions are source Y and 75% of Cb/Cr residual amplitude.

All 2,359,296 captured reconstructed samples match independent decoding.
A finite search finds a passing final-picture model in all three cases, after
2, 7 and 12 proposals respectively. The selected seeds are 8839, 39757 and 24912.
The first needs no spatial counterterm; the other two need one. All original
per-picture source checks remain unchanged. This is a separate compression-aware
full Y/Cb/Cr proposal, not proof that copied pre-encode luma survives compression.

Writing those complete models into the actual AV1 streams reproduces another
2,359,296 oracle samples exactly with AOM and dav1d. All base pictures, the first
fifteen displayed pictures, clocks and colour metadata remain unchanged. The
capture and output checks total 384 fresh decoded observations; 192 prior
observations are reused only after proving the packet copy. No-op writing is
byte-identical. These short controls do not measure full-title size or speed.

## Calibrating the spatial score

D40 generates source and comparison grain with the **same known AV1 model**,
using disjoint sets of 32 seeds. It tests white and spatially correlated,
luma-coupled grain at 8 and 10 bits. The model, strength and base stay fixed;
only the seed changes. These are generative controls, not perceptual ground truth.
Ordinary finite-template variation can itself be visible.

None of the 128 independent comparison pictures passes every original
0.08 spatial/8% variance/0.125 mean bound. Most failures concern colour spatial
covariance. All four comparisons pooled over 32 pictures pass, as do comparisons
between the two training halves. Exact self-comparisons pass, and every declared
half-strength, excess-strength, wrong-shape and dropout negative fails. The
study generates 384 pictures and retains moments, parameters and raw hashes;
completed raw synthesis buffers are retired.

This means an isolated failure of that exploratory score cannot distinguish a
model defect from this measured same-model variability. It does **not** establish
that every failure is harmless, change a threshold, or invalidate source-detail,
range, ripple or temporal regressions. The historical per-seed failures remain.

## Temporal statistics need individual-picture protection

D41 keeps the same bounds and examines fixed, non-overlapping windows. All
eight-picture windows pass for the four known-model controls. A single dropout
can nevertheless disappear inside a 32-picture average; one excess-grain
picture can disappear in a 16- or 32-picture average. Every isolated negative
still fails the individual-picture check. A pooled-only quality gate is rejected.

Two actual compressed-base controls then use the original source-fitted shape
with no seed-specific spatial counterterms. Each seed receives bounded integer
strength calibration from training pixels. All 64 calibrations are valid;
all eight-picture colour windows pass. No individual picture passes every old
spatial bound. Separate native-luma, variance and mean checks pass 24/32 and
22/32 pictures; all remaining failures concern the unchanged mean limit.
These numbers describe model diagnostics, not percentages of visible quality.

The next finite trial, D42, uses two sequences of sixteen different constructive
pictures through actual NVENC lookahead/reordering. It freezes shape from the
first eight training frames, tries at most four seeds per picture, retains the
old spatial results, and checks individual amplitude/mean separately from pooled
colour shape. No positive result can approve an unsupported real population.
Automatic call sites, broader temporal behaviour, unseen quality, bytes, speed
and the Tdarr policy remain open in the [roadmap](RETENTION-ROADMAP.md).

## Local evidence

Under the current `colour-recovery-20260922` evidence root:

- `roadmap-r3-promoted-sdr-20260923/`: `comparison.json`,
  `selection-report.json`, `serialization.json`, `drain-pause.json`.
- `roadmap-r3-metric-calibration-20260923/`: pinned `manifest.json`,
  complete `report.json`, and per-seed source/comparison moments.
- `roadmap-r3-window-model-20260923/`: `manifest.json`, `window-controls.json`
  and complete `report.json` including every rejected individual picture.
- `roadmap-r3-continuous-model-20260923/`: the manually started D42 ledger.

All studies have finite budgets. No trial is scheduled or restarts automatically.
