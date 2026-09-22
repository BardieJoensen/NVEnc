// Nominal strength units, retained-base refits and finite-template gain conversion.
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainModel.h"
#include "NVEncFilmGrainTemplate.h"

using namespace fgsmodel;
static NV_ENC_FILM_GRAIN_PARAMS_AV1 model() {
    NV_ENC_FILM_GRAIN_PARAMS_AV1 p{};
    p.applyGrain = 1;
    p.numYPoints = p.numCbPoints = p.numCrPoints = 2;
    p.pointYValue[1] = p.pointCbValue[1] = p.pointCrValue[1] = 255;
    std::fill_n(p.pointYScaling, 2, 96);
    std::fill_n(p.pointCbScaling, 2, 80);
    std::fill_n(p.pointCrScaling, 2, 0);
    std::fill_n(p.arCoeffsYPlus128, 24, 128);
    std::fill_n(p.arCoeffsCbPlus128, 25, 128);
    std::fill_n(p.arCoeffsCrPlus128, 25, 128);
    return p;
}

int main() {
    float lut[FGS_STRENGTH_LUT_SIZE];
    for (int bits : {8, 10, 12}) for (unsigned shift = 0; shift < 4; ++shift)
        for (unsigned scale = 0; scale < 4; ++scale) {
            auto p = model(); p.grainScaleShift = shift; p.grainScalingMinus8 = scale;
            for (int plane = 0; plane < 3; ++plane) {
                const double gain = plane == 0 ? 1.25 : 1.5;
                const int strength = plane == 0 ? 96 : plane == 1 ? 80 : 0;
                // Independent physical units: strength / display denominator
                // times nominal Gaussian sigma in native sample values.
                const double expected = strength * gain * std::ldexp(32.0, bits - 8 - int(shift))
                    / (1U << (scale + 8));
                build_strength_lut(p, bits, lut, plane, gain);
                for (float value : lut) assert(value == expected);
            }
            p.chromaScalingFromLuma = 1;
            build_strength_lut(p, bits, lut, 2, 1.0);
            assert(lut[97] == 96 * std::ldexp(32.0, bits - 8 - int(shift)) / (1U << (scale + 8)));
        }

    // Source-minus-base refitting at the actual already-rounded base: retain=0
    // is deliberate. The supplied base must not be blended for a second time.
    for (int bits : {8, 10}) for (unsigned shift = 0; shift < 4; ++shift) {
        auto p = model(); p.grainScaleShift = shift;
        const auto before = p;
        const double depth = 1 << (bits - 8);
        FilmGrainLocalStrengthStats stats{};
        for (int x : {32, 128, 224}) {
            stats.blocks[x] = 16;
            stats.intensitySum[x] = 16 * x * depth;
            stats.varianceSum[x] = 16 * 13 * depth * depth; // 9 existing + 4 missing
            stats.baseVarianceSum[x] = 16 * 9 * depth * depth;
        }
        assert(refit_local_strength(stats, bits, 1.0, 0.0, p));
        build_strength_lut(p, bits, lut);
        for (int x : {32, 128, 224}) assert(std::abs(lut[x] - 2 * depth) < 1e-6);
        assert(p.grainScaleShift == shift && p.grainScalingMinus8 == before.grainScalingMinus8);
        assert(std::memcmp(p.pointCbScaling, before.pointCbScaling, sizeof(p.pointCbScaling)) == 0);
        assert(std::memcmp(p.pointCrScaling, before.pointCrScaling, sizeof(p.pointCrScaling)) == 0);
        assert(!film_grain_local_strength_fidelity(stats, p, bits, 1.0).needsSource(.001, .001));
        // A fixed shared scaling shift cannot represent arbitrarily strong
        // missing grain. Do not truncate or quietly change the chroma scale.
        p.grainScaleShift = 3;
        const auto bounded = p;
        for (int x : {32, 128, 224}) stats.varianceSum[x] = 16 * 409 * depth * depth;
        assert(!refit_local_strength(stats, bits, 1.0, 0.0, p));
        assert(std::memcmp(&p, &bounded, sizeof(p)) == 0);
    }

    for (unsigned shift = 0; shift < 4; ++shift) {
        auto p = model(); p.grainScaleShift = shift; p.arCoeffLag = 1;
        p.arCoeffsYPlus128[3] += 32; // 1/2 feedback at AR shift 6
        const double expected = 24.0 / (1U << shift);
        assert(film_grain_luma_dc_amplitude(p, 0.0) == expected);
        assert(std::abs(film_grain_luma_dc_amplitude(p, .5) - expected * std::sqrt(.75)) < 1e-12);
        p.arCoeffsYPlus128[3] += 32;
        assert(!std::isfinite(film_grain_luma_dc_amplitude(p, 0.0)));
        auto a = model(), b = a;
        a.numCbPoints = b.numCbPoints = a.numCrPoints = b.numCrPoints = 0;
        a.grainScaleShift = b.grainScaleShift = shift;
        std::fill_n(a.pointYScaling, 2, 1); std::fill_n(b.pointYScaling, 2, 2);
        // Absolute jitter floor is in 8-bit sigma units, not syntax codes.
        assert(film_grain_params_close(a, b) == (shift != 0));
        b.grainScaleShift = (shift + 1) % 4;
        assert(!film_grain_params_close(a, b));
    }

    auto p = model();
    for (double gain : {0.0, -1.0, std::numeric_limits<double>::quiet_NaN()}) {
        build_strength_lut(p, 10, lut, 0, gain);
        for (float value : lut) assert(!std::isfinite(value));
    }
    p.numCrPoints = 0;
    build_strength_lut(p, 10, lut, 2, 0.0);
    for (float value : lut) assert(value == 0); // Inactive component needs no gain.
    p.numYPoints = 15;
    assert(!film_grain_params_close(p, p));
    build_strength_lut(p, 10, lut);
    for (float value : lut) assert(!std::isfinite(value));

    // Finite gains use the actual rounded innovation, not an assumed exact
    // 32-code Gaussian. Independent AOM constants cover every depth/shift.
    const double innovation[3][4] = {
        {1021.43017578125, 255.8388671875, 63.82177734375, 16.0830078125},
        {16353.6416015625, 4089.34912109375, 1021.43017578125, 255.8388671875},
        {261658.265625, 65414.56640625, 16353.6416015625, 4089.34912109375},
    };
    std::array<uint8_t, 24> coeff{}; coeff.fill(128); coeff[23] += 116;
    std::array<uint16_t, 16> seeds{};
    for (unsigned i = 0; i < seeds.size(); ++i) seeds[i] = (i + 1) * 1031;
    for (int bits : {8, 10, 12}) for (unsigned shift = 0; shift < 4; ++shift) {
        const auto power = film_grain_luma_template_power(coeff.data(), 3, 7, bits, shift, seeds.data(), seeds.size());
        assert(power.valid && power.bitDepth == unsigned(bits) && power.grainShift == shift);
        assert(power.innovationSecondMoment == innovation[(bits - 8) / 2][shift]);
        const double sigma = std::ldexp(32.0, bits - 8 - int(shift));
        assert(std::abs(power.nominalLumaGain * sigma
            - std::sqrt(power.lumaPower * power.innovationSecondMoment)) < 1e-10);
    }
    std::cout << "Grain scale: native units, retained-base refits, DC/hold limits and finite nominal gains passed\n";
}
