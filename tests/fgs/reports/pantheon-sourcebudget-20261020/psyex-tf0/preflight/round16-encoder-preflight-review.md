# R16 encoder-runner draft preflight

Reviewed `worker/psyex-r16-tf0-budget/encode_r16.py` SHA256 `e82359d8db69b7c888e892aba1151acf90e436f948daa10a8619ed3b49e3a676`, preview receipt SHA256 `9c46b208b05387055492defb1d8d99f41aaa1e3afa77f2ba23d957b7e541551e`, README `def67b…`, and source audit `c4352f…`.

## Literal policy result

An independent AST extraction of `POLICY` and exact comparison to admitted R8 receipt `ceea9943…` finds one and only one setting difference: `--enable-tf: 1→0`. No option is added or removed; in particular no R15 `--min-qp`, `--max-qp`, or static `--qp` survives. Both preview pass commands use the exact R8 app/input, 336 frames, CPU0–7/nice10, fresh common stats, pass-specific outputs, and request 10313. The preview makes no outcome claim.

## Disposition

The preview is a correct command specification, but this revision is deliberately not executable and must not be released as the measured runner. Line 47 always raises on a non-preview invocation. Parent integration must add the following concrete admission/provenance controls rather than merely remove that guard:

1. Hard-pin and validate the admitted R8 command receipt, its completed status, input, app, library, and source/build records. Lines 31–36 only record whatever app/library currently occupy the paths; they do not establish equality to R8. Programmatically require the final policy/argv normalization to differ from R8 only by TF, request, and fresh stats/output paths.
2. Hard-pin the reviewed contract and final runner hash/snapshot; reject optimized Python. Record and compare input/app/library/source/tool identities before and after both passes, validate the private loader resolution, and preserve a failure receipt for preflight, pass, remux, or validation failure.
3. Execute two genuinely fresh passes for every request, snapshot the resulting stats, and require pass2 to consume that same request's stats. Retain per-pass UTC/monotonic timing, return codes, logs, effective settings, output/reconstruction hashes, complete IVF/MKV packet/cadence/color accounting, and the measured 96:336 rate.
4. Encode the contract statuses explicitly: decisive only for `0.99*source <= actual <= source`; lower positive under-cap output is observational; above-cap is ineligible. Record source/R8 ratios. Permit only the initial request or the deterministic parent-authorized proportional calibration lineage and stop after three requests.

These are expected execution-runner responsibilities, but they are scientifically necessary because the current preview's identities and `diff_vs_r8` are descriptive rather than asserted. No encode should start from this draft.

## Executable revision `1e0709…`

Reviewed `encode_r16.py` SHA256 `1e07091d8b18fb5056d3ceec28a54232d1056d23c8bbee4e7491a1cb4b80a3771` and fresh preview receipt `preview-10313-full/command.json` SHA256 `3788df362f81f86d447bce02b4d72b6729f90e58bba7b6162705097e80a4db15`.

The execution body correctly inherits the proven R15 harness, removes both public-QP flags and static-QP assumptions, constructs and executes both pass commands after comparing their normalized argv to admitted R8, uses fresh same-run statistics, validates the loaded R8 library, checks effective log settings, remuxes and records both IVF/MKV packet populations, uses Matroska 96:336 rate consistently, and separates `status=encoded`, source-ceiling eligibility, and 99–100% comparability.

Four release blockers remain:

1. The R8 receipt is not hard-pinned. `R8_COMMAND` is loaded and checked only for completed status; its SHA is recorded after the fact. Require SHA256 `ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138` before using its commands. Include it in before/after identities.
2. The executable accepts any integer request from 1 to 100,000. README prose does not enforce the preregistered calibration. Permit 10,313 directly; for every other request require a hard-bound preceding receipt and assert `round(previous_request * (0.997*9.6765224) / previous_actual_mbps)`, same policy/input/build, sequential attempt number, and total attempts ≤3. Record that lineage in the receipt.
3. Assertion-based admission has no explicit optimized-Python rejection. Add `if not __debug__: raise ...` before the first assertion.
4. Failures before line 138/run-directory creation are not recorded. The task explicitly requires failure receipts; wrap preflight/launch with a persistent owned receipt or create the fresh run and failure handler before mutable preflight. Also add the R8 receipt, source before/after manifests, and reviewed build runner to the live before/after identity set because they determine this run's provenance checks.

Until these are corrected, arbitrary calibrated requests and a drifting R8 comparator can be admitted, and preflight failures can disappear. No encode should run from SHA `1e0709…`.

## Corrected revision `f8c326…`: exact-diff review

Reviewed `encode_r16.py` SHA256 `f8c326eb3c4eadbf2d48a9c335bad3cd5ff7437402b2f67d32cab442078c8ba7`, README SHA256 `71ce3d3b1d6390fa0c9206e5ff7a75750594f0c980746e3738448e361305d7f2`, and source audit SHA256 `25cdfd05825087287bf1fc8522510342cc84a8f013a76e4c3b10faaa86bb911d`.

The explicit optimized-Python rejection, hard R8 receipt SHA, initial-request rule, immediate-parent proportional formula, at-most-three-attempt check, and final encoded/rate flags are present. The command construction and normalization still establish exactly the intended R8 policy with only TF `1→0`, TBR, and fresh paths differing. The current `preview-10313-calibrated` receipt is not final-current provenance: its `source_audit` identity is `cf8e9b…`, whereas the current audit is `25cdfd…`; recreate a preview after the final code/audit revision if it is cited.

Two linked release blockers remain:

1. `validate_chain` at lines 143–157 recursively checks only status, settings, command TBR, and eventual initial request. For every noninitial link it must also require the stored previous-receipt identity exactly, attempt=`previous.attempt+1` and ≤3, previous actual rate outside the 99–100% source interval, exact formula request, exact source/input/build/R8 receipt, and the final reviewed runner/snapshot identity. It must reject a nominal attempt-2 receipt whose link to attempt 1 used an arbitrary request or an in-window prior. Require each prior receipt's `identity_before==identity_after` and issued-script identity as well. Return the complete chain paths, not just the parsed top receipt.
2. `identity_paths` at lines 195–200 omits `R8_COMMAND` and every calibration receipt. `previous_paths` at line 170 contains only the immediate parent and is never used. Add the hard-pinned R8 receipt and every recursively discovered receipt to before/after identities. This is necessary because both the comparator command and calibration rates determine the command being executed.

The proposed outer execution boundary is adequate for the remaining early-failure receipt requirement: `parent/psyex-real-r15/execute.py` SHA256 `93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858` verifies the child script SHA, writes `status=running` before launching it, captures exact argv/log/return code, rehashes wrapper/script/python/nice/taskset, and records subprocess or post-run failures. Its own no-existing-receipt/script-hash checks happen before receipt creation, but those prevent child launch; once the encoder runner is invoked, a failure is retained. Final admission must preserve and bind this outer receipt and still require the inner `status=encoded`; outer `complete` alone is not scientific admission. The outer CPU8–11 affinity does not override the encoder commands' explicit CPU0–7 taskset.

**Disposition:** blocked only on the recursive-chain semantics and live identity population above. No encode should run from `f8c326…`.

## Final revision `2c146047…`: released

Reviewed `encode_r16.py` SHA256 `2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b`. The two remaining blockers are resolved: the module-level recursive validator now checks the exact issuing runner/snapshot, rehashes every recorded before/after identity, verifies exact source/validity/provenance, recomputes the scored packet rate, enforces every attempt/formula/window link and cycle rejection, and returns the entire live dependency population. Main adds all returned paths plus the hard R8 receipt to the two-pass identity set.

Together with required outer wrapper `execute.py` SHA `93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858`, this revision is accepted for the initial real encode. No quality or rate outcome is implied.
