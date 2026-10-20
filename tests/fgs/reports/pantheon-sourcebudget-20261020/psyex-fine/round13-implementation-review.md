# R13 revised implementation review

Reviewed `experiment.py` SHA `8bd546141797d4559a5d919b0a103b84dd1a7bb4184ab7cb10b5a33ad1bdcdd4`. The `run.py` currently on disk hashes to `d97457414941d20f634aeef657725933b74672d43fd687aa11135fa2fc93256a`, not the task-supplied `46e52060...`; this identity must be reconciled and frozen before execution. Contract SHA `4dcd8abfffdc31455f8e020a518b1444bafccfe44b4084b97f78ef4b71dfd302` matches.

## Blocking corrections

1. **Per-ROI coding-input distances are absent.** `experiment.py:99-102` computes global invoked-support distances to both raw and coding input, but each ROI gets only `distance(m, raw, ...)`. The corrected contract requires primary invoked-support distances to raw **and coding input** globally and per ROI. Add, for each ROI and arm, separately named raw and coding-input distance objects using the identical `inv_mask & roi_mask` support. Preserve the current full-ROI original-referenced descriptors as secondary context.

2. **The R11 admission is not pinned to the admitted R12 dependency.** `experiment.py:48-50` validates the live admission's internals but does not require its SHA to equal R12's `r11_admission` identity. The contract explicitly binds R11 admission. After loading the exact R12 result, require `ident(adp) == prior_result['r11_admission']` (or pin the admitted SHA `f9aba0b6...`). This prevents a different internally self-consistent admission from being joined to R12 arrays.

3. **The outer success receipt does not cross-bind inner outputs.** `run.py:31-32` checks only `inner['status']=='complete'`; it does not require the inner receipt's `result` and `q1_arrays` identities to equal the live files, nor require live `result.json.status == 'admitted_diagnostic'`. Add those equality/status checks before setting the outer receipt to complete. Then freeze and report the actual runner hash; the current hash differs from the assigned one.

## Required small structural check

Before using R12 offsets (`experiment.py:76-85`), assert the invoked rows' coefficient and pixel intervals form the exact ordered, non-overlapping, gap-free populations represented by each admitted flat array. The coefficient concatenation check is strong but indirect; there is no corresponding pixel-offset population check. Explicit interval checks make the reused-array/token mapping fail closed without rerunning any native baseline or q32 arm.

## Advisory reporting correction

`q1_vs_raw_forward_coeff` at line 115 subtracts quantized `q` indices from raw transform coefficients. Those arrays have different units, so this should be removed or labeled cross-domain and excluded from scalar-distance interpretation. `q1_dq_vs_raw_forward_coeff` is the meaningful same-domain residual. Add q1-versus-q32 Q/DQ aggregates (and baseline equivalents) over the invoked population; per-TU values alone make the promised coefficient-distance comparison difficult to audit.

## Checks that are sound

- Paths resolve to the shared scratch root correctly.
- The implementation imports the SHA-pinned R12 helper and reuses the admitted result/arrays; it does not rerun baseline or q32 native kernels.
- Only q1 runs through `Native.paired`, which independently checks direct-C/runtime Q, DQ, EOB, scan-derived EOB, zero-Q DQ, and native/direct inverse equality for every invoked TU.
- Replacing table rows `[0,1,6]` is correct; rows `[2,3,4,5]`, raw input, QM/IQM, scan, predictor, transform, and geometry remain fixed.
- Distance arithmetic converts samples to float64 before subtraction; coefficient arithmetic uses int64. The visible edge clipping and `/4` conversion are consistent with R12/R9.
- The 720 non-invoked owners retain predictors, while the primary mask includes only the 2,187 invoked-owner pixels.
- Both scripts preserve before/after input identities and persistent failure receipts.

Disposition: blocked only on the three admission corrections and explicit offset population check above. No intervention was executed during this review.
