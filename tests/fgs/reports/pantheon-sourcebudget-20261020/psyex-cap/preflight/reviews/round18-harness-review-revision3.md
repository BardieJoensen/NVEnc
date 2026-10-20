# R18 harness revision 3 review

## Scope

Focused follow-up to `round18-harness-review.md`; no build or encode was run. Reviewed the exact identities in `parent/psyex-cap-r18/harness-revision3.json` (SHA-256 `bf7fce139b7e6dbd23282805f281f576f2de2e3f0c356ea011a2af0fd2c7dea9`):

- `run.py` `ebfce2b97bd8002db2e866086ed44ac8dece936d64bfeaa01062f29dc5bf6bb3`
- `prepare_build.py` `f0c29f5be5bd910f7bf7ea04b021005fbdeb7dbfeb4730937386f4d6510b58e8`
- `pin_build.py` `dd5093a3cddd6e309e36e51f329dea2937c2591c8524c5659b55896655f84d9a`
- `execute_build.py` `7f366b22bcd3d38bd87e32c7af58753925a4efd99920280fc7b47248531b6a32`
- `README.md` `49aa03f310684ab5ccdec1137f82d8625f257686f6be963cdec861fa873604bd`

## Disposition

**Harness logic accepted, conditional on the corrected native patch receiving a fresh implementation review and on every real invocation being wrapped and retained exactly as the README requires.** The earlier script-level blockers are resolved. This does not release the currently rejected native source for build.

## Resolution of prior findings

1. **Build provenance is now closed.** `pin_build.py:35-50` requires the preparation status, exact reviewed preparer SHA, exact admitted R11 seed SHA, live identities for preparer/seed/manifest/generated runner, the build-local manifest copy, and byte-exact derivation of the generated shell recipe. It then re-walks the complete non-Git source domain and verifies before/after manifests, tool stability, measured runner and artifact hashes (`:51-94`). The final invocation must pass the eventual corrected patch and its new independent review; those dynamic identities are correctly recorded in completed pins rather than prematurely hardcoded here.
2. **Mode and producer lineage are exact.** `run.py:44-84` requires every prerequisite to have been produced by this exact runner, reproduces its argv from the admitted R16 command, checks mode-specific environment, contract/original/settings/input/validity/source rate, output identities and recursive cap parent/control lineage. Main setup independently validates the admitted R16 lineage and live completed-build identities (`:121-160`). Baseline, fresh pass one, cap and trace consume the intended stats in the intended order (`:161-218`), and the cap/trace environment changes only at `:181-182,224-233`.
3. **Early failure persistence has an explicit outer boundary.** `execute_build.py` creates a launch receipt before invoking the shell recipe and records inputs before/after, time, return code and failure. The README requires the already pinned R15 `execute.py` SHA `93c074...` for preparation, build bridge, pinning, previews and every run. That outer receipt is scientifically part of each actual invocation and must be retained and bound by later aggregate admission; the inner scripts do not claim to prove their own parent invocation.
4. **Resource accounting now matches the declared policy.** `run.py:125` requires 160 GiB before a run; `:271-273` records the post-run state and requires at least 120 GiB on success, while `:278-282` records it on failure. The generated build shell uses the declared 160 GB pre-build gate. Revision 3's diff from preserved `run-v3.py` is limited to these post-run records and success floor.

## Rechecked controls

- The runner derives both passes from the admitted R16 argv, fixes TBR 10042 and TF-off settings through exact receipt/settings equality, and excludes public QP bounds (`run.py:163-178`).
- Pass one has cap and all trace FDs absent. Baseline uses the admitted R16 stats. Cap uses the newly reproduced exact stats. Trace uses the cap stats and must reproduce cap IVF, all-336 reconstruction and stats exactly (`:44-84,203-268`).
- The private loader resolution, app/library/source/build pins, input/validity and original artifacts are live-hashed before execution and again after (`:137-152,209-223,269-270`).
- Trace FDs are separate fresh append-only files with explicit inheritance and cleanup. The R18 artifact is correctly named `.bin` (`:224-232,243-249`). Native framing/completeness remains the later validator's responsibility.
- IVF packet parsing enforces 1920x1080, 24/1, 336 packets, sequential PTS and exact EOF; reported rates remain explicitly IVF payload scope (`:87-106`). Remux/scored packet accounting is still required downstream.

## Execution-time conditions

Before any build, replace the rejected native source with the corrected frozen manifest/patch, generate a fresh preparation directory, and use the corrected implementation review SHA in `pin_build.py`. Preserve the outer execution receipts for preparation, `execute_build.py`, pinning, previews and each encoder mode. Completed-build and downstream admission should bind those receipts alongside the inner artifacts; successful inner receipts alone do not demonstrate compliance with the outer-wrapper workflow.
