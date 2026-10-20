# R10 independent outcome review

Reviewed read-only on 2026-10-20, before a parent interpretation:

- admission `parent/aom-decoder-r10-v2/admitted-1/admission.json`, SHA-256 `4848fa5164df8ffbca7a2204de8f2df03982aed251fc7d2737709d5019e8de79`
- analysis `worker/decoder-r10-analysis/result-1.json`, SHA-256 `04091c7095658710d28bd1a3e5a912ca2a4c2f3b6bed1a728398ada9a6a74222`
- structural fault checks, SHA-256 `7b9184606df89efb5181c56b768f8b4c8b7ed34504a614ff86f52d2d7a34a51a`
- exact prior boundary analysis, SHA-256 `b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5`

## Validity

Admission is sound for the frozen question. Both private off/on decodes reproduce all 336 admitted R8 frames in all planes; the 502-event/336-coded-frame stream is independently rebound to consumed IVF bytes and OBUs; target coded event 314 is joined to display/input 216; captured luma preloop equals R9 and postloop equals R9 in all planes. The target has complete, disjoint visible luma ownership: 9,843 leaves and 9,843 analysis units, including 8,138 actual TU observations and whole-owner skipped-inter units. Predictor equals reconstruction for every absent-residual unit. All nine targeted malformed traces were rejected; those probes establish selected structural checks, not exhaustive parser correctness.

The source-frozen ROIs and all 858 frame-120 controls were declared before this outcome. Quiet has zero eligible tiles and remains explicitly null. The analysis uses connected unit/ROI intersections, carries evaluable/support counts, and labels the complete versus outside-only control populations correctly.

## Observations

Whole-frame syntax coverage is 31,424 skip-mode pixels (1.52%), 352,832 other no-coded-residual pixels (17.02%), 1,984 EOB-zero TU pixels (0.10%), and 1,687,360 EOB-positive TU pixels (81.37%). Category 2 comprises 1,591 inter and 277 intra units; it is a final no-residual category, not proof that quantization was absent.

The two target ROIs are more strongly residual-bearing:

- Shirt: EOB-positive units cover 18,368/20,000 pixels (91.84%); skip-mode and other no-residual syntax cover 1.12% and 7.04%; no EOB-zero unit intersects it.
- Background: EOB-positive units cover 42,680/45,000 pixels (94.84%); the remaining 5.16% is no-residual syntax; neither skip-mode nor EOB-zero units intersect it.

Thus predictor-only final syntax does not spatially dominate either target. In shirt EOB-positive intersections, native inverse reconstruction lowers pixel-weighted MSE from predictor 3.155 to preloop 1.538, but barely restores source texture: pixel-weighted per-intersection HF error changes 0.569 to 0.545 and source HF correlation remains approximately zero (-0.0069 to 0.0028). The exact full-shirt R9 surface similarly has preloop HF 0.0937 versus source 0.6063, source-HF correlation 0.0082, and ACF1 error 0.1965. Final filtering further lowers full-shirt HF to 0.0545.

In background EOB-positive intersections the native residual matters much more: predictor-to-preloop MSE improves 13.398 to 5.665, HF error 1.410 to 0.609, and source-HF correlation 0.064 to 0.428. The exact full-background surface has source/preloop HF 1.676/1.280 and correlation 0.539. Postloop filtering then increases full-background HF error from 0.396 to 0.829 while leaving correlation near 0.52, corroborating the already observed R9 filter-boundary loss.

The face control differs: absent-residual syntax covers 36.40% and EOB-positive syntax 63.60%. This variation is evidence against generalizing target coverage to the whole frame. Across all 858 frozen tiles, coding input remains near source (mean HF correlation 0.943); predictor is poor (0.126); preloop recovers some structure (0.293); postloop retains similar correlation (0.289) while increasing mean HF error from 0.437 to 0.589. The outside-only 840-tile values are close, so the target result is not hiding a contrary outside population at this frame.

## Interpretation and limits

R10 rejects the narrow hypothesis that final no-residual/predictor-only syntax accounts for most target pixels. It does not show that coefficient coding itself caused most texture loss. EOB-positive says at least one final decoded coefficient is present; those coefficients may primarily carry DC or low-frequency correction. The shirt result shows that the transmitted residual improves pixel error but restores almost none of the source high-frequency structure. Background shows a useful decoded residual followed by a large filtering amplitude loss. These mechanisms differ by ROI.

Decoder `coded_qindex` (observed range 71-115), decoder dequant/IQM state, EOB and final coefficients are normative bitstream facts. They do not establish the encoder's forward-quantizer call, prequant coefficients, optimizer path, or an RD discard. Zero/absent residual never proves quantization did not execute. Likewise, a poor final predictor can reflect reference ancestry and prior decoded losses; it is not proof of a defective prediction search. Per-unit weighted HF/ACF/correlation summaries are descriptive and non-additive; they must not be presented as fractions of the whole-ROI HF loss.

This remains one luma frame with fixed spatial descriptors. It changes no bitrate or quality gate, establishes no repair, and supplies no motion or playback evidence. Exact output identity permits reuse of R8's existing full-window quality evidence but does not make this diagnostic a practical candidate.

## Next discriminator

The narrowest informative follow-up is an observational encoder coefficient-path capture for the exact final committed, decoder-joined EOB-positive shirt owners, with the no-residual owners retained as a comparison population. Capture the actual prediction residual/prequant transform coefficients, forward-quant invocation provenance, initial and final qcoeff/EOB, optimizer/dropout provenance, and final predictor/reconstruction; require exact bitstream and decoded-surface neutrality and join each final owner/TU to this admitted decoder map. This distinguishes texture energy absent before transform from energy removed by quantization/optimization or mode commitment. It should precede another public settings arm. A separate scratch inverse is unnecessary unless the encoder-to-decoder coefficient/reconstruction identity check fails, because R10 already proves the native decoder inverse surface exactly.
