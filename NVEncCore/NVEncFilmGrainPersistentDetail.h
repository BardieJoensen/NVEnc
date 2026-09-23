// Source/base change along independent historical picture directions.
// Necessary detail evidence only: no grain classification or encoder call sites.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainJointModel.h"

namespace fgsmodel {
struct FilmGrainPersistentMoments {
    // Population covariance and means in 8-bit code units, on identical pixels.
    // S=current source, B=actual rounded candidate, A/H=disjoint older averages.
    std::array<double, 16> covariance{}; // S, B, A, H; not a missing-noise matrix.
    std::array<double, 4> mean{};
    uint64_t samples = 0;
};
struct FilmGrainPersistentLimits {
    // No implicit policy defaults: a study must declare its detail limits.
    double relativeContrast = 0.0, projectedRms = 0.0, meanError = 0.0;
    double sourceHistoryCorrelation = 0.0, historyCorrelation = 0.0;
};
struct FilmGrainPersistentDetail {
    bool valid = false, anchorsSupported = false, withinLimits = false;
    std::array<double, 2> sourceCorrelation{}, contrastLoss{}, removedProjectionRms{};
    double historyCorrelation = 0.0, meanError = 0.0, sourceBaseRms = 0.0;
};

// A historical reference is a source-only spatial direction. The projection of
// (source - base) on that direction is an exact finite-picture measurement; no
// assumption that its residual is random grain is needed. Persistent noise is
// protected by the same check as texture. Agreement with these two directions
// does not prove preservation of every structure or account for arbitrary motion.
inline FilmGrainPersistentDetail film_grain_persistent_detail(
    const FilmGrainPersistentMoments& m, const FilmGrainPersistentLimits& limit) {
    FilmGrainPersistentDetail out;
    for (double value : {limit.relativeContrast, limit.projectedRms, limit.meanError,
                         limit.sourceHistoryCorrelation, limit.historyCorrelation})
        if (!std::isfinite(value) || value < 0.0) return out;
    if (limit.relativeContrast > 1.0 || limit.projectedRms > 256.0 || limit.meanError > 256.0
        || limit.sourceHistoryCorrelation <= 0.0 || limit.sourceHistoryCorrelation > 1.0
        || limit.historyCorrelation <= 0.0 || limit.historyCorrelation > 1.0
        || m.samples < 1 || m.samples > 1000000000
        || !joint_model_detail::semidefinite<4>(m.covariance)) return out;
    for (double value : m.mean) if (!std::isfinite(value) || value < 0.0 || value > 256.0) return out;
    const auto& c = m.covariance;
    // A one-pixel border has a measurable mean but no spatial direction.
    if (m.samples == 1)
        for (double value : c) if (std::abs(value) > 1e-9) return out;
    for (unsigned i = 0; i < 4; ++i) if (c[i*4+i] > 65536.0) return out;
    const double differenceVariance = c[0] + c[5] - 2*c[1];
    const double tolerance = std::max(1e-12, std::max(c[0], c[5])*1e-9);
    if (differenceVariance < -tolerance) return out;
    out.meanError = m.mean[0] - m.mean[1];
    out.sourceBaseRms = std::sqrt(std::max(0.0, differenceVariance)
                                + out.meanError*out.meanError);
    out.valid = true;
    // Below numerical evidence resolution there is no usable contrast anchor.
    // This also prevents subnormal denominators from manufacturing correlation.
    if (c[0] <= 1e-12 || c[10] <= 1e-12 || c[15] <= 1e-12) return out;
    out.historyCorrelation = c[11] / std::sqrt(c[10]*c[15]);
    out.anchorsSupported = out.historyCorrelation >= limit.historyCorrelation;
    bool details = std::abs(out.meanError) <= limit.meanError;
    for (unsigned i = 0; i < 2; ++i) {
        const unsigned h = i+2;
        const double sourceHistory = c[h], historyVariance = c[h*4+h];
        out.sourceCorrelation[i] = sourceHistory / std::sqrt(c[0]*historyVariance);
        if (out.sourceCorrelation[i] < limit.sourceHistoryCorrelation) {
            out.anchorsSupported = false;
            continue; // An absent/reversed anchor is unknown, never a detail pass.
        }
        const double removed = sourceHistory - c[4+h];
        out.contrastLoss[i] = removed / sourceHistory; // Keep sharpening's sign too.
        out.removedProjectionRms[i] = std::abs(removed) / std::sqrt(historyVariance);
        details = details && std::abs(out.contrastLoss[i]) <= limit.relativeContrast
            && out.removedProjectionRms[i] <= limit.projectedRms;
    }
    out.withinLimits = out.anchorsSupported && details;
    return out;
}
} // namespace fgsmodel
