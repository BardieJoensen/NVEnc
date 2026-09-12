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

// Brightness-local protection attacks immediately but releases only after
// fresh fits and a gradual restart. Keep this independent of the AR cache:
// changing a model's knot positions must not clear recent source evidence.
class FilmGrainSourceCaps {
public:
    static constexpr int holdFrames = 24;
    static constexpr int rampFrames = 16;
    FilmGrainSourceCaps() { reset(); }
    void reset() {
        for (auto& plane : gains_) plane.fill(1.0);
        for (auto& plane : holds_) plane.fill(0);
    }
    void advance(bool freshFit) {
        if (!freshFit) return;
        for (int p = 0; p < 3; ++p) for (int x = 0; x < 256; ++x) {
            if (holds_[p][x]) --holds_[p][x];
            else if (gains_[p][x] < 1.0) gains_[p][x] += 1.0 / rampFrames;
        }
    }
    void preserveRange(int plane, int begin, int end) {
        if (plane < 0 || plane >= 3) return;
        if (begin < 0) begin = 0;
        if (end > 255) end = 255;
        for (int x = begin; x <= end; ++x) {
            gains_[plane][x] = 0.0;
            holds_[plane][x] = holdFrames;
        }
    }
    // Lower both bracketing knots. With the original knot positions retained,
    // the entire new curve is bounded above by the original curve, including
    // between knots. No unconstrained refit can overshoot a protected interval.
    void preserveCurveInterval(int plane, const uint8_t *values, uint32_t count,
        int begin, int end) {
        if (!count) return;
        uint32_t left = 0, right = count - 1;
        while (left + 1 < count && values[left + 1] <= begin) ++left;
        while (right > 0 && values[right - 1] >= end) --right;
        preserveRange(plane, values[left], values[right]);
    }
    bool lowerCurve(int plane, const uint8_t *values, uint8_t *scalings, uint32_t count) const {
        bool changed = false;
        for (uint32_t i = 0; i < count; ++i) {
            const auto reduced = static_cast<uint8_t>(std::lround(scalings[i] * gains_[plane][values[i]]));
            changed |= reduced != scalings[i];
            scalings[i] = reduced;
        }
        return changed;
    }
    double gain(int plane, int x) const { return gains_[plane][x]; }
private:
    std::array<std::array<double, 256>, 3> gains_;
    std::array<std::array<uint8_t, 256>, 3> holds_;
};

} // namespace fgsmodel
#endif
