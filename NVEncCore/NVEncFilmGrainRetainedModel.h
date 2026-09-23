// Construct a quantized chroma shape for an actual rounded retained base.
// Construction is not admission: source populations, held-out synthesis,
// complete native coverage and final joint colour evidence remain mandatory.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainBalancedModel.h"
#include "NVEncFilmGrainJointTemplate.h"
#include "NVEncFilmGrainStability.h"

namespace fgsmodel {
enum FilmGrainRetainedModelReason : uint32_t {
    FGS_RETAIN_MODEL_INVALID = 1u << 0,
    FGS_RETAIN_MODEL_TARGET = 1u << 1,
    FGS_RETAIN_MODEL_FIT = 1u << 2,
    FGS_RETAIN_MODEL_QUANTIZATION = 1u << 3,
    FGS_RETAIN_MODEL_STABILITY = 1u << 4,
    FGS_RETAIN_MODEL_LUMA = 1u << 5
};

class FilmGrainRetainedLuma {
    FilmGrainJointTemplateParameters parameters_{};
    FilmGrainLumaTemplatePower power_{};
    bool valid_ = false;
    friend FilmGrainRetainedLuma film_grain_retained_luma(
        const FilmGrainJointTemplateParameters&, const uint16_t*, size_t);
public:
    bool valid() const { return valid_; }
    const FilmGrainJointTemplateParameters& parameters() const { return parameters_; }
    const FilmGrainLumaTemplatePower& power() const { return power_; }
};

// Bind the finite luma driver to its exact quantized shape/depth/scale. An
// unlabelled scalar from another model must not be used as this evidence.
// Explicit seeds are calibration evidence, not a bound for all possible seeds.
inline FilmGrainRetainedLuma film_grain_retained_luma(
    const FilmGrainJointTemplateParameters& p, const uint16_t* seeds, size_t count) {
    FilmGrainRetainedLuma out;
    if (!p.valid() || p.lag != 3 || !p.lumaActive || !seeds || !count || count > 512
        || !film_grain_ar_synthesis_safe(p.y.data(), p.lag, p.arShift)) return out;
    out.power_ = film_grain_luma_template_power(p.y.data(), p.lag, p.arShift,
        p.bitDepth, p.grainShift, seeds, count);
    out.parameters_ = p;
    out.valid_ = out.power_.valid && out.power_.roundedAverageLumaPower > 0.0;
    return out;
}

constexpr size_t FGS_RETAINED_LUMA_VARIABLES = 25; // 24 native Y neighbours, current Y.
using FilmGrainRetainedLumaMatrix = std::array<double,
    FGS_RETAINED_LUMA_VARIABLES * FGS_RETAINED_LUMA_VARIABLES>;
struct FilmGrainRetainedLumaMoments {
    FilmGrainRetainedLumaMatrix source{}, base{}, sourceBase{};
    uint64_t observations = 0, blocks = 0;
};
struct FilmGrainRetainedLumaFit {
    FilmGrainRetainedLuma luma{};
    FilmGrainBalancedFit balanced{};
    uint32_t reasons = 0;
    bool valid() const { return reasons == 0 && luma.valid(); }
};

// Refit the native luma shape for the rounded candidate, without changing its
// proposed retention fraction. The existing 26-variable minimax solver can
// solve a 25-variable luma problem by embedding an independent unit-variance
// dummy predictor. Its exact zero cross terms force a zero driver coefficient.
// This is only an algebraic embedding, never measured averaged-luma evidence.
inline FilmGrainRetainedLumaFit film_grain_fit_retained_luma(
    const std::vector<FilmGrainRetainedLumaMoments>& training,
    unsigned bitDepth, unsigned sharedArShift, unsigned grainShift,
    const uint16_t* seeds, size_t seedCount) {
    FilmGrainRetainedLumaFit out;
    if (training.empty() || training.size() > 20 || (bitDepth != 8 && bitDepth != 10)
        || sharedArShift < 6 || sharedArShift > 9 || grainShift > 3
        || !seeds || !seedCount || seedCount > 512) {
        out.reasons = FGS_RETAIN_MODEL_INVALID;
        return out;
    }
    constexpr size_t N = FGS_JOINT_VARIABLES, L = FGS_RETAINED_LUMA_VARIABLES;
    std::vector<FilmGrainJointTarget> targets;
    for (const auto& original : training) {
        FilmGrainJointMoments embedded;
        embedded.blocks = original.blocks; embedded.observations = original.observations;
        for (size_t i = 0; i < L; ++i) for (size_t j = 0; j < L; ++j) {
            const size_t index = (i == 24 ? 25 : i)*N + (j == 24 ? 25 : j);
            embedded.source[index] = original.source[i*L+j];
            embedded.base[index] = original.base[i*L+j];
            embedded.sourceBase[index] = original.sourceBase[i*L+j];
        }
        embedded.source[24*N+24] = double(original.observations);
        const auto target = film_grain_joint_target(embedded, {});
        if (!target.valid) {
            out.reasons = FGS_RETAIN_MODEL_TARGET;
            return out;
        }
        targets.push_back(target);
    }
    out.balanced = film_grain_fit_balanced_chroma(targets);
    if (!out.balanced.valid || out.balanced.predictors[24] != 0.0) {
        out.reasons = FGS_RETAIN_MODEL_FIT;
        return out;
    }
    FilmGrainJointTemplateParameters p;
    p.bitDepth = bitDepth; p.lag = 3; p.arShift = sharedArShift;
    p.grainShift = grainShift; p.lumaActive = p.cbActive = p.crActive = true;
    p.cb.fill(128); p.cr.fill(128);
    for (unsigned i = 0; i < 24; ++i) {
        const double scaled = std::ldexp(out.balanced.predictors[i], sharedArShift);
        if (!std::isfinite(scaled) || scaled <= -128.5 || scaled >= 127.5) {
            out.reasons = FGS_RETAIN_MODEL_QUANTIZATION;
            return out;
        }
        p.y[i] = static_cast<uint8_t>(std::lround(scaled) + 128);
    }
    if (!film_grain_ar_synthesis_safe(p.y.data(), p.lag, p.arShift)) {
        out.reasons = FGS_RETAIN_MODEL_STABILITY;
        return out;
    }
    out.luma = film_grain_retained_luma(p, seeds, seedCount);
    if (!out.luma.valid()) out.reasons = FGS_RETAIN_MODEL_LUMA;
    return out;
}

struct FilmGrainRetainedChroma {
    bool constructed = false;
    uint32_t reasons = 0;
    std::array<uint8_t, 25> coefficients{};
    FilmGrainBalancedFit balanced{};
    FilmGrainJointChromaFit fit{};
    // Predictor units for each original training group after quantization.
    // The same training conversion must be used on its independent check group.
    std::vector<std::array<double, 25>> groupPredictors;
    std::vector<double> quantizedTrainingExcess;
    bool valid() const { return constructed && reasons == 0; }
};

// Inputs are moments of source and the ALREADY rounded candidate base, in
// identical native source-selected cohorts. Retention is deliberately absent
// from this API: applying the linear blend again would count retention twice.
// No check/holdout moments participate in fitting or parameter quantization.
inline FilmGrainRetainedChroma film_grain_fit_retained_chroma(
    const std::vector<FilmGrainJointMoments>& training,
    const FilmGrainRetainedLuma& luma) {
    FilmGrainRetainedChroma out;
    out.coefficients.fill(128);
    const auto& p = luma.parameters();
    if (training.empty() || training.size() > 20) {
        out.reasons = FGS_RETAIN_MODEL_INVALID;
        return out;
    }
    if (!luma.valid() || !p.valid() || p.lag != 3 || !p.lumaActive
        || !luma.power().valid || luma.power().bitDepth != p.bitDepth
        || luma.power().grainShift != p.grainShift || !luma.power().seeds
        || luma.power().seeds > 512 || !std::isfinite(luma.power().roundedAverageLumaPower)
        || luma.power().roundedAverageLumaPower <= 0.0) {
        out.reasons = FGS_RETAIN_MODEL_LUMA;
        return out;
    }
    std::vector<FilmGrainJointTarget> targets;
    const std::array<double, FGS_JOINT_VARIABLES> noFurtherRetention{};
    for (const auto& moments : training) {
        const auto target = film_grain_joint_target(moments, noFurtherRetention);
        if (!target.valid) {
            out.reasons = FGS_RETAIN_MODEL_TARGET;
            return out;
        }
        targets.push_back(target);
    }
    out.balanced = film_grain_fit_balanced_chroma(targets);
    if (!out.balanced.valid) {
        out.reasons = FGS_RETAIN_MODEL_FIT;
        return out;
    }
    out.fit = film_grain_fit_joint_chroma(out.balanced.normalizedTarget,
        luma.power().roundedAverageLumaPower);
    if (!out.fit.valid) {
        out.reasons = FGS_RETAIN_MODEL_FIT;
        return out;
    }
    std::array<double, 25> normalized{};
    for (unsigned i = 0; i < 25; ++i) {
        const double value = i < 24 ? out.fit.spatial[i] : out.fit.templateLumaCoefficient;
        const double scaled = std::ldexp(value, p.arShift);
        // Test before integer conversion; never clip an unrepresentable fit.
        if (!std::isfinite(scaled) || scaled <= -128.5 || scaled >= 127.5) {
            out.reasons = FGS_RETAIN_MODEL_QUANTIZATION;
            return out;
        }
        const long q = std::lround(scaled);
        out.coefficients[i] = static_cast<uint8_t>(q + 128);
        normalized[i] = std::ldexp(double(q), -int(p.arShift));
    }
    normalized[24] *= std::sqrt(out.fit.innovationVariance / out.fit.lumaInnovationVariance);
    if (!film_grain_ar_synthesis_safe(out.coefficients.data(), p.lag, p.arShift)) {
        out.reasons = FGS_RETAIN_MODEL_STABILITY;
        return out;
    }
    constexpr size_t N = FGS_JOINT_VARIABLES;
    for (size_t group = 0; group < targets.size(); ++group) {
        auto predictors = normalized;
        predictors[24] *= out.balanced.chromaScale[group] / out.balanced.lumaScale[group];
        const auto optimum = film_grain_fit_joint_chroma(targets[group], 1.0);
        if (!optimum.valid) {
            out.reasons = FGS_RETAIN_MODEL_FIT;
            return out;
        }
        std::array<double, N> error{};
        for (unsigned i = 0; i < 25; ++i) error[i] = -predictors[i];
        error[25] = 1.0;
        double variance = 0.0;
        for (size_t i = 0; i < N; ++i) for (size_t j = 0; j < N; ++j)
            variance += error[i] * targets[group].covariance[i*N+j] * error[j];
        const double excess = variance / optimum.innovationVariance - 1.0;
        if (!std::isfinite(excess) || excess < -1e-7) {
            out.reasons = FGS_RETAIN_MODEL_FIT;
            return out;
        }
        out.groupPredictors.push_back(predictors);
        out.quantizedTrainingExcess.push_back(excess);
    }
    out.constructed = true;
    return out;
}
} // namespace fgsmodel
