// Finite 4:2:0 colour-template model for experimental retention fitting.
// This is not complete displayed-pixel synthesis or source/model qualification.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainTemplate.h"

namespace fgsmodel {
struct FilmGrainJointTemplateParameters {
    unsigned bitDepth = 0, lag = 0, arShift = 0, grainShift = 0;
    // Active means a scaling curve is PRESENT (or chroma-from-luma is used).
    // A present all-zero curve still generates an internal colour template.
    // Full AV1 point-count/shared syntax validation belongs to the caller.
    bool lumaActive = false, cbActive = false, crActive = false;
    std::array<uint8_t, 24> y{};
    std::array<uint8_t, 25> cb{}, cr{};
    bool valid() const {
        return template_detail::parameters(y.data(), lag, arShift, bitDepth, grainShift);
    }
    bool operator==(const FilmGrainJointTemplateParameters& b) const {
        return bitDepth == b.bitDepth && lag == b.lag && arShift == b.arShift && grainShift == b.grainShift
            && lumaActive == b.lumaActive && cbActive == b.cbActive && crActive == b.crActive
            && y == b.y && cb == b.cb && cr == b.cr;
    }
};
struct FilmGrainChromaTemplate {
    static constexpr unsigned width = 44, height = 38;
    std::array<int16_t, width * height> samples{};
    unsigned clipped = 0, filtered = 0;
};
struct FilmGrainJointTemplate {
    bool valid = false;
    FilmGrainJointTemplateParameters parameters{};
    uint16_t seed = 0;
    FilmGrainLumaTemplate y{};
    FilmGrainChromaTemplate cb{}, cr{};
};

// Generate all three normative finite templates. Cb/Cr reset their random
// registers independently; chroma AR uses the rounded 2x2 *native template*
// luma driver, not displayed luma or the horizontal strength-lookup pair.
inline bool film_grain_joint_template(const FilmGrainJointTemplateParameters& p,
    uint16_t seed, FilmGrainJointTemplate& out) {
    using namespace template_detail;
    out = {};
    if (!p.valid()) return false;
    if (p.lumaActive && !film_grain_luma_template(p.y.data(), p.lag, p.arShift,
        p.bitDepth, p.grainShift, seed, out.y)) return false;
    const unsigned gaussianShift = 12 - p.bitDepth + p.grainShift;
    const int rounding = (1 << gaussianShift) / 2;
    const int low = -(1 << (p.bitDepth - 1)), high = (1 << (p.bitDepth - 1)) - 1;
    for (unsigned plane = 0; plane < 2; ++plane) {
        if (!(plane == 0 ? p.cbActive : p.crActive)) continue;
        auto& chroma = plane == 0 ? out.cb : out.cr;
        const auto& coeff = plane == 0 ? p.cb : p.cr;
        const unsigned line = plane == 0 ? 7 : 11;
        uint16_t state = seed ^ (((line * 37 + 178) & 255) << 8) ^ ((line * 173 + 105) & 255);
        for (auto& value : chroma.samples)
            value = static_cast<int16_t>(floor_shift(gaussian[random_index(state)] + rounding, gaussianShift));
        for (int y = 3; y < int(chroma.height); ++y) for (int x = 3; x < int(chroma.width) - 3; ++x) {
            int prediction = 0;
            unsigned tap = 0;
            for (int dy = -int(p.lag); dy <= 0; ++dy)
                for (int dx = -int(p.lag); dx <= int(p.lag) && (dy < 0 || dx < 0); ++dx)
                    prediction += (int(coeff[tap++]) - 128) * chroma.samples[(y + dy) * chroma.width + x + dx];
            if (p.lumaActive) {
                const unsigned ly = 2 * (y - 3) + 3, lx = 2 * (x - 3) + 3;
                int sum = 0;
                for (unsigned dy = 0; dy < 2; ++dy) for (unsigned dx = 0; dx < 2; ++dx)
                    sum += out.y.samples[(ly + dy) * out.y.width + lx + dx];
                prediction += (int(coeff[tap]) - 128) * floor_shift(sum + 2, 2);
            }
            auto& value = chroma.samples[y * chroma.width + x];
            const int filtered = value + floor_shift(prediction + (1 << (p.arShift - 1)), p.arShift);
            chroma.clipped += filtered < low || filtered > high;
            ++chroma.filtered;
            value = static_cast<int16_t>(std::clamp(filtered, low, high));
        }
    }
    out.parameters = p; out.seed = seed; out.valid = true;
    return true;
}

struct FilmGrainJointTemplateMoments {
    bool valid = false;
    FilmGrainJointTemplateParameters parameters{};
    size_t seeds = 0;
    // Native, BEFORE strength scaling/output rounding/overlap/picture clipping.
    std::array<double, 3> mean{}, componentSecondMoment{}, nominalGain{}, clippedFraction{};
    // Common coordinates in fixed order [unrounded average Y, Cb, Cr].
    // This Y is distinct from the rounded AR driver. Moments include means;
    // a covariance caller must subtract mean[i]*mean[j] explicitly.
    std::array<double, 9> jointSecondMoment{};
    double driverMean = 0.0, driverSecondMoment = 0.0;
    std::array<double, 2> driverColourSecondMoment{};
};

// Exact enumeration of all 16x16 block offsets, reduced to their triangular
// multiplicities. Each offset uses a 32x32 Y / 16x16 Cb/Cr block. A finite seed
// ensemble is declared evidence, not a worst-seed bound. Never transfer gains
// between parameter sets, depths, shifts, or active-component configurations.
inline FilmGrainJointTemplateMoments film_grain_joint_template_moments(
    const FilmGrainJointTemplateParameters& p, const uint16_t* seeds, size_t seedCount) {
    using namespace template_detail;
    FilmGrainJointTemplateMoments out;
    if (!p.valid() || !seeds || seedCount == 0 || seedCount > 65536) return out;
    double count = 0.0;
    std::array<double, 3> clips{}, filtered{};
    for (size_t s = 0; s < seedCount; ++s) {
        FilmGrainJointTemplate grain;
        if (!film_grain_joint_template(p, seeds[s], grain)) return {};
        clips[0] += grain.y.clipped; clips[1] += grain.cb.clipped; clips[2] += grain.cr.clipped;
        filtered[0] += grain.y.filtered; filtered[1] += grain.cb.filtered; filtered[2] += grain.cr.filtered;
        for (int yy = 0; yy < 31; ++yy) for (int xx = 0; xx < 31; ++xx) {
            const int weight = std::min(yy + 1, 31 - yy) * std::min(xx + 1, 31 - xx);
            int sum = 0;
            for (int dy = 0; dy < 2; ++dy) for (int dx = 0; dx < 2; ++dx) {
                const int y = grain.y.samples[(9 + 2 * yy + dy) * grain.y.width + 9 + 2 * xx + dx];
                sum += y; out.componentSecondMoment[0] += double(y) * y * (.25 * weight);
            }
            const double cb = grain.cb.samples[(6 + yy) * grain.cb.width + 6 + xx];
            const double cr = grain.cr.samples[(6 + yy) * grain.cr.width + 6 + xx];
            const std::array<double, 3> values{{sum * .25, cb, cr}};
            for (unsigned i = 0; i < 3; ++i) {
                out.mean[i] += values[i] * weight;
                if (i) out.componentSecondMoment[i] += values[i] * values[i] * weight;
                for (unsigned j = 0; j < 3; ++j) out.jointSecondMoment[i * 3 + j] += values[i] * values[j] * weight;
            }
            const double driver = floor_shift(sum + 2, 2);
            out.driverMean += driver * weight;
            out.driverSecondMoment += driver * driver * weight;
            out.driverColourSecondMoment[0] += driver * cb * weight;
            out.driverColourSecondMoment[1] += driver * cr * weight;
            count += weight;
        }
    }
    const double nominal = std::ldexp(32.0, int(p.bitDepth) - 8 - int(p.grainShift));
    for (unsigned i = 0; i < 3; ++i) {
        out.mean[i] /= count; out.componentSecondMoment[i] /= count;
        out.nominalGain[i] = std::sqrt(out.componentSecondMoment[i]) / nominal;
        out.clippedFraction[i] = filtered[i] ? clips[i] / filtered[i] : 0.0;
    }
    for (auto& m : out.jointSecondMoment) m /= count;
    out.driverMean /= count; out.driverSecondMoment /= count;
    for (auto& m : out.driverColourSecondMoment) m /= count;
    out.parameters = p; out.seeds = seedCount; out.valid = true;
    return out;
}
} // namespace fgsmodel
