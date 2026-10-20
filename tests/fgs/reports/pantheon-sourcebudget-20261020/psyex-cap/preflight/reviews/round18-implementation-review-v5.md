# R18 focused native revision review (v5)

## Scope and disposition

Reviewed only the four blockers from `round18-implementation-review.md` and the added TPL-grid metadata in:

- patch SHA-256 `ad24de1b0ef55901332bc6c76de6607ad1f816531e4a467990a57b157c4f81f7`
- manifest SHA-256 `f7d8521f422e6ea492964b8ab17379db472b0ba99417af85c3937d5f5e5ed7e9`
- README SHA-256 `9f5e404b00b1ae4dec4562325201ebe4fb497c687ab6a90da72271ec3e675192`
- plan SHA-256 `dbdd7c080bf8891ca7143dc521ee0beb3706b9d23b72620c9ff535779e1a0116`

**Not released for build.** Three of four source blockers are corrected, but the skip-mode double begin remains unchanged. The manifest also contains the right 1,790 files and hashes in an order incompatible with the accepted preparer/build walk.

## Remaining source blocker: skip mode still begins twice

The revision did not change this path:

- `pc_skip()` calls `pb_r18_skip()` first (`pc_impl.h:121-123`).
- With R18 active on a selected SB, `pb_r18_skip()` calls `pb_r18_begin()` and leaves `r18_tu.active=1` (`pb_trace.c:316-336`).
- For target picture 216 with the R11 coefficient observer active, `pc_skip()` then calls `pc_begin()` (`pc_impl.h:124-129`). `pc_begin()` calls `pb_r18_begin()` again (`:91-95`), which immediately fails on the already-active TU (`pb_trace.c:316-318`).

Smallest correction: in `pc_skip()`, send non-target or coefficient-observer-inactive calls through `pb_r18_skip()` and return. For target216 with the coefficient observer active, perform the existing R11 setup and call `pc_begin()` only; its common `pb_r18_begin()` already classifies the unit skipped from `blk_ptr->skip_mode`. This preserves one R18 lifecycle and the R11 source/predictor capture.

## Corrected source blockers

1. **Accepted generation:** `r18_emit()` now accepts an explicit generation (`pb_trace.c:77-80`), and `pb_r18_accept()` supplies the saved pre-decision generation (`:359-366`). The frame envelope and JSON can no longer diverge when the encoder resets `loop_count` after an accepted recode.
2. **Cap-off neutrality:** the R18 commit offset calculation and its assertions are now wholly gated by `pb_r18_is_active()` (`pc_impl.h:208-218`; declaration in `pb_trace.h`). With no R18 FD, it initializes only the observer's once-state and does not execute those new coding-state assumptions. The preexisting R11 target commit checks remain unchanged.
3. **Decode identity:** both every-application and accepted records now include `decode_order` and `order_hint` alongside source picture and generation (`pb_trace.c:194-220,359-366`). This supplies the all-picture identity required by the contract; later admission must keep it constant across generations and join target216 to the independently parsed coded event.

## TPL-grid metadata

The type-8 lambda record now exports `synth_blk_size`, factor columns and factor rows (`pb_trace.c:222-233`). For this fixed fixture, synth16 yields 120x68 and synth32 yields 60x34. These match the actual factor addressing in `sb_setup_lambda()` and the policy helper: 1920 columns and the 1088-aligned/`mi_rows*4` row domain (`rc_process.c:1150-1203,1806-1810`). `ceil(1080/synth)` happens to equal the aligned-domain row count for both supported synth sizes. Admission should still calculate expected indices from these recorded dimensions rather than infer a visible-only array.

## Manifest-only blocker

The manifest contains the exact current 1,790 non-Git file paths, sizes and hashes, with no missing, extra or content-mismatched row. Its row order differs from the accepted harness algorithm, however. The manifest uses lexical relative-string order while `prepare_build.py` and the generated build recipe use `sorted(source.rglob('*'))` Path ordering. The first divergence is row 6:

- manifest: `.gitlab-ci.yml`
- harness walk: `.gitlab/merge_request_templates/default.md`

Therefore `prepare_build.py`'s exact `found == rows` check would reject this manifest. Regenerate it using the exact harness walk/order; this requires no source or patch change.

No build or encode was run.
