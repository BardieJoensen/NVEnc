# Experimental source-fidelity improvements

The prototype improves directional-detail retention in the bilateral
`retain=auto` path and preserves the source when a safe grain model poorly
represents the removed residual's amplitude. It is an isolated experiment;
the existing repair encoder and Tdarr flow are unchanged.

The encoder tested is commit `25d200bc55f116f6f94a3343ccdc297185d1df2a`,
SHA-256 `977990b1e4d8200f3202b84292dc9a824d559319e44aafbe9270755ce635d0d5`.
The baseline is the deployed `e778a88b` encoder, SHA-256
`5423d8abda1d2c248f25508c311ed4ca0eda08462e1ebc6bce95fba22e830249`.
Builds use the same cached CUDA 13.3 compiler image and an immutable source
checkout. No media are included in this repository.

## Implementation

The existing gradient-coherence mask previously protected the FFT3D
refinement pass but was absent from plain bilateral denoising. Automatic
retention now uses that mask before estimating the removed residual. Added
protection ramps from zero at sigma 2.5 to full strength at sigma 6, in 8-bit
equivalent code values. This avoids spending large numbers of bits on weak
grain for a negligible detail gain. Numeric retention and defaults retain
their previous paths.

After temporal model selection, automatic retention compares the actual
selected strength curves with occupied bins in the current residual. The
comparison weights bins by observed block count, checks Y/U/V separately,
and evaluates each curve at the GPU collection interval's centre. The legacy
fitter's endpoint grid is not the collection grid. Relative RMS error above
25% and absolute RMS error above 0.5 8-bit code values request source fallback;
non-finite occupied evidence cannot establish fidelity.

Fallback copies the original picture into the encoder and disables synthesis.
Lossy encoding still applies. It also invalidates remembered/pending models.
Recovery requires a settled model window and three consecutive closer fits
(10% relative / 0.25 absolute limits). This prevents the tested strength
transition from alternating source fallback and under-strength synthesis.
Existing unstable/periodic-model rejection remains earlier in the pipeline.

## Controlled evidence

`fidelity_compare.py` generated ten deterministic 768x432, 48-frame clips.
Known clean detail and independently generated noise allow detail preservation
to be measured separately from residual noise. All old controls are pinned by
source, binary, encoded-file and decoded-pixel hashes. The final candidate
passes `fidelity_regression.py`.

For detail-bearing fixtures, the following compares old auto at QP 20 with
the first candidate encoding no larger than that output. QP is searched in
integer steps up to 32; this is a size bound, not an exactly matched bitrate.
Contrast gain 1 means the original known texture contrast is preserved.

| Input | Old auto contrast gain | New auto contrast gain | Candidate QP | Size change |
|---|---:|---:|---:|---:|
| Fine grain + directional detail | 0.622 | 0.705 | 26 | -2.75% |
| Coarse grain + directional detail | 0.725 | 0.806 | 25 | -2.11% |
| Weak grain + directional detail | 0.901 | 0.901 | 20 | 0.00% |
| 10-bit PQ + directional detail | 0.876 | 0.882 | 21 | -5.91% |
| Woven detail | 0.361 | 0.362 | 21 | -4.75% |

At unchanged QP 20, the fine/coarse detail fixtures cost 17.0%/9.7% more
bytes. The weak-grain fixture is decoded-pixel identical to old auto. Woven
detail is still poorly separated; directional coherence does not recognize
all structured textures. The small PQ gain does not establish HDR perceptual
optimization. On the flat and asymmetric-chroma cases, behaviour is close to
the old output; the suspected missing one-sided chroma replacement was not
reproduced.

On a sigma 6-to-10 transition at frame 24, old auto's decoded grain falls to
about 58–59% of source strength for eight frames. The candidate preserves
source frames 24–30 and then returns to synthesis; its post-transition
strength stays above 92% of source in this fixture. That two-second clip
costs 103.5% more bytes at fixed QP. Alternating strong/weak intensity bands
also trigger source fallback for all 48 frames and cost 103.5% more bytes;
median decoded/source strength improves from about 0.897 to 0.979. Neither
fallback-heavy case fits old auto's size by QP 32.

These comparisons are against the existing opt-in automatic retention mode.
The default `retain=0` is substantially smaller on some synthetic sources.
An eight-point texture-contrast gain is not an eight-percent improvement in
overall perceptual picture quality, nor a prediction for an entire library.

## Regression controls

The CPU suite passes, including amplitude mismatches, separate chroma curves,
8/10-bit scaling, empty and rare bins, the absolute noise floor, non-finite
evidence, and sloping curves at the collected intensity-bin centres.
Compiling the new centre tests against the previous implementation produces
the expected two failures (8-bit and 10-bit).

The first prototype preserved too much weak-grain residual and pumped during
the strength transition. Its controlled report fails four assertions in the
new decoded regression check; the final candidate passes. A detector that
only accepts the final candidate would not establish this negative control.

The local quick gate passes all 21 bilateral GPU fixtures, including HDR,
scene changes, chroma boundaries, fixed retention and automatic retention;
table export/failure-path checks and both model-gate controls pass. The
additional automatic-retention detail/flat checks also pass with FFT3D and
motion denoisers (four checks). These are development checks, not extra
production validation.

## Real-film pilot and speed

The corrected pilot verifies four real clips. The 150-second Gentlemen
fixture is encoded in old/new/new/old order; the other three fixtures contain
24 frames each. All 16 outputs pass the full `synthesis_texture_v1` scan,
full decoding with grain on and off, and frame-count checks. The three short
clips' default-mode decoded pixels are identical before and after. Silo and
Alien also produce identical decoded pixels between the two auto modes.

| Input | Old auto bytes | New auto bytes | Size change |
|---|---:|---:|---:|
| The Gentlemen (150 seconds) | 48,004,693 | 48,354,868 | +0.73% |
| Taxi Driver (24 frames, PQ) | 2,978,460 | 2,987,804 | +0.31% |
| Silo (24 frames, SDR) | 179,138 | 179,138 | +0.00% |
| Alien (24 frames, PQ) | 1,982,178 | 1,982,178 | +0.00% |

The candidate adds source-fidelity fallback on 191 of 3,600 Gentlemen frames
(5.3%); this is separate from the existing unsafe-model fallback. Both
candidate repeats decode identically. The known jacket scenes at episode
34:06 and 34:24.5 still disable synthesis on all planes and preserve the
source to the same measured encoding error as the old auto output.

Gentlemen wall times were 118.7s / 89.8s for old auto and
90.0s / 105.9s for new auto. Their ranges overlap substantially;
shared-server contention prevents a defensible small speedup/slowdown claim.
No other experiment used the GPU during these four timing runs. Short-clip
sizes are not forecasts for a whole title.

The initial short-clip benchmark omitted explicit colour-copy flags and
failed its colour-tag check on the baseline HDR output. Those encodes were
excluded and rerun with the same colour/chroma/mastering copy flags already
present in the Tdarr flow. The corrected SDR/PQ colour checks pass. The
completed Gentlemen checks were preserved in a separate, verified report.
This was a benchmark-command correction, not a production-flow change.

## Scope and remaining limits

The fallback checks the amplitude of the removed residual, not whether that
residual is entirely grain, and not its complete spatial/temporal texture.
Twenty intensity bins and a global frame fallback remain coarse decisions.
The underlying legacy strength-fit grid is unchanged; the new guard measures
its physical mismatch rather than silently adopting its coordinates.

Temporal separation for woven/isotropic detail and a calibrated HDR
perceptual objective remain development opportunities. This prototype does
not justify enabling auto across the library or scheduling re-encodes.
Its expensive experiments are offline and add no work to Tdarr validation.

Local detailed reports, source hashes, immutable binaries, intermediate
encodes and the comparison figure are under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/encoder-fidelity-20260908/`.
