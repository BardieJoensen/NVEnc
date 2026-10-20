# R10 corrected observer, replay, and validator review

Reviewed current hashes:

- `pantheon_decoder.h`: `f3e2dfc9f329ab835408f0c257ebb806de3f1018f798efd62fb18481a56c9ffe`
- `apply_instrumentation.py`: `b20f483729f48908cbcd456cacccb9a192463b188c18857e976b2e3247c38e80`
- `replay.py`: `5fbbf22370d806c66660e86c3ce300206f560fb92a5a9cf729b345da969d24f0`
- `validate.py`: `375cd88613d0a944cb9cb1777553e47c5c30879bd9a463d738ee1b5b65fac936`

## Observer disposition

The four blocking implementation findings are resolved correctly. The corrected
observer is accepted for the private build:

- `p10_end` receives and checks the passed input end before copying the consumed
  span;
- show-existing `frame_type`/`showable` are explicit invalid sentinels;
- every non-skip TU obtains normative tx type, including EOB zero;
- EOB-positive TUs retain the complete adjusted dqcoeff population and bound EOB
  with `av1_get_max_eob()`.

The qindex lifetime check, intra dead-field sentinels, compound-MV validity,
explicit IQM state, and enum/nominal geometry bounds are also sound. For an
EOB-positive TU, a null IQM pointer is correctly represented as normative flat
state; for EOB zero/skip, `iqm_state=-1` correctly says no inverse contribution.
The full adjusted coefficient population is sufficient for reduced 64-level
transforms.

No remaining C validity defect blocks the build. Retain the runtime exact
pre-loop/post-loop and output-neutrality checks; compile success is still
evidence to be supplied by the build receipt.

## Replay/admission blockers before capture

The draft replay and validator are not yet sufficient to admit the build whose
observer was reviewed. These fixes do not require rebuilding after a successful
reviewed build:

1. **Bind the reviewed build and source domain.** `replay.py` accepts any build
   directory, while `validate.py` proves only that off/on used the same app/lib.
   Require a completed-build pins/receipt with exact app and library hashes,
   pristine/full source manifest, three-file patch/diff scope, observer header,
   apply script, build runner/config/toolchain, and before/after source checks.
   Pin that receipt and expected app/lib identities in admission. Otherwise an
   unrelated mutually consistent decoder could pass.
2. **Pin reviewed scripts/helpers.** Admission currently rehashes the live replay
   recorded in each command but has no approved replay/validator hash, and it
   imports `aom_tu_binding.py` without an expected hash. Add fixed reviewed hashes
   (updated after corrections) before execution/admission.
3. **Cross-bind the command's trace artifacts.** The runner records
   `trace.jsonl`, `payload.bin`, and `decode.log`, but admission parses the live
   trace/payload without requiring those live identities equal the corresponding
   command fields. Assert exact equality; likewise require the off receipt has no
   trace/payload fields or files. Bind the command receipt itself into the final
   result as already planned.
4. **Validate show-existing sentinels and safe metadata.** For every
   show-existing event require `frame_type == showable == -1`, `show_frame == 1`,
   and compare order hint/other independently available fields to the external
   event record. Keep the external parser authoritative for the slot lifecycle.
5. Use absolute, identity-recorded `/usr/bin/nice`, `/usr/bin/taskset`, and
   `/usr/bin/ldd` (or their reviewed resolved equivalents). Current PATH-resolved
   tools weaken the otherwise exact loader/command claim. A persistent failure
   receipt for preflight/launch exceptions would also prevent an owned partial
   directory from looking merely incomplete.

## Validator logic accepted after those bindings

The structural parser itself is well formed: payload offsets are strictly
contiguous; owner and TU maps reject overlap/holes; skip/EOB-zero predictor
identity is enforced; complete coefficient suffixes are proven zero; all 502
consumed spans are paired to the independent packet/OBU inventory; packet
consumption is exhaustive; target pre-loop luma and post-loop all planes match
R9; and display frame 216 matches the exact admitted 336-frame reconstruction.

One optional strengthening is to bind `scan[eob-1]` and all post-EOB scan
positions using the exact source scan table. It is not needed to answer this
round's predictor-versus-present-residual branch because native reconstruction,
full dqcoeff storage, EOB, and exact pre-loop output are already paired; avoid
claiming an independently reconstructed coefficient scan until that check exists.
