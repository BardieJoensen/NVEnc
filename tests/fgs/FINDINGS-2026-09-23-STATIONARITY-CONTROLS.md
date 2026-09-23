# Temporal population analysis: motion and correlation controls

The frozen study rejects short-history consistency plus a small motion search
as a sufficient population classifier. It catches several known failures but
also misses fast zero-grain motion and cannot distinguish persistent noise from
static detail. No source population was promoted and no encoder output changed.
Automatic partial retention remains unfinished.

The later [disjoint-frame-pair follow-up](FINDINGS-2026-09-23-MOTION-HOLDOUT.md)
removes the recorded flat-grain false motion conflicts on these development
controls. Fast-motion and persistent-grain counterexamples remain unresolved;
the original frozen results below remain valid for the first diagnostic.

## What was implemented

`temporal_stationarity_reference.py` extends the existing eight-frame reference
with a bounded translation diagnostic. A fixed binomial low-pass precedes a
four-pixel search on 121 common interior samples per adjacent frame pair and
component. All comparisons use the same coordinates without padded pixels or
wrapped image edges. Zero displacement wins exact ties.

The study freezes necessary checks before inspecting its results: conditional
variance 0.04–256, lag-energy agreement within 20%, disjoint-history agreement
within 30%, mean differences at most one 8-bit code value, and translated matches
improving error by more than 20% on at least four of seven pairs. These are
exploratory diagnostic bounds, not visibility thresholds or an acceptance policy.
The helper always reports that population acceptance and stationarity
qualification are false. It has no encoder call sites.

## Known-source results

The finite manifest contains 16 synthetic families, 32 seeds and both native
8-bit and 10-bit rounding: 1,024 tiles and 3,072 component observations.
The observations within a tile/depth pair are related; these counts are not
independent statistical confidence bounds.

| Source condition | Components without a recorded conflict | Interpretation |
| --- | ---: | --- |
| Independent grain on static detail | 192 / 192 | The stationary hypothesis works on this control |
| Spatially correlated grain on static detail | 190 / 192 | Useful control, not broader qualification |
| Independent grain on a flat field | 63 / 192 | Motion fitting on the same small patch overfits noise |
| Temporal AR correlation, each of three coefficients | 0 / 192 | Lag/history diagnostics detect these controls |
| Zero-grain translation by one or four pixels | 0 / 192 | In-range translation is detected |
| Zero-grain translation by seven pixels | 101 / 192 | Fast detail can evade every diagnostic |
| Persistent plus independent grain | 192 / 192 | Conditional variance omits roughly half the actual grain variance |

Exposure drift, scene cuts, a current-frame grain-strength increase, a moving
sinusoid, and noise combined with one-pixel translation all produce conflicts.
Fully frozen grain gives zero conditional grain energy and is also rejected.
The persistent-plus-independent case is different: it passes the necessary
checks while attributing persistent grain to the scene. An identical observed
sequence can describe static texture instead. Temporal covariance alone cannot
resolve that ambiguity. Keeping that persistent residual in the base and
independently protecting detail would require its own evidence.

Eight CPU regressions cover an independent scalar motion-cost oracle, exact
known translation, quiet/static ties, depth/offset invariance, exposure and
correlation, invalid history, and the two conflict-free counterexamples above.
The complete CPU suite passes **201 Python tests in 28 suites and 29 C++ programs**.
No encoder rebuild is required for these offline tools.

## Existing HDR development windows

The same 3,960 complete Shining tiles are replayed. All native source/previous
planes, identities, clocks and previously measured moment arrays match exactly.
R1 population classifications and support counts remain unchanged. Each frame
and component still has 46,080 partial-border samples outside this tile study.

Among previously rejected tiles, 173/122 Cb tiles and 21/12 Cr tiles have no
recorded conflict in frames 30/210. They **remain rejected**: the known-source
counterexamples show why an empty conflict list cannot certify them. Numerous
other tiles fail lag consistency or the small-translation check. Those checks
do not determine whether motion or correlated grain is the physical cause.
The measurements remain native code-space diagnostics, not HDR display metrics.

## Decision and evidence

Do not connect this diagnostic to source-population admission or fit a new
whole-picture model from its conflict-free tiles. Preserve R1, existing source
fallbacks, and the 8%/0.08 model bounds. Further source-model work needs
independent motion evidence, coverage of motion outside a small tile search,
and explicit preservation of temporally persistent residual. Merely widening
the diagnostic thresholds would hide the observed failures.

In the [handoff](WORK-TO-PRODUCTION.md) evidence root, read
`roadmap-r3-stationarity-controls-20260923/manifest.json`, `synthetic.json`,
`real.json`, `report.json` and `cpu.json`. The manifest predates the results;
the source and script hashes are pinned. No GPU job, worker pause, production
change, new raw-video output or reserved-corpus inspection was needed.
