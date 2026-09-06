// Reject strongly directional periodic texture in automatically fitted grain.
// CPU-only; MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>

namespace fgsmodel {
struct FilmGrainSpectrum {
    double peakToMean = 0.0;
    double peakToRing = 0.0;
};
namespace spectrum_detail {
constexpr int gridSize = 64;
struct Frequency {
    std::array<double, 24> real{}, imag{};
    double radius = 0.0;
};
inline const std::array<Frequency, gridSize * gridSize>& frequencies() {
    static const auto grid = [] {
        std::array<Frequency, gridSize * gridSize> result{};
        constexpr double pi = 3.14159265358979323846;
        for (int fy = 0; fy < gridSize; ++fy) for (int fx = 0; fx < gridSize; ++fx) {
            auto& point = result[fy * gridSize + fx];
            const double u = (fx < gridSize / 2 ? fx : fx - gridSize) / double(gridSize);
            const double v = (fy < gridSize / 2 ? fy : fy - gridSize) / double(gridSize);
            point.radius = std::hypot(u, v);
            int i = 0;
            for (int y = -3; y <= 0; ++y) for (int x = -3; x <= 3 && (y < 0 || x < 0); ++x) {
                const double phase = 2.0 * pi * (u * x + v * y);
                point.real[i] = std::cos(phase); point.imag[i++] = std::sin(phase);
            }
        }
        return result;
    }();
    return grid;
}
} // namespace spectrum_detail

// The AR transfer power is 1/|1 - sum(c_xy exp(i*(x*u+y*v)))|^2.
// Film grain can have a broad radial peak (including high-pass grain), so a
// peak alone is not a defect. Reject only a peak away from DC that exceeds
// both the whole-spectrum mean by 16x (12 dB) and the same-radius mean by 4x
// (6 dB). The latter separates a diagonal mesh from coarse isotropic grain.
// These are conservative automatic-synthesis limits, not conformance rules
// or a proof of perceptual quality. Rejection preserves the original picture.
inline FilmGrainSpectrum film_grain_ar_spectrum(const uint8_t *coeff, unsigned lag, unsigned shift) {
    using namespace spectrum_detail;
    FilmGrainSpectrum result;
    if (!coeff || lag > 3 || shift < 6 || shift > 9) {
        result.peakToMean = result.peakToRing = std::numeric_limits<double>::infinity();
        return result;
    }
    std::array<double, 24> values{};
    unsigned input = 0, output = 0;
    for (int y = -3; y <= 0; ++y) for (int x = -3; x <= 3 && (y < 0 || x < 0); ++x) {
        if (y >= -static_cast<int>(lag) && x >= -static_cast<int>(lag) && x <= static_cast<int>(lag))
            values[output] = (int(coeff[input++]) - 128) / double(1U << shift);
        ++output;
    }
    const auto& grid = frequencies();
    std::array<double, gridSize * gridSize> power{};
    double sum = 0.0, peak = 0.0;
    size_t peakIndex = 0;
    for (size_t i = 0; i < grid.size(); ++i) {
        double real = 1.0, imag = 0.0;
        for (size_t j = 0; j < values.size(); ++j) {
            real -= values[j] * grid[i].real[j]; imag -= values[j] * grid[i].imag[j];
        }
        const double denominator = real * real + imag * imag;
        if (denominator < 1e-20 || !std::isfinite(denominator)) {
            result.peakToMean = result.peakToRing = std::numeric_limits<double>::infinity();
            return result;
        }
        power[i] = 1.0 / denominator; sum += power[i];
        if (grid[i].radius >= 1.0 / 16.0 && power[i] > peak) { peak = power[i]; peakIndex = i; }
    }
    double ringSum = 0.0;
    unsigned ringCount = 0;
    for (size_t i = 0; i < grid.size(); ++i) {
        if (std::abs(grid[i].radius - grid[peakIndex].radius) < 1.0 / gridSize) {
            ringSum += power[i]; ++ringCount;
        }
    }
    result.peakToMean = peak / (sum / grid.size());
    result.peakToRing = peak / (ringSum / ringCount);
    return result;
}
inline bool film_grain_ar_spectrum_safe(const uint8_t *coeff, unsigned lag, unsigned shift) {
    const auto spectrum = film_grain_ar_spectrum(coeff, lag, shift);
    return std::isfinite(spectrum.peakToMean) && std::isfinite(spectrum.peakToRing)
        && !(spectrum.peakToMean > 16.0 && spectrum.peakToRing > 4.0);
}
} // namespace fgsmodel
