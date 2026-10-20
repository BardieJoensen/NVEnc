# R17 independent outcome review

## Disposition

R17 is admitted as a valid **single-frame, fixed-decision native qindex4 diagnostic**. It is an unfavorable result for q4 under the R16 predictor/partition/transform population: background is restored, but the prescribed shirt texture still misses both frozen texture criteria. The remaining shirt deficit is localized primarily to the already-lossy 64×64 reduced-coefficient transform population, rather than to insufficient q4 coefficient precision on the smaller transforms.

This does not reject a real lower-q policy that changes search, partitions, transforms, references, filtering, or feedback. It makes another still-finer fixed-q point low value.

## Evidence and independent reconstruction

Frozen result identities:

- outer execution `3efeacef74c8d95ca10816da6bea4c2567d207131a31a42e450afa26da263e93`, complete/rc0, 3.706 s
- inner receipt `4eb2aefae90ff65c2e985cafdfc14f878107c5f8df36d971aad9ad7d6c8728a6`, complete, 3.594 s
- result `a04eb728936d62662afb4ab6dbc554db394c25f1ac433c563beff59278b3abdb`
- native arrays `ee8c41ed2188efacd940ebf3a9fbb6dd5821e9bf2e6c56c75ff4e5d3e8a26b23`
- mosaics `aba4ec13038906060b0ec59c1bee1ed342835e2a60caf472200a030b950af50c`
- token rows `899febd238c4baec09fdb389f1140266f4d2d6880db017b280e7fe89f10f85d0`
- baseline control `62747b190b9facf89e96a626c54a1ee68c523dc7e68b2c5b2e2b3fb4bdbc6cac`

Independent derivation:

- script `derive.py` SHA256 `e54a7befec2a0b313d5de19a6a9ca39cd54746e678599d541a3ad6993eb7519d`
- successful outer receipt `derive-execution-v2.json` SHA256 `0a1fc84ad0c25fd41d8966ed61760af0812eb974c1aa173c88a835f6c9d277fa`
- compact result `derived-v2.json` SHA256 `801d9f44c3656ac021702b5b0be86b89442226d3ac8fee4cde3241dd32ca9587`

The derivation reparsed coded ordinal 210, reconstructed all mosaics from the admitted trace plus token-indexed saved arrays, verified coefficient/pixel offsets, scan-derived EOBs, and exact baseline q/DQ/EOB/inverse and raw-inverse arrays, and reproduced every saved whole-ROI, invoked/uninvoked, and native-transform metric. Saved mosaics and masks were byte/numerically exact. All 316 `inputs_before` identities remained live and equal to `inputs_after`.

The first reviewer derivation receipt (`derive-execution.json`, SHA256 `a2d3fe45d1b16513670d498a8dfddfab99aed395e69dbf2fd077dc6c64fc7abe`) is preserved as failed. My script incorrectly required the target trace to cover the entire 1920×1080 frame; it covers 345,792 pixels and completely covers every predeclared ROI. The correction only restricted predictor equality to admitted coverage and compared NaN outside-coverage cells explicitly.

## Observations

All 2,169 invoked tokens passed the recorded direct-C/runtime q4 equality gate. The preserved run also reports exact direct-C/runtime/capture baseline and raw-inverse equality for all 2,169. Baseline has 2,130 positive-EOB and 39 invoked zero-EOB tokens; q4 has positive EOB on all 2,169, changes EOB on 2,154, and expands nonzero coefficients from 20,974 to 203,490. The 39 baseline-zero tokens occupy no shirt pixels, 48 background pixels, and 4,352 face pixels. The 701 uninvoked owners remain predictor-only and receive no q4 intervention.

Whole-ROI values, all independently reproduced:

| ROI/stage | HF/source | ACF1 error | HF correlation | MSE vs source |
|---|---:|---:|---:|---:|
| Shirt raw | 86.735% | 0.03792 | 0.85378 | 0.19326 |
| Shirt scalar/final | 21.013% | 0.34788 | 0.05472 | 1.47524 |
| **Shirt q4** | **86.080%** | **0.05612** | **0.83228** | **0.21869** |
| Background raw | 99.300% | 0.00016 | 0.99143 | 0.16197 |
| Background final | 77.987% | 0.13869 | 0.54625 | 5.75958 |
| **Background q4** | **99.605%** | **0.00492** | **0.98810** | **0.19733** |
| Face raw | 93.322% | 0.02433 | 0.92225 | 4.22464 |
| Face final | 90.083% | 0.06563 | 0.78737 | 8.88770 |
| Face q4 | 93.543% | 0.02525 | 0.92133 | 4.25032 |

Thus q4 passes the frozen HF ±10% and ACF ≤0.05 descriptor criteria for background, but shirt remains 13.92% below source HF and its ACF error is 0.0561. These are diagnostic single-frame descriptors, not a campaign acceptance result.

The transform strata localize the shirt deficit. All 20,000 shirt pixels are invoked at actual qindex71. The 2,496 16×16 pixels and 12,880 32×32 pixels reach respectively 98.67% and 99.95% of their stratum source HF at q4. The 4,624 64×64 pixels (23.12% of the shirt) reach only 28.93%; even their unquantized/raw diagnostic reaches only 29.50%. The adjusted 64×64 support therefore loses the decisive energy before scalar quantization. Q4 is slightly worse than raw overall (86.08% versus 86.74% HF), so finer scalar precision cannot cross the shirt's 90% floor while these fixed transform decisions remain.

Background is 97.69% invoked, and q4 restores the invoked strata apart from its small 64×64 population. Face remains partly limited by its 81,472 uninvoked pixels (33.95%); q4 cannot affect those pixels. HF/ACF are nonadditive, so these stratum observations identify where the deficit resides but are not a causal percentage decomposition.

## Interpretation and scope

The fixed R16 scalar stage is responsible for most of the removable texture loss: q4 raises shirt HF from 21.0% to 86.1% and background from 78.0% to 99.6%. Later optimizer/final processing is numerically immaterial for these R16 ROIs. For the shirt, however, q4 reaches the raw ceiling rather than the source target. The residual is linked to the fixed 64×64 transform representation under this diagnostic, not shown to arise from any one encoder search comparison.

There is no entropy coding, packet cost, encoder feedback, reference update, filtering, legal-reconstruction, repair, full-window, temporal, color, or playback evidence in R17. R15 already demonstrates that a real low-q bundle can change decisions and preserve texture at high cost; R17 cannot predict its rate after a targeted decision change.

## Cheapest next discriminator

Use one local, fixed-predictor transform-support diagnostic on the already admitted 64×64 population: split each predeclared 64×64 residual into four native 32×32 transforms, keeping source, predictor, transform type where supported, q4 table semantics, and all non-64 owners fixed. Require existing 64×64 raw/q4 replay to reproduce first, direct-C/runtime equality for every split transform, exact visible geometry and additive SSE, and report the same whole-ROI plus support-masked descriptors.

If the split reaches the shirt gate locally, that justifies investigating a real maximum-transform/search intervention with measured rate and displaced damage. If it does not, the next trace should inspect predictor/partition candidate decisions. This split remains a counterfactual diagnostic and carries no bitrate or deployability claim.

## Erratum to the preflight review

The two nonblocking cleanup notes in `round17-parent-preflight/REVIEW.md` were my errors. The frozen runner has one receipt initialization at line 230. Also, `pantheon-independent-20261019/investigate.py:14` explicitly imports `high_pass` and `autocorr` from the pinned `matched_rate_sweep.py`, so the runner's provenance comment is accurate. Neither point affected the release or result.
