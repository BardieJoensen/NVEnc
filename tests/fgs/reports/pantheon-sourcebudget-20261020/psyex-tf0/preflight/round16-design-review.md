# R16 TF-off source-budget design review

Reviewed `ROUND16_TF0_BUDGET_CONTRACT.md` SHA256 `28a28bc18d71e51c64ef0dffed026e122073ab4bd721521a4d7c049889914331` against admitted R8 and R15 evidence.

## Disposition

The experiment is justified and bounded. It is the missing practical factorial arm: exact admitted R8 PSYEX settings with only TF enabled→disabled, fresh two-pass statistics, and request-only rate calibration. It directly tests a source-budget candidate and does not reinterpret R15's 19.6777× result as practical.

One interpretation sentence needs tightening before outcome. Lines 52–54 currently let “original-identical coding input and coarse actual q” identify absolute-cap allocation. Coarse q alone is insufficient when skipped/no-residual support or search/partition decisions may dominate. Require original-identical input **plus sufficient realized residual support and loss localized at scalar quantization** before selecting the absolute cap. If skipped/no-residual owners or missing legal support dominate, select the decision trace. This changes no encode or gate; it prevents the native observation from being interpreted toward a preferred next mechanism.

## Checked design facts

- The decisive source interval is `[9.579757176, 9.6765224]` Mbps. Relative to admitted R8 `9.6279048` Mbps, its endpoints are `0.995000` and `1.005050`, so every admitted 99–100% source result is within 1% of R8. The 99.7% target is `9.6474928328` Mbps (`1.002034×` R8) and stays below the hard source cap.
- Starting at the unchanged 10,313 kbps request and updating only integer TBR by `previous_request × target/actual` is an outcome-independent calibration rule. The three-request stop, fresh statistics/output for every request, and parent reevaluation on nonresponse prevent a hidden settings sweep.
- The policy scope is accurate. TF-off may change source processing, references, first-pass statistics, search, support, partitions, and later feedback. It is a one-public-setting end-to-end policy contrast, not an input-only or isolated-TF causal test. QP bounds, static QP, AQ, QM, psy, search, filters, GOP, and threading remain R8.
- Dynamic syntax binding is required rather than inheriting R15 event/population identities. Neutral off/on equality, independent all336 decoder agreement, and exact encoder-to-decoder joins cover intervention validity. Actual final-forward q claims must remain restricted to proven invocations; skip/no-residual owners need separate syntax/decision categories and must not inherit stale q/EOB semantics.
- The five-frame HF/ACF thresholds, all 12,870 control tiles, source correlation, quiet positive tail, face/edge, campaign tails, banding, and temporal traces are unchanged. There is no new aggregate threshold or permission to hide a regression behind the midpoint mean.
- A pass is only a provisional E05 numerical candidate under the rate cap. E04/regression-window transfer and eventual playback remain separate. A failed single arm rejects this policy, not AV1, TF-off generally, or all spatial allocation.

After the interpretation condition is corrected, I find no design blocker. Runner admission should prove its literal R8 command differs only in `--enable-tf`, request/output/stats paths, and should bind each calibration receipt to its own fresh first-pass statistics before any quality work.

## Final contract clearance

Cleared revised `ROUND16_TF0_BUDGET_CONTRACT.md` SHA256 `5ed81849c12af6daeb206e2184fa7ad0ddacb4b6d7d3ec35fab3b845c9901c71`. The requested interpretation now requires source-identical coding input, sufficient realized residual support, and scalar-quantization-localized loss before selecting the absolute cap; coarse q alone is explicitly insufficient, while dominant skip/no-residual/missing support selects decision tracing. Policy, rate, quality gates, and experiment scope are unchanged.
