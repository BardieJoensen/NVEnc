# R11: actual committed coefficient stages

Primary question: on the frozen R8/R10 E05 shirt transform units, does the initial scalar quantizer or subsequent coefficient processing account for the poor reconstruction? This is a diagnostic of one encoder configuration and frame, not a repair trial.

The practical gate remains at or below original packet bitrate, including whole-window protection and actual human playback. R11 changes no encoding decisions. No new quality score or rate claim is admissible unless the resulting bytes match the admitted R8 control or the full new-path campaign is performed.

## Frozen evidence and controls

Use the exact 1,789-file R9 source manifest `12f345e1f738b97fd00d9b9b2978864c53df995ad7590374edc21d31004124ce`, copied into fresh `parent/psyex-coeff-r11/source`. Preserve earlier source/builds/traces unchanged. Replay the exact R8 second pass, input, first-pass statistics and configuration. Require off and on IVF and all 336 reconstructed frames to match admitted R8 hashes.

Trace display-input picture 216, accepted generation, independently resolved to R10 coded event 314 / coded ordinal 210 / order hint 88. Capture every luma transform intersecting the existing shirt [1200,650,200,100], background [950,50,250,180] and face [160,600,500,480] ROIs, retaining complete transform domains. No selection by observed improvement. Require all 24 R10 positive-EOB shirt units, and explicitly account for absent-residual owners. Keep the 858 frozen frame tiles for any whole-frame interpretation; these ROIs alone do not establish quiet-region safety.

## Instrument and validate

1. Before every target superblock's final EncDec dispatch, record and assert effective preset M4, 10-bit, picture bypass=0 and MD bypass=0. Record fixed-partition state. An inside-EncDec hook alone cannot establish route coverage.
2. Assign a durable token to each observed final EncDec luma invocation, binding picture, generation, SB, block and TU geometry, transform depth/type, coefficient offset and actual context. Preserve source, predictor, signed residual and forward coefficients at their real boundaries. Record skipped calls explicitly without inventing coefficient data.
3. Inside the actual quantizer call, bind its raw coefficient pointer to the token and capture requested and resolved qindex, segmentation offset, DC/AC dequant and quantization tables, QM/IQM, scan, transform scale, bit depth, lambda and relevant branch controls. Capture the first scalar result and separately any fast optimization, B requantization, full optimization and noise normalization, plus final q/DQ/EOB. Branch execution and no-op results are distinct.
4. Capture final native per-TU reconstruction. Match every token to the subsequent `encdec_update` committed block owner and metadata copy, including the final SB qcoeff buffer for positive-EOB units. Require source agreement with R9 coding input, predictor and preloop agreement with R10, final DQ/EOB/layout/QM/qindex agreement with R10 for all positive-EOB target units. Decoder DQ is available; decoder qcoeff is not. Do not pretend a decoder qcoeff equality was measured. R10 final syntax plus identical encoded bytes completes the committed-output link.
5. Accepted-generation barrier, route coverage, unique tokens, complete footer, bounded lengths, input hashes and no missing/duplicate target units are mandatory. Rejected generations remain diagnostic and cannot replace accepted data.
6. Private-buffer native inverse transforms may be captured for raw and each coefficient stage with the exact predictor, transform and bit depth. They must not modify encoder buffers/state. Final-stage inverse must equal actual native reconstruction and independent R10; scan/EOB and adjusted 64-point coefficient domains must be explicit. Raw inversion is a forward/inverse diagnostic, not a claim of pixel-perfect reversibility.

## Analysis and limits

Separate observations from attribution. Pair HF amplitude with ACF and source correlation, plus MSE/edge error. Analyze fixed intersections, complete transforms and all controls without summing nonlinear errors as causal loss fractions. Compare initial scalar against final coefficients and reconstruction before making a quantization or optimizer claim. Quantized nonzero counts and magnitudes are coefficient proxies, not measured coded bits.

Fixed-predictor local counterfactuals are not coherent re-encodes: they do not feed altered references into later predictions and have no measured entropy-rate cost. Any promising stage intervention must subsequently be implemented in a real scratch encode, admitted through the campaign, measured by actual packets and checked for displaced whole-window damage before being called a candidate.

Fail closed on route, token, geometry, scaling, stage completeness, byte neutrality or final-output mismatches. Resolve the smallest instrumentation defect before interpreting results. Do not weaken the practical gate. No playback observation can be claimed from stills.

## Ownership and resources

Parent owns R11 source hooks, build/replay/admission and the Git index. Worker owns only `worker/psyex-r11-targets` and later explicitly assigned analysis; reviewer owns new files under `reviewer`. No recursive delegation or production changes. Bound builds to four jobs on CPUs 0–7, encodes to the established LP1 replay, serialize GPU work, and maintain the staging floor. Record commands, versions, hashes, failures and truthful execution receipts. Preserve useful evidence and archive only after the investigation reaches a valid stopping point.
