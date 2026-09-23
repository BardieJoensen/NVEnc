// Explicit experimental colour-only policy. It does not change the R1 selector.
// Keep the complete source Y and prove its preservation under the final model.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainSourcePreservation.h"

namespace fgsmodel {
struct FilmGrainSourceLumaJointEvidence {
    FilmGrainRetentionJointEvidence colour{};
    std::array<FilmGrainSourceComponentCounts,3> sourceComponents{};
    uint64_t modelId = 0; // Full combined parameters AND native base identity.
    NV_ENC_FILM_GRAIN_PARAMS_AV1 parameters{};
    bool matrixIdentity = false;
};
struct FilmGrainSourceLumaDecision {
    FilmGrainRetentionDecision selection{};
    bool sourceLumaProven = false;
    unsigned sourcePreservedMask = 0;
};

// This separate policy is never an implicit retry after the ordinary selector.
// Evaluate at most five fractions per colour, then one complete joint check.
// Each callback request has lumaRetain=1. Old partial-Y evidence is stale.
// The whole-source terminal result requires no synthesis or changed base.
template<class Evaluate, class Joint>
FilmGrainSourceLumaDecision film_grain_select_with_source_luma(
    const FilmGrainRetentionFrame& frame, Evaluate evaluate, Joint joint) {
    FilmGrainSourceLumaDecision result;
    auto& out = result.selection;
    out.selected.frame = frame;
    if (!frame.valid()) {
        out.rejectionReasons[0] = FGS_RETAIN_INVALID;
        return result;
    }
    for (unsigned component = 1; component < 3; ++component) {
        bool accepted = false;
        for (unsigned index = 0; index < FGS_RETENTION_CANDIDATES.size(); ++index) {
            const FilmGrainRetentionRequest request{frame, component, 1.0f, FGS_RETENTION_CANDIDATES[index]};
            const auto candidate = evaluate(request);
            auto& assessment = out.attempts[component-1][index];
            assessment = film_grain_assess_retention_candidate(request, candidate);
            ++out.evaluations[component];
            out.rejectionReasons[component] |= assessment.reasons;
            if (assessment.accepted()) {
                out.selected.retain[component] = request.retain;
                out.selected.modelId[component] = candidate.modelId;
                out.sourceMask &= ~(1u << component);
                accepted = true;
                break;
            }
        }
        if (!accepted) out.rejectionReasons[component] |= FGS_RETAIN_NO_COMPONENT_CANDIDATE;
    }
    out.beforeJoint = out.selected;
    if (out.sourceMask == 7) return result;
    const auto evidence = joint(out.selected);
    out.jointEvaluations = 1;
    if (!(evidence.colour.combination == out.selected)) out.jointReasons |= FGS_RETAIN_STALE_EVIDENCE;
    if (!evidence.colour.checks.valid(FGS_RETAIN_ALL_JOINT_CHECKS)) out.jointReasons |= FGS_RETAIN_INVALID;
    out.jointUnmeasured = FGS_RETAIN_ALL_JOINT_CHECKS & ~evidence.colour.checks.measured;
    out.jointFailed = evidence.colour.checks.measured & ~evidence.colour.checks.passed;
    if (out.jointUnmeasured) out.jointReasons |= FGS_RETAIN_UNMEASURED;
    if (out.jointFailed) out.jointReasons |= FGS_RETAIN_FAILED_CHECK;
    // A failed colour search can leave another component fully retained. Its
    // present zero curve also runs the decoder clamp, so Y proof alone is not
    // sufficient for a mixed source/synthesized combination.
    for (unsigned component = 0; component < 3; ++component) {
        if (!(out.sourceMask & (1u << component))) continue;
        if (film_grain_component_source_preserved(evidence.sourceComponents[component],
            frame, evidence.modelId, component, evidence.parameters, evidence.matrixIdentity))
            result.sourcePreservedMask |= 1u << component;
        else out.jointReasons |= FGS_RETAIN_FAILED_CHECK;
    }
    result.sourceLumaProven = (result.sourcePreservedMask & 1u) != 0;
    if (out.jointReasons) {
        out.jointReasons |= FGS_RETAIN_JOINT_UNPROVEN;
        out.sourceMask = 7;
        out.selected.retain = {{1.0f,1.0f,1.0f}};
        out.selected.modelId = {};
    } else out.sourceFrame = false;
    return result;
}
} // namespace fgsmodel
