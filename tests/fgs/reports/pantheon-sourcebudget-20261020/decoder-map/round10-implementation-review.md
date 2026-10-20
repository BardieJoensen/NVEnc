# R10 decoder implementation v1 review

Reviewed:

- `parent/aom-decoder-r10/pantheon_decoder.h`, SHA
  `8f484249cc47bc81140b60101dd7770f79788cf7dbbc70f813f027ec99db8993`
- `parent/aom-decoder-r10/apply_instrumentation.py`, SHA
  `5de312f06ead19ea9bb4d05d0ea635e6be26b87272bef72cf0050cd6bdd7757a`
- patched source and committed `ROUND10_DECODER_CONTRACT.md`

Disposition: the hook topology is good, but I would not build/run v1 until the
four blocking corrections below are made. All are local observer fixes.

## Blocking corrections

1. **Bound the decoder-consumed pointer before using it.** `p10_end()` receives
   only `start` and `end`, then subtracts and copies them. Pass the original
   `source + size` as well and require `start < end <= input_end` before pointer
   subtraction/copy. This is the central multiheader-packet framing invariant;
   the decoder normally supplies it, but a fail-closed trace must validate it.

2. **Show-existing event metadata currently contains stale fields.** The decoder
   show-existing branch sets `show_frame`, order hint, and refresh behavior, but
   does not assign `cm->current_frame.frame_type` or `cm->showable_frame` from the
   referenced buffer (`decodeframe.c:4485-4563`). Therefore `p10_end()` must emit
   those fields as null/not-valid for show-existing events, or add the previously
   identified local-slot hook and read the referenced buffer's properties. Do
   not compare current `frame_type`/`showable` to parsed show-existing syntax.
   The existing independent parser can remain authoritative for slot lifecycle.

3. **Non-skip EOB-zero TU type is recorded incorrectly.** `p10_tu()` leaves
   `tx_type=-1` unless EOB is positive. For an all-zero, non-skip luma TU,
   `av1_read_coeffs_txb()` explicitly sets the map entry to `DCT_DCT`
   (`decodetxb.c:133-159`), so this loses an authoritative final transform fact.
   For every `!skip_txfm` TU, read `av1_get_tx_type()` after coefficient parsing;
   keep `-1` only for syntax-absent skip-transform TUs.

4. **Capture or prove the complete inverse input.** The code serializes the
   contiguous dqcoeff prefix through `max_scan_line`, but neither emits the scan
   nor proves all remaining entries consumed by the native inverse are zero.
   The smallest robust fix is to serialize the entire adjusted coefficient
   population `get_txb_wide(tx) * get_txb_high(tx)` for EOB-positive TUs. It is
   at most 1024 values and handles reduced 64-level transforms directly.
   Alternatively assert/hash that the omitted suffix is zero and bind the exact
   source scan table. Also validate `eob <= av1_get_max_eob(tx)`, not merely the
   adjusted rectangle area, and treat `max_scan_line` as a raster-index bound,
   not a scan length.

## Focused correctness notes

- In `p10_leaf()`, use `m->current_qindex` as `qbase` and assert it equals
  `xd->current_base_qindex` at this immediate serial hook. The current value is
  probably equal here, but the MBMI field is the stored normative CurrentQIndex
  tied to this final owner. The computed segment q and `seg_dequant_QTX` values
  are otherwise taken at the correct lifetime.
- IQM capture is structurally correct: `av1_get_iqmatrix()` is called after
  tx type is known, and `get_txb_wide/high()` uses adjusted dimensions for
  reduced 64-level transforms. Emit an explicit `iqm_flat`/`iqm_present` field
  and adjusted matrix dimensions. A null pointer is the normative flat matrix,
  not missing evidence. `using_qmatrix` and `qm_level_y` alone do not describe
  the actual per-TU matrix.
- Add bounds before array indexing: validate `tx` and derived adjusted count,
  nonnegative row/col, visible origin, and nominal TU end. Current values come
  from trusted decoder enums, but these checks make corrupt trace state fatal
  before pointer arithmetic.
- Numeric refs/MVs/motion mode on intra leaves may be dead state. Emit them only
  under an explicit inter-valid flag (intrabc remains separately unsupported),
  or require analysis to treat them as null. The same applies to dequant/Q
  context on syntax-absent skip owners: it is normative context, not evidence of
  a transform or quantizer execution.

## Accepted topology and scoped limitations

- `p10_begin()` precedes OBU decode and the end hook precedes
  `update_frame_buffers()`, so event numbering and current-frame lifetime are
  correct. Target event 314/coded ordinal 210 is checked with hidden/order-hint/
  refresh metadata rather than ordinal alone.
- Intra capture is after native prediction and before inverse; inter capture is
  after complete inter/OBMC/intrabc prediction and before each native inverse.
  EOB and dqcoeff are copied before native clearing. Skip-transform buffers are
  correctly not read.
- Luma geometry uses tagged-pointer conversion correctly. Per-TU after surfaces
  plus skipped-inter owner surfaces can assemble pre-loop luma. Admission must
  still prove exact single coverage and byte equality to R9 pre-loop. A second
  skipped-inter copy at block exit would independently demonstrate no subsequent
  write, but exact assembled pre-loop equality is sufficient for this fixed
  path.
- A per-TU intra predictor mosaic is an actual sequence of local predictors;
  because later intra prediction may depend on earlier reconstructed neighbors,
  it is not a coherent predictor-only whole-frame counterfactual.

The patch should remain bit-neutral after these changes. No result or mechanism
conclusion is available before private off/on stream/sample identity and full
admission.
