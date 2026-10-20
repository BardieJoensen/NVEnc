# R18 native implementation review

## Disposition

**Rejected before build.** The frozen policy implementation has a sound cap/lambda placement and a useful quantizer-call lifecycle, but four concrete observer defects must be corrected first. Two can abort the exact target run, one corrupts generation authority after a recode, and one omits an explicit contract binding.

Reviewed artifacts:

- contract `ROUND18_ABSOLUTE_CAP_CONTRACT.md`: SHA-256 `97d68ee39c6ad1922c1025143583fffc02d480b3370f4aaa1c58817029f7b4bf`
- frozen patch `worker/psyex-r18-cap/r18-cap.patch`: SHA-256 `120773258760fc0f1506c8dce4ff6bce77c5501aef2dd855a671c770932c5fab`
- corrected non-Git source manifest: SHA-256 `87b9e46b05cd18684d9b16e4c893ff4ed191b9aedf84648a8843fb5e9036cc02`, 1,790 rows
- the earlier `3805a407...` manifest is superseded: it included 28 nested `third_party/cpuinfo/.git/*` entries outside the established source domain. The 1,790 non-Git rows matched the reconstructed R11 domain, with exactly the declared six changed source files.

No build or encode was run.

## Blocking defects

### 1. The accepted record's framed generation can disagree with its JSON generation after recode

`enc_dec_process.c:3561-3569` saves `r18_generation` before `recode_loop_decision_maker()` and correctly passes that saved value to `pb_r18_accept()`. On a non-recode decision, however, `recode_loop_decision_maker()` resets `ppcs->loop_count` to zero at `enc_dec_process.c:2763-2765`. `pb_r18_accept()` puts the saved generation in JSON (`pb_trace.c:353-358`) but emits through `r18_emit()` (`:359`), whose envelope takes the now-current `loop_count` (`:76-79`). A frame accepted after generation N>0 therefore has envelope generation 0 and JSON generation N.

Smallest fix: have `pb_r18_accept()` lock `r18_lock` and call `r18_header(type=6, ..., generation, ...)` directly with the supplied generation. Admission must require envelope generation, JSON generation, and all final records to agree.

### 2. A target skip-mode TU enters the R18 lifecycle twice and aborts

For skip mode, `av1_encode_generate_recon()` calls `pc_skip()` (`coding_loop.c:603-624`). `pc_skip()` first calls `pb_r18_skip()` (`pc_impl.h:121-123`), which creates an active R18 TU through `pb_r18_begin()` (`pb_trace.c:326-330`). It then calls `pc_begin()` (`pc_impl.h:128-129`), which unconditionally calls `pb_r18_begin()` again (`:91-95`). The second begin hits `if (r18_tu.active) REQUIRE(0)` at `pb_trace.c:310-312`.

Smallest fix: establish the common begin once, then mark it skipped. For example, call `pc_begin()` first and `pb_r18_skip()` afterward, or remove the redundant begin path while retaining the R11 predictor/source capture. Preserve the invariant that every skip-mode unit emits one R18 TU with `invoked=false`, no qinfo, and EOB zero.

### 3. R18-only commit calculations/assertions run even when R18 is inactive

`pc_commit()` performs the new R18 offset reconstruction and `REQUIRE` checks before calling `pb_r18_final_commit()` (`pc_impl.h:208-218`). Only the callee checks `r18_active()` (`pb_trace.c:229-232`). Thus the disabled-cap/disabled-R18 neutrality binary still executes new assumptions and can abort before reaching the no-op callee.

Smallest fix: put the entire R18 prelude, including pointer/tx-depth/offset assertions, behind `r18_active()` (and let the callee retain its policy check). Keep the existing R11 commit path outside that guard. The off control must exercise no R18 assertions or state.

### 4. The all-frame application/accept records omit the required decode identity

The contract requires source picture and decode identity for every initial/recode application (`contract:60-63`). Type-1 application and type-6 accepted records contain source picture/generation but no `ppcs->decode_order` or equivalent coded identity (`pb_trace.c:193-218,353-359`). The older boundary record has decode order only for picture 216, so it cannot supply this all-frame binding.

Smallest fix: record `decode_order` in each application and accepted record (order hint may be added as a cross-check). Admission should require it to stay constant across all generations of a source picture and join the representative picture to the independent header lifecycle rather than infer coded order from source ordinal.

## Verified implementation properties

Subject to those fixes, the core intervention is appropriately bounded:

- `r18_apply_selected_sb_cap()` runs after the initial normalization path and inside the recode branch after q reset, variance/TPL derivation, and normalization (`rc_process.c:1742-1848`, hook sites `:3862` and `enc_dec_process.c:2738-2762`). It selects exactly the 28 native 64x64 SBs by fixed rectangle intersection, applies `min(pre,4)`, forbids q0, and sets legal resolution 1.
- The helper snapshots all 510 SB qindices and checks every unselected value bit-for-bit unchanged (`rc_process.c:1767-1794`). It also holds frame base q, child/parent/public QP, and lambda activation fixed (`:1842-1846`).
- When the preexisting TPL lambda path is active, the source derives the same 16/32-pixel factor geometry used by `sb_setup_lambda()` (`rc_process.c:1150-1204,1797-1840`), snapshots both arrays, proves the original factors unchanged, and proves no unselected factor is directly written. The fixed 1920x1080/64-SB geometry bounds the factor index domain.
- MD inherits each selected SB q after `svt_aom_mode_decision_configure_sb()` (`enc_dec_process.c:3393-3400`). The final quantizer hook is immediately before the native FP/B dispatch (`full_loop.c:1690-1755`); it records the requested index, effective segmented index, and an actual invocation token. R18 requires segment delta zero and effective q equal the selected stored SB q (`pb_trace.c:332-339`). This supports “effective q passed to final quantization,” not an assertion about a skipped transform.
- Non-skip, EOB-zero units remain quantizer invocations. MD-skip and skip-mode units require no qinfo and remain separately labeled (`pb_trace.c:310-351`). After the skip double-begin correction, this distinction is suitable for the contract.
- Final block records are emitted directly after `svt_aom_move_blk_data()` and before the destination `av1xd` handoff (`coding_loop.c:2239-2253`). They bind selected-SB q, chosen-source skip/coefficient state, copied destination EOB/tx types, geometry, and coefficient offset. The full 64x64 spatial allocation used for offsets matches EncDec's `coded_area_sb` accounting; reduced transform coefficient support must still be interpreted from TX/EOB rather than the allocation size.
- R18 output uses a separate append-only FD, a mutex-protected sequence, little-endian framed records, bounded JSON and a 512 MiB byte cap (`pb_trace.c:29-79`). TU state is thread-local. The cap state changes occur before parallel MD or after the all-SB recode barrier; the trace functions otherwise mutate only observer state.

## Required admission checks after correction

These do not require additional C changes if the validator enforces them fail-closed:

1. Parse to exact EOF with continuous sequence numbers. Require source pictures 0..335, exactly one accepted generation per picture, and complete application history for generation 0 plus every recode generation.
2. For every application require exactly 28 unique expected SB geometries; for its accepted generation require 28 unique route, MD-q and final-SB records, and gap-free committed block/TU geometry within each selected SB. Reconcile TU records to committed EOB/type/offset rather than counting records alone.
3. Require every invoked TU to have exactly one qinfo, `segment=0`, and `actual_qindex == stored post-cap SB q <= 4`; require every non-invoked unit to be explicitly skipped and never describe its stored q as an executed quantizer.
4. Require application/route/commit/accept records to agree on source picture, corrected generation and decode order. Independently bind the representative coded event/OBU and native decoder q/DQ/EOB as specified by the contract.
5. Require cap-on with and without the R18 FD to be byte/reconstruction identical, and cap-off private binary to reproduce the admitted R16 stream. The R18 stream lacks its own terminal record/close, so successful process completion, exact EOF, expected all-frame counts and stable artifact identity are necessary; adding an R18 completion record and explicit `fsync`/close would make this authority local but is not necessary if those external checks are exact.

## Nonblocking hardening

- `r18_cap_enabled()` treats any nonempty value other than literal `1` as disabled (`rc_process.c:1732-1739`). The frozen harness pins the exact value, and an active R18 FD later rejects a false policy, so this does not invalidate the specified run. Failing immediately on malformed nonempty values would prevent a typo from silently producing a baseline stream in an unobserved invocation.
- The R18 FD's numeric distinctness check can occur before the boundary FD is initialized (`pb_trace.c:37-46`). Fresh-file checks will later fail if two configured descriptors share an inode, but direct `fstat` inode comparison after both observer initializations would state the separation invariant more clearly.
