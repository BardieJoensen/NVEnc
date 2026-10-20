# R11 normal-EncDec route simplification review

## Disposition

The simplification is sound **if the route check surrounds the final EncDec dispatch rather than living only inside the normal EncDec call**, and the coefficient token is admitted only by an exact join to final decoder syntax. A separate route-only encode would add no scientific information: the same bit-neutral R11 replay can prove the route and capture the coefficient stage together.

The source derivation in `worker/psyex-r11-committed-audit/route-audit.md` (SHA-256 `4cabca3f2b1e195216bc63ff01b0bcc9c6e8d7ebd61fe0e4f8aefd6a56caf7d1`) is correct:

- `enc_mode_config.c:7756-7771` returns `bypass_encdec=0` for non-8-bit input at `enc_mode <= ENC_M7`.
- `enc_mode_config.c:8135-8140,8547-8554` uses the per-picture `pcs->enc_mode` and static encoder bit depth; segmentation can only force bypass to zero.
- `md_process.c:593-616` copies `pcs->pic_bypass_encdec` into each reset MD context. The source tree has no later live assignment to that context field.
- `enc_dec_process.c:3494-3535` computes final-PD state and conditionally calls `svt_aom_encode_decode`; `coding_loop.c:1751-1764` derives `md_skip_blk` per final block. Thus bypass is picture configuration, while final skip is not.

R8 admission independently recorded postprocessed `enc_mode=4` and `encoder_bit_depth=10` in `parent/psyex-observation/admission-1.json`. Those values imply the normal route for that admitted arm. They are not sufficient by themselves for a new private executable: `resource_coordination_process.c:180-302,1008,1081-1087` shows that `pcs->enc_mode` is a runtime picture field and can be changed when speed control is enabled. The fixed R8 run used the static preset path, but R11 should prove the effective values again.

## Required admission conditions

1. At the target final-PD dispatch, before `if (!md_ctx->bypass_encdec)`, record/assert for every target-picture SB: effective `pcs->enc_mode==ENC_M4`, `scs->static_config.encoder_bit_depth==10`, `pcs->pic_bypass_encdec==0`, and `md_ctx->bypass_encdec==0`. Coverage must equal the accepted target SB population. A check only inside `svt_aom_encode_decode` would silently miss bypassed SBs.
2. Keep the existing exact off/on IVF and application-reconstruction identity requirements and bind the target accepted generation/frame to R8/R9/R10. They establish that instrumentation did not alter the final decisions.
3. Issue a token only at the actual **final EncDec** forward-quantizer call, never at an MD candidate/search call. Key it by accepted generation, picture, SB, final owner/block and luma-TU geometry/index. Reject duplicates, ambiguous coordinate joins, or tokens from rejected generations.
4. Require exactly one matched token for each of the 24 preregistered R10 shirt EOB-positive DCT_DCT/q71 TUs. Join the token's final EOB, scan/transform geometry, quantized coefficients and dequantized coefficients to the decoder-observed final syntax/normative DQ data. Any EOB-positive target without a token falsifies the assumed normal producer path and blocks interpretation.
5. Record `md_skip_blk` at the same final owner. It must be false for every EOB-positive target. Coefficient-absent controls may retain an explicit `producer_unknown/final_no_residual` state; they cannot be used to distinguish skipped prediction from executed quantization that produced or selected zero.
6. Treat any target bypass, mode/depth mismatch, missing/duplicate token, final-syntax mismatch, or unsupported quant mode as a fail-closed trigger for the fuller producer-propagation design. Do not repair such a failure by coordinate-only matching.

Under these conditions, omitting MD-candidate reuse/token propagation is controlled: the experiment asks what happened in normal final EncDec, and direct producer evidence plus decoder equality answers that question. It does not prove how MD search arrived at the selected transform/mode, nor does it localize coefficient removal for coefficient-absent controls. `fixed_partition` may be logged for scope but need not gate the 24-TU scalar-versus-postquant comparison once the actual final producer token is present.
