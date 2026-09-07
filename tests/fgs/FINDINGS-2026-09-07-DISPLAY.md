# Full-image and HDR grain analysis, 2026-09-07

The decoded inspector now offers explicit SDR/PQ/HLG reference-display analysis
over every image pixel in each measured frame. It retains local peaks, their
coordinates, area-weighted percentiles and directional structure in all four
display channels. Bounded review runners make these results inspectable and
resumable without introducing pixel analysis into routine transcode validation.

## Gaps addressed

- Nine small patches could miss a corner, an image edge, or a local defect between
  patches. Averaging correlations could also dilute a local directional pattern.
  The new mode measures a complete tile partition and retains local maxima.
- Treating PQ/HLG as SDR produces misleading residuals. The new mapping uses
  absolute display luminance and records its display assumptions. HLG applies
  system gamma through luminance, preserving the required coupling between RGB
  channels.
- Some real retained AV1 clips have unspecified colour signalling. Analysis
  refuses those by default; a separately labelled BT.709 scenario is available
  only when it does not conflict with signalled colour data. It does not repair
  metadata or prove what the original colourimetry was.
- A silent choice between multiple video streams, stale source data, partial
  output, duplicate tiles, concurrent writers or an obsolete cached success page
  could undermine a review. Explicit selection, identity/completion/coverage
  checks and output locks now guard these cases.
- Scratch test archives now include the shared diagnostic code. The mutation
  self-check first requires an unmodified scratch baseline to pass, preventing
  a missing prerequisite from masquerading as successful defect detection.

The underlying standards and display limitations are documented in the
[tool guide](../../tools/fgs/README.md). PU21 provides the luminance encoding;
this tool's spatial descriptors are empirical diagnostics, not a validated
perceptual quality model.

## Calibration controls

The initial corpus contains **15 cases and 404 full-image sampled frames**:
reviewed real ripple/ordinary-grain clips, live action, animation, fine-grain SDR,
coarse-grain PQ, synthetic HLG/4K PQ, independent chroma, heavy clipping and
grain-free controls. Retained real sources were encoded with the verified
`e778a88b3f825a51e9f91122e29d99ec6a2dca4e` encoder, SHA-256
`5423d8abda1d2c248f25508c311ed4ca0eda08462e1ebc6bce95fba22e830249`.

[The calibration record](baselines/reference-display-calibration-v1.json)
contains source/CSV hashes, decoder identity, dimensions, sampling periods and
colour assumptions. Film/TV media are retained locally and are not distributed.
Synthetic SDR controls were explicitly tagged as their intended BT.709 scenario
before measurement; ambiguous real inputs used the recorded CLI assumption.

The following are maxima over sampled frames, channels and tiles at the default
1000-nit HDR peak / 100-nit SDR white. Texture and directional scores have
different definitions and should be read as separate descriptors.

| Control | Texture score | Directional score |
| --- | ---: | ---: |
| Grain-free synthetic | 0.000 | 0.000 |
| Silo, current fine-grain SDR encode | 0.900 | 0.466 |
| Gentlemen, reviewed source-preserving encode | 2.818 | 1.828 |
| Gentlemen, confirmed mesh encode | 5.317 | 6.248 |
| Taxi Driver, current coarse-grain PQ encode | 6.025 | 2.550 |
| Alien, current coarse-grain PQ encode | 3.760 | 1.901 |
| Synthetic HLG | 2.848 | 2.298 |
| Synthetic 4K PQ | 3.188 | 2.713 |
| Synthetic coarse luma | 2.746 | 1.222 |
| Synthetic independent chroma | 2.146 | 1.942 |
| Synthetic clipped 10-bit chroma | 2.930 | 1.771 |
| Ford garage excerpt | 15.421 | 28.095 |
| Ford podium excerpt | 11.761 | 18.552 |
| South Park excerpt | 55.554 | 15.915 |
| Adventure Time excerpt | 6.430 | 5.108 |

The ordinary texture score for the current coarse Taxi encode exceeds the
confirmed Gentlemen mesh score. Directional comparisons separate those two
controls better, but the animation results still require contextual review.
These observations do not establish a cross-title cutoff, a watchability rank,
or a reason to replace any of the sampled files.

A second **12-case / 54-frame** experiment holds four bitstreams fixed while
varying reference peak through 400, 1000 and 4000 nits. HLG texture maxima change
from 2.457 through 2.848 to 3.516. The synthetic 4K PQ control changes from 34.96%
to 24.99% to 9.00% of grained pixels clipped by the reference display mapping;
its texture peak is 3.188, 3.188 and 3.362 respectively. The sampled Taxi and
Alien peaks stay unchanged over these settings. Display dependence is real and
content dependent; a blanket HDR-to-SDR conversion would conceal that context.

## Verification and operational limits

- Default nine-patch CSV output was regenerated with the new binary and was
  byte-identical to the previous inspector on four clips / **1,243 frames**.
  Existing recurrence baselines remain on that compatibility method.
- Numeric controls verify published PQ points, HLG colour coupling, 8/10/12-bit
  full/limited ranges and LUT error against analytic mapping. Maximum observed
  LUT discrepancy was **0.00374492 PU21 units** across the tested points.
- Complete pixel coverage is checked on tiny, odd, cropped-HD and 4K dimensions.
  Injected alternating rows in one corner and a pattern confined to the final
  row remain detectable. A constant mean offset produces no texture score.
- Software AV1 CLI controls exercise colour rejection/assumptions, stream
  selection, HDR/12-bit decoding, explicit temporal sampling, empty intervals
  and intact tile coverage. Runner controls cover incomplete/corrupt output,
  changed fixtures, conflicting writers and cache invalidation.

Full spatial coverage does not imply full temporal coverage. The window runner
defaults to two seconds at four sampled frames per second; short transients
outside those samples can be missed. Native `--extended` can inspect every frame,
at a higher CPU cost. The descriptor measures decoder-added grain, so it cannot
discover texture already baked into the base picture or prove source fidelity.
Dynamic HDR display mapping, viewing distance, temporal masking and observer
calibration remain outside this implementation. Additional observer-labelled
footage would be needed before proposing a perceptual threshold.
