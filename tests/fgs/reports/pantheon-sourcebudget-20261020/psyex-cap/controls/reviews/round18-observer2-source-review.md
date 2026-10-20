# Round 18 corrected observer source review

## Reviewed identities

- Observer-only patch: `a53d222914c87e20cbedd12497774a93a375448c53a3fe78c60a93e616505024`
- Corrected 1,790-file manifest: `305f06b51bf94988bd9d6c1002cfa880736071799f52d38f3bc7c25f5248a22b`
- Frozen policy-source manifest: `f405193d6b35d74919d452457e9b8c93e52938ebbf184dda07c7622180af75ca`
- Correction addendum: `3a4848fb219c874117ec43e80931356c96c5cc8c89d03b796ed79e3dd2531957`
- Preparation receipt: `0c95558f01197d15a8e3766340b7ec67061ab809c4f8e8374bddd7eaa05498ba`

The old and new manifests have the same 1,790 paths. Exactly
`Source/Lib/Codec/pb_trace.c`, `pb_trace.h`, and `pc_impl.h` differ.
The patch contains only the observer API/call change and replacement of the
invalid late EncDec cursor calculation.

## Correctness

The corrected offset is valid for this frozen 64x64-SB configuration.
`coding_loop.c:1885-1900` visits only allowed final D1 blocks. For each such
block, `svt_aom_move_blk_data` initializes
`final_blk_arr[final_blk_itr]`, then the hook receives that same pointer and
ordinal, and only afterward is the ordinal incremented
(`coding_loop.c:2239-2253`). Thus every array element below `ordinal` was
committed earlier in the same SB and encode attempt; no uninitialized suffix or
prior-generation entry participates.

The prefix quantity is the coefficient-layout offset. Each committed block
contributes its full luma area. When the transform loop runs, the native cursor
adds `tx_width * tx_height` for every TU
(`coding_loop.c:2029-2035,2181-2184`); the TU tiling covers the block, so its
sum is `bwidth * bheight`. Blocks for which that later CDF/copy loop is
skipped still occupy the same final coefficient-layout span, which is why the
old conditional cursor was not authoritative. Skipped/no-coefficient blocks
are still committed final blocks and are therefore handled without reading
coefficient contents.

The implementation checks that the destination is exactly the current final
array element, validates each predecessor's `mds_idx`, resolves geometry from
the native table, and bounds every partial and current-block sum to 4096
(`pb_trace.c:255-265`). The maximum final-block allocation for a 64x64 SB is
256 entries (`coding_unit.c:78-84`), matching the ordinal bound. The selected
28 SBs are interior to the visible frame, so incomplete edge-SB partition
exceptions do not affect this trace population.

Recode generations are safe: the final array is rewritten in ordinal order on
every EncDec attempt, and the emitted generation remains
`pcs->ppcs->loop_count`. Actual encoding-path TU offsets remain separate and
must join this derived final-layout prefix in admission; the correction does
not substitute one observation for the other.

The hook writes no encoder state. With the R18 FD absent it returns before any
policy or geometry access. With the FD active it changes only trace
construction. I found no new race: final-array reads occur synchronously in the
same SB coding thread before the current ordinal advances, while serialized
file emission retains the existing trace lock.

## Control interpretation and disposition

The correction addendum accurately adopts the previously reviewed two-build
control. Build 1 remains the policy provenance for baseline/pass1/frozen
`cap-1`; build 2 is observer provenance only. A corrected trace is admissible
only if it consumes the exact frozen pass-1 statistics and reproduces
`cap-1` IVF bytes, all 336 reconstruction frames, and statistics exactly. The
cap's packet rate, quality, and normal two-pass runtime remain build-1 facts;
observer replay time is diagnostic overhead. Any mismatch triggers the
addendum's new-build cap control before trace interpretation.

**Released for the private observer build and neutral replay controls.** This
is a source-method disposition, not trace admission or a policy-result claim.
