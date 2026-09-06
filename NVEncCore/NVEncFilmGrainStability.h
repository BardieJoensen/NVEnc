// AV1 grain AR feedback stability. No decoder or GPU dependencies.
// Copyright (c) 2026 NVEnc contributors. MIT license, as NVEncFilmGrainModel.h.
#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <utility>
#include <vector>

namespace fgsmodel {
namespace stability_detail {

// A real-coefficient Laurent polynomial evaluated on the unit circle.
struct Polynomial {
    int degree;
    std::vector<double> c;
    explicit Polynomial(int d = 0) : degree(d), c(2 * d + 1, 0.0) {}
    double get(int k) const { return c[k + degree]; }
    double& at(int k) { return c[k + degree]; }
};

inline Polynomial product(const Polynomial& a, const Polynomial& b, bool conjugateA) {
    Polynomial out(a.degree + b.degree);
    for (int i = -a.degree; i <= a.degree; ++i) {
        for (int j = -b.degree; j <= b.degree; ++j) {
            out.at(i + j) += a.get(conjugateA ? -i : i) * b.get(j);
        }
    }
    return out;
}

// Certify positivity over an interval, rather than just sampling frequencies.
// A Taylor bound using the local slope and a global curvature bound encloses
// every point between samples, including flat minima. Near a boundary
// or the recursion limit, reject conservatively instead of accepting an
// unproven model. The caller can retain the original picture in that case.
inline bool positiveInterval(const Polynomial& p, double curvatureBound,
    double left, double right, int depth) {
    const double mid = (left + right) * 0.5;
    double value = p.get(0), slope = 0.0;
    for (int k = 1; k <= p.degree; ++k) {
        const double pair = p.get(k) + p.get(-k);
        value += pair * std::cos(k * mid);
        slope -= k * pair * std::sin(k * mid);
    }
    constexpr double tolerance = 1e-10;
    if (!std::isfinite(value) || value <= tolerance) return false;
    const double radius = (right - left) * 0.5;
    if (value - std::abs(slope) * radius - 0.5 * curvatureBound * radius * radius > tolerance) return true;
    if (depth == 0) return false;
    return positiveInterval(p, curvatureBound, left, mid, depth - 1)
        && positiveInterval(p, curvatureBound, mid, right, depth - 1);
}

inline bool positiveEverywhere(const Polynomial& p) {
    double curvatureBound = 0.0;
    double endpoint0 = p.get(0), endpointPi = p.get(0);
    for (int k = 1; k <= p.degree; ++k) {
        const double pair = p.get(k) + p.get(-k);
        curvatureBound += k * k * (std::abs(p.get(k)) + std::abs(p.get(-k)));
        endpoint0 += pair;
        endpointPi += (k & 1) ? -pair : pair;
    }
    if (!std::isfinite(curvatureBound) || endpoint0 <= 1e-10 || endpointPi <= 1e-10) return false;
    constexpr double pi = 3.14159265358979323846;
    return positiveInterval(p, curvatureBound, 0.0, pi, 24);
}

inline bool horizontalStable(std::array<double, 4> a, int degree) {
    for (int n = degree; n > 0; --n) {
        if (std::abs(a[n]) >= std::abs(a[0]) - 1e-10) return false;
        std::array<double, 4> next{};
        for (int i = 0; i < n; ++i) next[i] = a[0] * a[i] - a[n] * a[n - i];
        const double scale = next[0];
        if (!std::isfinite(scale) || scale <= 1e-10) return false;
        for (int i = 0; i < n; ++i) a[i] = next[i] / scale;
    }
    return true;
}
} // namespace stability_detail

// The AV1 raster-causal stencil includes lag previous rows and lag pixels to
// the left. Fourier transforming horizontally leaves a lag-order recurrence
// between rows. Schur reduction tests its poles without root finding. Each
// Schur inequality is a trigonometric polynomial; interval bounds certify it
// over ALL horizontal frequencies, including between frequency-grid points.
// Test the quantized coefficients that the decoder will actually use.
inline bool film_grain_ar_stable(const uint8_t *coeffsPlus128, unsigned lag, unsigned shift) {
    using namespace stability_detail;
    if (lag > 3 || shift < 6 || shift > 9 || !coeffsPlus128) return false;
    if (lag == 0) return true;
    const int d = static_cast<int>(lag);
    // Absolute contraction is a cheap, rigorous sufficient condition. It
    // also avoids ill-conditioned repeated Schur products for simple models
    // close to the unit boundary (for example a lone coefficient 63/64).
    unsigned absoluteSum = 0;
    for (unsigned i = 0; i < 2 * lag * (lag + 1); ++i) {
        absoluteSum += std::abs(static_cast<int>(coeffsPlus128[i]) - 128);
    }
    if (absoluteSum < (1U << shift)) return true;
    std::vector<Polynomial> a(d + 1, Polynomial(d));
    a[0].at(0) = 1.0;
    std::array<double, 4> horizontal{1.0, 0.0, 0.0, 0.0};
    int index = 0;
    for (int y = -d; y <= 0; ++y) {
        for (int x = -d; x <= d && (y < 0 || x < 0); ++x) {
            const double c = (static_cast<int>(coeffsPlus128[index++]) - 128) / static_cast<double>(1U << shift);
            a[-y].at(x) -= c;
            if (y == 0) horizontal[-x] = -c;
        }
    }
    if (!horizontalStable(horizontal, d)) return false;
    for (int n = d; n > 0; --n) {
        std::vector<Polynomial> next;
        double scale = 0.0;
        for (int i = 0; i < n; ++i) {
            auto lhs = product(a[0], a[i], true);
            const auto rhs = product(a[n - i], a[n], true);
            for (size_t k = 0; k < lhs.c.size(); ++k) {
                lhs.c[k] -= rhs.c[k];
                scale = std::max(scale, std::abs(lhs.c[k]));
            }
            next.push_back(std::move(lhs));
        }
        if (!std::isfinite(scale) || scale <= 1e-20) return false;
        for (auto& p : next) for (auto& v : p.c) v /= scale;
        if (!positiveEverywhere(next[0])) return false;
        a = std::move(next);
    }
    return true;
}
} // namespace fgsmodel
