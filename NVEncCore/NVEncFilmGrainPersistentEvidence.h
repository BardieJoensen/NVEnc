// Bind native persistent-detail vetoes to one current retention candidate.
// Passing these necessary projections never creates a full detail/model pass.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainPersistentCollect.h"
#include "NVEncFilmGrainRetentionSelect.h"

namespace fgsmodel {
struct FilmGrainPersistentEvidenceTile {
    FilmGrainPersistentTile tile{};
    FilmGrainPersistentResult measurement{};
};
struct FilmGrainPersistentEvidence {
    FilmGrainRetentionRequest request{};
    uint64_t modelId = 0; // Same rounded base and quantized model as the candidate.
    std::vector<FilmGrainPersistentEvidenceTile> tiles; // Complete native raster order.
};
struct FilmGrainPersistentAssessment {
    uint32_t reasons = 0;
    uint64_t samples = 0, changedSamples = 0, unknownSamples = 0, conflictSamples = 0;
};
inline FilmGrainPersistentAssessment film_grain_assess_persistent_evidence(
    const FilmGrainRetentionCandidate& candidate, const FilmGrainPersistentEvidence& evidence,
    const FilmGrainPersistentLimits& limits) {
    FilmGrainPersistentAssessment out;
    const auto& request = candidate.request;
    if (!request.frame.valid() || request.component > 2 || !candidate.modelId
        || !std::isfinite(request.retain) || request.retain < 0 || request.retain >= 1
        || !std::isfinite(request.lumaRetain) || request.lumaRetain < 0 || request.lumaRetain > 1) {
        out.reasons = FGS_RETAIN_INVALID;
        return out;
    }
    if (!(request == evidence.request) || candidate.modelId != evidence.modelId) {
        out.reasons = FGS_RETAIN_STALE_EVIDENCE;
        return out;
    }
    const unsigned side = request.component ? 32 : 64;
    const unsigned width = request.frame.width / (request.component ? 2 : 1);
    const unsigned height = request.frame.height / (request.component ? 2 : 1);
    const unsigned columns = (width+side-1)/side, rows = (height+side-1)/side;
    if (evidence.tiles.size() != size_t(columns)*rows) {
        out.reasons = FGS_RETAIN_INCOMPLETE_PICTURE;
        return out;
    }
    for (unsigned i = 0; i < evidence.tiles.size(); ++i) {
        const auto& cell = evidence.tiles[i];
        const unsigned x = i%columns*side, y = i/columns*side;
        const unsigned samples = std::min(side,width-x)*std::min(side,height-y);
        // Checking the entire canonical grid prevents duplicates, overlaps or
        // a missing partial border from masquerading as complete coverage.
        if (cell.tile.component != request.component || cell.tile.x != x || cell.tile.y != y
            || cell.measurement.samples != samples || cell.measurement.changedSamples > samples) {
            out.reasons |= FGS_RETAIN_INVALID | FGS_RETAIN_INCOMPLETE_PICTURE;
            return out;
        }
        const auto detail = film_grain_persistent_result_detail(cell.measurement,limits);
        if (!detail.valid) {
            out.reasons |= FGS_RETAIN_INVALID | FGS_RETAIN_UNMEASURED;
            return out;
        }
        out.samples += samples;
        out.changedSamples += cell.measurement.changedSamples;
        if (std::abs(detail.meanError) > limits.meanError
            || (detail.anchorsSupported && !detail.withinLimits)) {
            out.conflictSamples += samples;
            out.reasons |= FGS_RETAIN_FAILED_CHECK;
        } else if (cell.measurement.changedSamples && !detail.anchorsSupported) {
            out.unknownSamples += samples;
            out.reasons |= FGS_RETAIN_UNMEASURED;
        }
    }
    return out;
}

// Apply before the existing selector assesses the candidate. This can only
// remove clearance. Full source-detail, population, synthesis and range checks
// are still required, even when every persistent direction stays within bounds.
inline FilmGrainPersistentAssessment film_grain_apply_persistent_veto(
    FilmGrainRetentionCandidate& candidate, const FilmGrainPersistentEvidence& evidence,
    const FilmGrainPersistentLimits& limits) {
    const auto result = film_grain_assess_persistent_evidence(candidate,evidence,limits);
    if (result.reasons) {
        candidate.checks.passed &= ~uint32_t(FGS_RETAIN_DETAIL);
        if (result.reasons & FGS_RETAIN_FAILED_CHECK) candidate.checks.measured |= FGS_RETAIN_DETAIL;
        else candidate.checks.measured &= ~uint32_t(FGS_RETAIN_DETAIL);
    }
    return result;
}
} // namespace fgsmodel
