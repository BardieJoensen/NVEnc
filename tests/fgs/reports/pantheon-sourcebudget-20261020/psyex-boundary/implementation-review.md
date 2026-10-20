# R9 boundary implementation review (pre-build)

## Disposition

**Hold the build for two small corrections.** The hook placement and generation model implement the narrowed contract correctly, but one missing vertical buffer bound weakens the promised fail-closed serialization, and one metadata field describes the next recode attempt rather than the captured attempt.

Reviewed artifacts:

- `pb_trace.c` SHA-256 `e5003f0fc7f8ae6a900685a044a31b9e5d7c24e3318aa070c9b1ecb2ab0e73b7`
- `pb_trace.h` SHA-256 `ac8b3153477b601417665ce7782cf294594ade150b97a84136b2325e06f8170e`
- `boundary.patch` SHA-256 `f8de34f9891bdfadd53cea5d47296c4304eb25d9a23b0ce39ec0860af2dd72ba`
- complete patched-source manifest SHA-256 `d88c0faca38171d52f6b7252349e825a089a4facbf5df7f6217aa0fc608e577d`

## Required corrections

1. **`rows()` checks only horizontal extent.** At `pb_trace.c:51-60`, `stride >= ox + ww` does not prove that `(oy + hh)` lies in the allocation. This is safe for the expected constructors but does not satisfy the contract's bounded-dimensions/fail-closed rule, particularly for the local packed SB buffer whose origin is deliberately ignored. Before any row write, require the final sample index to be within `b->luma_size` for Y and `b->chroma_size` for U/V, using 64-bit arithmetic, for example `(oy + hh - 1) * stride + ox + ww <= plane_size`. Also require even padded origins for 4:2:0 and assert 16-bit storage (`bit_depth`/pipeline field appropriate to each buffer). This both prevents an unexpected descriptor from causing an out-of-bounds read and proves the serialized payload matches its declared geometry.

2. **`base_qindex` is post-decision state for a rejected attempt.** The hook calls `recode_loop_decision_maker` before `pb_attempt`. On `do_recode=true`, that function changes `frm_hdr.quantization_params.base_q_idx` for the *next* attempt (`enc_dec_process.c:2722-2740`). `picture_meta()` then writes that value beside the just-captured reconstruction. Since R9 makes no quantizer claim, remove this field. Alternatively capture the completed attempt's value before the decision and pass it explicitly. Leaving the current field invites a false attempt-level interpretation.

## Correct implementation properties

- `pb_source` is immediately after `prepare_input_picture` and copies the visible portion of the per-thread packed 16-bit SB source before reuse. Its SB64 population is exactly 30 by 17 = 510 records; edge clipping gives even 4:2:0 dimensions. A bypassed EncDec path yields missing records and fails at `pb_attempt`, rather than silently substituting another source.
- The first target source hook checks `sb_based_dlf == 0` before reconstruction of that SB. The pre-loop frame is copied only after `enc_dec_coded_sb_count == sb_total_count`, after `do_recode` is computed and before either branch. With SB DLF forbidden, no filter can modify the shared reconstruction before this barrier; frame DLF cannot begin until the accepted branch posts EncDec results.
- Every generation has disjoint `seen` state. A complete type-2 record is emitted before generation increment/reset, only the recode branch increments, and exactly one non-recode attempt becomes accepted. `attempts == generation + 1`, one post record and the end marker close the population.
- The `intra_mutex` count barrier follows each worker's completed SB loop. The trace mutex serializes source payload writes and the final snapshot. Holding the trace lock does not mutate codec state; scheduling changes remain covered by required whole-stream/reconstruction identity.
- The post hook is inside actual recon output after restoration. Film grain, resize, superres and alt-ref paths fail closed. With those gates, the buffer precedes only the application's format copy and can be required to equal admitted app frame 216.
- The envelope is fixed-width little-endian, sequence-numbered and length-framed. Payload byte counts are correct for 4:2:0 16-bit samples: `3 * width * height`. Writes handle `EINTR`, reject short/zero writes, enforce a 512 MiB cap, and the end record is written only after encoder threads stop.
- The inherited FD is validated as fresh, regular, append-only and writable; the private duplicate is synced and closed at completion. Missing/duplicate SBs, attempts, posts or unsupported configuration terminate with a nonzero fatal status.

## Scope

The type-1 surface is specifically the packed **EncDec residual input**, not proof of the samples used by every preceding mode-decision search. Reports should call it that, or “packed coding input,” and retain the original-source comparison without claiming it identifies one temporal/preprocessing component.

After the two corrections, the implementation is suitable for a private build and off/on bit-neutral replay. Admission must still parse every record to exact declared length, reconstruct each generation's Y/U/V mosaics, verify sequence/type/population rules, and bind the accepted post surface to the independent R8 frame and complete unchanged stream/reconstruction.

## Final correction review

**Accepted for build.** Current `pb_trace.c` SHA-256 is `2beee0be4f20f448c6b5c4da8967d8980956f71915d190ec47c43c84a86345de`.

The focused delta resolves both findings:

- `rows()` now restricts storage to 10/16-bit descriptors, requires even padded origins, computes the last addressed sample with 64-bit arithmetic, and checks it against `luma_size`/`chroma_size` in addition to the row-stride bound. Those descriptor capacities are sample counts for these picture constructors, so the comparison is dimensionally correct before `uint16_t` serialization.
- `base_qindex` and its post-recode read were removed completely from metadata, eliminating the attempt-state ambiguity.

The regenerated six-file patch is SHA-256 `69c61c844532966496bc313cb2beaeb6d867bae5f93b5139c2774f4f0d069f3e`; the 1,789-file source manifest is SHA-256 `12f345e1f738b97fd00d9b9b2978864c53df995ad7590374edc21d31004124ce`, and its `pb_trace.c`/`.h` entries equal the live files.

Build runner SHA-256 `933ef9a3607a6e8e0b46f4bb1c31e0d885cac11590bf18b6ecc3ebd6bb54ca75` differs from the accepted R8 runner `ba90de74c22b6e4767d8825747314c43e2365d1553efa2e7cd2c2c4b507c9dd1` only by replacing the pre- and post-build reviewed-manifest pins with the new exact manifest hash. The byte comparison to `source-manifest.json`, post-build source equality, tool/configuration/binary receipts and failure handling remain unchanged. No further implementation blocker remains before the private build.
