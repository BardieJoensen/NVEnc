// Explicit offline evidence for the final 4:2:0 model sent to NVENC.
// Disabled unless a bounded joint probe requests template seeds. This is not
// a retention acceptance test or an estimate of complete displayed synthesis.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainJointTemplate.h"
#include "../NVEncSDK/Common/inc/nvEncodeAPI.h"
#include "../json/json.hpp"
#include <set>
#include <stdexcept>
#include <vector>

namespace fgsmodel {
inline std::vector<uint16_t> film_grain_probe_template_seeds(const nlohmann::json& manifest) {
    if (!manifest.contains("template_seeds")) return {};
    const auto& input = manifest.at("template_seeds");
    if (!input.is_array() || input.empty() || input.size() > 32)
        throw std::runtime_error("joint probe requires 1..32 explicit template seeds");
    std::set<uint16_t> seen;
    std::vector<uint16_t> seeds;
    for (const auto& item : input) {
        if (!item.is_number_integer() || item < 0 || item > 65535)
            throw std::runtime_error("joint probe template seed must be an integer in 0..65535");
        const auto seed = item.get<uint16_t>();
        if (!seen.insert(seed).second) throw std::runtime_error("duplicate joint probe template seed");
        seeds.push_back(seed);
    }
    return seeds;
}

// Validate the signalled 4:2:0 syntax before using fixed arrays. Grain-off
// frames ignore stale model fields, as the decoder does. Presence of a zero
// strength curve still enables the internal template for that component.
inline bool film_grain_model_template_parameters(const NV_ENC_FILM_GRAIN_PARAMS_AV1& p,
    unsigned depth, FilmGrainJointTemplateParameters& out) {
    out = {};
    if (depth != 8 && depth != 10 && depth != 12) return false;
    FilmGrainJointTemplateParameters candidate{depth, 0, 6, 0};
    candidate.y.fill(128); candidate.cb.fill(128); candidate.cr.fill(128);
    if (!p.applyGrain) { out = candidate; return true; }
    if (p.numYPoints > 14 || p.numCbPoints > 10 || p.numCrPoints > 10
        || (p.chromaScalingFromLuma && (p.numCbPoints || p.numCrPoints))
        || (!p.numYPoints && (p.numCbPoints || p.numCrPoints))
        || ((p.numCbPoints == 0) != (p.numCrPoints == 0))
        || (p.numCbPoints && p.cbOffset > 511) || (p.numCrPoints && p.crOffset > 511)) return false;
    const unsigned count[3] = {p.numYPoints, p.numCbPoints, p.numCrPoints};
    const uint8_t* values[3] = {p.pointYValue, p.pointCbValue, p.pointCrValue};
    for (unsigned plane = 0; plane < 3; ++plane)
        for (unsigned i = 1; i < count[plane]; ++i)
            if (values[plane][i] <= values[plane][i - 1]) return false;
    candidate.lag = p.arCoeffLag; candidate.arShift = p.arCoeffShiftMinus6 + 6;
    candidate.grainShift = p.grainScaleShift;
    candidate.lumaActive = p.numYPoints > 0;
    candidate.cbActive = p.numCbPoints > 0 || p.chromaScalingFromLuma;
    candidate.crActive = p.numCrPoints > 0 || p.chromaScalingFromLuma;
    const unsigned taps = 2 * candidate.lag * (candidate.lag + 1);
    if (candidate.lumaActive) std::copy_n(p.arCoeffsYPlus128, taps, candidate.y.begin());
    if (candidate.cbActive) std::copy_n(p.arCoeffsCbPlus128, taps + candidate.lumaActive, candidate.cb.begin());
    if (candidate.crActive) std::copy_n(p.arCoeffsCrPlus128, taps + candidate.lumaActive, candidate.cr.begin());
    out = candidate;
    return true;
}

inline nlohmann::json film_grain_final_model_evidence(const NV_ENC_FILM_GRAIN_PARAMS_AV1& p,
    unsigned depth, const std::vector<uint16_t>& seeds) {
    using Json = nlohmann::json;
    FilmGrainJointTemplateParameters t;
    if (seeds.empty() || seeds.size() > 32 || std::set<uint16_t>(seeds.begin(), seeds.end()).size() != seeds.size()
        || !film_grain_model_template_parameters(p, depth, t))
        throw std::runtime_error("invalid final joint probe model or seed ensemble");
    const auto m = film_grain_joint_template_moments(t, seeds.data(), seeds.size());
    if (!m.valid) throw std::runtime_error("could not calculate final joint template moments");
    Json syntax = {{"apply_grain", bool(p.applyGrain)}};
    if (p.applyGrain) {
        syntax.update({{"ar_coeff_lag", unsigned(p.arCoeffLag)}, {"ar_coeff_shift", unsigned(p.arCoeffShiftMinus6 + 6)},
            {"grain_scale_shift", unsigned(p.grainScaleShift)}, {"scaling_shift", unsigned(p.grainScalingMinus8 + 8)},
            {"chroma_scaling_from_luma", bool(p.chromaScalingFromLuma)}, {"overlap_flag", bool(p.overlapFlag)},
            {"clip_to_restricted_range", bool(p.clipToRestrictedRange)},
            {"cb_mult", p.cbMult}, {"cb_luma_mult", p.cbLumaMult}, {"cb_offset", p.cbOffset},
            {"cr_mult", p.crMult}, {"cr_luma_mult", p.crLumaMult}, {"cr_offset", p.crOffset}});
        const unsigned counts[3] = {p.numYPoints, p.numCbPoints, p.numCrPoints};
        const uint8_t* values[3] = {p.pointYValue, p.pointCbValue, p.pointCrValue};
        const uint8_t* scaling[3] = {p.pointYScaling, p.pointCbScaling, p.pointCrScaling};
        const uint8_t* coefficients[3] = {p.arCoeffsYPlus128, p.arCoeffsCbPlus128, p.arCoeffsCrPlus128};
        for (unsigned plane = 0; plane < 3; ++plane) {
            const char* key = plane == 0 ? "y" : plane == 1 ? "cb" : "cr";
            auto& points = syntax["scaling_points"][key]; points = Json::array();
            for (unsigned i = 0; i < counts[plane]; ++i) points.push_back({values[plane][i], scaling[plane][i]});
            auto& ar = syntax["ar_coeffs"][key]; ar = Json::array();
            const unsigned taps = 2 * t.lag * (t.lag + 1) + (plane ? unsigned(t.lumaActive) : 0);
            if (plane == 0 ? t.lumaActive : plane == 1 ? t.cbActive : t.crActive)
                for (unsigned i = 0; i < taps; ++i) ar.push_back(int(coefficients[plane][i]) - 128);
        }
    }
    return {{"bit_depth", depth}, {"syntax", syntax}, {"template_seeds", seeds},
        {"seed_scope", "declared ensemble; the per-frame NVENC bitstream seed is assigned later"},
        {"template_scope", "native pre-strength samples; excludes output rounding, overlap and picture clipping"},
        {"template_active", {t.lumaActive, t.cbActive, t.crActive}},
        {"template_mean", m.mean}, {"component_second_moment", m.componentSecondMoment},
        {"nominal_innovation_gain", m.nominalGain}, {"clipped_fraction", m.clippedFraction},
        {"joint_second_moment_y_average_cb_cr", m.jointSecondMoment},
        {"rounded_luma_driver_mean", m.driverMean}, {"rounded_luma_driver_second_moment", m.driverSecondMoment},
        {"rounded_luma_driver_colour_second_moment", m.driverColourSecondMoment}};
}
} // namespace fgsmodel
