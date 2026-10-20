# R11 scalar-quantization versus postquant design review

## Recommendation

Use one bit-neutral **actual producer-stage capture**, followed by offline fixed-decision inverses. Do not begin with a synthetic quantizer call. The population is already frozen by R10: every one of the 24 EOB-positive decoder TUs intersecting the shirt, without selecting by loss. All are DCT_DCT with normative decoder qindex 71: twenty 32x32, two 16x16, one 32x16 and one reduced-domain 64x64. Retain full coded TU domains for validation and restrict texture summaries to their fixed shirt intersections.

The capture must distinguish **initial scalar output** from **post-scalar coefficient modification**, not assume every later change is removal. If the PSYEX quantizer wrapper combines scalar rounding and optimizer/RDOQ in one inseparable call, an internal pre-optimizer hook is required. Calling a lower-level scalar routine separately would be a counterfactual and must not be labeled the actual initial output.

## Minimum actual-stage record

For each target TU, assign a durable producer token at the call that actually produces its coefficients. Carry that token through normal EncDec or every MD-reuse/bypass copy into the accepted `svt_aom_encdec_update()` leaf. Join by accepted generation, picture, SB, final leaf/TU geometry, plane, transform size/type and token. A geometry/hash coincidence among search candidates is insufficient.

The producer record needs exact copies, never retained pointers, of:

- coding-input samples, final predictor and their exact signed residual;
- raw forward-transform coefficients in the native packed domain and scan;
- actual quantizer function/path plus every precision input it consumes (QP/qindex-domain argument, bit depth, plane, segment/delta state, dequant tables, QM/iqm state, quant algorithm/path flags);
- qcoeff, dqcoeff and EOB immediately after scalar quantization but before trellis, optimizer, dropout, shaving or other coefficient-domain modification;
- qcoeff, dqcoeff and EOB at the last coefficient-domain point committed to entropy coding;
- native reconstructed samples after the production inverse.

Record route states separately: normal final EncDec quantizer call; final EncDec MD-skip; whole-EncDec bypass with proven copied producer; other proven reuse; unresolved. Stored `BlkStruct.qindex`, coefficient presence or EOB is never an execution token. A bypassed result is admissible only when its producer token and coefficient payload are copied unchanged into the committed block. Otherwise its actual-forward fields remain unknown and it blocks a complete-population mechanism conclusion.

## Decoder and surface binding

Require unchanged PSYEX IVF and all 336 decoded frames. For every target TU, normalize the encoder's final coefficient layout to the R10 decoder's canonical packed domain and require exact final EOB, scan extent, dequantized coefficients, normative dequant/QM state, predictor pixels and preloop pixels. The single 64x64 TU needs its reduced 32x32 packed coefficient domain retained explicitly; do not treat it as a physical 64-wide raster.

Encoder coding input must equal admitted R9 `coding_input` over the full TU, and the final encoder predictor must equal the R10 decoder predictor. Original source is a reference descriptor, not the forward transform input. The encoded native reconstruction must equal R10 preloop over every full TU and as an assembled visible mosaic. Any mismatch is an extraction/provenance failure, not an outcome.

## Fixed-decision inverses

After the actual stages are admitted, make private copies of the proven predictor and reconstruct three domains with the exact native transform scaling, bit depth, clipping, transform size/type and scan layout:

1. raw forward coefficients;
2. immediate scalar dqcoeff;
3. final committed dqcoeff.

Final-domain inverse must reproduce R10 native preloop exactly. A decoder-side scratch inverse seeded with the captured predictor is an economical independent check for the final and scalar normative dq domains. Use it for raw forward coefficients only after source inspection or an encoder-native cross-check proves that raw coefficients use the same inverse-domain scaling and packed layout. Otherwise use PSYEX's native inverse for raw coefficients and compare its final-domain result against the decoder scratch result. These local mosaics keep real predictors/partitions/transforms fixed; they are neither legal alternative decodes nor feedback-consistent encodes and carry no entropy-cost claim.

Measure coefficient changes as well as pixels, because clipping can hide them. Report nonzero positions added/removed, magnitude/sign changes, EOB movement and coefficient energy by full frozen population, transform stratum and fixed ROI intersection. Use connected TU intersections for HF/ACF/correlation and retain evaluable counts.

## Outcome interpretation

- Raw inverse source-like, scalar inverse degraded, scalar and final similar: loss is localized mainly to scalar quantization at this actual precision and fixed decision.
- Scalar inverse source-like, final inverse degraded: post-scalar coefficient modification is decisive.
- Both transitions degrade: mixed scalar and post-scalar loss; retain both.
- Raw inverse already poor: the fixed predictor/transform/support or transform rounding cannot represent the coding input well in this decision. It does not establish codec-wide unrepresentability.
- Predictor poor but raw inverse restores coding input: prediction quality alone is not the fixed-decision representation limit.

## Stop conditions

Stop every scalar-versus-postquant conclusion if any of the 24 TUs lacks a unique accepted producer token; if MD reuse/bypass provenance is unresolved; if an actual pre/post boundary cannot be identified; if final coefficients, predictor or preloop fail the R10 join; if raw-domain scaling is unproven; or if instrumentation changes the bitstream/reconstruction. A valid partial subset may be reported only as coverage, not generalized to the shirt population. No new setting, quality threshold, rate claim or playback claim is warranted by R11.
