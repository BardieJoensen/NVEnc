// -----------------------------------------------------------------------------------------
// NVEnc by rigaya
// -----------------------------------------------------------------------------------------
//
// The MIT License
//
// Copyright (c) 2026 NVEnc contributors
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.
//
// Flat-block scoring, lag-3 AR modeling, strength fitting, and AV1 parameter
// quantization follow the design in libaom aom_dsp/noise_model.c.  That source
// is Copyright (c) 2017 Alliance for Open Media and is licensed under the BSD
// 2-Clause License and Alliance for Open Media Patent License 1.0.  This file
// is an independent implementation and does not require libaom at runtime.
// ------------------------------------------------------------------------------------------

#if defined(_WIN32) && !defined(NOMINMAX)
#define NOMINMAX
#endif

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>

#include "NVEncFilmGrainModel.h"

NVEncFilmGrainDiagnostics::NVEncFilmGrainDiagnostics() :
    flatBlocks(0), totalBlocks(0), modelFrames(0), noiseStdDev(), observations(),
    detailRisk(0.0f), residualRetain(0.0f), grainCorrelation(0.0f),
    sourceModelCorrelation(0.0f), sourceArScale(1.0f), sourceStrengthGain(1.0f),
    sourceRegularizationRejected(false),
    reliable(false), sceneReset(false), modelHeld(false) {
}

namespace fgsmodel {

bool solve_linear_system(std::vector<double> matrix, std::vector<double> rhs, std::vector<double>& solution, const int n) {
    if (static_cast<int>(matrix.size()) != n * n || static_cast<int>(rhs.size()) != n) return false;
    double diagonalMean = 0.0;
    for (int i = 0; i < n; ++i) diagonalMean += std::abs(matrix[i * n + i]);
    diagonalMean /= n;
    const double regularization = std::max(1e-9, diagonalMean * 1e-6);
    for (int i = 0; i < n; ++i) matrix[i * n + i] += regularization;
    for (int column = 0; column < n; ++column) {
        int pivot = column;
        for (int row = column + 1; row < n; ++row) {
            if (std::abs(matrix[row * n + column]) > std::abs(matrix[pivot * n + column])) pivot = row;
        }
        if (!std::isfinite(matrix[pivot * n + column])
            || std::abs(matrix[pivot * n + column]) < regularization * 1e-5) return false;
        if (pivot != column) {
            for (int j = column; j < n; ++j) std::swap(matrix[column * n + j], matrix[pivot * n + j]);
            std::swap(rhs[column], rhs[pivot]);
        }
        const double divisor = matrix[column * n + column];
        for (int row = column + 1; row < n; ++row) {
            const double factor = matrix[row * n + column] / divisor;
            if (factor == 0.0) continue;
            matrix[row * n + column] = 0.0;
            for (int j = column + 1; j < n; ++j) matrix[row * n + j] -= factor * matrix[column * n + j];
            rhs[row] -= factor * rhs[column];
        }
    }
    solution.assign(n, 0.0);
    for (int row = n - 1; row >= 0; --row) {
        double value = rhs[row];
        for (int j = row + 1; j < n; ++j) value -= matrix[row * n + j] * solution[j];
        solution[row] = value / matrix[row * n + row];
        if (!std::isfinite(solution[row])) return false;
    }
    return true;
}

FilmGrainSolvedPlane solve_plane(const FilmGrainGpuPlaneStats& stats, const bool chroma,
    const FilmGrainSolvedPlane *lumaSolved) {
    FilmGrainSolvedPlane solved;
    const int n = chroma ? FGS_AR_COEFFS_CHROMA : FGS_AR_COEFFS;
    const int triCount = chroma ? FGS_TRI_C : FGS_TRI_Y;
    if (stats.observations < 256) return solved;
    std::vector<double> matrix(n * n, 0.0);
    std::vector<double> rhs(n, 0.0);
    for (int i = 0; i < n; ++i) {
        rhs[i] = static_cast<double>(stats.atb[i]);
        for (int j = i; j < n; ++j) {
            const int index = tri_index(n, i, j);
            if (index >= triCount) return solved;
            matrix[i * n + j] = matrix[j * n + i] = static_cast<double>(stats.ata[index]);
        }
    }
    if (!solve_linear_system(matrix, rhs, solved.coeffs, n)) return solved;
    for (const auto coeff : solved.coeffs) {
        if (!std::isfinite(coeff) || std::abs(coeff) > 2.0) return solved;
    }
    const int spatialCoeffs = chroma ? n - 1 : n;
    double predictorVariance = 0.0;
    for (int i = 0; i < spatialCoeffs; ++i) predictorVariance += matrix[i * n + i] / stats.observations;
    predictorVariance /= spatialCoeffs;
    double explained = 0.0;
    for (int i = 0; i < spatialCoeffs; ++i) {
        double bi = rhs[i];
        if (chroma) bi -= matrix[i * n + n - 1] * solved.coeffs[n - 1];
        explained += bi * solved.coeffs[i] / stats.observations;
    }
    const double innovationVariance = std::max(1e-6, predictorVariance - explained);
    solved.arGain = std::max(1.0, std::sqrt(std::max(1e-6, predictorVariance / innovationVariance)));
    if (!std::isfinite(solved.arGain) || solved.arGain > 16.0) return solved;
    // For chroma the decoder synthesizes scaling(x) * (AR + corr * avgLumaGrain),
    // so the correlated part of the chroma noise must not also be counted in the
    // scaling curve (libaom add_noise_std_observations).  The curve is derived
    // from the total variance divided by the template variance including the
    // correlated term; the total synthesized chroma energy then matches the
    // measurement even when the correlation coefficient clamps.
    double templateVariance = solved.arGain * solved.arGain;
    if (chroma && lumaSolved && lumaSolved->valid) {
        double totalVarSum = 0.0;
        uint64_t totalWeight = 0;
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            totalVarSum += stats.binVarSum[bin];
            totalWeight += stats.binBlockCount[bin];
        }
        double lumaVarSum = 0.0;
        uint64_t lumaWeight = 0;
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            const double lumaStd = lumaSolved->strength[bin] * lumaSolved->arGain;
            lumaVarSum += lumaStd * lumaStd * lumaSolved->strengthWeight[bin];
            lumaWeight += lumaSolved->strengthWeight[bin];
        }
        const double sigmaPred2 = stats.lumaPredBlocks > 0
            ? stats.lumaPredVarSum / static_cast<double>(stats.lumaPredBlocks) : 0.0;
        if (totalWeight > 0 && lumaWeight > 0 && sigmaPred2 > 1e-6 && lumaVarSum > 0.0) {
            const double corrFit = solved.coeffs.back();
            const double sigmaLuma = std::sqrt(lumaVarSum / lumaWeight);
            const double totalVar = totalVarSum / totalWeight;
            // The regression predictor is the 2x2-averaged luma residual, so the
            // correlated chroma variance is corr^2 * var(predictor), not
            // corr^2 * var(luma).
            const double corrVar = std::min(corrFit * corrFit * sigmaPred2, totalVar * 15.0 / 16.0);
            const double uncorrStd = std::sqrt(std::max(totalVar / 16.0, totalVar - corrVar));
            const double corrIdeal = corrFit * (sigmaLuma / lumaSolved->arGain)
                / std::max(1e-6, uncorrStd / solved.arGain);
            solved.signalCorrelation = std::min(1.9, std::max(-1.9, corrIdeal));
            const double avgLumaTemplateStd = std::sqrt(sigmaPred2) / sigmaLuma * lumaSolved->arGain;
            templateVariance += solved.signalCorrelation * solved.signalCorrelation
                * avgLumaTemplateStd * avgLumaTemplateStd;
        }
    }
    solved.templateGain = std::sqrt(templateVariance);
    int populatedBins = 0;
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        solved.strengthWeight[bin] = stats.binBlockCount[bin];
        if (stats.binBlockCount[bin] == 0) continue;
        const double variance = std::max(0.0,
            stats.binVarSum[bin] / static_cast<double>(stats.binBlockCount[bin]));
        solved.strength[bin] = std::sqrt(variance) / solved.templateGain;
        ++populatedBins;
    }
    if (populatedBins == 0) return solved;
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        if (solved.strengthWeight[bin] != 0) continue;
        int left = bin - 1;
        while (left >= 0 && solved.strengthWeight[left] == 0) --left;
        int right = bin + 1;
        while (right < FGS_STRENGTH_BINS && solved.strengthWeight[right] == 0) ++right;
        if (left < 0) solved.strength[bin] = solved.strength[right];
        else if (right >= FGS_STRENGTH_BINS) solved.strength[bin] = solved.strength[left];
        else {
            const double mix = static_cast<double>(bin - left) / (right - left);
            solved.strength[bin] = solved.strength[left] * (1.0 - mix) + solved.strength[right] * mix;
        }
    }
    auto smoothed = solved.strength;
    for (int bin = 1; bin + 1 < FGS_STRENGTH_BINS; ++bin) {
        smoothed[bin] = (solved.strength[bin - 1] + 2.0 * solved.strength[bin] + solved.strength[bin + 1]) * 0.25;
    }
    solved.strength = smoothed;
    solved.valid = true;
    return solved;
}

double implied_luma_correlation(const std::vector<double>& coeffs, const double scale) {
    if (coeffs.size() != FGS_AR_COEFFS || !std::isfinite(scale)) return 0.0;
    // Match the AV1 lag-3 luma template footprint.  The fixed hash supplies a
    // deterministic white field; only correlation is measured, so its uniform
    // distribution does not affect the AR process's covariance.  Avoiding a
    // random library makes table decisions repeatable across runs and hosts.
    constexpr int width = 82;
    constexpr int height = 73;
    std::array<double, width * height> field = {};
    for (size_t index = 0; index < field.size(); ++index) {
        const uint32_t hash = fgs_sample_hash(static_cast<uint32_t>(index) + 0x9e3779b9U);
        field[index] = (static_cast<double>(hash & 0xffffU) - 32767.5) / 32767.5;
    }
    for (int y = FGS_AR_LAG; y < height; ++y) {
        for (int x = FGS_AR_LAG; x < width - FGS_AR_LAG; ++x) {
            double value = field[y * width + x];
            int coefficient = 0;
            for (int dy = -FGS_AR_LAG; dy < 0; ++dy) {
                for (int dx = -FGS_AR_LAG; dx <= FGS_AR_LAG; ++dx) {
                    value += coeffs[coefficient++] * scale * field[(y + dy) * width + x + dx];
                }
            }
            for (int dx = -FGS_AR_LAG; dx < 0; ++dx) {
                value += coeffs[coefficient++] * scale * field[y * width + x + dx];
            }
            if (!std::isfinite(value) || std::abs(value) > 1e100) return 1.0;
            field[y * width + x] = value;
        }
    }
    const int x0 = FGS_AR_LAG;
    const int x1 = width - FGS_AR_LAG;
    const int y0 = FGS_AR_LAG;
    double mean = 0.0;
    uint64_t count = 0;
    for (int y = y0; y < height; ++y) {
        for (int x = x0; x < x1; ++x) {
            mean += field[y * width + x];
            ++count;
        }
    }
    mean /= std::max<uint64_t>(1, count);
    double variance = 0.0;
    double horizontal = 0.0;
    double vertical = 0.0;
    uint64_t horizontalCount = 0;
    uint64_t verticalCount = 0;
    for (int y = y0; y < height; ++y) {
        for (int x = x0; x < x1; ++x) {
            const double value = field[y * width + x] - mean;
            variance += value * value;
            if (x > x0) {
                horizontal += value * (field[y * width + x - 1] - mean);
                ++horizontalCount;
            }
            if (y > y0) {
                vertical += value * (field[(y - 1) * width + x] - mean);
                ++verticalCount;
            }
        }
    }
    variance /= std::max<uint64_t>(1, count);
    if (!(variance > 1e-12) || !std::isfinite(variance)) return 0.0;
    const double h = horizontal / std::max<uint64_t>(1, horizontalCount) / variance;
    const double v = vertical / std::max<uint64_t>(1, verticalCount) / variance;
    return std::clamp(0.5 * (h + v), -1.0, 1.0);
}

static bool regularize_source_luma(const FilmGrainGpuPlaneStats& stats,
    FilmGrainSolvedPlane& solved, const double maxCorrelation,
    NVEncFilmGrainDiagnostics& diagnostics) {
    diagnostics.sourceArScale = 1.0f;
    diagnostics.sourceStrengthGain = 1.0f;
    diagnostics.sourceRegularizationRejected = false;
    diagnostics.sourceModelCorrelation = 0.0f;
    // The shipping/default residual path must pay no simulator cost and must
    // remain byte-identical.  A negative ceiling means source regularisation
    // was not requested.
    if (maxCorrelation < 0.0) return true;
    diagnostics.sourceModelCorrelation = static_cast<float>(
        implied_luma_correlation(solved.coeffs));
    if (diagnostics.sourceModelCorrelation <= maxCorrelation) return true;

    double low = 0.0;
    double high = 1.0;
    for (int iteration = 0; iteration < 10; ++iteration) {
        const double middle = 0.5 * (low + high);
        if (implied_luma_correlation(solved.coeffs, middle) <= maxCorrelation) low = middle;
        else high = middle;
    }

    const double observations = static_cast<double>(stats.observations);
    if (!(observations > 0.0)) return false;
    double targetVariance = 0.0;
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        targetVariance += static_cast<double>(
            stats.ata[tri_index(FGS_AR_COEFFS, i, i)]) / observations;
    }
    targetVariance /= FGS_AR_COEFFS;
    std::vector<double> regularized = solved.coeffs;
    for (auto& coefficient : regularized) coefficient *= low;
    double residualVariance = targetVariance;
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        residualVariance -= 2.0 * regularized[i]
            * static_cast<double>(stats.atb[i]) / observations;
        for (int j = 0; j < FGS_AR_COEFFS; ++j) {
            const int lo = std::min(i, j);
            const int hi = std::max(i, j);
            residualVariance += regularized[i] * regularized[j]
                * static_cast<double>(stats.ata[tri_index(FGS_AR_COEFFS, lo, hi)])
                / observations;
        }
    }
    const double newArGain = std::max(1.0, std::sqrt(
        std::max(1e-6, targetVariance) / std::max(1e-6, residualVariance)));
    const double strengthGain = solved.templateGain / newArGain;
    diagnostics.sourceArScale = static_cast<float>(low);
    diagnostics.sourceStrengthGain = static_cast<float>(strengthGain);
    diagnostics.sourceModelCorrelation = static_cast<float>(
        implied_luma_correlation(solved.coeffs, low));
    if (!std::isfinite(newArGain) || !std::isfinite(strengthGain)
        || newArGain > 16.0 || strengthGain > FGS_SOURCE_MAX_STRENGTH_GAIN) {
        diagnostics.sourceRegularizationRejected = true;
        return false;
    }

    solved.coeffs = std::move(regularized);
    solved.arGain = newArGain;
    solved.templateGain = newArGain;
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        solved.strength[bin] *= strengthGain;
    }
    return true;
}

std::vector<StrengthPoint> fit_strength_points(const FilmGrainSolvedPlane& solved, const int bitDepth, const int maxPoints) {
    std::vector<StrengthPoint> points;
    const double maxValue = static_cast<double>((1 << bitDepth) - 1);
    const double depthScale = static_cast<double>(1 << (bitDepth - 8));
    points.reserve(FGS_STRENGTH_BINS);
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        points.emplace_back(bin * maxValue / (FGS_STRENGTH_BINS - 1) / depthScale,
            std::max(0.0, solved.strength[bin] / depthScale));
    }
    while (static_cast<int>(points.size()) > maxPoints) {
        size_t remove = 1;
        double leastError = std::numeric_limits<double>::max();
        for (size_t i = 1; i + 1 < points.size(); ++i) {
            const double mix = (points[i].first - points[i - 1].first)
                / std::max(1e-9, points[i + 1].first - points[i - 1].first);
            const double estimate = points[i - 1].second * (1.0 - mix) + points[i + 1].second * mix;
            const double error = std::abs(points[i].second - estimate) * (points[i + 1].first - points[i - 1].first);
            if (error < leastError) { leastError = error; remove = i; }
        }
        points.erase(points.begin() + remove);
    }
    return points;
}

void add_plane_stats(FilmGrainGpuPlaneStats& dst, const FilmGrainGpuPlaneStats& src) {
    for (int i = 0; i < FGS_TRI_C; ++i) dst.ata[i] += src.ata[i];
    for (int i = 0; i < FGS_AR_COEFFS_CHROMA; ++i) dst.atb[i] += src.atb[i];
    for (int i = 0; i < FGS_STRENGTH_BINS; ++i) {
        dst.binVarSum[i] += src.binVarSum[i];
        dst.binBlockCount[i] += src.binBlockCount[i];
    }
    dst.lumaPredVarSum += src.lumaPredVarSum;
    dst.lumaPredBlocks += src.lumaPredBlocks;
    dst.observations += src.observations;
}

bool build_film_grain_params(const FilmGrainGpuStats& stats, const int bitDepth,
    const bool analyzeChroma, const bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics, const double maxLumaCorrelation) {
    std::array<FilmGrainSolvedPlane, 3> solved;
    solved[0] = solve_plane(stats.plane[0], false, nullptr);
    if (!solved[0].valid) return false;
    if (!regularize_source_luma(
        stats.plane[0], solved[0], maxLumaCorrelation, diagnostics)) return false;
    if (analyzeChroma) {
        // AV1 4:2:0 requires grain on both chroma components or neither.  A
        // single solvable chroma plane must therefore degrade to luma-only
        // grain; numCbPoints=0 with numCrPoints>0 (or the reverse) is a
        // non-conformant frame header.
        solved[1] = solve_plane(stats.plane[1], true, &solved[0]);
        solved[2] = solve_plane(stats.plane[2], true, &solved[0]);
        if (!solved[1].valid || !solved[2].valid) {
            solved[1] = FilmGrainSolvedPlane();
            solved[2] = FilmGrainSolvedPlane();
        }
    }
    // The decoder builds its grain template by running the AR recursion over
    // innovation samples of std 2^(bitDepth-3) and clipping every output to
    // +/-2^(bitDepth-1), so the clip sits at 4/arGain standard deviations --
    // independent of bit depth, because both scale together.  White grain has
    // arGain ~1 and never reaches it.  A correlated fit does: at arGain 3.4 the
    // limit is 1.2 sigma, 13% of template samples saturate, and the realised
    // template std falls ~30% below the value the strength curve was divided
    // by, so the synthesised grain lands ~30% weak.  Measured on coarse_luma:
    // predicted 3.554 against 2.490 delivered, and the shortfall matches the
    // simulated clipping loss to within 0.02 on every arm tested.
    //
    // grain_scale_shift is the format's lever for exactly this.  It scales the
    // innovation down before the recursion, giving it headroom, and the
    // strength curve scales up by the same factor so the signalled sigma is
    // unchanged.  Pick the smallest shift that pushes the clip out to
    // FGS_TEMPLATE_CLIP_SIGMA; it stays 0 for white grain, which keeps
    // fine-grain content bit-identical.
    double maxArGain = 0.0;
    for (const auto& plane : solved) {
        if (plane.valid) maxArGain = std::max(maxArGain, plane.arGain);
    }
    int grainScaleShift = 0;
    while (grainScaleShift < FGS_MAX_GRAIN_SCALE_SHIFT
        && 4.0 * (1 << grainScaleShift) < FGS_TEMPLATE_CLIP_SIGMA * maxArGain) {
        ++grainScaleShift;
    }
    if (grainScaleShift > 0) {
        // strength * templateGain is the signalled sigma and must not move;
        // only the split between curve and template changes.
        const double scale = static_cast<double>(1 << grainScaleShift);
        for (auto& plane : solved) {
            if (!plane.valid) continue;
            plane.templateGain /= scale;
            for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) plane.strength[bin] *= scale;
        }
    }
    std::array<std::vector<StrengthPoint>, 3> points = {
        fit_strength_points(solved[0], bitDepth, 14),
        solved[1].valid ? fit_strength_points(solved[1], bitDepth, 10) : std::vector<StrengthPoint>(),
        solved[2].valid ? fit_strength_points(solved[2], bitDepth, 10) : std::vector<StrengthPoint>()
    };
    double maxScaling = 1e-4;
    for (const auto& planePoints : points) {
        for (const auto& point : planePoints) maxScaling = std::max(maxScaling, point.second);
    }
    const int maxScalingLog2 = std::clamp(static_cast<int>(std::floor(std::log2(maxScaling)) + 1), 2, 5);
    const int scalingShift = 5 + (8 - maxScalingLog2);
    const double scalingFactor = static_cast<double>(1 << (8 - maxScalingLog2));

    std::memset(&params, 0, sizeof(params));
    std::fill(std::begin(params.arCoeffsYPlus128), std::end(params.arCoeffsYPlus128), static_cast<uint8_t>(128));
    std::fill(std::begin(params.arCoeffsCbPlus128), std::end(params.arCoeffsCbPlus128), static_cast<uint8_t>(128));
    std::fill(std::begin(params.arCoeffsCrPlus128), std::end(params.arCoeffsCrPlus128), static_cast<uint8_t>(128));
    params.applyGrain = 1;
    params.overlapFlag = 1;
    params.clipToRestrictedRange = limitedRange ? 1 : 0;
    params.grainScalingMinus8 = scalingShift - 8;
    params.arCoeffLag = FGS_AR_LAG;
    params.grainScaleShift = static_cast<uint32_t>(grainScaleShift);
    params.numYPoints = static_cast<uint32_t>(points[0].size());
    for (size_t i = 0; i < points[0].size(); ++i) {
        params.pointYValue[i] = static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(points[0][i].first)), 0, 255));
        params.pointYScaling[i] = static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(points[0][i].second * scalingFactor)), 0, 255));
    }
    {
        params.numCbPoints = static_cast<uint32_t>(points[1].size());
        params.numCrPoints = static_cast<uint32_t>(points[2].size());
        for (size_t i = 0; i < points[1].size(); ++i) {
            params.pointCbValue[i] = static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(points[1][i].first)), 0, 255));
            params.pointCbScaling[i] = static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(points[1][i].second * scalingFactor)), 0, 255));
        }
        for (size_t i = 0; i < points[2].size(); ++i) {
            params.pointCrValue[i] = static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(points[2][i].first)), 0, 255));
            params.pointCrScaling[i] = static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(points[2][i].second * scalingFactor)), 0, 255));
        }
    }

    const std::array<double, 2> yCorrelation = { solved[1].signalCorrelation, solved[2].signalCorrelation };
    double maxCoeff = 1e-4;
    double minCoeff = -1e-4;
    for (int c = 0; c < 3; ++c) {
        if (!solved[c].valid) continue;
        for (int i = 0; i < FGS_AR_COEFFS; ++i) {
            maxCoeff = std::max(maxCoeff, solved[c].coeffs[i]);
            minCoeff = std::min(minCoeff, solved[c].coeffs[i]);
        }
    }
    for (const auto corr : yCorrelation) {
        maxCoeff = std::max(maxCoeff, corr);
        minCoeff = std::min(minCoeff, corr);
    }
    const int positiveExponent = 1 + static_cast<int>(std::floor(std::log2(std::max(maxCoeff, 1e-9))));
    const int negativeExponent = static_cast<int>(std::ceil(std::log2(std::max(-minCoeff, 1e-9))));
    const int arShift = std::clamp(7 - std::max(positiveExponent, negativeExponent), 6, 9);
    params.arCoeffShiftMinus6 = arShift - 6;
    const double coeffScale = static_cast<double>(1 << arShift);
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        params.arCoeffsYPlus128[i] = static_cast<uint8_t>(
            std::clamp(static_cast<int>(std::lround(solved[0].coeffs[i] * coeffScale)), -128, 127) + 128);
        if (solved[1].valid) {
            params.arCoeffsCbPlus128[i] = static_cast<uint8_t>(
                std::clamp(static_cast<int>(std::lround(solved[1].coeffs[i] * coeffScale)), -128, 127) + 128);
        }
        if (solved[2].valid) {
            params.arCoeffsCrPlus128[i] = static_cast<uint8_t>(
                std::clamp(static_cast<int>(std::lround(solved[2].coeffs[i] * coeffScale)), -128, 127) + 128);
        }
    }
    if (solved[1].valid) {
        params.arCoeffsCbPlus128[FGS_AR_COEFFS] = static_cast<uint8_t>(
            std::clamp(static_cast<int>(std::lround(yCorrelation[0] * coeffScale)), -128, 127) + 128);
        params.cbMult = 128;
        params.cbLumaMult = 192;
        params.cbOffset = 256;
    }
    if (solved[2].valid) {
        params.arCoeffsCrPlus128[FGS_AR_COEFFS] = static_cast<uint8_t>(
            std::clamp(static_cast<int>(std::lround(yCorrelation[1] * coeffScale)), -128, 127) + 128);
        params.crMult = 128;
        params.crLumaMult = 192;
        params.crOffset = 256;
    }
    for (int c = 0; c < 3; ++c) {
        diagnostics.observations[c] = stats.plane[c].observations;
        if (!solved[c].valid) continue;
        double weightedVariance = 0.0;
        uint64_t total = 0;
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            weightedVariance += solved[c].strength[bin] * solved[c].strength[bin] * solved[c].strengthWeight[bin];
            total += solved[c].strengthWeight[bin];
        }
        diagnostics.noiseStdDev[c] = total > 0
            ? static_cast<float>(std::sqrt(weightedVariance / total) * solved[c].templateGain) : 0.0f;
    }
    return true;
}

double eval_scaling_curve(const uint8_t *values, const uint8_t *scalings, const uint32_t count, const double x) {
    if (count == 0) return 0.0;
    if (x <= values[0]) return scalings[0];
    for (uint32_t i = 1; i < count; ++i) {
        if (x <= values[i]) {
            const double mix = (x - values[i - 1]) / std::max(1.0, static_cast<double>(values[i] - values[i - 1]));
            return scalings[i - 1] * (1.0 - mix) + scalings[i] * mix;
        }
    }
    return scalings[count - 1];
}

// True when the two parameter sets synthesize visually equivalent grain, so
// the previously signalled model can be held instead of flickering through
// per-frame requantization.  Distances are measured on the real-valued
// scaling curves (sigma in 8-bit code values) and AR coefficients, which is
// robust against the point fitter picking different knot positions.
bool film_grain_params_close(const NV_ENC_FILM_GRAIN_PARAMS_AV1& a, const NV_ENC_FILM_GRAIN_PARAMS_AV1& b,
    const double relativeSigmaTolerance, const double coefficientTolerance) {
    if (a.applyGrain != b.applyGrain) return false;
    const double sigmaScaleA = 1.0 / (1 << (a.grainScalingMinus8 + 8 - 5));
    const double sigmaScaleB = 1.0 / (1 << (b.grainScalingMinus8 + 8 - 5));
    double maxSigma = 0.0;
    double maxSigmaDiff = 0.0;
    const struct { const uint8_t *va, *sa, *vb, *sb; uint32_t na, nb; } curves[3] = {
        { a.pointYValue,  a.pointYScaling,  b.pointYValue,  b.pointYScaling,  a.numYPoints,  b.numYPoints },
        { a.pointCbValue, a.pointCbScaling, b.pointCbValue, b.pointCbScaling, a.numCbPoints, b.numCbPoints },
        { a.pointCrValue, a.pointCrScaling, b.pointCrValue, b.pointCrScaling, a.numCrPoints, b.numCrPoints },
    };
    for (const auto& curve : curves) {
        for (int x = 0; x <= 255; x += 15) {
            const double sigmaA = eval_scaling_curve(curve.va, curve.sa, curve.na, x) * sigmaScaleA;
            const double sigmaB = eval_scaling_curve(curve.vb, curve.sb, curve.nb, x) * sigmaScaleB;
            maxSigma = std::max(maxSigma, std::max(sigmaA, sigmaB));
            maxSigmaDiff = std::max(maxSigmaDiff, std::abs(sigmaA - sigmaB));
        }
    }
    if (maxSigmaDiff > std::max(0.10, relativeSigmaTolerance * maxSigma)) return false;
    const double coeffScaleA = 1.0 / (1 << (a.arCoeffShiftMinus6 + 6));
    const double coeffScaleB = 1.0 / (1 << (b.arCoeffShiftMinus6 + 6));
    double maxCoeffDiff = 0.0;
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        maxCoeffDiff = std::max(maxCoeffDiff, std::abs(
            (static_cast<int>(a.arCoeffsYPlus128[i]) - 128) * coeffScaleA
            - (static_cast<int>(b.arCoeffsYPlus128[i]) - 128) * coeffScaleB));
    }
    for (int i = 0; i < FGS_AR_COEFFS_CHROMA; ++i) {
        maxCoeffDiff = std::max(maxCoeffDiff, std::abs(
            (static_cast<int>(a.arCoeffsCbPlus128[i]) - 128) * coeffScaleA
            - (static_cast<int>(b.arCoeffsCbPlus128[i]) - 128) * coeffScaleB));
        maxCoeffDiff = std::max(maxCoeffDiff, std::abs(
            (static_cast<int>(a.arCoeffsCrPlus128[i]) - 128) * coeffScaleA
            - (static_cast<int>(b.arCoeffsCrPlus128[i]) - 128) * coeffScaleB));
    }
    return maxCoeffDiff <= coefficientTolerance;
}

void build_strength_lut(const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, const int bitDepth, float lut[FGS_STRENGTH_LUT_SIZE]) {
    if (!params.applyGrain || params.numYPoints == 0) {
        std::fill(lut, lut + FGS_STRENGTH_LUT_SIZE, 0.0f);
        return;
    }
    // The scaling curve stores sigma * 2^(scalingShift - 5) in 8-bit units
    // (see fit_strength_points / the scalingShift derivation); convert back to
    // a real std in the frame's native code values.
    const double sigmaScale = 1.0 / (1 << (params.grainScalingMinus8 + 8 - 5));
    const double depthScale = static_cast<double>(1 << (bitDepth - 8));
    for (int x = 0; x < FGS_STRENGTH_LUT_SIZE; ++x) {
        lut[x] = static_cast<float>(
            eval_scaling_curve(params.pointYValue, params.pointYScaling, params.numYPoints, x)
            * sigmaScale * depthScale);
    }
}

} // namespace fgsmodel
