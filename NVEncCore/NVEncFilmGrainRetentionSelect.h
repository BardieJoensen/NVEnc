// Bounded experimental retention policy. Not connected to encoder output.
// Evidence is supplied by independently checked measurement/model stages;
// this helper cannot turn missing measurements into picture qualification.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace fgsmodel {
constexpr std::array<float, 5> FGS_RETENTION_CANDIDATES{{0.0f, .1f, .25f, .5f, .75f}};

// Required candidate checks are independent vetoes. A missing check is neither
// a pass nor an observed defect. In particular a successful predictor solve
// does not imply finite-synthesis fidelity, quiet/detail safety or coverage.
enum FilmGrainRetentionCheck : uint32_t {
    FGS_RETAIN_ROUNDED_BASE = 1u << 0,
    FGS_RETAIN_MISSING_TARGET = 1u << 1,
    FGS_RETAIN_QUANTIZED_MODEL = 1u << 2,
    FGS_RETAIN_CAUSAL_SPECTRAL = 1u << 3,
    FGS_RETAIN_FINITE_SYNTHESIS = 1u << 4,
    FGS_RETAIN_DETAIL = 1u << 5,
    FGS_RETAIN_QUIET = 1u << 6,
    FGS_RETAIN_AMPLITUDE = 1u << 7,
    FGS_RETAIN_ALL_CHECKS = (1u << 8) - 1
};
enum FilmGrainRetentionPopulationCheck : uint32_t {
    FGS_RETAIN_NATIVE_RANGE = 1u << 0,
    FGS_RETAIN_SOURCE_POPULATION = 1u << 1,
    FGS_RETAIN_RECONSTRUCTED_POPULATION = 1u << 2,
    FGS_RETAIN_ALL_POPULATION_CHECKS = (1u << 3) - 1
};
enum FilmGrainRetentionJointCheck : uint32_t {
    FGS_RETAIN_Y_CB = 1u << 0,
    FGS_RETAIN_Y_CR = 1u << 1,
    FGS_RETAIN_CB_CR = 1u << 2,
    FGS_RETAIN_SHARED_SYNTAX = 1u << 3,
    FGS_RETAIN_ALL_JOINT_CHECKS = (1u << 4) - 1
};
struct FilmGrainRetentionChecks {
    uint32_t measured = 0, passed = 0;
    bool valid(uint32_t required) const {
        return !(measured & ~required) && !(passed & ~measured);
    }
    bool complete(uint32_t required) const {
        return valid(required) && measured == required && passed == required;
    }
};
enum FilmGrainRetentionReason : uint32_t {
    FGS_RETAIN_INVALID = 1u << 0,
    FGS_RETAIN_STALE_EVIDENCE = 1u << 1,
    FGS_RETAIN_UNMEASURED = 1u << 2,
    FGS_RETAIN_FAILED_CHECK = 1u << 3,
    FGS_RETAIN_INCOMPLETE_PICTURE = 1u << 4,
    FGS_RETAIN_UNSUPPORTED_SYNTHESIS = 1u << 5,
    FGS_RETAIN_UNPROVEN_BASE_CHANGE = 1u << 6,
    FGS_RETAIN_NO_COMPONENT_CANDIDATE = 1u << 7,
    FGS_RETAIN_JOINT_UNPROVEN = 1u << 8,
    FGS_RETAIN_SOURCE_REQUESTED = 1u << 9
};
struct FilmGrainRetentionFrame {
    unsigned width = 0, height = 0, bitDepth = 0;
    int64_t frameId = -1, timestamp = std::numeric_limits<int64_t>::min();
    uint64_t epoch = 0;
    // Caller-issued identity of the complete, source-only population map.
    // It MUST stay fixed across fractions; it is not a file/provenance hash.
    uint64_t sourcePopulationId = 0;
    bool valid() const {
        return width >= 64 && height >= 64 && width <= 8192 && height <= 8192
            && !(width & 1) && !(height & 1) && (bitDepth == 8 || bitDepth == 10)
            && frameId >= 0 && timestamp != std::numeric_limits<int64_t>::min()
            && sourcePopulationId != 0;
    }
    bool operator==(const FilmGrainRetentionFrame& b) const {
        return width == b.width && height == b.height && bitDepth == b.bitDepth
            && frameId == b.frameId && timestamp == b.timestamp && epoch == b.epoch
            && sourcePopulationId == b.sourcePopulationId;
    }
};
enum class FilmGrainRetentionPopulation : unsigned {
    Grain = 0, Quiet = 1, Rejected = 2, Border = 3
};
// One cell in a complete native-lookup/population census, NOT just the fitted
// tiles. Do not merge source brightness/strength populations with different
// evidence. Rejected tiles and partial borders must be counted as well.
//
// Revision 1 has no qualified model for Quiet/Rejected/Border populations.
// Such cells can pass only with exactly unchanged native base and zero grain.
// Future population-specific acceptance requires separate qualification; it
// must not be enabled by setting these check bits on a rejected source tile.
struct FilmGrainRetentionPopulationCell {
    FilmGrainRetentionPopulation population = FilmGrainRetentionPopulation::Rejected;
    unsigned nativeLookup = 0, scaling = 0;
    uint64_t samples = 0, changedSamples = 0;
    unsigned trainBlocks = 0, checkBlocks = 0;
    FilmGrainRetentionChecks checks{};
};
struct FilmGrainRetentionCoverage {
    uint32_t reasons = 0;
    uint64_t samples = 0, exactZeroSamples = 0, supportedSamples = 0;
    uint64_t unsupportedSynthesisSamples = 0, unprovenChangedSamples = 0;
    std::array<uint64_t, 4> populationSamples{};
};
inline FilmGrainRetentionCoverage film_grain_retention_coverage(
    const FilmGrainRetentionFrame& frame, unsigned component,
    const std::vector<FilmGrainRetentionPopulationCell>& cells) {
    FilmGrainRetentionCoverage result;
    // Every cell contains at least one sample. The separate cap bounds policy
    // processing even if a caller supplies a pathologically fragmented census.
    constexpr size_t maxCells = 20 * 6 * 4 * 1024;
    if (!frame.valid() || component > 2 || cells.empty() || cells.size() > maxCells) {
        result.reasons = FGS_RETAIN_INVALID | FGS_RETAIN_INCOMPLETE_PICTURE;
        return result;
    }
    const uint64_t expected = uint64_t(frame.width) * frame.height / (component ? 4 : 1);
    for (const auto& cell : cells) {
        const unsigned population = static_cast<unsigned>(cell.population);
        if (population > 3 || cell.nativeLookup >= (1u << frame.bitDepth) || cell.scaling > 255
            || !cell.samples || cell.samples > expected || cell.changedSamples > cell.samples
            || cell.trainBlocks > 10000000 || cell.checkBlocks > 10000000
            || !cell.checks.valid(FGS_RETAIN_ALL_POPULATION_CHECKS)
            || result.samples > expected - cell.samples) {
            result.reasons |= FGS_RETAIN_INVALID | FGS_RETAIN_INCOMPLETE_PICTURE;
            return result;
        }
        result.samples += cell.samples;
        result.populationSamples[population] += cell.samples;
        if (cell.scaling == 0 && cell.changedSamples == 0) {
            result.exactZeroSamples += cell.samples;
            continue; // Exact source/no synthesis is a proof, even without grain evidence.
        }
        const bool supported = cell.population == FilmGrainRetentionPopulation::Grain
            && cell.trainBlocks >= 16 && cell.checkBlocks >= 16
            && cell.checks.complete(FGS_RETAIN_ALL_POPULATION_CHECKS);
        if (supported) {
            result.supportedSamples += cell.samples;
        } else {
            if (cell.scaling) {
                result.unsupportedSynthesisSamples += cell.samples;
                result.reasons |= FGS_RETAIN_UNSUPPORTED_SYNTHESIS;
            }
            if (cell.changedSamples) {
                result.unprovenChangedSamples += cell.changedSamples;
                result.reasons |= FGS_RETAIN_UNPROVEN_BASE_CHANGE;
            }
        }
    }
    if (result.samples != expected) result.reasons |= FGS_RETAIN_INCOMPLETE_PICTURE;
    return result;
}

struct FilmGrainRetentionRequest {
    FilmGrainRetentionFrame frame{};
    unsigned component = 0;
    float lumaRetain = 1.0f, retain = 1.0f;
    bool operator==(const FilmGrainRetentionRequest& b) const {
        return frame == b.frame && component == b.component
            && lumaRetain == b.lumaRetain && retain == b.retain;
    }
};
struct FilmGrainRetentionCandidate {
    FilmGrainRetentionRequest request{};
    // Identifies all quantized parameters AND the actual rounded base. Model
    // reuse does not exempt a candidate from current-picture measurements.
    uint64_t modelId = 0;
    FilmGrainRetentionChecks checks{};
    std::vector<FilmGrainRetentionPopulationCell> cells;
};
struct FilmGrainRetentionAssessment {
    uint32_t reasons = 0, unmeasuredChecks = 0, failedChecks = 0;
    FilmGrainRetentionCoverage coverage{};
    bool accepted() const { return reasons == 0; }
};
inline FilmGrainRetentionAssessment film_grain_assess_retention_candidate(
    const FilmGrainRetentionRequest& expected, const FilmGrainRetentionCandidate& candidate) {
    FilmGrainRetentionAssessment result;
    if (!expected.frame.valid() || expected.component > 2
        || !std::isfinite(expected.lumaRetain) || expected.lumaRetain < 0 || expected.lumaRetain > 1
        || !std::isfinite(expected.retain) || expected.retain < 0 || expected.retain >= 1
        || !candidate.modelId || !candidate.checks.valid(FGS_RETAIN_ALL_CHECKS))
        result.reasons |= FGS_RETAIN_INVALID;
    if (!(candidate.request == expected)) result.reasons |= FGS_RETAIN_STALE_EVIDENCE;
    result.unmeasuredChecks = FGS_RETAIN_ALL_CHECKS & ~candidate.checks.measured;
    result.failedChecks = candidate.checks.measured & ~candidate.checks.passed;
    if (result.unmeasuredChecks) result.reasons |= FGS_RETAIN_UNMEASURED;
    if (result.failedChecks) result.reasons |= FGS_RETAIN_FAILED_CHECK;
    result.coverage = film_grain_retention_coverage(expected.frame, expected.component, candidate.cells);
    result.reasons |= result.coverage.reasons;
    return result;
}

struct FilmGrainRetentionCombination {
    FilmGrainRetentionFrame frame{};
    std::array<float, 3> retain{{1.0f, 1.0f, 1.0f}};
    std::array<uint64_t, 3> modelId{}; // Zero requires source copy and zero strength.
    bool operator==(const FilmGrainRetentionCombination& b) const {
        return frame == b.frame && retain == b.retain && modelId == b.modelId;
    }
};
struct FilmGrainRetentionJointEvidence {
    FilmGrainRetentionCombination combination{};
    FilmGrainRetentionChecks checks{};
};
struct FilmGrainRetentionDecision {
    FilmGrainRetentionCombination selected{};
    FilmGrainRetentionCombination beforeJoint{};
    bool sourceFrame = true;
    unsigned sourceMask = 7, jointEvaluations = 0;
    std::array<unsigned, 3> evaluations{};
    std::array<uint32_t, 3> rejectionReasons{};
    FilmGrainRetentionAssessment luma{};
    std::array<std::array<FilmGrainRetentionAssessment, 5>, 2> attempts{};
    uint32_t jointReasons = 0, jointUnmeasured = 0, jointFailed = 0;
};

// evaluate(request) must measure/fit only that candidate, on fixed source-only
// cohorts; joint(combination) rechecks Y/Cb, Y/Cr AND Cb/Cr after final component
// choice. Neither callback may install output. This returns a proposal for the
// later temporal/output guards, never an unconditional encode authorization.
// The selector invokes <=1 existing Y proposal, <=5 candidates per colour and
// <=1 final joint check. There is no joint failure backtracking or stale reuse.
template<class Evaluate, class Joint>
inline FilmGrainRetentionDecision film_grain_select_retention(
    const FilmGrainRetentionFrame& frame, float lumaRetain, Evaluate evaluate, Joint joint) {
    FilmGrainRetentionDecision result;
    result.selected.frame = frame;
    const auto sourceFrame = [&]() {
        result.sourceFrame = true;
        result.sourceMask = 7;
        result.selected.retain = {{1.0f, 1.0f, 1.0f}};
        result.selected.modelId = {};
    };
    if (!frame.valid() || !std::isfinite(lumaRetain) || lumaRetain < 0
        || (lumaRetain > .5f && lumaRetain != 1.0f)) {
        result.rejectionReasons[0] = FGS_RETAIN_INVALID;
        return result;
    }
    // The existing Y policy requesting full source is terminal. A future
    // colour-only policy needs independent qualification, not an implicit
    // change to the existing luma safety decision.
    if (lumaRetain == 1.0f) {
        result.rejectionReasons[0] = FGS_RETAIN_SOURCE_REQUESTED;
        return result;
    }
    const FilmGrainRetentionRequest yRequest{frame, 0, lumaRetain, lumaRetain};
    auto luma = evaluate(yRequest);
    result.evaluations[0] = 1;
    result.luma = film_grain_assess_retention_candidate(yRequest, luma);
    result.rejectionReasons[0] = result.luma.reasons;
    if (!result.luma.accepted()) return result;
    result.selected.retain[0] = lumaRetain;
    result.selected.modelId[0] = luma.modelId;
    result.sourceMask &= ~1u;
    for (unsigned component = 1; component < 3; ++component) {
        bool selected = false;
        for (unsigned index = 0; index < FGS_RETENTION_CANDIDATES.size(); ++index) {
            const FilmGrainRetentionRequest request{frame, component, lumaRetain, FGS_RETENTION_CANDIDATES[index]};
            auto candidate = evaluate(request);
            auto& assessment = result.attempts[component - 1][index];
            assessment = film_grain_assess_retention_candidate(request, candidate);
            ++result.evaluations[component];
            result.rejectionReasons[component] |= assessment.reasons;
            if (assessment.accepted()) {
                result.selected.retain[component] = request.retain;
                result.selected.modelId[component] = candidate.modelId;
                result.sourceMask &= ~(1u << component);
                selected = true;
                break;
            }
        }
        if (!selected) result.rejectionReasons[component] |= FGS_RETAIN_NO_COMPONENT_CANDIDATE;
    }
    result.beforeJoint = result.selected;
    const auto evidence = joint(result.selected);
    result.jointEvaluations = 1;
    if (!(evidence.combination == result.selected)) result.jointReasons |= FGS_RETAIN_STALE_EVIDENCE;
    if (!evidence.checks.valid(FGS_RETAIN_ALL_JOINT_CHECKS)) result.jointReasons |= FGS_RETAIN_INVALID;
    result.jointUnmeasured = FGS_RETAIN_ALL_JOINT_CHECKS & ~evidence.checks.measured;
    result.jointFailed = evidence.checks.measured & ~evidence.checks.passed;
    if (result.jointUnmeasured) result.jointReasons |= FGS_RETAIN_UNMEASURED;
    if (result.jointFailed) result.jointReasons |= FGS_RETAIN_FAILED_CHECK;
    if (result.jointReasons) {
        result.jointReasons |= FGS_RETAIN_JOINT_UNPROVEN;
        sourceFrame();
    } else {
        result.sourceFrame = false;
    }
    return result;
}
} // namespace fgsmodel
