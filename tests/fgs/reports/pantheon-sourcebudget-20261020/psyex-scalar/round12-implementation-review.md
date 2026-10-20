# R12 native/helper and experiment-driver review

## Disposition

The native implementation and scientific data flow are sound. I found no C ABI,
RTCD, transform-layout, object-provenance, or counterfactual-validity blocker.
One small driver correction is required before execution to keep the baseline
control internally immutable; it does not require rebuilding `native.so`.

Reviewed identities:

- `native.c`: `8f1cf5b69700e1a1b2d26d8bf29a0cb87cfe2f2e0b2351881be20106731934fc`
- `experiment.py`: `9fb770c0c7ee8bf4d444f54edc80e91c495ac5b5b0f8aedacb7339fc9b21680f`
- `build-2/native.so`: `07fe2554623523d8e6dfe5218d94a89cdb2437bb2221123a86678090af6f2228`
- `build-2/receipt.json`: `4b56e9cbd1450f68ec42d02a70d6db2e082db065c6314f34ef17443ef6cb7df5`
- revised contract: `3898232cd10ba310c3c94ba04d219f8187ffe179f68e7a614b1ce695a3704d3d`
- policy audit: `4b21a39dabd58edd6c71b0a9fa6b22699b1d18a7d99dd7cb90b7ce0059eb943a`

## Native wrapper

`rp_init` follows the encoder's relevant initialization order: it obtains the
host-supported flags and initializes both common and AOM RTCD tables before any
facade use (`native.c:14-20`). The admitted R8 command has no CPU-level override,
so this is the same selection policy. The returned mask is retained in both the
receipt and result.

The four quantizer modes correctly pair direct C FP/B with the high-bit-depth
runtime facades. The table layout matches the R11 capture: FP consumes
`round_fp/quant_fp/dequant`, while B consumes `zbin/round/quant/quant_shift/dequant`.
Scan/iscan is a checked permutation; matrix pointers are both present or both
absent; inputs are copied into aligned private storage and checked unchanged.
The C symbol used for B with matrices is correct: RTCD maps
`svt_av1_highbd_quantize_b_qm` to `svt_aom_highbd_quantize_b_c` for the C path.

The inverse wrapper uses the admitted native coefficient population
`av1_get_max_eob(tx)`, zero-pads its private 4,096-coefficient buffer, preserves
the full predictor, and supports exactly the eight exercised shapes. Direct C
and `svt_aom_inv_transform_recon` use the same 10-bit luma, transform type, EOB,
and nonlossless state. Reduced 64-point storage is therefore preserved. EOB zero
returns the predictor without reading stale coefficients. Every counterfactual
arm requires exact C/runtime q, DQ, EOB, and inverse agreement, resolving the
earlier C-versus-SIMD concern on novel B and q32 inputs.

## Build and input binding

Build 2 links the exact object population from the R11 `build.ninja`, records
every object/tool/helper/export-map identity, and proves its inputs and the
1,790-file source manifest unchanged before/after. It uses a private output and
`--no-undefined`; Build 1 is explicitly superseded. Reusing the objects neither
changes nor executes the encoder path.

The driver admits the complete R11 provenance before native work. It completes
all 2,187 generated-table, baseline q/DQ/EOB/inverse, raw-inverse, and
C/runtime checks before computing B or q32. It verifies actual qindex >32,
10-bit, zero segment delta, and exact captured FP tables. The 10-bit DC lookup
table is strictly increasing at every observed qindex, so matching the captured
DC row with delta zero functionally establishes the used delta; q32 uses the
same pinned lookup. Counterfactual arrays retain deterministic coefficient and
pixel offsets. All 720 noninvoked owners use their admitted predictors.

The local mosaics use original luma as the metric reference while retaining the
R9 coding-input identity separately. Whole fixed ROIs are primary; invoked,
noninvoked, positive, and quantized-zero support remains explicit. The result's
scope correctly excludes encoder feedback, entropy/rate, a legal encode,
full-window quality, repair, and playback.

## Required small driver correction

At `experiment.py:126-133`, `control["native_fp_tables"]` and `qtables` refer to
the same mutable dictionary. `baseline-control.json` is serialized before q32 is
added, but the later `qtables["32"] = ...` mutation causes the copy embedded as
`result["controls"]` to include q32. The two representations of the baseline
control would therefore disagree, and q32 would be mislabeled as a baseline
table.

Freeze the observed-q mapping when constructing `control` (for example, a deep
copy), or embed only the hash-bound `baseline-control.json` in the final result.
Keep the separately named `generated_fp_tables` mapping for observed rows plus
q32. This changes no native calculation and needs no rebuild.

As a provenance improvement, add the revised contract identity to
`dependency_paths`; the computation is already bound to its source, build,
admission, helper, and metric artifacts, so this is not a numerical blocker.

## Policy interpretation correction

Pinned PSYEX has no public `--trellis`/RDOQ switch. A favorable same-q B result
cannot justify a one-flag `--trellis 0` arm. Any real B-policy test would require
a private source intervention with runtime coverage and would bundle first-stage
B selection with optimizer/search changes. The current contract and driver do
not make the unsupported flag claim, so the diagnostic itself is unaffected.

No experiment output or scientific outcome was inspected or derived during this
review.
