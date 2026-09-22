// Compare actual synthesized moments with independently supported targets.
// Experimental CPU analysis only; no encoder decisions use this helper.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainJointModel.h"

namespace fgsmodel {
struct FilmGrainJointSynthesisFidelity {
    bool valid = false;
    double chromaVarianceError = 0.0; // Signed fractions, not percentages.
    double averagedLumaVarianceError = 0.0;
    double maximumVarianceError = 0.0;
    double maximumCovarianceError = 0.0;
    double rmsCovarianceError = 0.0;
    double lumaChromaCovarianceError = 0.0;

    bool needsSource(double varianceTolerance = .08, double covarianceTolerance = .08) const {
        return !valid || !std::isfinite(varianceTolerance) || !std::isfinite(covarianceTolerance)
            || varianceTolerance < 0.0 || varianceTolerance > 1.0
            || covarianceTolerance < 0.0 || covarianceTolerance > 1.0
            || maximumVarianceError > varianceTolerance
            || maximumCovarianceError > covarianceTolerance;
    }
};

// A good predictor fit does not establish that the decoder produces the same
// covariance: finite block boundaries, clipping, rounding and the luma driver
// all affect the emitted picture. Compare independently measured synthesis,
// including those effects, in the SAME units and detrending convention as the
// source/base target. Keep train/holdout separation and minimum source support
// outside this mathematical helper. Passing is not whole-picture eligibility.
//
// Normalize each covariance error by the target standard deviations, never
// by the possibly near-zero target cross term. Test every diagonal as well as
// the current C and averaged Y; errors in neighbour energy must not be hidden.
inline FilmGrainJointSynthesisFidelity film_grain_joint_synthesis_fidelity(
    const FilmGrainJointTarget& target, const FilmGrainJointTarget& synthesis) {
    constexpr size_t N = FGS_JOINT_VARIABLES;
    FilmGrainJointSynthesisFidelity result;
    if (!target.valid || !synthesis.valid
        || !joint_model_detail::semidefinite<N>(target.covariance)
        || !joint_model_detail::semidefinite<N>(synthesis.covariance)) return result;
    std::array<double, N> sigma{};
    for (size_t i = 0; i < N; ++i) {
        const double variance = target.covariance[i*N+i];
        if (variance <= 1e-12) return result;
        sigma[i] = std::sqrt(variance);
        const double error = synthesis.covariance[i*N+i] / variance - 1.0;
        if (!std::isfinite(error)) return result;
        result.maximumVarianceError = std::max(result.maximumVarianceError, std::abs(error));
        if (i == 24) result.averagedLumaVarianceError = error;
        if (i == 25) result.chromaVarianceError = error;
    }
    double squares = 0.0;
    for (size_t i = 0; i < N; ++i) for (size_t j = 0; j < i; ++j) {
        const double error = (synthesis.covariance[i*N+j] - target.covariance[i*N+j])
            / (sigma[i] * sigma[j]);
        if (!std::isfinite(error) || !std::isfinite(error * error)) return result;
        result.maximumCovarianceError = std::max(result.maximumCovarianceError, std::abs(error));
        squares += error * error;
        if (i == 25 && j == 24) result.lumaChromaCovarianceError = error;
    }
    result.rmsCovarianceError = std::sqrt(squares / (N * (N - 1) / 2));
    result.valid = std::isfinite(result.rmsCovarianceError);
    return result;
}
} // namespace fgsmodel
