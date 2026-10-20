# R17 fixed-q4 contract review

Reviewed `ROUND17_FIXED_Q4_CONTRACT.md` SHA `c207781f7fd77d488df17a9892988c78d660cf88c3ab8216209a91c73ab29f8c` against the admitted R16 support and the R12/R13 native route.

**Disposition:** accepted for implementation review. The question is falsifiable and correctly scoped to the R16 fixed predictor/partition/TX/scan/QM population. It preserves the distinction between an unfavorable local q4 result and a real lower-q policy that can change decisions. It also correctly excludes rate, legal-encode, repair, full-window-gate and playback claims.

The runner must make two details literal rather than relying on the prose alone:

1. Before q4, generate the current-q FP rows for every invoked token using the independently established R16 luma-DC delta and require exact equality with captured table rows `[0,1,6]`. The current R12 `Native.tables(q)` hardcodes delta zero. Reuse without rebuild is permitted only if R16 evidence proves that exact model for every invoked token; otherwise stop or expose the proven delta in a separately reviewed helper. The q4 intervention must replace exactly rows `[0,1,6]` and preserve `[2,3,4,5]` byte-for-byte.
2. Treat admission's 64x64 layout checks as input validation, not proof of helper equivalence. The fresh runner must execute baseline direct/runtime q, DQ, EOB and inverse equality plus captured raw-inverse equality on every invoked R16 token, including reduced-`n` 64x64 tokens. It must preserve captured `n`, scan/iscan, `log_scale`, TX/type and QM/IQM; no 4096-coefficient expansion is allowed.

All invoked-zero-EOB tokens remain in the baseline and q4 direct/runtime population. Only genuinely uninvoked owners receive no q4 result; their predictors may populate the explicitly secondary whole-ROI mosaic. Primary results should use the identical invoked mask for baseline/raw/q4 distances, with complete fixed-ROI coverage and spatially additive SSE reported separately from nonlinear HF/ACF/correlation descriptors.

No further gate or setting is needed before runner review. One q4 point is sufficient; another quantizer point or encode would exceed this contract.
