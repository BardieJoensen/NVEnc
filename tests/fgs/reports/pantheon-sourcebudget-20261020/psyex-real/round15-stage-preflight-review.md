# R15 stage-diagnostic preflight

Reviewed unexecuted `parent/psyex-real-r15/stage_diagnostic.py` SHA256 `c6f133f4097ba9fbc142a48bc35647f6c196dc74e83e3e027aa9e67572ceed31`.

## Disposition

Cleared. The script pins final R15 admission implementation `7dc554ff…`, the dynamically parameterized parser `45f11c…`, admitted R11 stage implementation `44b8037c…`, R10 unit helper `d10bfb…`, and the prior R9 metric-helper graph. It rehashes the admission artifact graph and all metric helpers before and after analysis, reparses the R15 coefficient trace with the independently bound coded ordinal, and requires the parsed terminal/population to equal admission.

`u.load_luma()` at `worker/decoder-r10-analysis/analyze_decoder_units.py:23-30` converts native 10-bit storage to eight-bit-equivalent float exactly once (`/4`). R11 `make_mosaics()` at `parent/psyex-coeff-r11/analyze.py:51-63` likewise divides native token images once. The R15 script does not divide either again. It proves the reconstructed predictor and final mosaics equal the admitted decoder predictor/preloop over every covered sample, and `make_mosaics` requires complete finite support over each fixed shirt/background/face ROI. Uninvoked tokens carry the predictor through raw/scalar/optimizer/final diagnostic stages, as defined by the pinned R11 `images()` helper; invoked stages use their exact captured native inverse images.

Every reported descriptor uses the exact admitted original frame as reference. Coding input, predictor, preloop, and postloop identities come from the admitted artifacts; raw/scalar/optimizer/final mosaics are deterministically regenerated from the admitted trace. The three boxes remain the fixed coordinates, and actual-q/support summaries are copied from the same admission whose token count/terminal have just been revalidated.

The scope is appropriately narrow: one admitted frame, original-referenced actual-stage descriptions, and a fixed-predictor local raw diagnostic. It explicitly excludes isolated-TF, matched-rate, full-window, repair, and playback claims. These stage descriptors are nonlinear and must not be called additive loss attribution or a deployable reconstruction.

## Minor reporting advice

- `stage_changes[*].numerically_changed` means q/DQ/EOB state differed from the preceding captured stage (lines 97-101); it does not test reconstructed pixels. Rename it `coefficient_state_changed` or document that definition in output metadata.
- Recording `covered_pixels` and optional SHA256 values of the regenerated ROI mosaics would make the complete-support/image identity easier to audit, although the pinned trace, deterministic parser, equality assertions, and fixed ROI descriptors already make the result reproducible.

Neither item is a validity blocker and neither changes metrics or acceptance gates. The script correctly rejects optimized Python and creates its result only after all checks.

## Final delta clearance

Cleared final `stage_diagnostic.py` SHA256 `1f1e42c05a50a4d2e8e243c073157113459bbb92ed84e303e972e386399a7a52`: its exact diff from preserved `stage_diagnostic-pre-review.py` SHA256 `c6f133f4097ba9fbc142a48bc35647f6c196dc74e83e3e027aa9e67572ceed31` only adds `covered_pixels=int(covered.sum())` and the accurate `stage_change_semantics` definition requested above; no analytical behavior or gate changed.
