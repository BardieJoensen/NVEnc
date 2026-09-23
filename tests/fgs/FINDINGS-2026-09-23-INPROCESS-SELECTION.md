# In-process reconstructed-base calibration

D47 moves strength calibration toward an encoder-callable implementation.
`NVEncFilmGrainRetainedStrengthBatch.h` cooperatively runs the existing scalar
search for Y, Cb and Cr. One synthesized picture supplies all three component
measurements. Each search replays its cached measurements rather than spawning
an interactive child process or implementing a second numerical search.
There are at most ten synthesis callbacks per seed; invalid and nonmonotone
measurements retain the original rejection rules.

The callback contract requires fixed source/base, seed, shape, point presence
and selected pixels, with each component's variance independent of the other
strengths. Actual AOM controls verify this on all eight zero/maximum strength
combinations at both native depths, including luma-coupled chroma templates.
All sixteen pictures match the prior independent oracle exactly. This does not
permit changing active point counts, shape or base inside a calibration.

`NVEncFilmGrainNativeVariance.h` measures whole-picture means and detrended
training/check variances for native Y, averaged Y, Cb and Cr. It handles bounded
planar native code spans and padded strides, checks native ranges, and currently
requires dimensions divisible by 64. Invalid layouts and incomplete halves
return invalid evidence. These are measurements, not source-population approval.
Nonaligned borders still need separate implementation and qualification.

The reusable `reconstructed_strength_reference.cpp` runs the pinned AOM and
these helpers in one process. It remains a development adapter: model shape is
supplied, and full spatial/cross-component/temporal acceptance stays external.
There is no automatic source admission or encoder call site for this selector.

## Qualification and cost

- 448 batch searches exactly match the existing independent scalar searches,
  including endpoint, quantization, invalid and nonmonotone cases.
- The 42 recorded D42 seed attempts replay all 420 measurements and preserve
  all 126 component decisions.
- Fresh in-process synthesis reproduces all 42 final candidate pictures exactly.
  All 420 calibration steps choose the same integer strengths. Independent
  NumPy variance differs by at most `1.4210854715202004e-14`, within the frozen
  arithmetic tolerance; no quality threshold changed.
- Native 8/10-bit checkerboard/plane controls, poisoned padding, span/layout
  failures and actual coupled-template plane independence pass.
- Full CPU suite: 214 Python tests in 30 suites plus 40 C++ programs.

On those fixed controls the new path took 2.54 seconds, versus 9.72 seconds for
the matched previous calibration path. The new timing includes input loading,
source/base statistics and final picture synthesis/write; the previous timing
measures calibration using already computed source/base statistics. This single
paired run is a useful substep cost result, not a complete encoder speedup or a
full-title throughput claim. Neither timing includes the full covariance gate,
model fitting, GPU encoding or storage tradeoff evaluation.

Temporary oracle pictures were hashed against the retained evidence and removed.
The local `roadmap-r3-inprocess-selection-20260923` ledger contains the manifest,
scalar replay, fresh native results, matched legacy measurements, independence
controls, exact commands and full CPU log. D46's live output qualification is
documented in [continuous output](FINDINGS-2026-09-23-CONTINUOUS-OUTPUT.md).

Continue by moving the complete spatial/cross-component checks and bounded seed
selection into the same process, followed by live source/base fitting and output
integration. Whole-picture eligibility, real population support, temporal
qualification and R4–R8 remain open. Production remains ordinary `cb903a17`,
retention/FEL off; the reserved corpus is unopened. No experiment restarts itself.
