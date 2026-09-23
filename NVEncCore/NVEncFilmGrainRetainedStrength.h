// Bounded integer strength calibration for an explicitly measured candidate.
// It chooses a proposal, not quality/population clearance. MIT license.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace fgsmodel {
struct FilmGrainRetainedStrengthTarget {
    unsigned channels = 0; // One colour variance, or native Y and averaged Y.
    std::array<double, 2> missing{}, source{};
};
struct FilmGrainRetainedStrengthMeasurement {
    bool valid = false;
    std::array<double, 2> variance{};
};
struct FilmGrainRetainedStrengthSample {
    unsigned strength = 0;
    FilmGrainRetainedStrengthMeasurement measurement{};
    double error = 0.0, balance = 0.0;
};
struct FilmGrainRetainedStrength {
    bool valid = false;
    unsigned strength = 0;
    double error = 0.0;
    // Includes all calls, even a rejected invalid/nonmonotone observation.
    std::vector<FilmGrainRetainedStrengthSample> samples;
};

// measure(strength) uses the same frozen model, base, populations and training
// seeds every time; check/holdout samples cannot select a strength. Integer
// display rounding makes variance nonlinear in strength, so a squared-scale
// extrapolation alone is insufficient for weak grain.
//
// With nondecreasing measured variances, max relative positive/negative errors
// bracket the minimax crossing for one or two targets. At most ten callbacks
// test the legal endpoints and adjacent integer strengths. Sampled violations
// reject; this does not prove monotonicity at every unmeasured strength, nor is
// it a global optimality claim for arbitrary callback functions. Independent
// actual source reconstruction (including base/grain covariance) still gates
// the selected proposal. The error is normalized by SOURCE variance.
template<class Measure>
FilmGrainRetainedStrength film_grain_calibrate_retained_strength(
    const FilmGrainRetainedStrengthTarget& target, Measure measure) {
    FilmGrainRetainedStrength out;
    if (target.channels < 1 || target.channels > 2) return out;
    bool positive = false;
    for (unsigned c = 0; c < target.channels; ++c) {
        if (!std::isfinite(target.missing[c]) || !std::isfinite(target.source[c])
            || target.source[c] <= 0.0 || target.missing[c] < 0.0
            || target.missing[c] > target.source[c]) return out;
        positive |= target.missing[c] > 0.0;
    }
    if (!positive) return out; // Exact-source/zero synthesis has its own proof.
    const auto sample = [&](unsigned strength) {
        FilmGrainRetainedStrengthSample s;
        s.strength = strength; s.measurement = measure(strength);
        double low = 0.0, high = 0.0;
        for (unsigned c = 0; c < target.channels; ++c) {
            const double v = s.measurement.variance[c];
            if (!std::isfinite(v) || v < 0.0) s.measurement.valid = false;
            const double error = (v-target.missing[c])/target.source[c];
            if (!std::isfinite(error)) s.measurement.valid = false;
            if (c == 0) low = high = error;
            else { low = std::min(low, error); high = std::max(high, error); }
        }
        s.error = std::max(std::abs(low), std::abs(high));
        s.balance = low + high;
        out.samples.push_back(s);
        return s;
    };
    auto low = sample(0), high = sample(255);
    if (!low.measurement.valid || !high.measurement.valid) return out;
    for (unsigned c = 0; c < target.channels; ++c)
        if (low.measurement.variance[c] > high.measurement.variance[c]) return out;
    // The crossing may lie outside the representable interval. An endpoint
    // remains a measurable proposal; its nonzero error cannot grant admission.
    if (low.balance < 0.0 && high.balance > 0.0) {
        for (unsigned step = 0; step < 8 && high.strength-low.strength > 1; ++step) {
            const auto mid = sample((low.strength+high.strength)/2);
            if (!mid.measurement.valid) return out;
            for (unsigned c = 0; c < target.channels; ++c)
                if (mid.measurement.variance[c] < low.measurement.variance[c]
                    || mid.measurement.variance[c] > high.measurement.variance[c]) return out;
            if (mid.balance < 0.0) low = mid;
            else high = mid;
        }
    }
    const auto best = std::min_element(out.samples.begin(), out.samples.end(),
        [](const auto& a, const auto& b) {
            return a.error < b.error || (a.error == b.error && a.strength < b.strength);
        });
    out.strength = best->strength; out.error = best->error; out.valid = true;
    return out;
}
} // namespace fgsmodel
