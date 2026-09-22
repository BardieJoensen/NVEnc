// Decisions and adversarial coverage controls, independent of a fitted model.
#include "NVEncFilmGrainRetentionSelect.h"
#include <iostream>
#include <stdexcept>
#include <string>
using namespace fgsmodel;
static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
static FilmGrainRetentionFrame frame() { return {256, 128, 10, 20, 800, 1, 99}; }
static FilmGrainRetentionCandidate supported(const FilmGrainRetentionRequest& request) {
    FilmGrainRetentionCandidate result;
    result.request = request;
    result.modelId = 100 + request.component;
    result.checks = {FGS_RETAIN_ALL_CHECKS, FGS_RETAIN_ALL_CHECKS};
    FilmGrainRetentionPopulationCell cell;
    cell.population = FilmGrainRetentionPopulation::Grain;
    cell.nativeLookup = 513; cell.scaling = 32;
    cell.samples = uint64_t(request.frame.width) * request.frame.height / (request.component ? 4 : 1);
    cell.changedSamples = cell.samples / 2;
    cell.trainBlocks = cell.checkBlocks = 16;
    cell.checks = {FGS_RETAIN_ALL_POPULATION_CHECKS, FGS_RETAIN_ALL_POPULATION_CHECKS};
    result.cells.push_back(cell);
    return result;
}
static FilmGrainRetentionJointEvidence jointPass(const FilmGrainRetentionCombination& combination) {
    return {combination, {FGS_RETAIN_ALL_JOINT_CHECKS, FGS_RETAIN_ALL_JOINT_CHECKS}};
}
static bool sourceOnly(const FilmGrainRetentionDecision& result) {
    return result.sourceFrame && result.sourceMask == 7
        && result.selected.retain == std::array<float, 3>{{1, 1, 1}}
        && result.selected.modelId == std::array<uint64_t, 3>{};
}
int main() {
    try {
        const auto key = frame();
        unsigned cases = 0;
        const auto choose = [&](const FilmGrainRetentionRequest& request) {
            auto c = supported(request);
            const float minimum = request.component == 1 ? .25f : .5f;
            if (request.component && request.retain < minimum) c.checks.passed &= ~FGS_RETAIN_FINITE_SYNTHESIS;
            return c;
        };
        auto decision = film_grain_select_retention(key, .1f, choose, jointPass);
        require(!decision.sourceFrame && decision.sourceMask == 0, "eligible candidate rejected");
        require(decision.selected.retain == std::array<float, 3>{{.1f, .25f, .5f}}, "not first admissible fractions");
        require(decision.evaluations == std::array<unsigned, 3>{{1, 3, 4}} && decision.jointEvaluations == 1,
            "candidate bound or short circuit violated");
        require(decision.rejectionReasons[1] & FGS_RETAIN_FAILED_CHECK, "earlier failure hidden by later pass"); ++cases;

        // Exhaust all 6x6 first-success locations (5 candidates plus no success).
        // The independently stated result is min location, fixed trial bound,
        // source copy only on exhausted components, and exactly one joint call.
        for (unsigned cb = 0; cb <= 5; ++cb) for (unsigned cr = 0; cr <= 5; ++cr) {
            unsigned calls[3]{};
            decision = film_grain_select_retention(key, .1f, [&](const FilmGrainRetentionRequest& request) {
                auto c = supported(request);
                const unsigned attempt = calls[request.component]++;
                if (request.component && attempt < (request.component == 1 ? cb : cr))
                    c.checks.passed &= ~FGS_RETAIN_FINITE_SYNTHESIS;
                return c;
            }, jointPass);
            require(!decision.sourceFrame && decision.jointEvaluations == 1, "bounded selection failed");
            for (unsigned component : {1u, 2u}) {
                const unsigned first = component == 1 ? cb : cr;
                require(calls[component] == (first == 5 ? 5 : first + 1), "selector searched beyond first pass");
                require(decision.selected.retain[component] == (first == 5 ? 1 : FGS_RETENTION_CANDIDATES[first]),
                    "selector chose wrong operating point");
                require(bool(decision.sourceMask & (1u << component)) == (first == 5), "incorrect component copy");
                require((decision.selected.modelId[component] == 0) == (first == 5), "fallback retained grain model");
            }
            ++cases;
        }

        const FilmGrainRetentionRequest request{key, 1, .1f, .25f};
        const auto assess = [&](const FilmGrainRetentionCandidate& c) { return film_grain_assess_retention_candidate(request, c); };
        for (unsigned bit = 0; bit < 8; ++bit) {
            auto c = supported(request);
            c.checks.measured &= ~(1u << bit); c.checks.passed &= ~(1u << bit);
            auto r = assess(c);
            require(!r.accepted() && r.unmeasuredChecks == (1u << bit) && !r.failedChecks, "unknown check became pass/failure");
            c.checks.measured |= 1u << bit;
            r = assess(c);
            require(!r.accepted() && r.failedChecks == (1u << bit) && !r.unmeasuredChecks, "measured failure lost"); ++cases;
        }
        auto c = supported(request);
        c.checks.measured = 0;
        require(assess(c).reasons & FGS_RETAIN_INVALID, "passed but never measured check accepted"); ++cases;

        // Full-picture counters must include borders and every population,
        // even if the high-support grain population dominates the frame.
        for (auto population : {FilmGrainRetentionPopulation::Quiet, FilmGrainRetentionPopulation::Rejected,
                                 FilmGrainRetentionPopulation::Border}) {
            c = supported(request);
            auto minority = c.cells.front(); minority.population = population;
            minority.samples = minority.changedSamples = 1; --c.cells[0].samples;
            c.cells.push_back(minority);
            auto r = assess(c);
            require((r.reasons & FGS_RETAIN_UNSUPPORTED_SYNTHESIS) && (r.reasons & FGS_RETAIN_UNPROVEN_BASE_CHANGE),
                "large grain population hid one unsupported changed pixel");
            c.cells.back().scaling = 0;
            r = assess(c);
            require((r.reasons & FGS_RETAIN_UNPROVEN_BASE_CHANGE) && !(r.reasons & FGS_RETAIN_UNSUPPORTED_SYNTHESIS),
                "zero curve certified changed unsupported source");
            c.cells.back().changedSamples = 0;
            require(assess(c).accepted(), "exact source with zero grain needs no grain classification");
            c.cells.back().scaling = 1;
            require(assess(c).reasons & FGS_RETAIN_UNSUPPORTED_SYNTHESIS, "quiet source received unproven grain"); ++cases;
        }
        for (unsigned bit = 0; bit < 3; ++bit) {
            c = supported(request); c.cells[0].checks.passed &= ~(1u << bit);
            require(assess(c).reasons & FGS_RETAIN_UNSUPPORTED_SYNTHESIS, "patch fit bypassed finer population proof"); ++cases;
        }
        c = supported(request); c.cells[0].checkBlocks = 15;
        require(!assess(c).accepted(), "training count replaced independent check count");
        c.cells[0].checkBlocks = 16; c.cells[0].trainBlocks = 15;
        require(!assess(c).accepted(), "check count replaced training count"); ++cases;
        c = supported(request); --c.cells[0].samples;
        require(assess(c).reasons & FGS_RETAIN_INCOMPLETE_PICTURE, "missing border silently accepted");
        c.cells.push_back(c.cells.front());
        require(assess(c).reasons & FGS_RETAIN_INVALID, "over-counted picture accepted"); ++cases;
        c = supported(request); c.cells[0].changedSamples = std::numeric_limits<uint64_t>::max();
        require(assess(c).reasons & FGS_RETAIN_INVALID, "invalid change count accepted");
        c.cells[0].changedSamples = 0; c.cells[0].samples = std::numeric_limits<uint64_t>::max();
        require(assess(c).reasons & FGS_RETAIN_INVALID, "overflowing census accepted"); ++cases;
        c = supported(request); c.cells[0].nativeLookup = 1024;
        require(!assess(c).accepted(), "out-of-range native lookup accepted");
        c = supported(request); c.request.frame.sourcePopulationId++;
        require(assess(c).reasons & FGS_RETAIN_STALE_EVIDENCE, "retention-dependent source classification accepted"); ++cases;
        c = supported(request); c.request.retain = .5f;
        require(assess(c).reasons & FGS_RETAIN_STALE_EVIDENCE, "wrong rounded base reused");
        c = supported(request); c.request.frame.epoch++;
        require(assess(c).reasons & FGS_RETAIN_STALE_EVIDENCE, "previous scene accepted"); ++cases;

        // Preserving Cr cannot bypass its relationship with newly synthesized
        // Y/Cb. Neither independent Y/C checks nor AV1 syntax proves Cb/Cr.
        for (unsigned bit = 0; bit < 4; ++bit) for (bool failed : {false, true}) {
            decision = film_grain_select_retention(key, .1f, [&](const FilmGrainRetentionRequest& request) {
                auto v = supported(request);
                if (request.component == 2) v.checks.passed &= ~FGS_RETAIN_FINITE_SYNTHESIS;
                return v;
            }, [&](const FilmGrainRetentionCombination& selected) {
                require(selected.retain[2] == 1 && selected.modelId[2] == 0, "joint test did not see actual source fallback");
                auto j = jointPass(selected); j.checks.passed &= ~(1u << bit);
                if (!failed) j.checks.measured &= ~(1u << bit);
                return j;
            });
            require(sourceOnly(decision) && decision.jointEvaluations == 1, "joint failure did not clear every grain model");
            require(decision.evaluations[1] == 1 && decision.evaluations[2] == 5, "joint failure caused backtracking");
            require(decision.jointReasons & FGS_RETAIN_JOINT_UNPROVEN, "joint fallback reason missing");
            require(decision.beforeJoint.retain[2] == 1 && decision.beforeJoint.modelId[0] != 0, "failed combination not recorded"); ++cases;
        }
        decision = film_grain_select_retention(key, .1f, supported, [](const FilmGrainRetentionCombination& selected) {
            auto j = jointPass(selected); j.combination.modelId[0]++; return j;
        });
        require(sourceOnly(decision) && (decision.jointReasons & FGS_RETAIN_STALE_EVIDENCE), "different shared model accepted"); ++cases;
        for (float y : {1.f, -.1f, .75f, std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity()}) {
            decision = film_grain_select_retention(key, y,
                [](const FilmGrainRetentionRequest&) -> FilmGrainRetentionCandidate { throw std::runtime_error("unexpected work"); },
                [](const FilmGrainRetentionCombination&) -> FilmGrainRetentionJointEvidence { throw std::runtime_error("unexpected joint work"); });
            require(sourceOnly(decision) && decision.evaluations == std::array<unsigned, 3>{}, "terminal source policy ran candidates"); ++cases;
        }
        decision = film_grain_select_retention(key, .1f, [](const FilmGrainRetentionRequest& request) {
            auto v = supported(request); v.checks.passed &= ~FGS_RETAIN_DETAIL; return v;
        }, [](const FilmGrainRetentionCombination&) -> FilmGrainRetentionJointEvidence { throw std::runtime_error("unexpected joint work"); });
        require(sourceOnly(decision) && decision.evaluations == std::array<unsigned, 3>{{1, 0, 0}}, "luma safety failure reached colour search"); ++cases;
        std::cout << "retention selector: " << cases << " decision/coverage cases passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
