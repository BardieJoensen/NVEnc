// Common-coordinate Y/Cb/Cr reconstruction checks for experimental retention.
// Offline CPU mathematics, not encoder qualification. MIT, as the model header.
#pragma once
#include "NVEncFilmGrainJointCollect.h"
#include "NVEncFilmGrainJointModel.h"

namespace fgsmodel {
struct FilmGrainColourMoments {
    // Sums in 8-bit code units, from identical detrended 26x26 observations.
    // Fixed Y/Cb/Cr order; Cb(x,y)/Cr(x+dx,y+dy), -3..3 row-major.
    std::array<double, 9> covariance{};
    std::array<double, 49> cbCrLag{};
    uint64_t blocks = 0, observations = 0, jointlySupportedBlocks = 0;
    uint64_t cohortId = 0; // Same independent source-selected coordinates.
};
struct FilmGrainColourFidelity {
    bool valid = false;
    std::array<double, 3> varianceError{};
    std::array<double, 3> pairError{}; // Y/Cb, Y/Cr, Cb/Cr normalized by source sigma.
    double maximumVarianceError = 0, maximumCovarianceError = 0, maximumCbCrLagError = 0;
    bool needsSource(double varianceLimit = .08, double covarianceLimit = .08) const {
        return !valid || !std::isfinite(varianceLimit) || !std::isfinite(covarianceLimit)
            || varianceLimit < 0 || varianceLimit > 1 || covarianceLimit < 0 || covarianceLimit > 1
            || maximumVarianceError > varianceLimit || maximumCovarianceError > covarianceLimit
            || maximumCbCrLagError > covarianceLimit;
    }
};
// The collector's colour matrices include every selected-component tile, even
// when the OTHER component failed its source gate. Do not treat the group's
// support count as a mask for moments that were already aggregated. Only an
// all-common cohort can be admitted here; otherwise recollect the intersection.
inline bool film_grain_colour_source_base(const FilmGrainCollectGroup& group, uint64_t cohortId,
    FilmGrainColourMoments& source, FilmGrainColourMoments& base) {
    source = {}; base = {};
    if (!cohortId || group.blocks < 16 || group.blocks > 10000000
        || group.observations != group.blocks * 676 || group.observations > 1000000000
        || group.otherColourSupportedBlocks != group.blocks) return false;
    constexpr unsigned colour = 3 * FGS_COLLECT_MATRIX;
    constexpr unsigned lag = colour + 3 * 9;
    std::copy_n(group.moments + colour, 9, source.covariance.begin());
    std::copy_n(group.moments + colour + 9, 9, base.covariance.begin());
    std::copy_n(group.moments + lag, 49, source.cbCrLag.begin());
    std::copy_n(group.moments + lag + 49, 49, base.cbCrLag.begin());
    source.blocks = base.blocks = group.blocks;
    source.observations = base.observations = group.observations;
    source.jointlySupportedBlocks = base.jointlySupportedBlocks = group.blocks;
    source.cohortId = base.cohortId = cohortId;
    return true;
}

// Compare the source with independently measured TOTAL reconstruction. Do not
// substitute synthesis alone, or assume Cov(base,grain)==0 on a finite decoded
// picture. The caller must measure the actual combination at these coordinates.
// This checks source-supported colour texture; it does not certify coverage,
// source detail, banding, clipping, temporal stability or perceptual quality.
inline FilmGrainColourFidelity film_grain_colour_fidelity(const FilmGrainColourMoments& source,
    const FilmGrainColourMoments& reconstructed) {
    FilmGrainColourFidelity result;
    if (!source.cohortId || source.cohortId != reconstructed.cohortId
        || source.blocks < 16 || source.blocks > 10000000 || source.blocks != reconstructed.blocks
        || source.observations != source.blocks * 676 || source.observations > 1000000000
        || source.observations != reconstructed.observations
        || source.jointlySupportedBlocks != source.blocks
        || reconstructed.jointlySupportedBlocks != source.blocks) return result;
    std::array<double, 9> s{}, r{};
    for (unsigned i = 0; i < 9; ++i) {
        s[i] = source.covariance[i] / source.observations;
        r[i] = reconstructed.covariance[i] / source.observations;
        if (!std::isfinite(s[i]) || !std::isfinite(r[i]) || std::abs(s[i]) > 65536
            || std::abs(r[i]) > 65536) return result;
    }
    if (!joint_model_detail::semidefinite<3>(s) || !joint_model_detail::semidefinite<3>(r)) return result;
    // Zero source variance is a strict mathematical case, not a relaxed
    // "quiet enough" perceptual threshold. Any reconstructed energy rejects it.
    for (unsigned p = 0; p < 3; ++p) {
        const double reference = s[p*3+p], actual = r[p*3+p];
        for (unsigned q = 0; q < 3; ++q) {
            if ((reference == 0 && (s[p*3+q] != 0 || s[q*3+p] != 0))
                || (actual == 0 && (r[p*3+q] != 0 || r[q*3+p] != 0))) return result;
        }
        if (reference == 0) {
            if (actual != 0) return result;
        } else {
            result.varianceError[p] = actual / reference - 1;
            if (!std::isfinite(result.varianceError[p])) return result;
            result.maximumVarianceError = std::max(result.maximumVarianceError, std::abs(result.varianceError[p]));
        }
    }
    const auto normalizedError = [](double difference, double a, double b, double& error) {
        if (!std::isfinite(difference)) return false;
        const double scale = std::sqrt(a) * std::sqrt(b);
        if (scale == 0) { error = 0; return difference == 0; }
        error = difference / scale;
        return std::isfinite(error);
    };
    const unsigned first[3] = {0, 0, 1}, second[3] = {1, 2, 2};
    for (unsigned pair = 0; pair < 3; ++pair) {
        const unsigned a = first[pair], b = second[pair];
        if (!normalizedError(r[a*3+b]-s[a*3+b], s[a*3+a], s[b*3+b], result.pairError[pair])) return result;
        result.maximumCovarianceError = std::max(result.maximumCovarianceError, std::abs(result.pairError[pair]));
    }
    for (unsigned lag = 0; lag < 49; ++lag) {
        // Check both terms, so NaN/inf cannot cancel or silently pass.
        const double a = source.cbCrLag[lag] / source.observations;
        const double b = reconstructed.cbCrLag[lag] / source.observations;
        double error = 0;
        if (!std::isfinite(a) || !std::isfinite(b) || std::abs(a) > 65536 || std::abs(b) > 65536
            || ((s[4] == 0 || s[8] == 0) && a != 0)
            || ((r[4] == 0 || r[8] == 0) && b != 0)
            || !normalizedError(b-a, s[4], s[8], error)) return result;
        result.maximumCbCrLagError = std::max(result.maximumCbCrLagError, std::abs(error));
    }
    // The centre lag is the same Cb/Cr measurement as the 3x3 matrix.
    const double tolerance = std::max(1e-12, std::max(s[4], s[8]) * 1e-9);
    if (std::abs(source.cbCrLag[24] / source.observations - s[5]) > tolerance
        || std::abs(reconstructed.cbCrLag[24] / source.observations - r[5]) > tolerance) return result;
    result.valid = true;
    return result;
}
} // namespace fgsmodel
