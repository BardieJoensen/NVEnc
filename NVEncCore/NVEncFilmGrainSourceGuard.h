#ifndef NVENC_FILM_GRAIN_SOURCE_GUARD_H
#define NVENC_FILM_GRAIN_SOURCE_GUARD_H

#include <array>
#include <cmath>
#include <cstdint>

namespace fgsmodel {

// Noisy blocks train the AR model, but cannot establish that synthesis belongs
// on a different, nearly uniform region at the same brightness. Check that
// missing evidence separately, using source measurements before denoising.
// Values use native code levels normalized to eight bits, not a display score.
struct FilmGrainQuietSourceGuard {
    std::array<uint64_t, 3> quietBlocks = {};
    std::array<uint64_t, 3> conflictingBlocks = {};
    std::array<double, 3> maxExcess = {};
    bool invalid = false;

    void observe(int plane, double mean8, double sourceSigma8, double modeledSigma8) {
        if (plane < 0 || plane >= 3 || !std::isfinite(mean8)
            || !std::isfinite(sourceSigma8) || !std::isfinite(modeledSigma8)
            || sourceSigma8 < 0.0 || modeledSigma8 < 0.0) {
            invalid = true;
            return;
        }
        // Avoid clipped range endpoints: this test cannot infer missing grain
        // from black bars or saturated code values. Other synthesis/range
        // validation remains independent. A full source block supplies 1024
        // luma or 256 chroma observations; a single such conflict is evidence.
        if (mean8 <= 20.0 || mean8 >= 232.0 || sourceSigma8 > 0.5) return;
        ++quietBlocks[plane];
        const double excess = modeledSigma8 - sourceSigma8;
        if (excess > maxExcess[plane]) maxExcess[plane] = excess;
        if (excess > 0.25) ++conflictingBlocks[plane];
    }

    bool needsSource() const {
        return invalid || conflictingBlocks[0] || conflictingBlocks[1] || conflictingBlocks[2];
    }
};

} // namespace fgsmodel
#endif
