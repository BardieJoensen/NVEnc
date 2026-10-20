# R10 integrated-report correction review

## Disposition

Accepted for the local R10 commit. The prior blocking command-provenance defect is resolved without rewriting the flawed historical receipts or overstating what can be recovered from them.

## Focused checks

- `decoder-map/analysis-command-correction.json` has SHA-256 `865b2574a5963c22e88429b504c584478b1f8559492cccfd0ab8a290169b30c9`. Its main result, analyzer, admission, and inner `command` objects exactly match the corresponding objects in the preserved successful `result-1.json`. It explicitly marks the old wrapper argv, affinity prefix, and elapsed time unverified. This is the correct scope: the successful result and all analyzed inputs remain bound, while the inaccurate outer receipt is evidence only of a flawed wrapper record.
- The rerun supplement script has SHA-256 `d3e90ad7f364d18fb20e0836cc888495d517e4927ef9248659def285e9511a63`; the repository copy is byte-identical to the executed scratch copy. It rejects optimized Python before argument processing and records its own argv/interpreter/script plus admission, validator, helper, stages, and frozen-control identities.
- Supplement result SHA-256 `d8aa311ddb1d40a5d386047049d0a04dfa6b4502cf6cd185d5679db75e33ec80` has exactly the same `full_roi` numeric object as superseded result `97dd4c33...`; only command/interpreter/script provenance changed. Receipt SHA-256 `580ac938633a029cbc99e9a88f8f44041c3ecf24747a9fe3507effd18596fcbc` contains the correct admitted-directory argument, wraps exactly the result's inner argv, and binds unchanged script/admission identities. The correction receipt binds that result hash.
- `decoder-map-result.json` selects the v2 result and correction receipt, while retaining the two flawed supplement artifacts under explicitly superseded names and retaining the inaccurate main wrapper receipt alongside the correction. Its limits now accurately disclaim the main wrapper affinity and elapsed time.
- `DECODER_MAP.md` says both main-wrapper paths were wrong, limits the recovered proof to the result's inner argv/script/data, and states that the supplement was rerun. `decoder-map/README.md` gives correct directory-argument commands for main analysis and supplement and now includes coefficient inspection and rendering. Its optimized-Python statement is narrowed to the four scripts that actually enforce it.

One harmless implementation detail remains: the v2 supplement records both the actual frozen-control identity and `control_sha_expected` but does not assert their equality in code. The completed result's recorded SHA equals that constant, and the supplement does not read that control JSON to calculate its fixed-ROI descriptors, so this is neither a provenance ambiguity nor a reason to rerun it.
