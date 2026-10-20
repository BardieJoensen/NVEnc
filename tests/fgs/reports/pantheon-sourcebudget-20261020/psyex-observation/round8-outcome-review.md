# R8 PSYEX independent outcome review

## Stage 1: runtime observation admission

Reviewed admission SHA `15e280b35907ec80c7ed9ade4ef24526fff22afbfe5676fb81851ef2491bef39`, neutral replay receipts `e64917cb...` (off) and `ca1042f3...` (on), and observation SHA `677a13f4...`. No quality result was inspected.

### Observations

- Observation was bit- and sample-neutral. Both private replays used the fixed original pass-2 command and stats SHA `d8038f...`, returned zero, and reproduced the unmodified full IVF byte-for-byte (`26f51d...`, 17,954,807 bytes) and app reconstruction byte-for-byte (`162c2e...`, 2,090,188,800 bytes). The off arm emitted no trace; the on arm emitted one complete schema-3 trace. Both loaded the pinned private app/library and retained identical before/after inputs and tools. Replay times 311.50/314.53 seconds are instrumented diagnostic timings only.
- The trace is complete over its declared domain: shape `[336,4,34]`, one encoder instance, no invalid index or overflow, and mode-selection activity for every input picture 0–335. I independently recomputed the principal optimizer and paired-term invariants from the trace and found no violation.
- Runtime static configuration matches the fixed arm: pass 2, 1920×1080 10-bit 4:2:0 limited BT.709 at 24 fps, preset 4/tune 0, PSY-RD 1, sharp-tx/sharpness 1, full-HBD MD 1, noise normalization 1, VBR/AQ2/variance boost/QM/TF settings and requested 10,313 kbps. `intra_period_length=239` is the correct internal form of keyint 240. CDEF and restoration `-1` remain automatic static sentinels, not measured resolved filter states.
- Target input picture 216 (scored frame 120) exercises every preregistered route: 149,806 optimizer calls used the sharp guard and zero rate weight; all 5,776 full-spatial prediction and reconstruction psy terms were nonzero; 17,709 spatial residual-zero comparisons and 849 spatial skip-mode comparisons occurred; and 20,666 selected-candidate commits carried the spatial route while all 51,804 used HBD mode decision. TX-domain psy terms, coefficient-bearing selected candidates, noise-normalization calls, residual-zero choices and skip-mode choices were also observed, although they were not extra admission gates.
- Across the window, the same route evidence is substantial: 55,919,022 zero-weight optimizer events; 3,413,531 nonzero full prediction/reconstruction terms; 21.8 million nonzero TX psy terms; 6,917,829 spatial residual-zero comparisons; and 612,787 spatial skip-mode comparisons. `PO_FAST_CALL`, `PO_OPT_EARLY_RATE`, and `PO_OPT_EARLY_EOB` are zero. Thus those particular fast/early-exit routes were observed as inactive in this fixed run and must not be presented as delivered mechanisms.

### Interpretation and limits

The admission supports the narrow claim that this exact legal PSYEX stream was produced with the bundled HBD/spatial psy search routes, sharp-tx zero-rate-weight optimizer route, and spatial zero/skip comparisons materially exercised, while observation itself did not change encoded bytes or samples. It does not isolate any one setting or prove that a counted term changed the winning decision.

Counts are repeated search events, not unique blocks, pixels, coefficients, bits, or effect sizes. Nonzero-term counters record only whether the wrapped integer return was nonzero. Selected-candidate commits can later lose partition search; schema 3 has no final partition survival or component-to-output-pixel ownership. Aggregate co-occurrence cannot pair an individual psy term with a particular residual-zero/skip choice or final block. The automatic filter state, actual perceptual repair, playback, and practical generalization are outside this stage.

**Runtime-stage disposition: admitted and scientifically adequate for aggregate search-route delivery, with the stated inactive routes and final-partition limitation retained. Quality outcome remains pending.**

## Stage 2: matched-rate quality outcome

Reviewed assessment SHA `cc3d2a38...`, controls SHA `e3854547...`, metric result SHA `763429a7...`, texture SHA `d4f62b4b...`, and accepted summary SHA `c563d0bb...`. All bindings and complete populations passed. No motion playback was performed.

### Qualification result

The fixed PSYEX bundle is a valid matched, under-cap arm: 9.6279048 Mbps is 99.4976% of the 9.6765224 Mbps source ceiling and 99.8840% of R3 PSNR's 9.639088 Mbps. All 336 app/dav1d/libaom/NVDEC frames and all 240 scored planes agree. Its measured two-pass wall time is 370.336 s versus R3's 391.652 s (0.9456×), but uncontrolled host load and different implementations preclude a throughput-superiority claim.

It **fails the unchanged preservation screen in both prescribed ROIs**:

- Shirt midpoint HF is 0.10515 versus source 0.61935, a **−83.02%** error; ACF1 error is **0.08587**. Required limits are ±10% and ≤0.05.
- Background midpoint HF is 1.03007 versus source 1.77849, a **−42.08%** error; ACF1 error is **0.11624**.

Relative to matched R3, PSYEX modestly raises midpoint HF and source correlation in both regions and improves shirt ACF error, while background ACF error worsens. These directional changes remain far from a pass and do not qualify the arm as a repair candidate.

### Whole-window behavior and controls

- Full 240-frame fixed-coordinate behavior is mixed but temporally steadier by this descriptor. Shirt mean HF deficit improves from −53.41% to −48.80%, while background improves from −37.22% to −35.78%. Temporal-HF-correlation absolute-error mean/p95 improve from 0.1033/0.3821 to 0.0752/0.2607 on the shirt and 0.0514/0.2063 to 0.0344/0.1165 on the background. These are correlated, fixed-coordinate observations without motion compensation.
- Whole frozen tiles trade amplitude/MSE against spatial structure. Overall MSE mean/p95 improve from 6.463/21.449 to 5.617/15.063 and HF absolute error improves from 0.7014 to 0.6485, but ACF1 error worsens from 0.1689 to 0.2126; 7,807 of 12,867 evaluable tiles have worse ACF error. The 12,600 outside-mask tiles show the same pattern, so this is not confined to the target boxes.
- Edge controls regress materially: MSE 6.441→9.285, HF error 0.4578→0.6034, ACF error 0.1317→0.1703, with 1,571/2,198 MSE, 1,550/2,198 HF, and 1,447/2,198 ACF paired regressions. The face control also worsens (MSE 5.874→8.562, edge-gradient MAE 4.013→5.061, gradient ratio 0.894→0.859).
- Flat-texture and other groups reduce MSE and generally reduce HF absolute error, but both worsen mean ACF error. Quiet tiles reduce HF absolute error slightly (0.09038→0.08624) while MSE worsens 0.2299→0.3542 and ACF error 0.1454→0.2161; 47/51 quiet tiles have worse MSE and 34/50 evaluable have worse ACF. Quiet signed-HF p95 remains negative (−0.02576), with one positive tile and maximum +0.025, so this evidence does not show broad excess-noise injection.
- Full-reference metrics also trade off: VMAF 94.0→92.6, VMAF-NEG 92.5→90.9, PSNR-Y 40.7→40.5, SSIMULACRA2 54.81→53.74 and Butteraugli max-p95 7.76→8.56 worsen; SSIM 0.9903→0.9914, SSIMULACRA2 p5 26.85→38.59, and CAMBI full-reference mean/max 0.3810/2.3095→0.1415/1.2263 improve. No single aggregate score reverses the failed texture gate or the edge/face regressions.

### Interpretation

This rejects only pinned PSYEX master `59d1a025`, preset 4/tune 0/psy-rd 1/sharp-tx 1/noise-normalization 1 at its measured source-matched rate. Runtime evidence rules out the explanation that the configured spatial psy and zero-rate-weight optimizer routes were wholly inactive. It does not show which counted candidates survived final partition selection or which mechanism caused the mixed spatial/temporal tradeoff. It does not establish an AV1, PSYEX, or source-budget impossibility.

The machine failure is decisive under the preregistered numerical screen; still inspection may explain artifacts but cannot convert this arm into a pass. `playback_observed=false` must remain explicit.

### Most informative next discriminator

Do not run another bundled strength/preset sweep. The smallest unresolved causal discriminator is one byte-neutral, target-frame observation of the **final surviving decision and filter boundary** for the existing PSYEX stream: bind picture 216 to final partition/block coordinates; record final skip/EOB/coeff state and whether its committed candidate used HBD/spatial policy; and capture exact visible pre-loop and post-loop luma with the existing source identity. Require observation-off/on full-IVF and app-reconstruction identity and complete visible-pixel ownership.

- If spatial-policy candidates survive in the failing ROIs and pre-loop texture is already absent, the remaining loss is in the winning partition/skip/quantized reconstruction, and a specific final-decision objective intervention is justified.
- If spatial candidates are evaluated but systematically displaced before final ownership, the next test should target partition/skip comparison rather than increase psy strength blindly.
- If pre-loop texture is substantially closer and post-loop loses it, a single matched-budget in-loop-filter contrast becomes justified.

This diagnostic separates the three remaining mechanisms without another quality encode, without fitting to a favorable metric, and without claiming that aggregate search counters map to final pixels.

**Final independent disposition: valid matched-rate negative. The bundled policy improves selected descriptors but fails both texture gates and introduces material edge, face, quiet-MSE and broad ACF regressions.**
