# Final-decision coefficient observation

The admitted E05 frame shows several distinct losses before in-loop filtering:
predictor-only skips, reduced support in a selected 64-pixel transform, initial
quantization, and subsequent coefficient processing. No one of these observations
establishes the best alternative coding decision or a repair at the original rate.

This is **input216/scored120 only**. Earlier texture tables average scored frames
116,118,120,122,124. The source and ordinary decoded descriptors here agree with
the earlier frame120 records within float32/float64 rounding; they must not be
compared directly to those five-frame averages.

## Evidence admission

Both disabled and enabled observation reproduce the installed R3 IVF exactly:
`ab233b3874583fbbb75f9bd9e91a63ff19efeae9a57e7639ca4fc499c7662052`.
The trace contains 7,382 records in the one final target generation238. Every
visible luma pixel has exactly one owner. Source minus predictor equals the
exported residual wherever a transform executes. Final dequantized coefficients
inverse-transform exactly to each actual TU reconstruction and the assembled
encoder pre-loop plane. The separately captured post-loop plane equals decoded
display216. Packed target OBU bytes equal the independently bound hidden frame.

The trace is51,460,928 bytes, SHA256
`5d699d733f741af85f5b61ce99b6351f8af4b9e8fb4f4de9ee63b5ca1e7fb980`.
Full source, predictor, residual, raw/initial/final coefficient vectors, scans,
quantizer parameters and reconstructions are retained. Skips have absent
coefficient vectors; no unexecuted quantizer is inferred.

## Observations

HF amplitude below is paired with spatial structure and source correlation in
[the complete result](aom-tu-result.json). The original single-frame shirt and
background ACF1 values are−0.222415 and−0.178995.

| Single-frame ROI | Source HF | Predictor | Raw inverse | Initial DQ inverse | Final/pre-loop | Post-loop |
|---|---:|---:|---:|---:|---:|---:|
| Shirt |0.606320|0.073864|0.338606|0.119503|0.070261|0.068586|
| Background |1.676388|0.297123|1.480467|1.457728|0.604104|0.601864|
| Face |2.700847|1.854595|2.629047|2.653638|2.238544|2.249365|

Only46.88% of shirt pixels undergo an observed transform;53.12% are coding-block
skips. Of the whole shirt ROI,29.60% belongs to exercised transforms with both
dimensions≤32, and17.28% to one intersecting64-dimension TU. Within same-TU
neighborhoods of the≤32 population, raw inversion has HF0.595637 against
source0.592131, ACF−0.167619 against−0.167403, and source-HF correlation0.993187.
Initial quantization reduces HF to0.145182 with ACF0.331571; final coefficient
processing reduces it further to0.055291. These are conditional comparisons
on the same mask, predictor and transform, not statistics on selected successes.

The shirt's64-dimension population fails even without quantization: raw HF
0.174389 against source0.575065, ACF0.420259 against−0.247247, correlation0.275408.
The reduced coefficient domain is preserved correctly in the observation.
Lower quantization alone with that transform fixed cannot recover frequencies
that the transform path already omitted. A real finer-quantization encode could
choose other transforms or partitions; that remains a separate experiment.

Background transform coverage is72.098%; all exercised transforms are≤32.
On their same-TU neighborhoods raw HF1.660150 closely matches source1.659858,
with correlation0.999772. Initial HF1.574276 is relatively close in amplitude
but ACF−0.041823 differs from source−0.145719, and correlation is only0.646778.
Final processing lowers HF to0.551477 and changes ACF to0.162024. Thus preserving
initial coefficients alone is not demonstrated to preserve the source texture.

All4,948 exercised records use the FP initial quantizer. Their actual
`x->qindex` spans57–77; shirt uses65 and background69–73. Base qindex is69.
The recorded `mbmi->current_qindex` field is first-block bookkeeping, frequently
zero, and must not substitute for the actual quantizer input. The independently
parsed target header confirms `delta_q_present=1`, `delta_q_res=2`, base69 and
no quantization matrix. Non-realtime libaom defaults to objective delta-Q.
An earlier proposal mistakenly read the realtime-only default; it is corrected
before selecting a real intervention. Public qmax limits base selection and
does not guarantee a cap on every exercised TU.

The858 frozen midpoint tiles comprise120 edge,480 flat-texture and258 other
tiles, **zero quiet tiles**. Whole-frame transform coverage is53.218%.
Raw/initial/final tile mean MSE is1.280509/2.966171/3.491886; p95 is
3.191559/6.393262/8.387109. Initial mosaics introduce positive HF excess in35
tiles (max0.283161); amplitude alone therefore remains insufficient. No new
quiet-region conclusion is available from this frame. The unchanged real
encode's complete15-frame controls,240-frame traces and GPU scores remain valid
through exact bitstream identity.

## Scope, cost and next discriminator

Confidence is high in the observed local stage differences and exact
reconstruction bindings. Raw/initial images are **local counterfactual TU
mosaics**: later intra predictors and reference pictures remain those of the
actual encode. They are not coherent alternative decoded frames, legal encodes
or bitrate estimates. Coefficient counts and magnitudes are not coded bits.
Prediction quality and partition/skip selection are not causally separated by
holding their final choices fixed.

The unchanged real parent remains a failed repair at9.639088Mbps,99.6131% of
the9.6765224Mbps source, with previously measured two-pass391.652s/336frames.
Private off/trace pass2 replay times were340.094/340.817s using existing pass1
statistics; these are diagnostic timings, not new candidate benchmarks.
Parent inspected the shirt/background/face gray still panels. **No playback
was performed.** No production change is justified.

The next useful real-encode question is whether a substantially lower actual
quantizer changes these skip/transform decisions and restores texture, with rate
initially unconstrained and measured. It must prove realized TU quantization,
retain the actual objective delta-Q policy, and assess the full window, including
quiet regions. Only demonstrated preservation warrants a subsequent attempt to
redistribute bits within the original ceiling. This does not assume qmax alone
will preserve texture or that a more costly arm is practical.

See [contract](AOM_COEFFICIENT_CONTRACT.md), [patch](aom-tu-observation.patch),
[schema](AOM_TU_SCHEMA.md), [reproduction](REPRODUCE.md), [review](REVIEW.md)
and [ledger](LEDGER.md). The machine result links every trace, map, tile,
coefficient record, command, source/build identity and visual artifact.
