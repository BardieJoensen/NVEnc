// A narrow but valid strength-curve change must not disappear between samples.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <random>
#include <set>
#include <vector>
#include "NVEncFilmGrainModel.h"

using namespace fgsmodel;

struct Curve {
    uint8_t *values, *scalings;
    uint32_t count;
};

static Curve curve(NV_ENC_FILM_GRAIN_PARAMS_AV1& p, int plane) {
    if (plane == 0) return {p.pointYValue, p.pointYScaling, p.numYPoints};
    if (plane == 1) return {p.pointCbValue, p.pointCbScaling, p.numCbPoints};
    return {p.pointCrValue, p.pointCrScaling, p.numCrPoints};
}

static void points(NV_ENC_FILM_GRAIN_PARAMS_AV1& p, int plane,
                   const std::vector<int>& positions, const std::vector<int>& amplitudes) {
    if (plane == 0) p.numYPoints = static_cast<uint32_t>(positions.size());
    if (plane == 1) p.numCbPoints = static_cast<uint32_t>(positions.size());
    if (plane == 2) p.numCrPoints = static_cast<uint32_t>(positions.size());
    auto c = curve(p, plane);
    for (size_t i = 0; i < positions.size(); ++i) {
        c.values[i] = static_cast<uint8_t>(positions[i]);
        c.scalings[i] = static_cast<uint8_t>(amplitudes[i]);
    }
}

static NV_ENC_FILM_GRAIN_PARAMS_AV1 constant_model() {
    NV_ENC_FILM_GRAIN_PARAMS_AV1 p = {};
    p.applyGrain = 1;
    p.arCoeffLag = 3;
    std::fill(std::begin(p.arCoeffsYPlus128), std::end(p.arCoeffsYPlus128), 128);
    std::fill(std::begin(p.arCoeffsCbPlus128), std::end(p.arCoeffsCbPlus128), 128);
    std::fill(std::begin(p.arCoeffsCrPlus128), std::end(p.arCoeffsCrPlus128), 128);
    for (int plane = 0; plane < 3; ++plane) points(p, plane, {0, 255}, {32, 32});
    return p;
}

// Exhaust every integer brightness independently of the comparator's choice
// of sample locations. Integer knots bound each linear segment, so this also
// bounds fractional brightness between them. All tested AR coefficients match.
static bool grid_oracle(NV_ENC_FILM_GRAIN_PARAMS_AV1 a, NV_ENC_FILM_GRAIN_PARAMS_AV1 b,
                        double tolerance) {
    double peak = 0.0, difference = 0.0;
    for (int plane = 0; plane < 3; ++plane) {
        const auto ca = curve(a, plane), cb = curve(b, plane);
        for (int x = 0; x < 256; ++x) {
            const double sa = eval_scaling_curve(ca.values, ca.scalings, ca.count, x)
                / (1 << (a.grainScalingMinus8 + 3));
            const double sb = eval_scaling_curve(cb.values, cb.scalings, cb.count, x)
                / (1 << (b.grainScalingMinus8 + 3));
            peak = std::max({peak, sa, sb});
            difference = std::max(difference, std::abs(sa - sb));
        }
    }
    return difference <= std::max(0.10, tolerance * peak);
}

static void random_curves(NV_ENC_FILM_GRAIN_PARAMS_AV1& p, std::mt19937& rng) {
    p.grainScalingMinus8 = rng() % 4;
    for (int plane = 0; plane < 3; ++plane) {
        const size_t count = 1 + rng() % (plane == 0 ? 14 : 10);
        std::set<int> xs;
        while (xs.size() < count) xs.insert(rng() % 256);
        std::vector<int> amplitudes;
        for (size_t i = 0; i < count; ++i) amplitudes.push_back(rng() % 256);
        points(p, plane, {xs.begin(), xs.end()}, amplitudes);
    }
}

int main() {
    for (int plane = 0; plane < 3; ++plane) {
        auto a = constant_model(), b = a;
        points(b, plane, {0, 6, 7, 8, 255}, {32, 32, 80, 32, 32});
        // The old 0,15,30,... grid sees identical curves, despite a 4 -> 10
        // code-value sigma change at brightness 7.
        if (film_grain_params_close(a, b) || film_grain_params_close(b, a)) {
            std::cerr << "FAIL: model reuse missed a narrow strength change on plane " << plane << '\n';
            return 1;
        }
        points(b, plane, {0, 6, 7, 8, 255}, {32, 32, 33, 32, 32});
        if (!film_grain_params_close(a, b)) return 2; // Existing jitter tolerance.
        points(b, plane, {0, 6, 7, 8, 255}, {32, 32, 32, 32, 32});
        if (!film_grain_params_close(a, b)) return 3; // Same curve, different knots.
        b = a;
        b.grainScalingMinus8 = 1;
        for (int c = 0; c < 3; ++c) points(b, c, {5, 128, 250}, {64, 64, 64});
        if (!film_grain_params_close(a, b)) return 4; // Same amplitude, different scaling shift.
    }
    std::mt19937 rng(20260911);
    int close = 0, changed = 0;
    constexpr int cases = 6000;
    for (int i = 0; i < cases; ++i) {
        auto a = constant_model();
        random_curves(a, rng);
        auto b = a;
        auto c = curve(b, rng() % 3);
        const int point = rng() % c.count;
        switch (i % 6) {
        case 0: break;
        case 1: c.scalings[point] = static_cast<uint8_t>(std::min(255, c.scalings[point] + 1)); break;
        case 2: c.scalings[point] = static_cast<uint8_t>(std::min(255, c.scalings[point] + 32)); break;
        case 3: c.scalings[point] = 0; break;
        case 4: b.grainScalingMinus8 = rng() % 4; break;
        case 5: random_curves(b, rng); break;
        }
        const double tolerance = (i % 3 + 1) * 0.025;
        const bool expected = grid_oracle(a, b, tolerance);
        if (film_grain_params_close(a, b, tolerance) != expected
            || film_grain_params_close(b, a, tolerance) != expected) {
            std::cerr << "FAIL: brightness-grid disagreement in case " << i << '\n';
            return 5;
        }
        expected ? ++close : ++changed;
    }
    if (close < 1000 || changed < 1000) return 6;
    std::cout << "Model hold: narrow luma/chroma changes, jitter and equivalent curves passed; "
              << cases << " grid-oracle cases (" << close << " close, " << changed << " changed) passed in both directions\n";
}
