#ifndef NVENC_FILM_GRAIN_SOURCE_GUARD_H
#define NVENC_FILM_GRAIN_SOURCE_GUARD_H

#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>

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
        // validation remains independent. Callers require at least 8x8 source
        // samples, including valid partial blocks at the image boundary.
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

// A current source region's total spatial variance includes both detail and
// grain. It is deliberately a loose ceiling, not an estimate of removable
// noise. This independent luma check also covers small, bright regions that
// are ineligible for the near-flat active-range test above. Never infer chroma
// noise from clipped luma; the existing chroma eligibility remains unchanged.
struct FilmGrainSourceVarianceGuard {
    uint64_t conflictingBlocks = 0;
    double maxExcess = 0.0;
    bool invalid = false;

    double observe(double mean8, double sourceSigma8, double modeledSigma8,
        int width, int height) {
        if (width < 8 || height < 8) return 1.0;
        if (!std::isfinite(mean8) || !std::isfinite(sourceSigma8)
            || !std::isfinite(modeledSigma8) || sourceSigma8 < 0.0
            || modeledSigma8 < 0.0) {
            invalid = true;
            return 1.0;
        }
        // Small blocks and correlated genuine grain have uncertain sample
        // variance. Only a gross overestimate enters protection; the existing
        // finer near-flat guard still handles smaller exact-source conflicts.
        const double attack = std::max(3.0, 2.0 * sourceSigma8 + 1.0);
        if (modeledSigma8 <= attack) return 1.0;
        ++conflictingBlocks;
        maxExcess = std::max(maxExcess, modeledSigma8 - sourceSigma8);
        return (1.5 * sourceSigma8 + 0.5) / modeledSigma8;
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
            else if (gains_[p][x] < 1.0) gains_[p][x] = std::min(1.0, gains_[p][x] + 1.0 / rampFrames);
        }
    }
    void preserveRange(int plane, int begin, int end, double gain = 0.0) {
        if (plane < 0 || plane >= 3) return;
        if (begin < 0) begin = 0;
        if (end > 255) end = 255;
        gain = std::max(0.0, std::min(1.0, gain));
        for (int x = begin; x <= end; ++x) {
            gains_[plane][x] = std::min(gains_[plane][x], gain);
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

    // Match the normative eight-bit AV1 scaling lookup, including its fixed
    // point slope and rounding. The high-bit-depth lookup interpolates these
    // entries, so an entrywise bound also bounds the higher-depth table.
    static int lookup(const uint8_t *values, const uint8_t *scalings,
        uint32_t count, int x) {
        if (!count) return 0;
        if (x <= values[0]) return scalings[0];
        for (uint32_t i = 0; i + 1 < count; ++i) {
            if (x < values[i + 1]) {
                const int distance = values[i + 1] - values[i];
                const int slope = (static_cast<int>(scalings[i + 1]) - scalings[i])
                    * ((65536 + distance / 2) / distance);
                return scalings[i] + ((slope * (x - values[i]) + 32768) >> 16);
            }
        }
        return scalings[count - 1];
    }

    // Fit a bounded curve around the actual protected levels instead of
    // zeroing the old model's sometimes distant bracketing knots. Greedy
    // removal only lowers the current polyline. A final normative-LUT check
    // handles interpolation rounding and never permits an envelope overshoot.
    // At most 256 samples and O(256^2) simple operations; no heap allocation.
    uint32_t refitCurve(int plane, uint8_t *values, uint8_t *scalings,
        uint32_t count, uint32_t capacity, bool& changed) const {
        if (!count) return count;
        bool limited = false;
        std::array<int, 256> envelope;
        for (int x = 0; x < 256; ++x) {
            const int original = lookup(values, scalings, count, x);
            envelope[x] = static_cast<int>(std::floor(original * gains_[plane][x]));
            limited |= envelope[x] != original;
        }
        if (!limited) return count;
        changed = true;
        struct Point { int value, previous, next; bool live; };
        std::array<Point, 256> points;
        for (int x = 0; x < 256; ++x) points[x] = {envelope[x], x - 1, x + 1, true};
        points[255].next = -1;
        for (int remaining = 256; remaining > static_cast<int>(capacity); --remaining) {
            double best = std::numeric_limits<double>::infinity();
            int remove = -1, leftValue = 0, rightValue = 0;
            for (int b = points[0].next; b != 255; b = points[b].next) {
                const int a = points[b].previous, c = points[b].next;
                int ya = points[a].value, yc = points[c].value;
                const double atB = (ya * (c - b) + yc * (b - a)) / static_cast<double>(c - a);
                if (atB > points[b].value) {
                    const double gain = points[b].value / atB;
                    ya = static_cast<int>(std::floor(ya * gain));
                    yc = static_cast<int>(std::floor(yc * gain));
                }
                double cost = (b - a) * (points[a].value + points[b].value)
                    + (c - b) * (points[b].value + points[c].value)
                    - (c - a) * (ya + yc);
                if (points[a].previous >= 0)
                    cost += (a - points[a].previous) * (points[a].value - ya);
                if (points[c].next >= 0)
                    cost += (points[c].next - c) * (points[c].value - yc);
                if (cost < best) { best = cost; remove = b; leftValue = ya; rightValue = yc; }
            }
            const int a = points[remove].previous, c = points[remove].next;
            points[a].value = leftValue;
            points[c].value = rightValue;
            points[a].next = c;
            points[c].previous = a;
            points[remove].live = false;
        }
        uint32_t size = 0;
        for (int x = 0; x >= 0; x = points[x].next) {
            values[size] = static_cast<uint8_t>(x);
            scalings[size++] = static_cast<uint8_t>(points[x].value);
        }
        for (uint32_t i = 0; i + 1 < size; ++i) {
            // Lowering endpoints cannot increase either neighboring segment.
            for (;;) {
                int excess = 0;
                for (int x = values[i]; x <= values[i + 1]; ++x)
                    excess = std::max(excess, lookup(values + i, scalings + i, 2, x) - envelope[x]);
                if (!excess) break;
                scalings[i] = static_cast<uint8_t>(std::max(0, static_cast<int>(scalings[i]) - excess));
                scalings[i + 1] = static_cast<uint8_t>(std::max(0, static_cast<int>(scalings[i + 1]) - excess));
            }
        }
        return size;
    }
    double gain(int plane, int x) const { return gains_[plane][x]; }
    bool hasProtection(int plane) const {
        return std::any_of(gains_[plane].begin(), gains_[plane].end(),
            [](double gain) { return gain < 1.0; });
    }
private:
    std::array<std::array<double, 256>, 3> gains_;
    std::array<std::array<uint8_t, 256>, 3> holds_;
};

} // namespace fgsmodel
#endif
