# Pantheon: effective quantization and bounded grain representability

**Lower actual quantization can preserve substantially more of this material.
The tested source-budget strategies do not provide a satisfactory repair.**
The software-encoder trace now locates separate losses in quantization,
rate-distortion coefficient pruning, skipped residual coding, and selected
64×64 transforms. This is evidence about the pinned SVT configuration; it does
not prove the same internal causes in NVENC or an AV1 efficiency limit.

The secondary check finds a **local same-frame conflict** between quiet and
stochastic texture requirements on the existing fixed NVENC base. It does not
prove that every legal grain model, frame or base is incapable of useful synthesis.
No new estimator or production change is proposed.

This follows the [completed causal investigation](../pantheon-causal-20261019/README.md)
at `58a113db`, without repeating the broad settings sweep. Original downloads,
96-frame preroll and exact primary fixtures were retained. New paths were checked:
both instrumented baselines are byte-identical to preserved IVF streams; captured
input/pre-filter reconstructions match archived stages; private final inverse
reconstruction is exact; independent dav1d agrees on all 240 final frames/all
planes. New reference extraction hashes match the verified originals.

## 1. Where the texture disappears

Final EncDec luma TUs were exported for E04 frame 134 and E05-1440 frame 120,
including actual predictor, input-minus-predictor residual, forward coefficients,
initial/final quantized and dequantized coefficients, reconstruction, effective
qindex/dequant tables/lambda, modes, block/transform geometry and skip decisions.
The input equals the original in both diagnostic ROIs. The missing texture is
available in the prediction residual; it did not disappear before encoder input.

| Diagnostic frame / ROI | Source HF | Predictor HF | After initial quantization | After full optimize_b | Quantizer bypass / final no-residual area |
|---|---:|---:|---:|---:|---:|
| E04 / purple | 2.512 | 0.465 | 2.561 | 1.750 | 8.68% / 9.56% |
| E05 / shirt | 0.606 | 0.060 | 0.108 | 0.057 | 26.00% / 35.92% |

HF is paired with ACF and source correlation throughout. E04's initial HF exceeding
the source is **not** proof of fidelity: its HF correlation is only 0.761. Actual
baseline qindices are 77 and 80; E05's actual DC/AC dequant entries are 287/337.
Coefficient shaving is disabled. Recorded thresholds 255/255 and nonzero initial
EOB prove that these quantized ROI TUs execute full `optimize_b`, without the
alternative density fallback or fast-optimization paths. The raw capture's
`rdoq` name alone would not establish this; see [review reconciliation](REVIEW.md).

Private regular-B quantization probes preserve the input, predictor, partition
and exercised transform, while changing quantizer algorithm/qindex and omitting
RDOQ. On **quantizer-run neighborhoods only**, E04 HF rises from 1.993 at q77 to
2.270 at q45 and 2.501 at q1, versus 2.561 source; HF correlation rises
0.689→0.865→0.977. E05 rises 0.070→0.148→0.471 at q80/q48/q1, versus 0.598 source.
These are diagnostic reconstructions, not full-stream encodes. Hypothetical
transforms for bypassed TUs are separately labeled and excluded from those numbers.

E05 also has a transform-support loss: the selected 64×64 AV1 transform can code
only its 32×32 low-frequency coefficient region. In actually transformed shirt
pixels, unquantized forward/inverse error SSE is 4,116.9 for 64×64 TUs versus
89.9 for 32×32 TUs, despite the latter covering more pixels. Smaller-transform
errors are at most 0.5 in 8-bit luma units here. A real supported TX32 cap at the
same CQP improves the five-frame shirt HF from 0.504 to 0.593, versus 0.619 source,
and ACF error from 0.098 to 0.048. The cap changes legal mode/partition decisions;
it is not a fixed-decision quantization test.

Thus effective quantization and RD pruning are implicated directly; skip/search
choices and transform support also matter. The prior pre-in-loop-filter loss
finding remains valid. Prediction/search optimality has **not** been exhaustively
separated. No exact block entropy-bit attribution was obtained: coefficient
counts/magnitudes are explicitly proxies, while packet rates are measured bits.

## 2. Real preservation and its budget cost

All reported rates cover only the 240 scored video frames. These are ten-second
windows, **not whole-episode equal-size benchmarks**. The original rates are
10.02936 Mbps (E04) and 9.67652 Mbps (E05). Every target block's realized qindex
was checked spatially across all scored frames; requested offsets are not evidence.

| Real encode | Actual Mbps | Diagnostic qindex | Texture result |
|---|---:|---:|---|
| E04 CQP4 | 121.215 | 16, versus 77 baseline | Purple HF 1.848 / source 1.859; ACF error 0.0068; HF correlation 0.959 |
| E04 CQP8 | 59.451 | 32 | HF amplitude passes, ACF error 0.0861 fails the unchanged 0.05 screen |
| E05 CQP4 | 129.785 | 16, versus 80 baseline | Shirt amplitude/ACF still fail |
| E05 CQP4 + TX32 | 131.047 | 16 | Shirt HF 0.593 / source 0.619; ACF error 0.0479; correlation 0.805 |

These high-rate results demonstrate preservation, not its minimum possible bit
cost. CQP4 realizes qindex 4–16 across the window because of hierarchy. The
instrumented 336-frame runs took roughly 62–74 seconds at LP1; those timings
include tracing and sometimes concurrent diagnostics, and are not production
throughput benchmarks. High-rate ROI screens are provisional, not perceptual
acceptance or approval to encode episodes.

One optimistic budget mechanism then held every SB intersecting the diagnostic
rectangle at **absolute qindex 16** throughout the fixture, with VBR allocating
remaining bits elsewhere. This hand-selected rectangle is not a production
classifier. E05 also retains the global TX32 cap; its budget result is a combined
intervention, so its costs cannot be assigned solely to allocation.

- **E05: matched rate achieved, repair rejected.** At 9.69348 Mbps (+0.175%),
  shirt HF is 0.634, ACF error 0.0150 and correlation 0.829. But SSIMULACRA2 p5
  falls 26.23→11.46, outside-allocation mean luma MSE rises 9.329→11.104,
  and the frame-120 face MSE rises 6.840→9.859. Native still inspection shows a
  rectangular change in shirt texture at the allocation boundary.
- **E04: no matched-rate candidate.** Six TBR calibration attempts end at
  10.59857 Mbps (+5.68%). Target texture is retained, but VMAF falls
  90.59→74.25, SSIMULACRA2 p5 42.67→−13.80, outside-allocation edge MSE
  9.370→31.655, and CAMBI full-reference mean 0.588→2.313. The full-frame still
  visibly loses structure and shows blocking/banding outside the protected patch.
  This rejects the allocation strategy even before further rate calibration.

The [full metric tables](RESULTS.md) include VMAF/NEG and tails,
SSIMULACRA2/Butteraugli, PSNR/SSIM and banding. [Machine-readable results](results.json)
also retain CIEDE2000, ACF/source correlation, temporal statistics and spatial
controls. A lower CAMBI score or higher target-ROI score does not override the
whole-picture regressions. No threshold was relaxed.

## 3. What the fixed-base grain model can represent

This track uses the preserved **NVENC FGS encoded base with decoder grain off**,
not the SVT encodes above. Source-clean and stochastic-looking controls were
selected from previously held-out frames, checked against original gradients and
adjacent-frame behavior, and compared within the same frame. We did not classify
all source-minus-base error as grain.

The strongest example is E05-1460 frame 72. Quiet and textured neighborhoods have
the **same constant decoded 10-bit luma code 72 across 3×3 neighborhoods**; block
overlap bands are excluded. Their original conditioned HF amplitudes are 0.0826
and 0.3964. Even allowing the unchanged provisional 10% amplitude tolerance gives
quiet ≤0.0908 versus texture 0.3568–0.4361: nonoverlapping requirements for those
matched inputs. These are diagnostic bounds, not an approved perceptual gate.

Across 32 legal seeds, the prior-AR model at scale 16 produces conditioned HF
0.2977 and 0.3036 respectively; the white-AR control gives 0.3521 and 0.3528.
Conditioned endpoint occupancy is below 0.06% at that scale. A second E04 frame
184 pair at constant code 102 also has nonoverlapping local ranges. The retained
native probes include ACF and clipping statistics; larger E05 scales clip
appreciably and are not used as linear extrapolations.

AV1's luma scaling uses decoded luma, without a source-clean/texture classification
input. Chroma can depend on luma/chroma combinations and luma-grain correlation,
but cannot gate luma noise spatially. Seed/AR phase can create finite-region
variation; the ensemble result bounds a **robust expected-amplitude conflict**
for these neighborhoods on this base. It is not an exhaustive search over legal
AR parameters/seeds, a whole-shot impossibility proof, or an AV1 limitation.

This separates a local representational constraint from an estimation error or
a safeguard that is merely too strict. The shirt at frame 120 itself has no
sufficient matched quiet control in this screening set, so its local compatibility
remains unresolved. E05-1420 yields no qualifying matched quiet/textured pair;
that is absence of evidence, not evidence of compatibility. No revised estimator
was fitted, and quiet protection was not relaxed. Strong original grain around
24:25 remains original-source evidence, not proof of excessive synthesis.

## 4. Evidence, limits and disposition

[Commands, field definitions and validation](REPRODUCE.md),
[build hashes](provenance.json), [patch validation](patch-validation.json),
[tool versions](tool-provenance.json), [decisions](DECISIONS.md), and
[independent method review](REVIEW.md) accompany the scripts and isolated patches.
Evidence is preserved under
`/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/`.
[Archive contents and cleanup receipt](ARTIFACTS.md) document preservation and
post-move SHA-256 verification. Earlier archives remain unchanged.

Minimum clips for human viewing:

- [E04 synchronized 10-bit comparison](/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/e04/quantization-synchronized-10bit.mkv)
  and [full-frame budget failure](/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/e04/budget5-frame134.png).
- [E05 synchronized 10-bit comparison](/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/e05-1440/quantization-synchronized-10bit.mkv),
  especially the fixed texture boundary and content changes.
- [Earlier E05-1460 synthesis regression clip](/media/merged-storage/cold-storage/docker-apps/pantheon-causal-20261019/e05-1460/a-comparison-synchronized.mkv)
  for quiet noise and switching; this is previous estimator evidence, not a new fit.

The new FFV1 clips retain exact 10-bit cropped pixels, checked for all four arms
and all 240 frames. E04 panel assembly was corrected to use frame-index PTS after
its new hash check caught millisecond timestamp-rounding differences. PNGs and
H.264 companions are 8-bit previews. Still images were inspected; temporal curves
were computed. **Motion playback and the user's player/display remain unverified.**
The near-black representability still is primarily a location guide; its numerical
result should not be treated as a verified display-level appearance judgment.

No production change is warranted. Quantization preservation is feasible in
these samples, but efficient whole-picture preservation remains unresolved.
The current evidence does not justify re-encoding the season, installing a new
encoder, changing Tdarr, or declaring AV1 incapable of this material. It also
does not explain NVENC's internal loss directly; the established 14.1-versus-10.0
Mbps observation remains separate from this SVT trace.

The most discriminating next experiment, if pursued, is a fixed-decision
coefficient-retention/RD-cost test at an intermediate actual qindex with exercised
≤32 transforms, measuring entropy-coder bit deltas rather than coefficient-count
proxies. That can test whether a texture-aware distortion term preserves useful
coefficients efficiently before another real encode. A deployable design would
still need automatic region selection, whole-window regression constraints,
held-out windows, episode-level size/speed qualification and human playback.
