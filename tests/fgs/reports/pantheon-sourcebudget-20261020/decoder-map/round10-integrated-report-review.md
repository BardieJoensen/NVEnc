# R10 integrated report accuracy review

Reviewed read-only on 2026-10-20:

- `DECODER_MAP.md` SHA-256 `2b434ed8a668050552e2dec098703ca62ab5357a3ad036c4f3501d7494f0538e`
- `decoder-map-result.json` SHA-256 `e7aceec72f03da4ea3a368faa93bb947467d0e804d8b47ab9eb6f67927c94bdf`
- full-ROI supplement script/result SHA-256 `65a14cba...` / `97dd4c33...`
- coefficient inspection SHA-256 `4a225a4f74882767e79999e0ae2225ca0d40baf931e390c03cc3955a33b137b0`

## Substantive accuracy

The report's numerical and scientific claims match the admitted evidence. Full-ROI HF, ACF1, source-HF correlation and MSE values match the supplement and prior exact R9 surfaces. Spatial category percentages match the admitted map. Every one of the 24 EOB-positive units intersecting shirt has decoder transform type 0 (DCT_DCT) and normative coded qindex 71. Their copied normative dequant arrays contain 1-11 nonzero entries; 23 have a nonzero beyond raster index zero. The inspection correctly limits the AC interpretation to DCT_DCT and disclaims coded-bit and encoder-prequant meaning. Background qindices 79/83/87 and whole-frame 71-115 are supported.

The prose properly rejects only spatial dominance by predictor-only syntax, distinguishes shirt from background behavior, labels decoder q/dequant/EOB as normative syntax rather than actual forward-quantizer evidence, and makes no motion-playback or repair claim. The visual labels correctly describe divided/rounded luma stills and a sequential local-predictor mosaic. `retained coefficients` at report line 41 would be more exact as `decoded dequantized coefficient entries`, but the adjacent limitations prevent a material overclaim.

## Blocking provenance/reproduction correction

Both preserved analysis receipts record an argv that could not have produced the result: their admitted-input argument ends in `admitted-1/admission.json`, while both scripts treat that argument as a directory and append `/admission.json`. The main result's own internally recorded `command.argv` proves the successful process used `.../admitted-1`; the supplement result could likewise not have completed with the receipt's recorded file path. The main receipt also preserves the known wrong output path. `DECODER_MAP.md:78-79` mentions only an output-path reporting error, and `decoder-map/README.md:32` incorrectly calls the supplement receipt argv exact.

Preserve the bad receipts. Add a bound correction receipt derived from the result's internal argv and other immutable identities, or cheaply rerun only the one-second supplement to a fresh output with a truthful receipt. Point the compact result to truthful provenance and describe both wrapper-recording errors. Do not imply a codec/metric rerun.

The reproduction README should include the full-ROI supplement, coefficient inspection and visual-render commands, or explicitly identify their exact preserved command receipts. The current supplement receipt cannot serve that role. Also narrow README line 34's optimized-Python claim to admission/main analysis, or add an explicit `if not __debug__` guard to the supplement and rerun it; its current asserts fail open under `-O`.

After those provenance/reproduction corrections, I find no substantive report blocker.
