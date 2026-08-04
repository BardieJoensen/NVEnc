# Pre-registered post-encode luma-strength closure gate

Date: 2026-08-04 UTC  
Branch: `fgs/test-automation`  
Authority: research only; no production, Tdarr, routing, or public-option change

## Question

Every bounded pre-encode luma response model has now failed an external
per-luma gate.  The exact AV1 emitter is understood; the unknown quantity is
the grain-like variance that survives base encoding.  This experiment asks
whether observing that base once removes the ambiguity cleanly enough for a
two-encode architecture.

It does not attempt to make the first encode cheaper, rewrite an AV1
bitstream, or solve chroma.  It is an existence and base-stability test.

## Frozen Interstellar sequence

Use the retained Interstellar causal clean Y4M and source-derived film-grain
table because this is the labelled clipped-black luma failure.  Both AV1
passes use the same pinned `40b987ff` binary, clean input, QVBR 29, 20 Mbit/s
maximum, P4, HQ, 10-bit output, metadata-copy settings, and fixed-table mode.

1. Encode the clean Y4M with the original table.  This is pass 1.
2. Measure source temporal truth and the actual grain-disabled pass-1 base on
   the frozen frames `10,58,106,154,202,250,275`.
3. Solve only luma scaling points against that **decoded pass-1 base**.  Use
   every eligible production-static block, four deterministic AV1 seeds, the
   existing quantized response Jacobian, existing damping and at most two
   iterations.  The target in each luma band is the exact post-encode missing
   variance `sqrt(1 - post_leak^2)`, not the QVBR prediction.
4. Audit the proposed table on the pass-1 base with the independent
   eight-seed/full-block oracle.  Every populated band must be within `0.020`
   of its exact synthesis target before a second encode is allowed.
5. Encode the **same original clean Y4M** with only the corrected table
   changed.  This is pass 2; it is not an encode of the decoded pass-1 output.
6. Require a full `libdav1d -xerror` decode.  Compare pass-1 and pass-2
   grain-disabled video hashes.  Byte identity is the desired proof; if they
   differ, report PSNR and remeasure rather than assuming the feedback stayed
   closed.
7. On pass 2, require every populated luma band's played-total ratio to lie
   within the existing `0.0442` bound of 1.000.  Report aggregate amplitude,
   bytes and encode time, but do not use compression or speed to waive a
   quality failure.

No sample-count retry, extra solver iteration, threshold adjustment, or table
re-fit follows a failed gate.  Taxi Driver and Deer Hunter run only if
Interstellar clears every step unchanged.

## Interpretation

A pass proves that post-encode feedback can close luma strength while holding
the clean input fixed.  It does not make a two-pass Tdarr workflow acceptable:
storage, throughput, failure recovery, full-title table timing, chroma, and
perceptual review would remain.

A failure—especially a pass-1/pass-2 base change—means even two encodes are
not a stable closure and leaves safe bitstream/header rewriting as the only
zero-reencode version worth investigating.  The guarded source-texture result
is independent in either outcome.
