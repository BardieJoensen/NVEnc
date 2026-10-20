# R9 independent boundary-observation design

## Disposition

The proposed one-frame observation is justified, with one scope correction: **do not require or claim a final per-block spatial-search marker unless that marker is explicitly captured when the selected candidate is committed and then carried through final partition selection to the emitted leaf**. The current R8 counters inspect mutable `ModeDecisionContext` fields (`hbd_md` and `mds_spatial_sse`) immediately before candidate data are copied into `BlkStruct` (`md_process.h:963,1066`; `mode_decision.c:4075-4088,4345-4357`). I found no evidence that `mds_spatial_sse` itself survives in final block state. Reading the later context, or joining aggregate counts to final blocks, would not prove that route for an emitted leaf.

R9 remains decisive without that marker: it can localize the target-frame loss to the final prediction/transform/quantized reconstruction before filtering versus the in-loop-filter boundary. If an implementation cannot preserve a route marker soundly, omit it and label final route unknown.

## Canonical target and final-attempt identity

The sole target is input `picture_number=216`, corresponding to scored frame 120. Admission must bind the record population to all of the following:

1. the exact visible source frame, including whole-frame and per-plane hashes (the established source whole MD5 is `94fa8bde346a2a52d40b26f8183afea5`);
2. codec/display identity sufficient to survive coding reorder or show-existing behavior: picture number plus available order hint, show/show-existing, frame type, and coding generation;
3. one unambiguous final accepted generation; and
4. the displayed post-loop frame at index 216 from the admitted R8 reconstruction (`recon.yuv` SHA-256 `162c2eb85dc9d036912aa5c3a20e613d4ce0fe2ecbc0505ea96bd6d0288d7099`).

Do not infer this binding from packet position or one-packet/one-frame assumptions. If a recode/retry can occur, retain generation markers and admit only the generation joined to the final output/reconstruction. A target hash recorded before deciding whether that attempt survives is insufficient.

Trace framing needs a version, record lengths/counts, an end marker and fatal short-write/overflow behavior. Row/thread completion order must not define identity: use stable block/TU keys and validate the population order-independently.

## Required final ownership population

Final visible luma leaf blocks must tile 1920x1080 exactly once after edge clipping: no gaps, no overlaps, and exactly 2,073,600 owned pixels. Each leaf needs a stable frame/SB/block identity, clipped and native geometry, final partition/shape, intra/inter and final mode/reference fields available in the surviving state, plus explicit whole-block skip/skip-mode/skip-coeff status.

For each final luma TU that actually produced the selected coefficients/reconstruction, record stable parent ownership, native geometry, transform size/type, EOB, coefficient-producing path/attempt, and the qindex read at that actual quantization call. This may be an MD call if EncDec reuses/bypasses coefficients; a later block-state qindex is not a substitute. Partition the entire final pixel population into three disjoint statuses:

- no transform/quantization exercised because the final block was skipped;
- transform/quantization exercised with final EOB zero;
- transform/quantization exercised with final EOB greater than zero.

Whole-block skips must carry null `actual_qindex`, EOB and transform-execution fields rather than inherited state. Validate TU nesting, clipping and `EOB <= max_eob` from the codec's actual transform layout. In particular, do not use spatial width times height as the EOB bound for reduced 64x64-family coefficient layouts. Report pixels and records by skip/EOB, actual qindex, transform family and coefficient-producing path; unsupported paths fail admission rather than falling into a generic zero class.

## Reconstruction boundaries

`pre_loop` must be the complete final luma reconstruction handed to the first in-loop filter, after every final block is assembled and before any deblock-search or filter operation mutates it. It must not be an MD candidate, scratch inverse transform, partially completed SB surface, or temporary deblock-search buffer. Capture the full visible plane once and prove its owner map covers every pixel.

`post_loop` is the actual decoded/reconstruction surface after deblock, CDEF and restoration. The source shows recon output only after restoration application (`rest_process.c:624-733`). The captured post-loop visible frame must equal the admitted R8 frame byte for byte; the complete trace-enabled output must also remain identical to the R8 IVF SHA-256 `26f51de25b0d1374cfb5bd274d04af13495c94caa4b28b9c4ddd97a5727baeca` and full reconstruction hash above. An observation-off replay should match the same artifacts as a separate neutrality control.

Source, pre-loop and post-loop samples must use explicit bit depth, strides, crop origin and visible geometry. Analysis may use luma, but source/post-loop full-frame identity remains all-plane. The pre-loop surface is a real internal stage, not a legal independently decodable reconstruction or repair candidate.

## Optional final policy-route marker

The only sound per-leaf marker is side state captured at selected-candidate commit and propagated with that candidate/block through partition survival, then joined bijectively to the final leaf. It may mean only “the candidate that became this leaf was committed while this route flag was active.” It cannot mean that a psy term was nonzero, that the route caused the win, or that it won by any margin.

`mds_spatial_sse` must not be read from a later reused context. HBD may be reported as a globally validated arm property if uniform, but should not be presented as per-leaf survival without the same propagation. No all-search margins are needed for R9. If safe propagation needs invasive mutable shared state, exclude these markers and retain the narrower reconstruction/ownership question.

## Fixed analysis and acceptance

Use the existing shirt and background rectangles at frame 120 and all 858 predeclared frame-120 tiles from the frozen 15-frame/12,870-tile control set. Retain their exact coordinates, kinds, outside-mask status and source descriptors. Do not choose tiles or strata based on the new differences.

For each whole contiguous source/pre-loop/post-loop image, report the established ROI amplitude/HF, ACF1 and source-HF correlation, plus pixel error. For frozen controls, report paired source-relative MSE/HF/ACF summaries by every existing group and tails. This introduces no new pass threshold: it is stage localization.

For skip/EOB/qindex/transform strata, report exact pixel and TU populations, pixel-domain error, and same-owner local HF stencils whose required neighbors share one owner/status. Do not compute ordinary ACF on disconnected masked arrays. If contiguous support is insufficient, omit stratum ACF and say so.

Interpretation is bounded:

- A large source-to-pre-loop loss with a small pre-to-post change implicates the final prediction/partition/transform/quantized reconstruction collectively; it does not isolate one mechanism.
- A materially closer pre-loop image followed by post-loop loss implicates the in-loop filter stack collectively. It does not separate deblock, CDEF and restoration, and a later filter setting contrast would also permit reference-feedback and decision changes.
- Correlation with skip, EOB, qindex, transform or an optional route marker is descriptive, not causal.
- One midpoint frame cannot establish full-window or episode behavior.
- No rate, deployable repair, playback or policy-superiority claim follows from byte-neutral observation.

The smallest sound R9 therefore consists of exact source/pre-loop/post-loop surfaces plus exhaustive final leaf/TU ownership and exercised-status data. Per-final-leaf spatial/HBD markers are useful only if the implementation meets the explicit commit-to-final propagation test; otherwise they should be left out rather than inferred.

## Addendum: narrowed first boundary round

The proposed narrower primary question—original source → actual coding input → pre-loop reconstruction → post-loop reconstruction—is scientifically adequate and cheaper. Final leaf/TU, skip/EOB and realized-quantizer attribution may be deferred to a separate discriminator. This narrows mechanism attribution but does not weaken any preservation gate: R9 is observational and the R8 quality result remains the applicable full-window result.

### Minimum admission

For every attempted generation of input picture 216, capture three complete visible 4:2:0 10-bit YUV surfaces:

1. `coding_input`, assembled from the exact packed SB source samples consumed by coding;
2. `pre_loop`, assembled from the final reconstructed SB samples immediately before their first possible in-loop-filter mutation; and
3. `post_loop`, captured after the complete deblock/CDEF/restoration path and equal to displayed frame 216 in the admitted R8 application reconstruction.

The independently bound fixture frame 216 remains the original reference. `coding_input` must **not** be required to equal it: temporal filtering or another admitted preprocessing path may legitimately change the coding samples. Instead report the exact source-to-coding-input difference. Each stage needs explicit plane dimensions, bit depth, crop origins, strides and per-plane plus whole-frame hashes.

For each generation and stage, clipped SB rectangles must tile Y 1920x1080 and U/V 960x540 exactly once, with no missing, duplicated or overlapping visible samples. Records need picture number, generation, SB address/origin/native and clipped sizes, stage and completion status. A framed end record must bind the surface hashes and population counts. Short writes, duplicates, stale generation data or incomplete planes are fatal.

The final-generation marker belongs only after the last-SB accounting and `do_recode` decision. The source makes that decision after `enc_dec_coded_sb_count == sb_total_count` (`enc_dec_process.c:3541-3558`), and a recode resets the count (`:3572-3579`). Retain rejected generations separately; clear or generation-index the mosaics rather than overwriting them. Admit exactly one complete generation marked accepted and bind its post-loop surface to the admitted R8 recon. Observation-off and observation-on must both reproduce the complete 336-frame R8 IVF and application reconstruction byte for byte.

### SB deblock safety

The pre-loop copy must occur **inside the SB coding path immediately before the first possible `svt_aom_loop_filter_sb` call**, not after `svt_aom_encode_decode` returns. In this source, SB-based DLF is invoked at `coding_loop.c:2278-2298`; by return, that SB or an adjacent completed SB may already have been modified. The filter can process current vertical edges and delayed horizontal edges in the previous column (`deblocking_filter.c:581-605`), so a later read from the shared recon surface cannot reconstruct the unfiltered mosaic.

Copying each SB's visible Y/U/V rectangle into a separate, write-once mosaic immediately before that call is sound provided admission establishes all of these:

- the snapshot hook executes even when SB-based DLF is disabled and when the final reconstruction uses a bypass/reuse path;
- exactly one writer owns each generation/SB destination rectangle;
- no DLF call may target pixels whose owning SB has not already been snapshotted; enforce this with runtime captured-owner state for the current/previous filter footprint, rather than relying on trace order;
- the live reconstruction and private mosaic do not share backing storage; and
- completion is published only after every SB copy is finished, with synchronization sufficient for worker threads.

The third condition is the specific safety control needed for cross-SB filtering. Current source scheduling is designed so the filter operates on the current or an already completed region, but the observation should fail closed if the actual segmented execution violates that premise. If that invariant cannot be asserted at the hook, this per-SB mosaic is not an admitted pre-loop frame; the fallback is a shadow reconstruction written before filtering, not a whole-frame snapshot after EncDec.

When SB-based DLF is not active (or tile-group conditions move filtering to the frame DLF kernel), the same per-SB copy remains valid because frame DLF occurs later (`dlf_process.c:105-122`). Record the actual branch and filter levels so the boundary is auditable, without interpreting them as interventions.

### Analysis and interpretation

Use the fixed frame-120 shirt/background rectangles and all 858 predeclared frame-120 control tiles. Compute the same descriptors and source-relative pixel errors on four contiguous surfaces: original, coding input, pre-loop and post-loop. Adjacent-stage pixel differences may be reported, but HF/ACF changes are nonlinear and must not be presented as additive percentage contributions.

- Original → coding-input differences localize an upstream sample change, not necessarily damage: later coding can compensate, and the observation does not isolate which preprocessing operation caused it.
- Coding-input → pre-loop differences summarize the complete prediction/partition/transform/quantization/reconstruction decision stack. Without final block/TU evidence, do not attribute them to skip, EOB, qindex or PSYEX search-route survival.
- Pre-loop → post-loop differences localize the net in-loop-filter stack. They do not separate deblock, CDEF and restoration.

This first round should make no final-HBD/spatial, TU-execution, skip-path or quantizer claims. If the pre-loop/post-loop boundary is decisive, the next causal test can target the implicated stage; if coding-input/pre-loop dominates, final realized-decision observation becomes the justified follow-up.

## Addendum: fixed-arm frame-barrier simplification

The effective fixed P4 configuration makes a cleaner implementation available and supersedes the per-SB deblock-footprint requirement above **for this arm only**. `get_dlf_level` selects level 2 for non-RTC P4 with `fast_decode=0` (`enc_mode_config.c:1342-1349`), and level 2 sets `sb_based_dlf=0` (`:1438-1446`). If the trace verifies that effective field before the first target SB and fails immediately when it is nonzero, no SB filter runs in `coding_loop.c:2281-2298`. Frame DLF begins only after an EncDec result reaches the DLF kernel (`dlf_process.c:105-122`). This makes a single full-frame reconstruction snapshot at the completed-SB barrier safer than a stitched SB reconstruction mosaic.

The concrete design is accepted with these conditions:

- Check `dlf_ctrls.enabled`, `dlf_ctrls.sb_based_dlf`, tile-group count and effective filter levels for every target attempt. The scientific requirement is `sb_based_dlf == 0`; DLF itself may remain enabled. This is an assertion of the existing configuration, not a setting change.
- Take the full visible Y/U/V pre-loop snapshot after `enc_dec_coded_sb_count == sb_total_count` and after `do_recode` is computed, but before entering either the recode or accepted branch. Every worker adds its completed SB count under `intra_mutex` only after its SB reconstruction loop (`enc_dec_process.c:3528-3548`), so the last-SB path is the frame-completion barrier. The trace must preserve this synchronization and must not post EncDec results before the copy completes.
- Dump one independently framed coding-input and pre-loop population for every attempt, then record `do_recode`. Increment/reset the generation only inside the recode branch. Require every rejected generation to be complete and exactly one complete `do_recode=false` generation to be accepted.
- Assemble coding input from the visible portion of the 16-bit packed SB buffer immediately after `prepare_input_picture` (`coding_loop.c:1555-1675,1704-1717`). This is the actual EncDec input in the supported path. Require exact per-generation SB coverage of Y/U/V; if `bypass_encdec` or another path omits this hook, coverage must fail rather than silently substitute `enhanced_pic`.
- Capture post-loop Y/U/V from the reconstruction obtained by `svt_aom_get_recon_pic` in `svt_aom_recon_output` and bind it byte-for-byte to application frame 216. With film grain, resize and superres all asserted disabled, this is the same visible surface copied to the application (`enc_dec_process.c:476-635`) after restoration has completed.

This removes the earlier cross-SB write risk: there is no SB DLF before the barrier, so no filter-footprint bitmap or per-SB pre-loop copy is needed. The runtime `sb_based_dlf==0` gate is essential; if it fails, the frame-barrier snapshot is no longer an admitted pre-loop surface and the implementation must fall back to the guarded mosaic design rather than disabling DLF.

The narrower interpretation is unchanged. Original-to-packed-input measures an upstream sample difference and may legitimately be nonzero. Packed-input-to-pre-loop covers the complete coding decision/reconstruction stack without attributing skip, EOB, qindex or route. Pre-loop-to-post-loop covers the net in-loop filter stack. None of the three differences alone proves causality, and the full R8 preservation gate is neither replaced nor relaxed.
