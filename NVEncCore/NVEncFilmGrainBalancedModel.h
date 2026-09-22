// Shared chroma shape fitted against the worst supported brightness group.
// Experimental CPU mathematics only; no encoder call sites or policy changes.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <array>
#include <cmath>
#include <vector>
#include "NVEncFilmGrainJointModel.h"

namespace fgsmodel {
struct FilmGrainBalancedFit {
    bool valid = false;
    FilmGrainJointTarget normalizedTarget{};
    std::array<double, 25> predictors{};
    std::vector<double> weights, lumaScale, chromaScale;
    double maximumRelativeExcess = 0.0;
    double lowerBound = 0.0;
    double dualityGap = 0.0;
    unsigned iterations = 0;
};

// Normalize C neighbours/current C together and averaged Y separately. This
// allows one template shape to be compared at different source amplitudes.
// All normalization and weights use TRAINING evidence only. The caller must
// still test held-out moments using these same training scales and preserve
// the original independent amplitude/coverage checks.
//
// Minimize the worst relative predictor-error excess over each group's own
// optimum. The simplex dual gives a lower bound, so the stopping criterion is
// an optimization gap, not a relaxed picture-quality threshold. Pairwise
// weight transfers remove irrelevant groups instead of asymptotically leaving
// them a nonzero weight. A bounded failure to converge is rejected.
inline FilmGrainBalancedFit film_grain_fit_balanced_chroma(
    const std::vector<FilmGrainJointTarget>& training, unsigned maxIterations = 256,
    double optimizationTolerance = 1e-7) {
    constexpr size_t N = FGS_JOINT_VARIABLES;
    FilmGrainBalancedFit result;
    if (training.empty() || training.size() > 20 || maxIterations == 0 || maxIterations > 4096
        || !std::isfinite(optimizationTolerance) || optimizationTolerance <= 0.0
        || optimizationTolerance > 1e-4) return result;
    std::vector<FilmGrainJointTarget> normalized;
    std::vector<double> innovations;
    for (const auto& target : training) {
        if (!target.valid || !joint_model_detail::semidefinite<N>(target.covariance)) return result;
        const double cv = target.covariance[25*N+25], yv = target.covariance[24*N+24];
        if (cv <= 1e-12 || yv <= 1e-12) return result;
        result.chromaScale.push_back(std::sqrt(cv));
        result.lumaScale.push_back(std::sqrt(yv));
        auto unit = target;
        for (size_t i = 0; i < N; ++i) for (size_t j = 0; j < N; ++j)
            unit.covariance[i*N+j] /= (i == 24 ? std::sqrt(yv) : std::sqrt(cv))
                * (j == 24 ? std::sqrt(yv) : std::sqrt(cv));
        const auto fit = film_grain_fit_joint_chroma(unit, 1.0);
        if (!fit.valid || fit.innovationVariance <= 1e-8) return result;
        normalized.push_back(unit);
        innovations.push_back(fit.innovationVariance);
    }
    struct Solution {
        bool valid = false;
        FilmGrainJointTarget target{};
        std::array<double, 25> beta{};
        std::vector<double> errors;
        double lowerBound = 0.0;
    };
    const auto solve = [&](const std::vector<double>& weights) {
        Solution s;
        s.target.valid = true;
        for (size_t b = 0; b < training.size(); ++b) {
            if (!std::isfinite(weights[b]) || weights[b] < 0.0) return s;
            const double weight = weights[b] / innovations[b];
            for (size_t i = 0; i < N*N; ++i) s.target.covariance[i] += weight * normalized[b].covariance[i];
        }
        const auto fit = film_grain_fit_joint_chroma(s.target, 1.0);
        if (!fit.valid) return s;
        std::copy(fit.spatial.begin(), fit.spatial.end(), s.beta.begin());
        s.beta[24] = fit.rawLumaCoefficient;
        std::array<double, N> error{};
        for (size_t i = 0; i < 25; ++i) error[i] = -s.beta[i];
        error[25] = 1.0;
        for (size_t b = 0; b < training.size(); ++b) {
            double loss = 0.0;
            for (size_t i = 0; i < N; ++i) for (size_t j = 0; j < N; ++j)
                loss += error[i] * normalized[b].covariance[i*N+j] * error[j];
            loss = loss / innovations[b] - 1.0;
            if (!std::isfinite(loss) || loss < -1e-7) return s;
            s.errors.push_back(loss);
            s.lowerBound += weights[b] * loss;
        }
        s.valid = true;
        return s;
    };
    result.weights.assign(training.size(), 1.0 / training.size());
    for (unsigned iteration = 0; iteration <= maxIterations; ++iteration) {
        const auto s = solve(result.weights);
        if (!s.valid) return result;
        size_t toward = 0, away = training.size();
        for (size_t i = 0; i < training.size(); ++i) {
            if (s.errors[i] > s.errors[toward]) toward = i;
            if (result.weights[i] > 0.0 && (away == training.size() || s.errors[i] < s.errors[away])) away = i;
        }
        result.maximumRelativeExcess = s.errors[toward];
        result.lowerBound = s.lowerBound;
        result.dualityGap = result.maximumRelativeExcess - result.lowerBound;
        result.iterations = iteration;
        if (result.dualityGap < -1e-10) return result;
        if (result.dualityGap <= optimizationTolerance) {
            result.normalizedTarget = s.target;
            result.predictors = s.beta;
            result.valid = true;
            return result;
        }
        if (iteration == maxIterations || toward == away || away == training.size()) return result;
        const double available = result.weights[away];
        const auto transfer = [&](double amount) {
            auto w = result.weights;
            w[toward] += amount;
            w[away] = amount == available ? 0.0 : w[away] - amount;
            return w;
        };
        auto boundary = solve(transfer(available));
        if (!boundary.valid) return result;
        if (boundary.errors[toward] >= boundary.errors[away]) {
            result.weights = transfer(available);
        } else {
            double low = 0.0, high = available;
            for (unsigned step = 0; step < 36; ++step) {
                const double amount = (low + high) * .5;
                auto trial = solve(transfer(amount));
                if (!trial.valid) return result;
                if (trial.errors[toward] > trial.errors[away]) low = amount;
                else high = amount;
            }
            result.weights = transfer((low + high) * .5);
        }
    }
    return result;
}
} // namespace fgsmodel
