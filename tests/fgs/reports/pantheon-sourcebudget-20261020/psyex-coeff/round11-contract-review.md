# R11 coefficient contract review

Contract reviewed: `ROUND11_COEFFICIENT_CONTRACT.md`, SHA-256 `1d0fdcdeb2793befe0a232bf4fa0eeb0296f14caaa6903cc7227bb0e3fa81fad`.

## Blocking factual correction

The contract/parent interpretation is correct: **R10 serialized dequantized, transform-size-scaled coefficients, not quantized level coefficients**. The worker target manifest is mislabeled and must be corrected before it becomes an R11 admission oracle.

Evidence is direct:

- In pinned libaom `decodetxb.c` (SHA-256 `ce9bd8f...`), lines 123–125 bind the destination as `dcb->dqcoeff_block` and obtain `dequant` plus `av1_get_tx_scale`. Lines 303–312 compute `dq_coeff = level * get_dqv(dequant, position, iqmatrix)`, right-shift it by the TX scale, sign/clamp it, and store it in that buffer.
- `pantheon_decoder.h` (SHA-256 `414e3629...`) lines 83–89 writes the complete adjusted coefficient domain directly from `dcb->dqcoeff_block`; it does so before native inverse. `decodeframe.c` (SHA-256 `cbf83581...`) lines 149–155 passes that same buffer to `av1_inverse_transform_block`, then clears it.
- `validate.py` (SHA-256 `fde9fa7a...`) lines 57–67 reads those bytes and correctly names their hash `dequant_coeff_sha256`.

Thus the stored signed int32 is the decoder's normative inverse-transform input after dequantization, IQM weighting, and TX-size right shift. It is not the entropy-decoded integer `level`, not encoder qcoeff, and not an unscaled `qcoeff * DC/AC dequant` product. This also explains values such as 166 or 83 under an AC dequant of 332 for transforms with shifts one or two.

`worker/psyex-r11-targets/extract_targets.py` (SHA-256 `1802267e...`) lines 33–43 renames `dequant_coeff_sha256` as `quantized_coeff_sha256`, lists the DQ values as `quantized_coeff_nonzero`, and says DQ is unavailable. Its README and `targets.json` SHA-256 `06adf440...` repeat the error. Preserve these as rejected. Regenerate or truthfully relabel the manifest, including the join-domain description. Target IDs, geometry, EOB, scan, predictor and IQM selection remain usable. R10 contains no qcoeff array, so R11 final qcoeff can only be committed indirectly through exact output bytes/EOB/syntax; R11 final DQ can be compared directly to the R10 scaled DQ array after proving identical adjusted layout.

## Method disposition

With that correction, the contract is methodologically sound and applies the accepted route simplification:

- It checks effective M4/10-bit and both picture/MD bypass values before every target-SB dispatch, rather than inferring route coverage from hooks reached only inside EncDec.
- Tokens originate in final EncDec and carry picture/generation/SB/block/TU identity. For unambiguous committed-stage provenance, admission should explicitly require each positive-EOB token to be consumed or matched at the subsequent `encdec_update` final-owner commit, in addition to the accepted-generation and R10 geometry/DQ/EOB join. Coordinate equality alone remains insufficient.
- All 24 preregistered EOB-positive shirt TUs require actual quantizer tokens. Skip/no-residual controls are explicit and cannot be interpreted as unexecuted quantization. Branch execution and no-op stages are separated.
- Capturing raw transform, first quantizer output, each later coefficient-processing stage, final q/DQ/EOB and native reconstruction can distinguish scalar loss from later removal at fixed predictor/partition/TX. The first-stage label must name the actual FP/B routine used; it is not a generic mathematical scalar quantizer.
- Scratch inverses use private predictor/destination/coefficient storage and the exact native transform/bit depth/scan/EOB/adjusted 64-point layout. Final scratch inverse equality to production and R10 is a required implementation check. Raw or intermediate inverses remain local, noncoherent counterfactuals with no feedback or entropy-rate evidence.

The quality/rate scope is appropriately bounded: byte-neutral tracing reuses admitted R8 quality only; no stage reconstruction is a repair, playback observation, coded-bit estimate, or practical candidate. The 858 frozen tiles can support whole-frame claims only where a whole-frame surface exists. Local stage counterfactuals captured solely for intersecting TUs cannot be represented as having passed those 858 controls.
