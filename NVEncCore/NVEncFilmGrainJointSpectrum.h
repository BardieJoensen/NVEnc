// Quantized AV1 4:2:0 grain transfer, including the luma-driven chroma term.
// CPU-only; MIT license, as NVEncFilmGrainModel.h.
// Experimental offline analysis; no encoder gain/eligibility policy uses this.
#pragma once
#include "NVEncFilmGrainSpectrum.h"

namespace fgsmodel {
struct FilmGrainJointSpectrum {
    bool valid = false;
    double lumaPower = 0.0;
    double averagedLumaPower = 0.0;
    std::array<double, 2> chromaPower{};
    std::array<double, 2> chromaHighpassFraction{};
    std::array<double, 2> lumaChromaCovariance{};
};

// The chroma recursion filters BOTH its independent innovation and the
// downsampled luma-grain input. Adding k^2 * var(avgY) after the chroma AR
// filter misses this interaction. Evaluate the actual quantized transfer.
// This stationary calculation excludes finite-template borders, rounding,
// clipping and block overlap; decoded witnesses remain necessary. `valid`
// denotes finite arithmetic only: it does not establish causal AR stability.
inline FilmGrainJointSpectrum film_grain_joint_spectrum(const uint8_t *y,
    const uint8_t *cb, const uint8_t *cr, unsigned lag, unsigned shift) {
    using namespace spectrum_detail;
    FilmGrainJointSpectrum result;
    if (!y || !cb || !cr || lag > 3 || shift < 6 || shift > 9) return result;
    const auto unpack = [&](const uint8_t *input) {
        std::array<double, 24> coeff{};
        unsigned i = 0, j = 0;
        for (int dy = -3; dy <= 0; ++dy) for (int dx = -3; dx <= 3 && (dy < 0 || dx < 0); ++dx) {
            if (dy >= -static_cast<int>(lag) && dx >= -static_cast<int>(lag) && dx <= static_cast<int>(lag))
                coeff[j] = (int(input[i++]) - 128) / double(1U << shift);
            ++j;
        }
        return coeff;
    };
    const auto yc = unpack(y);
    const std::array<std::array<double, 24>, 2> cc = {unpack(cb), unpack(cr)};
    const unsigned couplingIndex = 2 * lag * (lag + 1);
    const std::array<double, 2> coupling = {
        (int(cb[couplingIndex]) - 128) / double(1U << shift),
        (int(cr[couplingIndex]) - 128) / double(1U << shift)};
    const auto& grid = frequencies();
    const auto denominator = [](const std::array<double, 24>& coeff, const Frequency& point) {
        std::array<double, 2> d = {1.0, 0.0};
        for (size_t i = 0; i < coeff.size(); ++i) {
            d[0] -= coeff[i] * point.real[i];
            d[1] -= coeff[i] * point.imag[i];
        }
        return d;
    };
    std::array<double, gridSize * gridSize> yp{};
    for (size_t i = 0; i < grid.size(); ++i) {
        const auto d = denominator(yc, grid[i]);
        const double energy = d[0] * d[0] + d[1] * d[1];
        if (!std::isfinite(energy) || energy < 1e-20) return result;
        yp[i] = 1.0 / energy;
        result.lumaPower += yp[i] / grid.size();
    }
    constexpr int side = gridSize / 2;
    constexpr double pi = 3.14159265358979323846;
    for (int fy = 0; fy < side; ++fy) for (int fx = 0; fx < side; ++fx) {
        // A 2x2 average followed by 2x2 decimation has four aliases. The
        // 1/4 alias factor is essential: white luma averages to variance 1/4.
        double averaged = 0.0;
        for (int ay = 0; ay < 2; ++ay) for (int ax = 0; ax < 2; ++ax) {
            const int x = fx + ax * side, yy = fy + ay * side;
            const double a = std::cos(pi * x / gridSize) * std::cos(pi * yy / gridSize);
            averaged += a * a * yp[yy * gridSize + x] * 0.25;
        }
        result.averagedLumaPower += averaged / (side * side);
        const auto& point = grid[(fy * 2) * gridSize + fx * 2];
        for (int plane = 0; plane < 2; ++plane) {
            const auto d = denominator(cc[plane], point);
            const double energy = d[0] * d[0] + d[1] * d[1];
            if (!std::isfinite(energy) || energy < 1e-20) return result;
            const double power = (1.0 + coupling[plane] * coupling[plane] * averaged) / energy;
            result.chromaPower[plane] += power / (side * side);
            result.chromaHighpassFraction[plane] += power * point.highpassPower / (side * side);
            result.lumaChromaCovariance[plane] += coupling[plane] * averaged * d[0] / energy / (side * side);
        }
    }
    for (int plane = 0; plane < 2; ++plane) {
        if (!std::isfinite(result.chromaPower[plane]) || result.chromaPower[plane] <= 0.0) return result;
        result.chromaHighpassFraction[plane] /= result.chromaPower[plane];
    }
    result.valid = std::isfinite(result.lumaPower) && result.lumaPower > 0.0
        && std::isfinite(result.averagedLumaPower) && result.averagedLumaPower > 0.0;
    return result;
}
} // namespace fgsmodel
