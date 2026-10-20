# R9 boundary validator review

Reviewed `validate_psyex_boundary.py` SHA-256 `0d816e06c0a88039108c5fec5be6da285d128dd967636653c938e6f0aa1181ce` against the final C helper (`2beee0be...`), schema (`c9f4cf30...`), patch (`69c61c84...`) and boundary contract.

## Disposition

**Two small blockers must be fixed before this script can issue an admitted result.** The trace parser and sample joins are otherwise sound.

1. `assert __debug__, "Do not disable admission assertions"` does not guard optimized execution. Python removes that statement along with every other assertion under `python -O`, so the validator would proceed with nearly all admission checks absent. Replace it with an executable guard, for example:

   ```python
   if not __debug__:
       raise RuntimeError("Do not disable admission assertions")
   ```

   This must occur before argument processing/output creation. A negative invocation with `python -O` should then fail and create no output.

2. The now-created completed-build identity is accepted from an arbitrary argument path and only checked against the current live files. Bind the reviewed JSON itself: `completed-build-pins.json` SHA-256 `b103a2af7c3aabcba15158c04a71ff7668e2043799c76468f8b60cb3bba799a7`, whose map is receipt `4c4871c9...`, artifact list `f60a450d...`, app `bcb53216...`, and library `481c93f0...`. The smallest correction is to pass that expected SHA to `bind("completed_build_pins", ...)`; retaining the exact key set and live-file checks is appropriate.

## Correct trace admission

- The parser consumes fixed 64-byte little-endian envelopes, requires contiguous sequence and current generation in every header, bounds JSON and payload sizes, rejects partial header/JSON/payload, rejects any record after the end record, and requires exact EOF.
- Record order is fail closed: type-1 SBs precede one type-2 attempt; rejected type-2 increments generation and clears coverage; a non-recode type-2 uniquely accepts; then exactly one type-3 post and exact type-4 terminal metadata follow. Attempt count, accepted generation, post count and pre-end sequence are cross-checked.
- For every generation, SB address/geometry is canonical for the fixed 1920x1080 frame and selected SB size. Duplicate SBs fail. Independent Y/U/V masks reject overlap and require every visible sample exactly once before an attempt record. Payload lengths, 4:2:0 shapes and 10-bit sample ranges are checked for SB and full-frame records.
- Full-frame metadata requires target picture, visible dimensions, 10-bit 4:2:0, complete SB count, even origins, adequate strides/dimensions, and `sb_based_dlf == 0`. Accepted attempt/post coding identity fields are equal.
- Coding-input samples are retained without an equality requirement. The original is independently bound both as frozen 240-frame source frame 120 and as exact full input-Y4M frame 216. The accepted trace post is byte-equal to R8 app-recon frame 216 and its admitted decoder hash. Off and on receipts each bind exact original 336-frame IVF/recon outputs and the normalized original pass-2 command.
- The validator writes stage files only after provenance, replay, trace, original and post-loop checks pass. The output scope correctly excludes per-TU quantizer, search-survival, repair and playback claims.

Reports should continue to call type 1 the **packed EncDec coding/residual input**. It is not evidence that every earlier mode-decision search consumed that same packed surface.

## Negative trace tests once a valid trace exists

Run these on copies through `parse_trace`, expecting rejection in every case:

1. truncate one byte from the terminal JSON and append one byte after an intact end record (partial-record and trailing-data checks);
2. alter a header sequence or generation, and alter a type/payload length (envelope and alignment checks);
3. remove one type-1 SB, duplicate one SB, or change an SB coordinate to overlap another (all-plane population checks);
4. flip an early attempt's `do_recode` while preserving JSON length, or change terminal accepted-generation/attempt count (acceptedness checks);
5. set one payload sample to 1024 (10-bit bound), and separately change a valid-range post-loop sample (the latter must survive structural parsing but fail the independent R8 post-frame equality in the full admission path);
6. invoke the validator under `python -O` and require the explicit runtime guard to fail before output creation.

The corruption harness should preserve each mutated artifact and expected rejection reason or stage. It need not weaken the live trace provenance checks; structural copies can exercise `parse_trace`, while the valid-range post mutation can exercise a small post-binding helper or a deliberately isolated full-path fixture.

## Correction disposition

Validator SHA-256 `4541f88cb2d399491843b8824018bb963beb7be4f550eb8089f708cc28e35814` resolves both blockers. The executable `if not __debug__: raise RuntimeError(...)` precedes argument parsing, and `completed-build-pins.json` is now bound to reviewed SHA-256 `b103a2af7c3aabcba15158c04a71ff7668e2043799c76468f8b60cb3bba799a7`. The validator is accepted pending the planned negative corruption receipt and a valid trace; those tests verify execution rather than require another design change.

## Runtime metadata erratum: `show_existing_frame`

The nominal parser stop on value `6` identifies an overstrong validator invariant, not corrupt trace data. In this source, `FrameHeader.show_existing_frame` is a DPB slot index:

- `pd_process.c:2150-2173` controls the separate `pcs->has_show_existing` flag and assigns `frm_hdr->show_existing_frame` from `lay*_idx`/`base*_idx` values when that mechanism is selected.
- `entropy_coding.c:3244-3259` receives a separate `show_existing` argument, writes that as the one-bit syntax flag, and only then writes `frm_hdr->show_existing_frame` as a three-bit literal.
- `packetization_process.c:869-871` stores `has_show_existing` and the slot field separately.

Thus `av1_structs.h:403-405` has a misleading flag-like comment for this member. The observed `6` is valid in the field's actual `0..7` domain. Because the R9 trace did not capture `pcs->has_show_existing`, it cannot establish whether the slot was active for this coded frame; when the flag is false the slot may retain an inactive value.

Accepted minimal correction: retain the raw field, validate it as an integer in `0..7`, and continue requiring exact equality between type-2 and type-3 metadata. Keep `show_frame`, `showable_frame`, and `is_ref` as Boolean checks. Add an admission/report note such as `show_existing_frame is a raw 3-bit DPB-slot field; activity flag was not captured and no show-existing claim is made.` No C rebuild or replay is needed. This correction does not affect attempt identity, all-plane coverage, coding/preloop/postloop samples, or the post-loop binding.
