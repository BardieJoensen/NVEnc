# R16 support-analyzer preflight

Reviewed `worker/psyex-r16-tf0-budget/support-analysis/analyze_support.py` SHA256 `f4c69bff208bf259c34f730b70d9a1d41cccb89188415ef08865cb5d0ee4b97a`. It was not executed because no admitted R16 receipt was supplied.

## Blocking functional defects

1. Line 28 imports the analyzer from nonexistent `ROOT/'psyex-coeff/analyze.py'`. The pinned SHA exists at `ROOT/'parent/psyex-coeff-r11/analyze.py'`.
2. Line 32 calls `an.u.load_luma`, but the pinned analyzer has no module attribute `u`; it loads the R10 helper inside `main`. Load exact `an.U` at `an.USHA` using `an.mod`, then call that module's `load_luma`. Retain its identity in output provenance.
3. Lines 34–36 cannot obtain the dynamic coded ordinal. `ad['decoder_admission']` is an identity record and the top-level admission has no `coded_ordinal`, so this always yields `-1`. Load the exact `ad['artifacts']['syntax_binding']` result and use `target_coded_event.coded_ordinal`; require its encode receipt equals the admission's original receipt.
4. The admitted token manifest is effectively unused. Lines 33/37 only compare key sets, allowing owner/category/q metadata disagreement. Require no duplicate manifest tokens and exact per-token `begin`, `end`, `commit`, and `info` equality against the parsed trace; carry admitted `unit` and `category` into rows/groups. Require invoked tokens to have integer actual q, and uninvoked tokens to have q `None` and EOB zero. This is necessary for the claimed support/positive-EOB partitions.
5. The output does not bind the analyzer script or invocation. Capture `script_before=ident(__file__)`, record it plus argv/Python, and rehash it immediately before writing. The present result binds producer/parser/helpers but not the code that computed the SSE.

## Small correctness fixes

- Initialize `result_rois={}` before the ROI loop rather than mutating `locals()` with `setdefault` at line 59.
- Line 38's finite assertion is tautological because it indexes each array by its own finite mask. Remove it or explicitly reject infinities; `make_mosaics` already proves every fixed ROI is covered and finite.
- Require `len(jmap)==len(joined)==ad['tokens']` before comparing key sets, so duplicate manifest rows cannot collapse silently.

The core metric construction is otherwise appropriate: the pinned `make_mosaics` applies exactly one `/4`, clips padded bottom TUs to visible rows, retains skipped prediction, and supplies raw/scalar/final surfaces. ROI intersections are nonoverlapping and exhaust all three frozen rectangles. Squared-error sums in eight-bit-equivalent units are additive within the invoked/EOB partitions; raw/scalar/preloop/postloop are diagnostic stages and no HF/ACF or repair fraction is inferred. After the binding fixes above, this is a useful supplement and creates no new acceptance gate.

**Disposition:** blocked before execution on path/helper, coded-event, token-join, and script-provenance defects.

## Revision `63843d8e…`

The module paths/helper loading, dynamic syntax-binding ordinal, exact token field joins, duplicate guard, and execution sidecar are corrected. The schema smoke SHA `69202d46…` proves the old admitted parser population and mosaic coverage, but stops before the ROI/output paths.

Two runtime blockers remain in those untested paths:

- Line 57 still evaluates `t.get('info', {}).get(...)`; uninvoked tokens have explicit `info=None`, so this raises `AttributeError`. Extract q conditionally from non-None info.
- `result_rois` is never initialized before assignment at line 67, causing `NameError` after the first ROI.

For the stated owner/category provenance, also carry joined manifest `unit` and `category` into each row and assert the admitted positive-EOB category relationship. Capture `script_before` before computation rather than after it, and include analyzer script, unit-helper identity, and argv in the primary result in addition to the execution sidecar.

**Disposition remains blocked;** SHA `63843d8e…` must not be run on the R16 admission.

## Final revision `2449552f…`

The prior runtime and provenance blockers are corrected. I reviewed
`analyze_support.py` SHA256
`2449552f30f24247b43494712528f30e3601f24736877aeacfb96736c18cc4da`
and the completed R15 control:

- result `9b058818ebd778f2468956acbcbaa3744fd6b7954ae1c4fd0f6a4f2eaa41ee7c`
- execution `4604faec3ac2180bbd6de093cecc3c8f98eaa6df0c938f21c5d567d54a0587a3`
- rows `1e17822c1d0db5178440abf60e7db161dbd951263ce853b1c0e8aaa89e5c286e`

The execution binds the same script before/after and binds the reported result
and rows. All 4,809 intersecting R15 rows are invoked, positive-EOB category 4,
with complete 20,000/45,000/240,000-pixel shirt/background/face coverage. The
reported additive SSE closes exactly to the previously admitted R15 stage MSEs:

| ROI | raw | scalar | final/preloop/postloop |
|---|---:|---:|---:|
| shirt | 0.000103125 | 0.0853 | 0.084015625 |
| background | 0.0000416666666667 | 0.0966333333333333 | 0.0924361111111111 |
| face | 0.0000953125 | 0.07775234375 | 0.07465 |

The final source handles real uninvoked records safely: `info` is tested for
`None` before reading `actual_qindex`, and the subsequent invariant requires
`q is None` and EOB zero. This branch was **not** exercised by the R15 control,
which contains zero uninvoked rows. The admitted R11 population confirms the
expected domain (720 uninvoked `info=None`, EOB-zero records: 67 category 1 and
653 category 2), but the current schema smoke selects R15 and therefore does
not constitute runtime coverage of that branch. This is a test-coverage
limitation, not a source defect: if R16 contains uninvoked owners, successful
execution itself supplies the missing coverage; if it contains none, the branch
does not affect the R16 result. Preserve the per-group population counts so
that distinction remains explicit.

Line 65's extra category assertion is logically vacuous because the same branch
already establishes EOB zero. Category/EOB validity nevertheless comes from the
hard-pinned admission: `admit.py` constructs this exact manifest and asserts
every positive-EOB unit is category 4 before admission. Tightening the local
assertion to `category in (1,2)` for uninvoked records would improve fail-closed
clarity, but is not required for this supplementary calculation.

**Disposition:** accepted for the R16 admitted runtime. It adds no gate and its
SSE outputs remain support attribution only. Do not cite the R15 control as
evidence that the uninvoked branch ran; use the actual R16 group counts and
successful completion for that claim.
