# R10 pristine libaom decoder hook review

Source reviewed: `worker/aom-decoder-r10-pristine/source-pristine`. This is a
pre-implementation source review; it contains no runtime observations.

## Disposition

The proposed serial-decoder route is sound with two required qualifications:

1. A receive call's exact consumed frame span is `[source, *psource)`, not
   `[source, source + size)`. The latter may contain later frame events from the
   same IVF packet.
2. `existing_frame_idx` is a local in frame-header parsing and is not retained
   as an authoritative slot field in `AV1_COMMON`. Complete decoder-side
   show-existing lifecycle evidence needs a tiny header-parser hook that records
   that local value, or it must rely on the already admitted independent header
   parser. Comparing reference-buffer pointers can be ambiguous when one buffer
   occupies multiple slots.

Subject to those corrections, beginning immediately before
`aom_decode_frame_from_obus()` and finalizing immediately after it but before
`update_frame_buffers()` is the correct all-event envelope
(`av1/decoder/decoder.c:424-492`).

## Frame/event framing and metadata

- Save `source = *psource` and the passed end before the call. On successful
  return require `source < *psource <= source + size`, then hash/copy precisely
  that consumed interval. `aom_decode_frame_from_obus()` stops after one frame
  completes (`obu.c:878-880,989-1001,1030-1039`). For show-existing it sets the
  returned pointer through `read_frame_header_obu()` (`obu.c:273-287`); for a
  coded event the final tile decoder supplies it (`obu.c:344-367`). The outer
  decoder then loops over the remaining bytes (`av1/av1_dx_iface.c:719-745`).
- The consumed interval can include temporal delimiters, sequence headers, or
  metadata before the frame OBU. Therefore it must not be asserted equal to the
  independently bound target OBU SHA/size. Independently parse that interval and
  require it contains the expected packed target OBU; retain both identities.
- Post-call, pre-update fields are authoritative: `cm->show_existing_frame`,
  `cm->show_frame`, `cm->showable_frame`,
  `cm->current_frame.frame_type`, `.order_hint`, and
  `.refresh_frame_flags`, plus `cm->width`, `cm->height`, sequence bit depth and
  subsampling. `update_frame_buffers()` consumes/nulls `cm->cur_frame` and
  updates references (`decoder.c:357-422`), so post capture cannot move below it.
- Record successful **header-event ordinal** and coded-event ordinal separately.
  A receive call that returns no completed frame must not silently increment
  either. Target admission should require the independent key (event 314/coded
  210, hidden, order hint 88, packed OBU identity and later display link), not an
  ordinal alone.
- Show-existing slot syntax is read into local `existing_frame_idx` at
  `decodeframe.c:4485-4496`; non-key show-existing subsequently overwrites
  refresh flags with zero (`4550-4554`). Those post fields cannot recover the
  slot. Add a read-only observer assignment at the local read if decoder-side
  slot proof is desired.
- The proposed post hook is already **post-loop**: tile wrap-up runs deblock,
  CDEF, super-resolution, and restoration before returning from the OBU decode
  (`decodeframe.c:5238-5343`). A full pre-loop admission snapshot belongs just
  after `decode_tiles*()` returns at `5251-5260`, before `5274`; require it to
  equal R9 pre-loop exactly.

Fail closed on decode error/longjmp, zero or backward progress, an incomplete
frame, unexpected large-scale/single-tile partial decoding, dimensions or format
changes, target-key ambiguity, or any event-count/header-counter disagreement.

## Final owner and TU hooks

With `threads=1` and row-mt disabled, `decode_tiles()` installs combined
parse/decode visitors (`decodeframe.c:2800-2804`), so final parsed `MB_MODE_INFO`
and reconstruction share one traversal. Assert those runtime conditions rather
than assuming them.

The following placements cover the four required paths:

- **Owner syntax:** enter/exit `decode_token_recon_block()`
  (`decodeframe.c:890-1000`) after `decode_mbmi_block()` has parsed final syntax
  (`1116-1172`). Record `mi_row/mi_col`, `bsize`, partition, segment,
  `skip_mode`, `skip_txfm`, intra/inter, intrabc, modes/references/MVs, and final
  visible clipping.
- **Inter and intrabc predictor:** copy the luma owner immediately after
  `predict_inter_block_visit()` at `940-943`. `predict_inter_block()` has already
  built ordinary/compound/intrabc prediction and OBMC (`834-862`). For
  `skip_txfm`, no TU loop runs; copy the final owner again at function exit and
  require predictor equals pre-loop reconstruction. `is_inter_block()` includes
  intrabc (`common/blockd.h:345-374`), but retain intrabc as its own mode class.
- **Non-skip inter TU:** in `decode_reconstruct_tx()`, capture after
  `read_coeffs_tx_inter_block_visit()` and immediately before
  `inverse_tx_inter_block_visit()` (`decodeframe.c:271-297`), then capture the
  same clipped TU after the inverse call. This is before coefficients are cleared
  by `inverse_transform_block()` (`143-155`).
- **Intra TU, including skip:** `predict_and_reconstruct_intra_block()` performs
  native prediction at `204-213`; capture immediately afterward, before the EOB
  test/native inverse at `214-225`, and again afterward. Coefficients were read
  immediately before this visitor (`930-934`). For `skip_txfm`, coefficient/EOB
  storage was not initialized for this TU; mark syntax-absent and never inspect
  those buffers. Intra predictors are sequential and may use earlier reconstructed
  neighbors, so their assembled pre-inverse samples are actual local predictors,
  not a coherent hypothetical whole-frame predictor-only reconstruction.

`skip_mode` normatively forces `skip_txfm=1` (`decodemv.c:1522-1527`). Neither
`skip_txfm` nor EOB zero proves that the encoder did or did not execute forward
quantization.

## Samples, geometry, coefficients, and Q state

- Destination offsets use four-sample units, exactly as at
  `decodeframe.c:222,245-247`. High-bit-depth buffers are tagged byte pointers;
  use `CONVERT_TO_SHORTPTR(dst)` and keep decoder stride in samples. A plain C
  cast is wrong (`aom_ports/mem.h:69-70`). Require high-bit-depth storage and
  bit depth 10 for this fixture.
- Derive owner origin from `mi_col/mi_row * MI_SIZE`; derive nominal owner/TU
  sizes from the block/TX tables, then clip against `cm->width/height` (and check
  the current buffer crop agrees). `pd->width/height` is nominal and forced to at
  least four (`av1_common_int.h:1328-1337`), so it is not sufficient for right or
  bottom edge clipping. Retain coded geometry separately from visible ownership.
  Require visible owner coverage exactly once and applicable TU coverage exactly
  once, including rectangular/sub-8 edge cases.
- CFL is chroma-only at the predictor facade (`reconintra.c:1670+`); luma capture
  is safe, but hooks must not disturb subsequent luma-to-CFL storage
  (`decodeframe.c:227-229,996`). Intrabc reads already reconstructed current-frame
  samples, so preserve traversal and perform only private copies.
- Capture `eob`, transform size/type, scan identity, and raster `dqcoeff` after
  coefficient reading and before inverse clearing. Validate
  `eob <= av1_get_max_eob(tx_size)` and every `scan[0:eob]` index. For EOB zero,
  emit no coefficient payload and require predictor==post-inverse; buffer contents
  can be stale. `max_scan_line` is the largest raster index used for clearing,
  not a coefficient count. This matters especially for reduced 64-level
  transforms.
- Do not report `xd->qindex[segment]` as TU coded Q: it is initialized from the
  frame base (`decodeframe.c:5037-5044`) and does not incorporate later delta-Q.
  The normative per-owner qindex is
  `av1_get_qindex(&cm->seg, mbmi->segment_id, mbmi->current_qindex)`;
  `mbmi->current_qindex` is captured after delta-Q parsing
  (`decodemv.c:732-795,1532-1539`). Check it against the DC/AC dequant table
  actually used (`decodeframe.c:1151-1167`, `decodetxb.c:110-166`).
- Quant-matrix evidence must distinguish frame `using_qmatrix`/Y level from the
  actual inverse matrix selected by `av1_get_iqmatrix()`: 1D/identity transforms
  use the flat matrix even when frame matrices are enabled
  (`quant_common.c:251-261`). The copied normative dqcoeff/EOB is authoritative;
  all Q fields remain decoder reconstruction state, never evidence of an encoder
  forward-quantizer call.

## Minimum admission

Require: exact private-off/private-on displayed 336-frame all-plane agreement;
all header events and coded events matched to the independent parser; exact target
compressed identity and refresh/show-existing link; exact target post-loop and
R8 display hashes; exact assembled target pre-loop equality to R9; complete,
nonoverlapping visible owner/TU populations; every coefficient-present native
before/after TU paired; and no trace overflow, unsupported path, or observer
write into codec-owned storage. These checks support the final-syntax/predictor
localization only; they do not identify encoder search, forward quantization, or
the cause of coefficient absence.
