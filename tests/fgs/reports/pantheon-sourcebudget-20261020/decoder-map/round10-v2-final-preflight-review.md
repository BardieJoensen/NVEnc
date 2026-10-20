# R10 decoder v2 final preflight review

Reviewed read-only on 2026-10-20:

- completed build pins `4c221ef0112291bcdd541b87a80c21f74ebef39e5b0ff507921d014b091f1af5`
- replay `6961b25542cb28f84ce2ba2993196bd85239d36380654ab131c615b3db5f1781`
- validator `fde9fa7a79c52de70b0098d38fe291670472e8250f629c4c5f3c648d322b471b`
- analyzer `454b3d6816f8ee92b00bb23dc926d0255f7ac0786b137d02beed10808a0665b3`
- analyzer smoke receipt `e642156712ef0fa4f2dae4a75da38c07ca70b96e32fabce7dd1b8d7aa0dafbaa`

## Capture/admission disposition

Approved. The only v1-to-v2 observer semantic change is the independently accepted width/height versus upscaled-width/height guard and detailed failure diagnostics. The completed build pins exact 1,345-file before/after manifests, the unchanged configuration, three expected changed source files, exact patch/app/library/build artifacts, and both relevant independent reviews. The new app/library hashes are `ce8a2cf1...` and `6b621938...`.

The replay now writes a preflight receipt immediately and catches pin/tool/loader/process-launch exceptions, preserving `validation_failed`, the exception and identities of artifacts that exist. Its successful decode path is unchanged. The validator's substantive controls are unchanged and it pins the v2 build and replay. Nominal off/on capture and admission may proceed; scientific interpretation still requires the full successful validator result.

## Analyzer disposition

The revision fixes optimized-Python rejection, analyzer self identity, required external validator-SHA matching, source correlation and signed HF change in ROI category aggregates, explicit outside-group meaning, explicit unweighted p95 naming, and the preserved functional smoke. Supplying validator SHA `fde9fa7a...` in the actual invocation is an acceptance condition and remains inspectable in the report command.

One small frozen-contract correction remains before numerical analysis: `control_report():91` still reports MSE, HF absolute error and ACF1 absolute error only. Add `hf_corr_source` and `signed_hf_delta` statistics there as well. Without them the 858 frozen controls cannot support the contract's correlation and directional-amplitude comparison even though the ROI categories can. Regenerate the smoke receipt after this script change. No capture or admission rerun follows from that analyzer-only correction.
