// Finite AV1 luma-template analysis for offline joint-colour experiments.
// No encoder call sites. Completion does not certify a model as safe or grain.
// MIT license, as NVEncFilmGrainModel.h. Gaussian data has its own BSD notice.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include "NVEncFilmGrainGaussian.h"

namespace fgsmodel {
struct FilmGrainLumaTemplate {
    static constexpr unsigned width = 82, height = 73;
    std::array<int16_t, width * height> samples{};
    unsigned clipped = 0;
    unsigned filtered = 0;
};
struct FilmGrainLumaTemplatePower {
    bool valid = false;
    unsigned bitDepth = 0, grainShift = 0;
    double innovationSecondMoment = 0.0; // Actual integer Gaussian table after rounding.
    double lumaPower = 0.0;
    double averagedLumaPower = 0.0;
    double roundedAverageLumaPower = 0.0;
    double lumaMean = 0.0; // Native template units, before display scaling.
    // Convert the actual-innovation-normalized powers above to the nominal
    // gain convention consumed by build_strength_lut/refit_local_strength:
    // native template RMS / (32 * 2^(bitDepth - 8 - grainShift)). These include
    // template mean energy, not just variance. Never reuse at a different
    // model/depth/shift. The rounded average is the chroma AR driver, not the
    // complete chroma template or a chroma strength-lookup prediction.
    double nominalLumaGain = 0.0;
    double nominalRoundedAverageLumaGain = 0.0;
    double clippedFraction = 0.0;
    size_t seeds = 0;
};
namespace template_detail {
// C++17 does not specify arithmetic right shift for a negative signed value.
inline int floor_shift(const int value, const unsigned shift) {
    const int divisor = 1 << shift;
    return value >= 0 ? value / divisor : -((-value + divisor - 1) / divisor);
}
inline unsigned random_index(uint16_t& state) {
    const unsigned bit = (state ^ (state >> 1) ^ (state >> 3) ^ (state >> 12)) & 1;
    state = static_cast<uint16_t>((state >> 1) | (bit << 15));
    return state >> 5;
}
inline bool parameters(const uint8_t* coeff, unsigned lag, unsigned arShift,
    unsigned bitDepth, unsigned grainShift) {
    return coeff && lag <= 3 && arShift >= 6 && arShift <= 9
        && (bitDepth == 8 || bitDepth == 10 || bitDepth == 12) && grainShift <= 3;
}
} // namespace template_detail

// The initial 3-row/3-column border is unfiltered, as in AV1. Generate the
// whole normative luma template, including integer rounding and internal
// clipping. This does not add grain to a picture or implement block overlap.
inline bool film_grain_luma_template(const uint8_t* coeff, unsigned lag,
    unsigned arShift, unsigned bitDepth, unsigned grainShift, uint16_t seed,
    FilmGrainLumaTemplate& output) {
    using namespace template_detail;
    output = {};
    if (!parameters(coeff, lag, arShift, bitDepth, grainShift)) return false;
    const unsigned gaussianShift = 12 - bitDepth + grainShift;
    const int gaussianRounding = (1 << gaussianShift) / 2;
    for (auto& value : output.samples)
        value = static_cast<int16_t>(floor_shift(gaussian[random_index(seed)]
            + gaussianRounding, gaussianShift));
    const int low = -(1 << (bitDepth - 1)), high = (1 << (bitDepth - 1)) - 1;
    for (int y = 3; y < int(output.height); ++y) {
        for (int x = 3; x < int(output.width) - 3; ++x) {
            int prediction = 0;
            unsigned tap = 0;
            for (int dy = -int(lag); dy <= 0; ++dy)
                for (int dx = -int(lag); dx <= int(lag) && (dy < 0 || dx < 0); ++dx)
                    prediction += (int(coeff[tap++]) - 128)
                        * output.samples[(y + dy) * output.width + x + dx];
            auto& sample = output.samples[y * output.width + x];
            const int value = sample + floor_shift(prediction + (1 << (arShift - 1)), arShift);
            output.clipped += value < low || value > high;
            ++output.filtered;
            sample = static_cast<int16_t>((std::clamp)(value, low, high));
        }
    }
    return true;
}

// Average exactly over the 16x16 possible AV1 block offsets for each supplied
// seed. Normalize second moments by the normative innovation's second moment.
// This accounts for finite boundaries, clipping and template rounding, unlike
// a stationary spectrum. It excludes display scaling, picture clipping and
// overlap. `averagedLumaPower` uses an unrounded 2x2 mean; the rounded field is
// the actual pre-scaling chroma driver. Seed coverage is explicit, not a
// confidence bound; validate on separate seeds and decoded pictures.
inline FilmGrainLumaTemplatePower film_grain_luma_template_power(
    const uint8_t* coeff, unsigned lag, unsigned arShift, unsigned bitDepth,
    unsigned grainShift, const uint16_t* seeds, size_t seedCount) {
    using namespace template_detail;
    FilmGrainLumaTemplatePower result;
    if (!parameters(coeff, lag, arShift, bitDepth, grainShift)
        || !seeds || seedCount == 0 || seedCount > 65536) return result;
    const unsigned gaussianShift = 12 - bitDepth + grainShift;
    double innovation = 0.0;
    for (const int value : gaussian) {
        const double sample = floor_shift(value + (1 << gaussianShift) / 2, gaussianShift);
        innovation += sample * sample / gaussian.size();
    }
    double count = 0.0, clips = 0.0, filtered = 0.0;
    for (size_t s = 0; s < seedCount; ++s) {
        FilmGrainLumaTemplate grain;
        if (!film_grain_luma_template(coeff, lag, arShift, bitDepth, grainShift, seeds[s], grain)) return {};
        clips += grain.clipped; filtered += grain.filtered;
        // Offset + position yields 31 distinct 2x2 pairs, with triangular
        // multiplicity 1..16..1 on each axis. This replaces 65,536 repeats.
        for (int yy = 0; yy < 31; ++yy) for (int xx = 0; xx < 31; ++xx) {
            const int weight = std::min(yy + 1, 31 - yy) * std::min(xx + 1, 31 - xx);
            int sum = 0;
            for (int dy = 0; dy < 2; ++dy) for (int dx = 0; dx < 2; ++dx) {
                const int value = grain.samples[(9 + 2 * yy + dy) * grain.width + 9 + 2 * xx + dx];
                result.lumaPower += value * value * (weight * .25);
                result.lumaMean += value * (weight * .25);
                sum += value;
            }
            result.averagedLumaPower += (sum * .25) * (sum * .25) * weight;
            const double rounded = floor_shift(sum + 2, 2);
            result.roundedAverageLumaPower += rounded * rounded * weight;
            count += weight;
        }
    }
    result.lumaPower /= count * innovation;
    result.averagedLumaPower /= count * innovation;
    result.roundedAverageLumaPower /= count * innovation;
    result.lumaMean /= count;
    result.clippedFraction = clips / filtered;
    result.bitDepth = bitDepth;
    result.grainShift = grainShift;
    result.innovationSecondMoment = innovation;
    const double nominalSigma = std::ldexp(32.0, int(bitDepth) - 8 - int(grainShift));
    result.nominalLumaGain = std::sqrt(result.lumaPower * innovation) / nominalSigma;
    result.nominalRoundedAverageLumaGain = std::sqrt(result.roundedAverageLumaPower * innovation) / nominalSigma;
    result.seeds = seedCount;
    result.valid = true;
    return result;
}
} // namespace fgsmodel
