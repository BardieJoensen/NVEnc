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
#include "NVEncFilmGrainStability.h"

NVEncFilmGrainDiagnostics::NVEncFilmGrainDiagnostics() :
    flatBlocks(0), totalBlocks(0), modelFrames(0), noiseStdDev(), templateGain{1.0f, 1.0f, 1.0f}, observations(),
    detailRisk(0.0f), residualRetain(0.0f), grainCorrelation(0.0f), strengthFitError(),
    sourceFidelityFallback(false), freshModel(false), strengthRefit(false), reliable(false), rejectedModel(false), sceneReset(false), modelHeld(false) {
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

std::vector<StrengthPoint> fit_strength_points(const FilmGrainSolvedPlane& solved, const int bitDepth, const int maxPoints,
    const bool useBinCenters) {
    std::vector<StrengthPoint> points;
    const double maxValue = static_cast<double>((1 << bitDepth) - 1);
    const double depthScale = static_cast<double>(1 << (bitDepth - 8));
    points.reserve(FGS_STRENGTH_BINS);
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        // Collection uses floor(mean * bins / (maxValue + 1)). A bin
        // estimates an interval, not an endpoint on a 0..maxValue grid.
        const double intensity = useBinCenters
            ? (bin + 0.5) * 256.0 / FGS_STRENGTH_BINS
            : bin * maxValue / (FGS_STRENGTH_BINS - 1) / depthScale;
        points.emplace_back(intensity,
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
        dst.binLumaSum[i] += src.binLumaSum[i];
    }
    dst.intensityBlocks += src.intensityBlocks;
    dst.lumaPredVarSum += src.lumaPredVarSum;
    dst.lumaPredBlocks += src.lumaPredBlocks;
    dst.observations += src.observations;
}

bool build_film_grain_params(const FilmGrainGpuStats& stats, const int bitDepth,
    const bool analyzeChroma, const bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics, const bool useBinCenters) {
    diagnostics.rejectedModel = false;
    diagnostics.strengthRefit = false;
    std::array<FilmGrainSolvedPlane, 3> solved;
    solved[0] = solve_plane(stats.plane[0], false, nullptr);
    if (!solved[0].valid) return false;
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
    std::array<std::vector<StrengthPoint>, 3> points = {
        fit_strength_points(solved[0], bitDepth, 14, useBinCenters),
        solved[1].valid ? fit_strength_points(solved[1], bitDepth, 10, useBinCenters) : std::vector<StrengthPoint>(),
        solved[2].valid ? fit_strength_points(solved[2], bitDepth, 10, useBinCenters) : std::vector<StrengthPoint>()
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
    params.grainScaleShift = 0;
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
    // A small training residual and a finite fitted gain do not establish
    // stability of the decoder's feedback process. Non-stationary statistics
    // (and coefficient quantization) can put poles outside the unit circle,
    // producing repeating stripes even in an otherwise valid AV1 stream.
    // Reject the actual signalled model, so the caller preserves the source
    // rather than denoising it and attaching an unsafe synthesis layer.
    // Stable but slowly decaying feedback also produces visible periodic
    // texture, so require the synthesis decay margin as well as stability.
    if (!film_grain_ar_synthesis_safe(params.arCoeffsYPlus128, params.arCoeffLag, arShift)
        || (params.numCbPoints && !film_grain_ar_synthesis_safe(
            params.arCoeffsCbPlus128, params.arCoeffLag, arShift))
        || (params.numCrPoints && !film_grain_ar_synthesis_safe(
            params.arCoeffsCrPlus128, params.arCoeffLag, arShift))) {
        diagnostics.rejectedModel = true;
        std::memset(&params, 0, sizeof(params));
        return false;
    }
    for (int c = 0; c < 3; ++c) {
        diagnostics.observations[c] = stats.plane[c].observations;
        if (!solved[c].valid) continue;
        double weightedVariance = 0.0;
        diagnostics.templateGain[c] = static_cast<float>(solved[c].templateGain);
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

static double strength_observation_x(const FilmGrainGpuPlaneStats& stats,
    const int bin, const int bitDepth) {
    if (stats.intensityBlocks == 0) return (bin + 0.5) * 256.0 / FGS_STRENGTH_BINS;
    uint64_t blocks = 0;
    for (const auto count : stats.binBlockCount) blocks += count;
    if (blocks != stats.intensityBlocks || stats.binBlockCount[bin] == 0)
        return std::numeric_limits<double>::quiet_NaN();
    const double x = stats.binLumaSum[bin] / stats.binBlockCount[bin] / (1 << (bitDepth - 8));
    const double lo = bin * 256.0 / FGS_STRENGTH_BINS;
    const double hi = (bin + 1) * 256.0 / FGS_STRENGTH_BINS;
    if (!std::isfinite(x) || x < lo - 1e-4 || x > hi + 1e-4)
        return std::numeric_limits<double>::quiet_NaN();
    return x;
}

// A regularized curve can erase a well-supported sharp change in grain
// strength. Retry only its scaling points, using actual occupied bins rather
// than spending AV1's point budget on interpolated, unobserved intensities.
// The AR model has already passed the normal solver and synthesis guards.
static bool refit_occupied_strength(const FilmGrainGpuStats& stats, const int bitDepth,
    NV_ENC_FILM_GRAIN_PARAMS_AV1& params, NVEncFilmGrainDiagnostics& diagnostics) {
    std::array<std::vector<StrengthPoint>, 3> points;
    std::array<std::vector<uint64_t>, 3> weights;
    const int limits[3] = { 14, 10, 10 };
    const bool active[3] = { params.numYPoints > 0, params.numCbPoints > 0, params.numCrPoints > 0 };
    const double depthScale = static_cast<double>(1 << (bitDepth - 8));
    double maxScaling = 1e-4;
    for (int plane = 0; plane < 3; ++plane) {
        if (!active[plane]) continue;
        const double gain = diagnostics.templateGain[plane];
        if (!(gain > 0.0) || !std::isfinite(gain)) return false;
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            const auto count = stats.plane[plane].binBlockCount[bin];
            if (count == 0) continue;
            const double sigma = std::sqrt(stats.plane[plane].binVarSum[bin] / count) / (gain * depthScale);
            const double measuredX = strength_observation_x(stats.plane[plane], bin, bitDepth);
            if (!std::isfinite(measuredX)) return false;
            const double x = std::clamp(std::round(measuredX), 0.0, 255.0);
            // Adjacent occupied buckets can describe the same quantized
            // intensity. Pool their energy rather than emitting duplicate
            // AV1 scaling positions or silently dropping one observation.
            if (!points[plane].empty() && points[plane].back().first == x) {
                const auto weight = weights[plane].back();
                const double oldSigma = points[plane].back().second;
                points[plane].back().second = std::sqrt((oldSigma * oldSigma * weight + sigma * sigma * count)
                    / (static_cast<double>(weight) + count));
                weights[plane].back() += count;
            } else {
                points[plane].emplace_back(x, sigma);
                weights[plane].push_back(count);
            }
            maxScaling = std::max(maxScaling, sigma);
        }
        if (points[plane].empty()) return false;
        const auto observations = points[plane];
        while (static_cast<int>(points[plane].size()) > limits[plane]) {
            size_t remove = 1;
            double leastError = std::numeric_limits<double>::infinity();
            for (size_t candidate = 1; candidate + 1 < points[plane].size(); ++candidate) {
                auto trial = points[plane];
                trial.erase(trial.begin() + candidate);
                double error = 0.0;
                size_t right = 1;
                for (size_t i = 0; i < observations.size(); ++i) {
                    const auto& sample = observations[i];
                    while (right + 1 < trial.size() && trial[right].first < sample.first) ++right;
                    const auto& lo = trial[right - 1];
                    const auto& hi = trial[right];
                    const double mix = (sample.first - lo.first) / (hi.first - lo.first);
                    const double difference = lo.second + mix * (hi.second - lo.second) - sample.second;
                    error += weights[plane][i] * difference * difference;
                }
                if (error < leastError) { leastError = error; remove = candidate; }
            }
            points[plane].erase(points[plane].begin() + remove);
        }
    }
    const int maxScalingLog2 = std::clamp(static_cast<int>(std::floor(std::log2(maxScaling)) + 1), 2, 5);
    const double factor = static_cast<double>(1 << (8 - maxScalingLog2));
    params.grainScalingMinus8 = 5 - maxScalingLog2;
    params.numYPoints = static_cast<uint32_t>(points[0].size());
    params.numCbPoints = static_cast<uint32_t>(points[1].size());
    params.numCrPoints = static_cast<uint32_t>(points[2].size());
    uint8_t *values[3] = { params.pointYValue, params.pointCbValue, params.pointCrValue };
    uint8_t *scaling[3] = { params.pointYScaling, params.pointCbScaling, params.pointCrScaling };
    for (int plane = 0; plane < 3; ++plane) {
        std::fill(values[plane], values[plane] + limits[plane], static_cast<uint8_t>(0));
        std::fill(scaling[plane], scaling[plane] + limits[plane], static_cast<uint8_t>(0));
        for (size_t i = 0; i < points[plane].size(); ++i) {
            values[plane][i] = static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(points[plane][i].first)), 0, 255));
            scaling[plane][i] = static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(points[plane][i].second * factor)), 0, 255));
        }
    }
    return true;
}

bool build_fidelity_recovery_model(const FilmGrainGpuStats& stats, const int bitDepth,
    const bool analyzeChroma, const bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics) {
    if (bitDepth != 8 && bitDepth != 10) return false;
    // Do not let a non-finite occupied observation reach quantization.
    for (const auto& plane : stats.plane) {
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            if (plane.binBlockCount[bin] != 0
                && (!std::isfinite(plane.binVarSum[bin]) || plane.binVarSum[bin] < 0.0)) return false;
        }
    }
    NV_ENC_FILM_GRAIN_PARAMS_AV1 fresh = {};
    NVEncFilmGrainDiagnostics freshDiagnostics;
    if (!build_film_grain_params(stats, bitDepth, analyzeChroma, limitedRange,
            fresh, freshDiagnostics, true)) return false;
    auto fidelity = film_grain_strength_fidelity(stats, fresh, bitDepth, freshDiagnostics.templateGain);
    if (fidelity.blocks[0] == 0) return false;
    if (fidelity.needsSource(0.10, 0.25)) {
        if (!refit_occupied_strength(stats, bitDepth, fresh, freshDiagnostics)) return false;
        fidelity = film_grain_strength_fidelity(stats, fresh, bitDepth, freshDiagnostics.templateGain);
        if (fidelity.needsSource(0.10, 0.25)) return false;
        freshDiagnostics.strengthRefit = true;
    }
    params = fresh;
    diagnostics = freshDiagnostics;
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

void build_strength_lut(const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, const int bitDepth,
    float lut[FGS_STRENGTH_LUT_SIZE], const int plane, const double templateGain) {
    const bool fromLuma = plane == 0 || params.chromaScalingFromLuma;
    const auto count = fromLuma ? params.numYPoints : (plane == 1 ? params.numCbPoints : params.numCrPoints);
    const auto values = fromLuma ? params.pointYValue : (plane == 1 ? params.pointCbValue : params.pointCrValue);
    const auto scalings = fromLuma ? params.pointYScaling : (plane == 1 ? params.pointCbScaling : params.pointCrScaling);
    if (!params.applyGrain || count == 0) {
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
            eval_scaling_curve(values, scalings, count, x)
            * sigmaScale * depthScale * templateGain);
    }
}

bool FilmGrainStrengthFidelity::needsSource(const double relativeLimit, const double absoluteLimit8bit) const {
    for (int plane = 0; plane < 3; ++plane) {
        if (blocks[plane] == 0) continue;
        if (!std::isfinite(relativeRmsError[plane]) || !std::isfinite(rmsError8bit[plane])
            || (relativeRmsError[plane] > relativeLimit && rmsError8bit[plane] > absoluteLimit8bit)) return true;
    }
    return false;
}

FilmGrainStrengthFidelity film_grain_strength_fidelity(const FilmGrainGpuStats& stats,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, const int bitDepth,
    const std::array<float, 3>& templateGain) {
    FilmGrainStrengthFidelity result;
    const double depthScale = static_cast<double>(1 << (bitDepth - 8));
    for (int plane = 0; plane < 3; ++plane) {
        const auto& observed = stats.plane[plane];
        float lut[FGS_STRENGTH_LUT_SIZE];
        build_strength_lut(params, bitDepth, lut, plane, templateGain[plane]);
        double squaredError = 0.0;
        double observedEnergy = 0.0;
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            const auto count = observed.binBlockCount[bin];
            if (count == 0) continue; // Empty bins cannot establish fidelity.
            result.blocks[plane] += count;
            const double actualVariance = observed.binVarSum[bin] / count;
            if (!std::isfinite(actualVariance) || actualVariance < 0.0) {
                squaredError = std::numeric_limits<double>::infinity();
                continue;
            }
            // A bucket centre can be several code values away from the
            // actual picture brightness. Sharp valid curves must be checked
            // where their evidence was measured, including after quantization.
            const double x = strength_observation_x(observed, bin, bitDepth);
            if (!std::isfinite(x)) {
                squaredError = std::numeric_limits<double>::infinity();
                continue;
            }
            const int left = std::clamp(static_cast<int>(std::floor(x)), 0, FGS_STRENGTH_LUT_SIZE - 1);
            const int right = std::min(left + 1, FGS_STRENGTH_LUT_SIZE - 1);
            const double modeledSigma = lut[left] * (1.0 - (x - left)) + lut[right] * (x - left);
            const double difference = modeledSigma - std::sqrt(actualVariance);
            squaredError += count * difference * difference;
            observedEnergy += observed.binVarSum[bin];
        }
        if (result.blocks[plane] == 0) continue;
        result.relativeRmsError[plane] = std::sqrt(squaredError / std::max(1e-12, observedEnergy));
        result.rmsError8bit[plane] = std::sqrt(squaredError / result.blocks[plane]) / depthScale;
    }
    return result;
}

bool FilmGrainLocalStrengthFidelity::needsSource(const double relativeLimit, const double absoluteLimit8bit) const {
    if (!valid) return true;
    for (int bin = 0; bin < FGS_LOCAL_STRENGTH_SLOTS; ++bin) {
        // Four independent patches reduce finite-sample noise; a lone block
        // cannot establish a mismatch or certify the unobserved picture.
        if (blocks[bin] < 4) continue;
        const double error = std::abs(modeledSigma[bin] - observedSigma[bin]);
        if (!std::isfinite(error)
            || (error > absoluteLimit8bit && error > relativeLimit * observedSigma[bin])) return true;
    }
    return false;
}

FilmGrainLocalStrengthFidelity film_grain_local_strength_fidelity(const FilmGrainLocalStrengthStats& stats,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, const int bitDepth, const double templateGain, const double residualRetain, const int plane) {
    FilmGrainLocalStrengthFidelity result;
    if (plane < 0 || plane > 2 || (bitDepth != 8 && bitDepth != 10) || !std::isfinite(templateGain) || templateGain <= 0.0
        || !std::isfinite(residualRetain) || residualRetain < 0.0 || residualRetain > 1.0) {
        result.valid = false;
        return result;
    }
    const double depthScale = static_cast<double>(1 << (bitDepth - 8));
    float lut[FGS_STRENGTH_LUT_SIZE];
    build_strength_lut(params, bitDepth, lut, plane, templateGain);
    for (int bin = 0; bin < FGS_LOCAL_STRENGTH_SLOTS; ++bin) {
        const int brightness = bin % FGS_LOCAL_STRENGTH_BINS;
        const auto count = stats.blocks[bin];
        result.blocks[bin] = count;
        if (!count) continue;
        const double variance = stats.varianceSum[bin] / count;
        const double baseVariance = stats.baseVarianceSum[bin] / count;
        const double covariance = stats.covarianceSum[bin] / count;
        const double x = stats.intensitySum[bin] / (count * depthScale);
        if (!std::isfinite(variance) || variance < 0.0 || !std::isfinite(baseVariance) || baseVariance < 0.0
            || !std::isfinite(covariance) || !std::isfinite(x) || x < std::max(0.0, brightness - 0.5001) || x > (brightness == 255 ? 255.75 : brightness + 0.5001)) {
            result.valid = false;
            continue;
        }
        const int left = std::clamp(static_cast<int>(std::floor(x)), 0, FGS_STRENGTH_LUT_SIZE - 1);
        const int right = std::min(left + 1, FGS_STRENGTH_LUT_SIZE - 1);
        const double modeled = lut[left] * (1.0 - (x - left)) + lut[right] * (x - left);
        const double covarianceLimit = std::sqrt(variance * baseVariance);
        if (std::abs(covariance) > covarianceLimit + 1e-6 * std::max({1.0, variance, baseVariance})) {
            result.valid = false;
            continue;
        }
        // Match the later residual blend and synthesis compensation. Grain
        // already retained in the base is correlated with the original.
        const double retain = residualRetain, cleanWeight = 1.0 - retain;
        const double baseEnergy = cleanWeight * cleanWeight * baseVariance + retain * retain * variance
            + 2.0 * retain * cleanWeight * std::clamp(covariance, -covarianceLimit, covarianceLimit);
        const double synthesisEnergy = modeled * modeled * (1.0 - retain * retain);
        result.observedSigma[bin] = std::sqrt(variance) / depthScale;
        result.modeledSigma[bin] = std::sqrt(std::max(0.0, baseEnergy + synthesisEnergy)) / depthScale;
    }
    return result;
}


bool refit_local_strength(const FilmGrainLocalStrengthStats& stats, const int bitDepth,
    const double templateGain, const double residualRetain, NV_ENC_FILM_GRAIN_PARAMS_AV1& params) {
    if ((bitDepth != 8 && bitDepth != 10) || !params.applyGrain || params.numYPoints == 0 || params.numYPoints > 14
        || params.numCbPoints > 10 || params.numCrPoints > 10 || params.chromaScalingFromLuma
        || params.grainScalingMinus8 > 3 || !std::isfinite(residualRetain) || residualRetain < 0.0 || residualRetain >= 1.0
        || !std::isfinite(templateGain) || templateGain <= 0.0) return false;
    for (uint32_t i = 1; i < params.numYPoints; ++i) {
        if (params.pointYValue[i] <= params.pointYValue[i - 1]) return false;
    }
    if (!film_grain_local_strength_fidelity(stats, params, bitDepth, templateGain, residualRetain).valid) return false;
    const double depthScale = static_cast<double>(1 << (bitDepth - 8));
    const double cleanWeight = 1.0 - residualRetain;
    const double synthesisWeight = 1.0 - residualRetain * residualRetain;
    const double scalingFactor = static_cast<double>(1 << (params.grainScalingMinus8 + 3));
    struct Observation { double x, scaling, weight, measuredX; };
    std::vector<Observation> observed;
    for (int bin = 0; bin < FGS_LOCAL_STRENGTH_BINS; ++bin) {
        const auto count = stats.blocks[bin];
        if (count < 4) continue;
        const double source = stats.varianceSum[bin] / count;
        const double base = stats.baseVarianceSum[bin] / count;
        const double covarianceLimit = std::sqrt(source * base);
        const double covariance = std::clamp(stats.covarianceSum[bin] / count, -covarianceLimit, covarianceLimit);
        const double baseEnergy = cleanWeight * cleanWeight * base + residualRetain * residualRetain * source
            + 2.0 * residualRetain * cleanWeight * covariance;
        const double sigma = std::sqrt(std::max(0.0, (source - baseEnergy) / synthesisWeight));
        const double scaling = sigma / (depthScale * templateGain) * scalingFactor;
        // Keep the shared scaling shift: retuning luma must not silently
        // change either colour component or clip an unrepresentable strength.
        if (!std::isfinite(scaling) || scaling > 255.0) return false;
        observed.push_back({ static_cast<double>(bin), scaling, static_cast<double>(count),
            stats.intensitySum[bin] / (count * depthScale) });
    }
    if (observed.empty()) return false;
    if (observed.size() == 1) {
        // A single quiet brightness (for example a black border around
        // correlated grain) supports a narrow zero plateau, not removal of
        // grain from the unobserved picture. Keep the old curve a code value
        // beyond each edge. Fractional 10-bit means need both adjacent zeros.
        const auto sample = observed.front();
        if (sample.scaling > 0.0) return false;
        const int lo = std::clamp(static_cast<int>(std::floor(sample.measuredX)), 0, 255);
        const int hi = std::clamp(static_cast<int>(std::ceil(sample.measuredX)), 0, 255);
        std::vector<Observation> isolated;
        for (uint32_t i = 0; i < params.numYPoints; ++i) {
            const int x = params.pointYValue[i];
            if (x < lo - 1 || x > hi + 1)
                isolated.push_back({ static_cast<double>(x), static_cast<double>(params.pointYScaling[i]), 1.0, static_cast<double>(x) });
        }
        if (lo > 0) isolated.push_back({ static_cast<double>(lo - 1),
            eval_scaling_curve(params.pointYValue, params.pointYScaling, params.numYPoints, lo - 1), 1.0, static_cast<double>(lo - 1) });
        isolated.push_back({ static_cast<double>(lo), 0.0, sample.weight, static_cast<double>(lo) });
        if (hi != lo) isolated.push_back({ static_cast<double>(hi), 0.0, sample.weight, static_cast<double>(hi) });
        if (hi < 255) isolated.push_back({ static_cast<double>(hi + 1),
            eval_scaling_curve(params.pointYValue, params.pointYScaling, params.numYPoints, hi + 1), 1.0, static_cast<double>(hi + 1) });
        std::sort(isolated.begin(), isolated.end(), [](const Observation& a, const Observation& b) { return a.x < b.x; });
        for (size_t i = 1; i + 1 < isolated.size();) {
            const auto& a = isolated[i - 1];
            const auto& b = isolated[i];
            const auto& c = isolated[i + 1];
            if (std::abs((b.scaling - a.scaling) * (c.x - a.x)
                    - (c.scaling - a.scaling) * (b.x - a.x)) < 1e-9) {
                isolated.erase(isolated.begin() + i);
            } else { ++i; }
        }
        if (isolated.size() > 14) return false;
        auto trial = params;
        trial.numYPoints = static_cast<uint32_t>(isolated.size());
        std::fill(std::begin(trial.pointYValue), std::end(trial.pointYValue), static_cast<uint8_t>(0));
        std::fill(std::begin(trial.pointYScaling), std::end(trial.pointYScaling), static_cast<uint8_t>(0));
        for (size_t i = 0; i < isolated.size(); ++i) {
            trial.pointYValue[i] = static_cast<uint8_t>(isolated[i].x);
            trial.pointYScaling[i] = static_cast<uint8_t>(std::lround(isolated[i].scaling));
        }
        if (film_grain_local_strength_fidelity(stats, trial, bitDepth, templateGain, residualRetain).needsSource(0.10, 0.25)) return false;
        params = trial;
        return true;
    }
    // Keep the old curve outside the range supported by independent evidence.
    // An isolated quiet patch cannot turn the entire unobserved picture quiet.
    std::vector<Observation> samples;
    for (uint32_t i = 0; i < params.numYPoints; ++i) {
        if (params.pointYValue[i] < observed.front().x)
            samples.push_back({ static_cast<double>(params.pointYValue[i]), static_cast<double>(params.pointYScaling[i]), 1.0, static_cast<double>(params.pointYValue[i]) });
    }
    samples.insert(samples.end(), observed.begin(), observed.end());
    for (uint32_t i = 0; i < params.numYPoints; ++i) {
        if (params.pointYValue[i] > observed.back().x)
            samples.push_back({ static_cast<double>(params.pointYValue[i]), static_cast<double>(params.pointYScaling[i]), 1.0, static_cast<double>(params.pointYValue[i]) });
    }
    // Add the largest supported interpolation error, with at most 14 scans
    // over the fine grid. Exhaustive point-deletion searches would make a
    // dense 256-bucket frame substantially more expensive to recover.
    std::vector<size_t> selected = { 0, samples.size() - 1 };
    while (selected.size() < std::min<size_t>(14, samples.size())) {
        size_t add = 0;
        double largestError = 0.0;
        for (size_t segment = 1; segment < selected.size(); ++segment) {
            const auto& lo = samples[selected[segment - 1]];
            const auto& hi = samples[selected[segment]];
            for (size_t i = selected[segment - 1] + 1; i < selected[segment]; ++i) {
                const auto& sample = samples[i];
                const double mix = (sample.x - lo.x) / (hi.x - lo.x);
                const double difference = lo.scaling + mix * (hi.scaling - lo.scaling) - sample.scaling;
                const double error = sample.weight * difference * difference;
                if (error > largestError) { largestError = error; add = i; }
            }
        }
        if (largestError == 0.0) break;
        selected.insert(std::lower_bound(selected.begin(), selected.end(), add), add);
    }
    std::vector<Observation> points;
    for (const auto index : selected) points.push_back(samples[index]);
    auto trial = params;
    trial.numYPoints = static_cast<uint32_t>(points.size());
    std::fill(std::begin(trial.pointYValue), std::end(trial.pointYValue), static_cast<uint8_t>(0));
    std::fill(std::begin(trial.pointYScaling), std::end(trial.pointYScaling), static_cast<uint8_t>(0));
    for (size_t i = 0; i < points.size(); ++i) {
        trial.pointYValue[i] = static_cast<uint8_t>(points[i].x);
        trial.pointYScaling[i] = static_cast<uint8_t>(std::lround(points[i].scaling));
    }
    if (film_grain_local_strength_fidelity(stats, trial, bitDepth, templateGain, residualRetain).needsSource(0.10, 0.25)) {
        // AV1 positions are integers, but observations have fractional mean
        // brightness. Refine the scaling amplitudes at the emitted positions
        // against those actual means; rounding both coordinates would smear
        // a sharp nearby quiet/noisy transition.
        const int count = static_cast<int>(points.size());
        std::vector<double> matrix(count * count, 0.0), rhs(count, 0.0), scaling;
        for (const auto& sample : samples) {
            int lo = 0, hi = 0;
            double blend = 0.0;
            if (sample.measuredX >= points.back().x) {
                lo = hi = count - 1;
            } else if (sample.measuredX > points.front().x) {
                hi = 1;
                while (hi + 1 < count && points[hi].x < sample.measuredX) ++hi;
                lo = hi - 1;
                blend = (sample.measuredX - points[lo].x) / (points[hi].x - points[lo].x);
            }
            const double a = 1.0 - blend, b = blend, weight = sample.weight;
            matrix[lo * count + lo] += weight * a * a;
            matrix[hi * count + hi] += weight * b * b;
            matrix[lo * count + hi] += weight * a * b;
            matrix[hi * count + lo] += weight * a * b;
            rhs[lo] += weight * a * sample.scaling;
            rhs[hi] += weight * b * sample.scaling;
        }
        if (!solve_linear_system(matrix, rhs, scaling, count)) return false;
        for (int i = 0; i < count; ++i) {
            if (!std::isfinite(scaling[i]) || scaling[i] > 255.0) return false;
            trial.pointYScaling[i] = static_cast<uint8_t>(std::lround(std::max(0.0, scaling[i])));
        }
        if (film_grain_local_strength_fidelity(stats, trial, bitDepth, templateGain, residualRetain).needsSource(0.10, 0.25)) return false;
    }
    params = trial;
    return true;
}

FilmGrainGpuStats local_strength_targets(const FilmGrainGpuStats& coarse,
    const FilmGrainLocalStrengthStats& local, const int bitDepth, const double residualRetain) {
    auto result = coarse;
    if ((bitDepth != 8 && bitDepth != 10) || !std::isfinite(residualRetain)
        || residualRetain < 0.0 || residualRetain >= 1.0) {
        result.plane[0].binBlockCount[0] = 1;
        result.plane[0].binVarSum[0] = std::numeric_limits<double>::infinity();
        return result;
    }
    FilmGrainGpuPlaneStats replacement = {};
    std::array<uint64_t, FGS_STRENGTH_BINS> supported = {};
    const double depthScale = static_cast<double>(1 << (bitDepth - 8));
    for (int bin = 0; bin < FGS_LOCAL_STRENGTH_BINS; ++bin) {
        const auto count = local.blocks[bin];
        if (!count) continue;
        const double x = local.intensitySum[bin] / count;
        if (!std::isfinite(x) || x < 0.0 || x > (1 << bitDepth) - 1) continue;
        const int target = std::clamp(static_cast<int>(x * FGS_STRENGTH_BINS / (256 * depthScale)), 0, FGS_STRENGTH_BINS - 1);
        const double r = residualRetain, clean = 1.0 - r;
        const double baseEnergy = clean * clean * local.baseVarianceSum[bin] + r * r * local.varianceSum[bin]
            + 2.0 * r * clean * local.covarianceSum[bin];
        const double desiredEnergy = std::max(0.0, (local.varianceSum[bin] - baseEnergy) / (1.0 - r * r));
        replacement.binVarSum[target] += desiredEnergy;
        replacement.binBlockCount[target] += count;
        replacement.binLumaSum[target] += local.intensitySum[bin];
        supported[target] += local.correlatedBlocks[bin];
    }
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        if (supported[bin] < 4) continue;
        result.plane[0].binVarSum[bin] = replacement.binVarSum[bin];
        result.plane[0].binBlockCount[bin] = replacement.binBlockCount[bin];
        result.plane[0].binLumaSum[bin] = replacement.binLumaSum[bin];
    }
    result.plane[0].intensityBlocks = 0;
    for (const auto count : result.plane[0].binBlockCount) result.plane[0].intensityBlocks += count;
    return result;
}

bool apply_local_covariance(FilmGrainGpuStats& stats,
    const FilmGrainLocalStrengthStats& local, const double residualRetain, double *highpassFraction) {
    if (local.covarianceBlocks < 16 || local.covarianceBlocks > 10000000
        || !std::isfinite(residualRetain) || residualRetain < 0.0 || residualRetain >= 1.0) return false;
    const double sourceVariance = local.sourceCovariance[0], baseVariance = local.baseCovariance[0];
    if (!std::isfinite(sourceVariance) || sourceVariance <= 0.0 || !std::isfinite(baseVariance) || baseVariance < 0.0
        || std::abs(local.crossCovariance[0]) > 2.0 * std::sqrt(sourceVariance * baseVariance)
            + 1e-5 * std::max(sourceVariance, 1.0)) return false;
    std::array<double, FGS_LOCAL_COVARIANCES> covariance = {};
    const double r = residualRetain, clean = 1.0 - r;
    for (int i = 0; i < FGS_LOCAL_COVARIANCES; ++i) {
        const double source = local.sourceCovariance[i], base = local.baseCovariance[i], cross = local.crossCovariance[i];
        if (!std::isfinite(source) || !std::isfinite(base) || !std::isfinite(cross)) return false;
        covariance[i] = (source - r * r * source - clean * clean * base - r * clean * cross)
            / ((1.0 - r * r) * local.covarianceBlocks);
    }
    if (!std::isfinite(covariance[0]) || covariance[0] <= 1e-6 || covariance[0] > 1048576.0) return false;
    for (const auto value : covariance) {
        if (!std::isfinite(value) || std::abs(value) > covariance[0] * 1.02) return false;
    }
    // Variance of center minus the four axial neighbours divided by four.
    // This independent target prevents an amplitude-correct model from
    // whitening coarse grain to satisfy a low-frequency response constraint.
    const double highpass = (1.25 * covariance[0] - covariance[fgs_covariance_index(0, 1)]
        - covariance[fgs_covariance_index(1, 0)] + 0.125 * (covariance[fgs_covariance_index(0, 2)]
        + covariance[fgs_covariance_index(2, 0)]) + 0.25 * (covariance[fgs_covariance_index(1, 1)]
        + covariance[fgs_covariance_index(1, -1)])) / covariance[0];
    if (!std::isfinite(highpass) || highpass <= 0.0 || highpass > 4.0) return false;
    // A small ridge represents sampling uncertainty in these spatial moments.
    // It must also make the complete normal matrix positive definite; an
    // arbitrary clipped/inverted covariance is not a recoverable grain model.
    std::array<std::pair<int, int>, FGS_AR_COEFFS> positions;
    int count = 0;
    for (int y = -3; y <= 0; ++y) for (int x = -3; x <= 3; ++x) {
        if (y < 0 || x < 0) positions[count++] = { y, x };
    }
    std::array<double, FGS_AR_COEFFS * FGS_AR_COEFFS> matrix = {}, cholesky = {};
    const double ridge = covariance[0] * 0.02;
    for (int i = 0; i < FGS_AR_COEFFS; ++i) for (int j = 0; j < FGS_AR_COEFFS; ++j) {
        const auto a = positions[i], b = positions[j];
        matrix[i * FGS_AR_COEFFS + j] = covariance[fgs_covariance_index(a.first - b.first, a.second - b.second)]
            + (i == j ? ridge : 0.0);
    }
    for (int i = 0; i < FGS_AR_COEFFS; ++i) for (int j = 0; j <= i; ++j) {
        double value = matrix[i * FGS_AR_COEFFS + j];
        for (int k = 0; k < j; ++k) value -= cholesky[i * FGS_AR_COEFFS + k] * cholesky[j * FGS_AR_COEFFS + k];
        if (i == j) {
            if (!std::isfinite(value) || value <= covariance[0] * 1e-8) return false;
            cholesky[i * FGS_AR_COEFFS + j] = std::sqrt(value);
        } else cholesky[i * FGS_AR_COEFFS + j] = value / cholesky[j * FGS_AR_COEFFS + j];
    }
    auto result = stats;
    auto& plane = result.plane[0];
    plane.observations = local.covarianceBlocks * FGS_LOCAL_COVARIANCE_SAMPLES;
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        plane.atb[i] = std::llround(covariance[fgs_covariance_index(positions[i].first, positions[i].second)] * plane.observations);
        for (int j = i; j < FGS_AR_COEFFS; ++j)
            plane.ata[tri_index(FGS_AR_COEFFS, i, j)] = std::llround(matrix[i * FGS_AR_COEFFS + j] * plane.observations);
    }
    stats = result;
    if (highpassFraction) *highpassFraction = highpass;
    return true;
}

double film_grain_luma_dc_amplitude(const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, const double residualRetain) {
    if (!std::isfinite(residualRetain) || residualRetain < 0.0 || residualRetain >= 1.0
        || params.arCoeffLag > 3 || params.arCoeffShiftMinus6 > 3 || params.numYPoints > 14
        || params.grainScalingMinus8 > 3 || params.grainScaleShift != 0) return std::numeric_limits<double>::infinity();
    if (!params.applyGrain || !params.numYPoints) return 0.0;
    const int coefficients = 2 * params.arCoeffLag * (params.arCoeffLag + 1);
    double sum = 0.0;
    for (int i = 0; i < coefficients; ++i)
        sum += (static_cast<int>(params.arCoeffsYPlus128[i]) - 128) / static_cast<double>(1 << (params.arCoeffShiftMinus6 + 6));
    if (sum >= 1.0) return std::numeric_limits<double>::infinity();
    const double scaling = *std::max_element(params.pointYScaling, params.pointYScaling + params.numYPoints);
    return scaling * std::sqrt(1.0 - residualRetain * residualRetain)
        / ((1 << (params.grainScalingMinus8 + 3)) * (1.0 - sum));
}

bool build_covariance_recovery_model(const FilmGrainGpuStats& stats, const int bitDepth,
    const bool analyzeChroma, const bool limitedRange, const double residualRetain, const double highpassFraction,
    NV_ENC_FILM_GRAIN_PARAMS_AV1& params, NVEncFilmGrainDiagnostics& diagnostics) {
    if (!stats.plane[0].observations || stats.plane[0].ata[0] <= 0
        || stats.plane[0].ata[0] > std::numeric_limits<int64_t>::max() / 4
        || !std::isfinite(highpassFraction) || highpassFraction <= 0.0 || highpassFraction > 4.0
        || !std::isfinite(residualRetain) || residualRetain < 0.0 || residualRetain >= 1.0) return false;
    for (int attempt = 0; attempt < 7; ++attempt) {
        auto target = stats;
        // Penalize response to a constant predictor without weakening the
        // existing pole/texture guards. This rank-one fit constraint focuses
        // on DC; ordinary ridge shrinkage changes every spatial frequency.
        const double penalty = attempt ? std::ldexp(0.005, attempt - 1) : 0.0;
        const int64_t offset = static_cast<int64_t>(std::llround(stats.plane[0].ata[0] * penalty));
        for (int i = 0; i < FGS_TRI_Y; ++i) {
            if (target.plane[0].ata[i] > std::numeric_limits<int64_t>::max() - offset) return false;
            target.plane[0].ata[i] += offset;
        }
        NV_ENC_FILM_GRAIN_PARAMS_AV1 trial = {};
        NVEncFilmGrainDiagnostics measured;
        if (!build_fidelity_recovery_model(target, bitDepth, analyzeChroma, limitedRange, trial, measured)) continue;
        const auto spectrum = film_grain_ar_spectrum(trial.arCoeffsYPlus128, trial.arCoeffLag, trial.arCoeffShiftMinus6 + 6);
        if (!std::isfinite(spectrum.meanPower) || spectrum.meanPower <= 0.0
            || !std::isfinite(spectrum.highpassFraction)
            || spectrum.highpassFraction < highpassFraction * 0.85 * 0.85
            || spectrum.highpassFraction > highpassFraction * 1.15 * 1.15) continue;
        // A constrained normal matrix is not itself the generated AR process.
        // Normalize its amplitude from the actual quantized transfer function.
        measured.templateGain[0] = static_cast<float>(std::sqrt(spectrum.meanPower));
        if (!refit_occupied_strength(stats, bitDepth, trial, measured)
            || film_grain_strength_fidelity(stats, trial, bitDepth, measured.templateGain).needsSource(0.10, 0.25)
            || film_grain_luma_dc_amplitude(trial, residualRetain) > 6.0) continue;
        measured.strengthRefit = true;
        params = trial;
        diagnostics = measured;
        return true;
    }
    return false;
}

FilmGrainChromaRestoreReason chroma_restore_reason(const FilmGrainGpuStats& stats,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, const int plane) {
    using Reason = FilmGrainChromaRestoreReason;
    if (plane < 1 || plane > 2) return Reason::InvalidPlane;
    if (params.chromaScalingFromLuma) return Reason::ScalingFromLuma;
    if (params.arCoeffLag != FGS_AR_LAG) return Reason::UnsupportedLag;
    if (params.arCoeffShiftMinus6 > 3) return Reason::InvalidShift;
    const auto coeffs = plane == 1 ? params.arCoeffsCbPlus128 : params.arCoeffsCrPlus128;
    const double signalled = std::abs(static_cast<int>(coeffs[FGS_AR_COEFFS]) - 128)
        / static_cast<double>(1 << (params.arCoeffShiftMinus6 + 6));
    if (signalled > 1.0 / 16.0) return Reason::SignalledCoupling;
    const auto& source = stats.plane[plane];
    if (source.observations < 1024) return Reason::InsufficientObservations;
    double energy = 0.0;
    uint64_t blocks = 0;
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        if (!std::isfinite(source.binVarSum[bin]) || source.binVarSum[bin] < 0.0) return Reason::InvalidVariance;
        energy += source.binVarSum[bin];
        blocks += source.binBlockCount[bin];
    }
    const double predictor = static_cast<double>(source.ata[tri_index(FGS_AR_COEFFS_CHROMA, FGS_AR_COEFFS, FGS_AR_COEFFS)]);
    if (!blocks || energy <= 0.0) return Reason::MissingEnergy;
    if (predictor <= 0.0) return Reason::MissingPredictor;
    const double targetEnergy = (energy / blocks) * source.observations;
    // Component-only recovery is qualified for nearly white colour grain.
    // Spatially correlated residuals have fewer independent observations;
    // preserve the whole source instead of trusting this sparse coupling fit.
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        if (std::abs(static_cast<double>(source.atb[i])) > 0.2 * targetEnergy) return Reason::SpatialCorrelation;
    }
    const double denominator = std::sqrt(predictor * targetEnergy);
    const double correlation = std::abs(static_cast<double>(source.atb[FGS_AR_COEFFS])) / denominator;
    // This is a conservative eligibility check, not proof of independence.
    // Coupled or sparse evidence retains the complete source frame instead.
    if (!std::isfinite(correlation)) return Reason::InvalidCorrelation;
    return correlation <= 0.05 ? Reason::Eligible : Reason::MeasuredCoupling;
}

bool can_restore_chroma_component(const FilmGrainGpuStats& stats,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, const int plane) {
    return chroma_restore_reason(stats, params, plane) == FilmGrainChromaRestoreReason::Eligible;
}

} // namespace fgsmodel
