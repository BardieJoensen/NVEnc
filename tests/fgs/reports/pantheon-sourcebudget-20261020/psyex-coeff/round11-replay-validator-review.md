# R11 replay v3 and validator draft review

## Replay v3

Reviewed `worker/psyex-r11-replay/replay.py` SHA256 `c4eedb26873066a6c7e6b8c2045687c79aae050a7babafce18267e5271d0cfbc`. It is suitable for the off/on replays once the corrected build pins exist.

It binds the exact admitted R8 command receipt (`ceea9943...`), copies the admitted pass-1 statistics, starts from the actual pass-2 argv, and changes only app, stats, IVF, and reconstruction paths. The original command supplies the `/usr/bin/nice` and `/usr/bin/taskset` resource bounds. It binds the private library through `LD_LIBRARY_PATH` and `ldd`, uses separate fresh append-only boundary and coefficient FDs only for `on`, preserves a measured script snapshot, checks all bound inputs before/after, and requires exact admitted IVF and app-reconstruction hashes. The first-envelope tests are appropriately only smoke checks; full trace admission belongs to the validator.

One nonblocking wording correction remains: the receipt scope says “Boundary observation neutrality only” although this replay carries both boundary and coefficient observations. Call it observer neutrality so later summaries do not accidentally omit the coefficient trace.

## Validator draft

Reviewed `parent/psyex-coeff-r11/validate.py` SHA256 `a3ad22b7e7b167726c3fc084d1fe46383ab5b6ccb5fc8c33f291bc29bebba0ae`. Its new branch-state simulation accurately mirrors the pinned `full_loop.c`: first scalar FP/B; threshold-driven B requantization or fast optimization; `optimize_b` only while RDOQ remains active and EOB is positive; noise-normalization call only for positive EOB/non-IDTX; then an unchanged final snapshot. `IDTX == 9` is correct in pinned `definitions.h:974-983`.

The validator is not yet final-admissible for these concrete reasons:

1. `--replay-sha` is caller-selected and only checked for self-consistency. Hard-pin approved replay SHA `c4eedb26...` (and, once available, the reviewed completed-build-pins SHA). Independently require each run's exact R8 `original_receipt`, source/measured replay identities, copied stats hash/path, private-loader/`ldd` result, exact off/on environment, and argv normalized from the pinned R8 pass2 with only the four authorized substitutions. Compare normalized off/on commands. At present lines 143-156 trust most of the replay receipt rather than independently binding it.

2. For every non-skipped token, require `info.requested_qindex == begin.qindex` and `info.actual_qindex == commit.qindex` for this fixed segment-zero arm, rather than applying that join only to R10 positive-EOB units at line 195. Require positive-EOB units to retain `end.type == begin.type` and `commit.source_block_has_coeff == 1`; require source skip-mode commits to report no block coefficient. For EOB0 non-skip TUs, keep `source_block_has_coeff` explicitly block-level because another TU may carry residual.

3. Parse JSON with duplicate-key rejection. `json.loads` at line 25 silently accepts duplicate metadata keys, weakening the otherwise fail-closed framing parser and its planned corruption tests.

The corrected target SHA is now hard-pinned and checked against the derived 24-shirt population. Visible clipping, complete ROI coverage, R9 coding-input, R10 predictor/preloop, final decoder DQ/EOB/IQM, packed owner, and accepted-generation joins are otherwise appropriately scoped. Final output language correctly limits admission to fixed-predictor stage diagnostics and makes no repair or rate inference.

The first private build failure is not evidence about the encoder. It correctly exposed the invalid `ppcs->pic_bypass_encdec` member; the replacement must use child `pcs->pic_bypass_encdec`, regenerate helper/source/patch/manifest, and receive fresh completed-build pins before either replay is admissible.
