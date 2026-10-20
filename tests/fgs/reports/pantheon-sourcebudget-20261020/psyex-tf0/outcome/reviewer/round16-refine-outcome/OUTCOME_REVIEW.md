# R16 refinement independent outcome review

## Evidence and independent derivations

The selected command SHA is `00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497`; admitted observation SHA is `a86db1bcc3e4ff49b8e0aa66dfc601ac8bc7b67bb4415b3886263df7daaf50ab`; stage result SHA is `02007de9587f0ad958f49abbcc0b425ba40e5eb855e76a5f24400193f8b36106`.

The independent admission derivation completed at `admission-review.json` SHA `f693e8069524d3c471f15b4dd6022d33aa8e08253b6ae5ac2c95bccb1dff5777` under outer receipt `admission-execution-3.json` SHA `64ae17a84b20deb96df9538b296d83cad3c714dd63b93939714046da46dda015`. The independent quality derivation completed at `quality-review.json` SHA `d00bd654ba6805cbf6a1a7459542cfec9cfc1d844c682d811a7aa388ff2ae173` under `quality-execution-4.json` SHA `82fac5829dae5a0e621ee40539e475c6ca86e0b43e7a441156011bf77cfc0495`.

The original frozen quality derivation failed closed on three report-schema assumptions: two packet-list fields were compared to integer `240`, and the decoded texture path was compared to the encoded MKV path. Failed receipts/logs and v2/v3 revisions are retained. Final v4 SHA `47fe6b0a1d828f3edfd1c91f7337c5d4c3a0caba2efca3653b67436c5388d1be` changes only those bindings: it requires both packet lists to have 240 rows and requires the texture path to be the scorer's tag-derived decoded MKV. Metric math is unchanged.

Support-v2 result SHA `f329a6416f3304130fb07a1cb153b88ad039b13e1392c868499cc70a4ad861bb` was independently cross-checked by `verify_support.py` SHA `e6b87f3b14f82d7f65ecd709695b86b19cb42c388a279350243a9aa9bf0b13bb`; its output SHA is `4e1baad1bbd02ecee84cb0083a416623afe6da1634348557561ca72028d116fc`. Every ROI group closes to complete coverage, its invoked/uninvoked/EOB/q distribution equals the independent admission derivation, and additive group SSE reproduces every admitted stage MSE exactly.

## Observations

The arm is practically and comparison-rate eligible: `9.6698472 Mbps`, `99.9310165%` of the source cap and `+0.4356337%` versus R8. Two-pass runtime is `372.2541 s` versus R8's `370.3358 s`. All 336 decoder outputs, coded events, target ownership and encoder-to-decoder DQ/EOB/IQM joins passed.

It fails both unchanged texture screens. At the five-frame midpoint:

| ROI | R16 HF error | R16 ACF1 error | R8 HF error | R8 ACF1 error |
|---|---:|---:|---:|---:|
| Shirt | -83.738% | 0.17584 | -83.023% | 0.08587 |
| Background | -41.427% | 0.11161 | -42.082% | 0.11624 |

Across 240 frames, R16 shirt HF loss improves from R8's `-48.796%` mean to `-46.195%`, but shirt ACF1 error worsens from `0.12358` to `0.13135`; background improves slightly on both means. Fixed-coordinate temporal-correlation error is essentially unchanged for shirt (`0.07520` versus `0.07518`) and worsens in mean for background (`0.03564` versus `0.03444`). These mixed descriptive changes do not approach the preservation gate.

General averages are likewise mixed. VMAF and mean Butteraugli are almost unchanged, while low tails regress: SSIMULACRA2 minimum/p1/p5 are `18.56/20.07/35.00`, versus R8 `25.37/32.62/38.59`; PSNR-Y p1 falls from `36.25` to `35.58`; Butteraugli 2-norm p95 rises from `1.973` to `2.036`. CAMBI improves materially (mean `0.20175` versus `0.28585`, p95 `0.6618` versus `0.8798`). Face MSE improves slightly (`8.4833` versus `8.5621`).

All 12,870 frozen control tiles are paired. Mean HF absolute error improves (`0.6073` versus `0.6485`), while its p95/p99 worsen (`1.241/1.715` versus `1.188/1.495`). Quiet positive HF maximum improves from `0.02500` to `0.02282` and quiet MSE improves; edge positive HF maximum worsens from `0.23590` to `0.42279`. Aggregate improvements therefore do not erase the tail and target regressions.

## Native-stage interpretation

For target frame 216/scored 120, TF-off coding input is byte-identical to the original. The observed loss occurs downstream:

- Shirt: all 20,000 pixels are positive-EOB invoked owners at actual qindex 71. Raw fixed-predictor reconstruction retains `86.74%` of source HF; scalar output retains `21.01%`; later optimizer/final/preloop are unchanged; post-loop retains `11.32%`.
- Background: 43,912/45,000 pixels are positive-EOB at q79-87. Raw retains `99.30%` of source HF; scalar retains `77.98%`; post-loop retains `52.07%`.
- Face: raw retains `93.32%`, scalar `90.09%`, and post-loop `79.29%`, but 81,472/240,000 pixels are uninvoked. Its missing-support contribution remains material.

The spatially additive final SSE partition assigns 100% of shirt error and 97.62% of background error to positive-EOB invoked owners. Face is split: 52.04% positive-EOB, 47.44% uninvoked, and 0.53% invoked-zero-EOB. This supports coarse scalar precision as the dominant observed shirt/background boundary under the selected target's fixed predictors, partitions and transforms. It does not prove that a different real encoder policy can allocate finer precision within the source budget. Filtering adds further HF loss, and the full-window score cannot be attributed from this single target frame.

## Conclusion and next discriminator

R16 is a valid source-cap, matched-rate negative result. TF-off alone does not preserve the target texture under the original budget, and the arm is not a practical candidate. No human playback was performed.

The cheapest informative next discriminator is the already reviewed native q4 replay on the exact R16 invoked population. The evidence now satisfies its selection premise: shirt and background have nearly complete residual-bearing support, actual q71-87, and most observed error after an informative raw reconstruction appears at scalar output. The replay must retain the R16 table/DC-delta and per-token baseline C/runtime/64x64 controls specified in `round16-counterfactual-route-review.md`. A favorable local q4 result would justify testing an absolute-cap allocation policy; an unfavorable result would direct work toward decision/transform support. The local replay cannot supply coded cost, bitrate, repair, full-window, or playback evidence.
