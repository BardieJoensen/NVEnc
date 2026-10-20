# R8 PSYEX summarizer pre-result review

Reviewed unexecuted `summarize_psyex.py` SHA `0a445b30bcec42cfc6cd04f38322b217a993b2fa57bb4b4970512712041860f3`. No PSYEX quality result or runtime counter was inspected.

## Corrections before execution

1. **Bind each texture artifact to the decoded stream it describes.** Lines 38–39 bind the decoded file through score identity, but the loaded texture JSON is accepted without checking its `case`, `tag`, or declared `path`. A stale same-name/same-shape JSON could therefore supply all 240 temporal rows and midpoint screens. For each arm require `t['case']==case`, `t['tag']==tag`, and the live hash of `t['path']` to equal `score_identity['distorted']['sha256']` (and preferably require the canonical decoded path). This is the only blocking evidence-binding defect.

2. **Retain the complete frozen control comparison.** Lines 69–73 summarize only the five base groups and silently omit the scorer's five `*_outside` legacy-mask groups. They also count paired MSE and HF regressions but omit paired ACF1-error regressions even though ACF is retained in each aggregate control summary. Iterate the same `(kind, outside)` population used by the scorer, label outside groups as legacy diagnostic masks, and add an ACF1-error-worse count over rows where both candidate and source ACF1 exist. Preserve the embedded mean/p95/signed-tail summaries. These are descriptive regressions, not new gates.

## Small binding hardening

- The decoder schema branch is otherwise correct: R3 uses `output`/`decoded_raw` and PSYEX uses `inputs['out.mkv']`/`recon`. For PSYEX also require `dv['status']=='admitted'`, bind `dv['inputs']['command.json']` to the fixed run receipt, and require `dv['recon']` to equal the run reconstruction identity. This avoids relying solely on the true aggregate boolean.
- Assert both assessments carry the same `source_mbps`; for each packet receipt bind the measured output identity and scored position/window fields, not only its numeric rate. The fixed command hashes, exact input equality, 99–100% eligibility, and pairwise 1% gate already make the rate comparison sound.
- The 12,870 tile population is exact and coordinate-paired across the two arms. The texture population is exactly frames 0–239 with source descriptors paired. CUDA frame numbers are exact 0–239; SSIMULACRA2 and Butteraugli formats have no frame IDs, so exact list length 240 is the strongest schema-level population check unless their aggregate arithmetic is recomputed. Recomputing is optional and should use the campaign's precise pooling/rounding rules.

## Scientific scope

The output reports the unchanged HF/ACF ROI screens, source correlation, 240-frame temporal traces, broad full-reference metrics, p1/p5/p95 tails, CAMBI mean/max, frozen controls, face control, signed quiet HF tails, rate, and bounded runtime scope. It does not introduce a p-value, confidence claim, or replacement acceptance threshold. Worse-tile counts must be labeled descriptive because tiles and frames are spatially and temporally correlated; they are not a formal significance test. The script reports a metric panel rather than optimizing or accepting on one score. The existing HF ±10% and ACF1 ≤ .05 screens remain the only numerical texture gates, with controls and playback limitations unchanged.

**Status: conditionally accepted after texture binding and complete control-group retention.**

## Final disposition after focused correction

Reviewed unexecuted final script SHA `0e0cf719d20ed00117a4652d7d75fb9697c66fbaef3d4dc83b0182056f32c785`. No PSYEX quality result or observation counter was opened.

**Accepted for execution.** Lines 38–41 now bind each texture document's case, tag, canonical decoded path, and live decoded hash. Lines 81–92 retain every frozen kind×outside population, preserve the aggregate mean/p95 controls, and add an explicitly counted ACF1-evaluable population and paired regression count. Lines 117–119 correctly label outside masks as legacy, correlated counts as descriptive, and the new full-window temporal summaries as fixed-coordinate, non-motion-compensated evidence without playback inference.

The PSYEX decoder branch now requires admitted status and binds its command, MKV, and reconstruction to the fixed run; source rate equality and packet window/position identities are also explicit. The temporal calculation uses only paired non-null source/candidate correlations and records its evaluable count, mean absolute error, and p95 across the complete ordered 240-row trace. It creates no new acceptance threshold. The original HF/ACF screens and the broad metric/control panel remain unchanged, so no single metric has been promoted into an optimization or acceptance criterion.

No remaining correction is required.
