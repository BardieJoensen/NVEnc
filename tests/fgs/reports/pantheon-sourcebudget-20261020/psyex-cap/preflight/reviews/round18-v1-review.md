# R18 rejected-v1 patch review

## Material reviewed

- Frozen patch: `worker/psyex-r18-cap/r18-cap.patch.rejected-v1`, SHA-256 `dc8ea030f04def6d989c5e29d7b00fe280349f8ccdcb2d2d6f9f618f8a22f85b64`.
- The live `r18-cap.patch` had already advanced to SHA-256 `49e429a0275f3b198917a435815d500cc42d1966126e420e0206d8ceef837b02`; I did **not** treat it as v1 evidence.
- Immutable R11 source, chiefly:
  - `rc_process.c` `5187c76a6f9d132ab05c445f71b26258d83499b9c17118f76b3c294dc65531e5`
  - `enc_dec_process.c` `e5731e1792b7724842f50fef9c1d79cab20ce413544879ba3c10c51cc684bb8a`
  - `pb_trace.c` `8c1b2840fbff9bf934aa1d1ec6f2098ef2c800b28d53455f9ec105735bca4af0`
  - `entropy_coding.c` `497acf4a6e62fad039d657da0811d867f7d8f6c173402775d2ab3f6cfa34dc28`
  - `full_loop.c` `e6942d07bf09fce5bc43d31347096b60115d2a8b568b652c2cd707fde202e588`

Review was source-only; I did not build or run the patch.

## Disposition

**Reject v1.** In addition to the parent's already identified blockers (assert-only admission, silent pass-one disable, missing complete committed-SB/final-q evidence, and no old-resolution/lambda-write proof), the observer is structurally attached to the wrong lifecycle and the geometry/effective-q checks are not fail-closed.

## Additional concrete blockers

### 1. The all-picture cap records reuse target-216 boundary state

The original boundary observer has process-global `generation`, `accepted`, `attempts`, `seen`, and `owner` state for picture 216 (`pb_trace.c:20-29`). Its header writes that global `generation` (`:52-54`), and only `pb_attempt` advances it for target 216 (`:118-130`). Its terminal check validates only the target's accepted generation/post record (`:140-149`).

V1's `header_for_picture()` keeps that same global generation while permitting a different picture number, then `pb_cap_application()` emits type 5 for every capped picture. Thus pictures before target 216 receive target generation 0; pictures after it inherit whatever generation target 216 happened to finish with. No terminal state counts one initial application plus every recode application for each of 336 pictures. The mutex makes writes atomic but does not make the metadata meaningful.

Smallest correction: give cap observation its own per-picture attempt state (keyed by picture/decode identity), record each initial/recode application, and terminally validate all expected pictures and attempts. It must not use the boundary target's `generation`, `owner`, or target-only `pb_finish` completeness assertion.

The same record omits required decode identity and frame base. Its JSON contains picture, attempt, recode, resolution and entries, whereas the contract requires source picture/decode identity, frame base, and old/new resolution. A dynamic parser cannot independently join recoded applications from this schema.

### 2. Observer enablement can silently produce no evidence

`pb_cap_application()` begins with `active()`, whose initializer only reads `SVT_PANTHEON_BOUNDARY_FD` (`pb_trace.c:32-42`). Therefore `SVT_PANTHEON_R18_OBS=1` without the legacy boundary FD simply returns. Invalid values of either `SVT_PANTHEON_R18_CAP` or `SVT_PANTHEON_R18_OBS` also silently behave as off. This can turn a requested policy/observation arm into an unobserved control without an error.

Smallest correction: parse each toggle once, accept only an explicitly enumerated off/on value, require a valid fresh append FD whenever observation is on, and fail if observation is requested while the policy is off (or vice versa where the run contract requires both). Pass-one policy reach must likewise be fatal, as already identified by the parent.

### 3. `count == 28` does not validate the frozen geometry

The helper checks only `sb_size == 64`, `sb_total_count <= 510`, and an intersection count of 28, all with `assert`. It does not establish 1920x1080 visible geometry, a 30x17 SB grid, `sb_total_count == 510`, coordinate alignment/bounds, unique SB IDs, or the exact selected set. Another geometry can happen to produce 28 intersections.

For this fixture the expected IDs are:

- background: rows 0-3, columns 14-18 (`14-18`, `44-48`, `74-78`, `104-108`);
- shirt: rows 10-11, columns 18-21 (`318-321`, `348-351`).

Smallest correction: runtime-fatal checks for the exact source/aligned geometry, 64-pixel SB size, 510 unique grid entries, and exact 28-ID/coordinate set on every application. Do not rely on count or release-disabled assertions.

### 4. Stored `sb_ptr->qindex` is not sufficient evidence of delivered q

The before/after loop proves only that this helper did not directly alter unselected `SuperBlock.qindex` fields. It does not prove the syntax/effective quantizer:

- V1 changes the frame-global `delta_q_present` and `delta_q_res` after normalization, so this is a whole-frame syntax change even if unselected stored values remain byte-equal.
- Delta-q is written only at an SB upper-left block when `(bsize != sb_size || skip_coeff == 0)` (`entropy_coding.c:4846-4856`, with the parallel path at `:4988-4997`). A whole-64 skipped SB can retain the previous syntax q rather than signal its stored value.
- Final quantization uses the block q only when delta-q is present and then adds segmentation ALT-Q (`full_loop.c:1615-1620`). The early frame-level `segmentation_enabled == 0` assertion is not a committed selected-block check and disappears under `NDEBUG`.

This does not make resolution 1 illegal: the frame header writes `OD_ILOG_NZ(delta_q_res)-1` (`entropy_coding.c:3498-3503`), so value 1 is correctly encoded as resolution code 0. It does mean admission must distinguish selected stored q, committed geometry/skip, actual quantizer calls, and decoded/syntax q. For selected executed luma calls, require exact `min(pre,4)` and zero committed ALT-Q; for skipped/no-residual SBs, report absence of quantizer execution rather than claiming q4 delivery. The old/new resolution and representative unselected syntax q also need observation.

### 5. The lambda flag is a claim, not a measured refresh

`sb_setup_lambda()` recomputes `tpl_sb_rdmult_scaling_factors` from original TPL factors and the current SB q (`rc_process.c:1148-1202`). V1 sets `lambda_refreshed=1` merely because it called the function. It neither snapshots the factor indices/values nor proves that only factors belonging to the 28 selected SBs were written. It also changes the picture-wide `blk_lambda_tuning` flag to true at `:1202` without recording its prior state.

The correction needs exact factor-index/value before/after records, nonselected direct-write exclusion, and a check that the expected lambda-tuning route was already active for this fixed policy. This is in addition to the parent's noted need to prove the old resolution and actual lambda writes.

## Source-path assessment

The placement itself is directionally correct: the initial helper follows variance/TPL normalization, and the recode helper is inside the `do_recode` branch after q reset, variance/TPL rederivation and normalization (`enc_dec_process.c:2724-2760`). MD later receives `sb_ptr->qindex` at `enc_dec_process.c:3390-3395`. I found no additional compile blocker in the frozen diff: the symbols and standard declarations it uses are available.

That does not clear the intervention. A corrected version still needs runtime proof that preset4/10-bit uses normal EncDec rather than bypass, plus final committed/actual-quantizer joins required by the contract. Source says the configured route should have bypass disabled for 10-bit modes through M7 (`enc_mode_config.c:7756-7771`), but source reachability is not runtime delivery evidence.

## Commands

Read-only evidence commands included `sha256sum` over the frozen patch and cited source files, `sed -n` over the rejected patch, and numbered source excerpts with `nl -ba`; no source tree, build, encoder, metric, GPU, or Git state was changed.
