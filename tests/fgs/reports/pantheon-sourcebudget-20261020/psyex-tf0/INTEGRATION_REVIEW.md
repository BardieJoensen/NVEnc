# R16 integration review

Reviewed read-only on 2026-10-20:

- `PSYEX_TF0_BUDGET.md` SHA-256 `e422ed268a0d51a3a8ceaa4767e28a4a8441733470b8b9d587c2152a4f4831b2`
- `HYPOTHESES.md` SHA-256 `b4cbf43f8f25a3f06da71d0fc6d2e44ed2d419e2e1a55f917dc171f71564d049`
- `LEDGER.md` SHA-256 `88f334c09c7d5648f5273b8d22484513ae2e10d87d4986f523fbeab1e1dd9bea`
- `README.md` SHA-256 `398ce8105bcf817b16ce0fed78acdf54707b8f10c7d64ed54a66f7a258cb4dd4`
- outcome manifest SHA-256 `83f7d7bc60e80e8453cdbf7862a2eae85560cd807d67044c156297c58feb3008`

## Disposition

Accept after one narrow scope correction. Rates, timings, packet count, texture failures, R8 comparisons, tails, CAMBI, native-stage values, support populations and review limitations agree with the independently derived evidence. The report clearly separates the matched-rate encode result from the single-frame native localization, retains the unchanged acceptance gates, and makes no playback or repair claim.

The outcome manifest contains exactly 85 frozen files totaling 1,917,439 bytes. Every frozen and source identity matches. The compact support file, both external large artifacts, and every admitted trace/media reference also exist at the recorded size and SHA-256. All local Markdown links in the four reviewed documents resolve.

## Required wording correction

Native observation established source/coding-input equality only for target frame 216/scored 120. The five-frame and 240-frame screens do not independently establish coding-input equality on their other frames. Preserve this boundary consistently:

- `PSYEX_TF0_BUDGET.md:69`: change to “For that target, coding input equals the original on all planes.”
- `HYPOTHESES.md:10,14`: replace “R16 original-input” with “R16's observed target has original coding input” or equivalent target-frame wording.
- `README.md:136` and `LEDGER.md:596`: qualify the original-input proof as applying to the observed target frame.

This does not alter the TF-off policy comparison, numerical result, or next-experiment choice. It prevents the single-frame native admission from being presented as an all-frame coding-input observation.

No other factual or package-integrity issue found.
