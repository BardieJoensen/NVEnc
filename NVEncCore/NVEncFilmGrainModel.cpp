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
#include <numeric>

#include "NVEncFilmGrainModel.h"

NVEncFilmGrainDiagnostics::NVEncFilmGrainDiagnostics() :
    flatBlocks(0), totalBlocks(0), modelFrames(0), noiseStdDev(), observations(),
    detailRisk(0.0f), residualRetain(0.0f), grainCorrelation(0.0f),
    sourceModelCorrelation(0.0f), sourceArScale(1.0f), sourceStrengthGain(1.0f),
    preEncodeLeak(0.0f), predictedPostEncodeLeak(0.0f), leakDeadzone(0.0f),
    textureBaseCovarianceWeight(0.0f), textureCovarianceMinPivotRatio(0.0f), temporalLeakBlocks(0),
    temporalTextureObservations(0), strengthRectifiedBlocks(0),
    sourceRegularizationRejected(false), sourceModelFallback(false), leakCompensated(false),
    textureLeakCompensated(false), textureLeakRejected(false),
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

struct LumaTemplateStats {
    double correlation;
    double gain;
};

static LumaTemplateStats simulate_luma_template(
    const std::vector<double>& coeffs, const double scale) {
    if (coeffs.size() != FGS_AR_COEFFS || !std::isfinite(scale)) return { 0.0, 1.0 };
    // Match the AV1 lag-3 luma template footprint.  The fixed hash supplies a
    // deterministic white field.  Correlation is normalised and gain is
    // measured against the exact same field before recursion.  Avoiding a
    // random library makes table decisions repeatable across runs and hosts.
    constexpr int width = 82;
    constexpr int height = 73;
    constexpr int x0 = FGS_AR_LAG;
    constexpr int x1 = width - FGS_AR_LAG;
    constexpr int y0 = FGS_AR_LAG;
    std::array<double, width * height> field = {};
    for (size_t index = 0; index < field.size(); ++index) {
        const uint32_t hash = fgs_sample_hash(static_cast<uint32_t>(index) + 0x9e3779b9U);
        field[index] = (static_cast<double>(hash & 0xffffU) - 32767.5) / 32767.5;
    }
    double whiteMean = 0.0;
    uint64_t count = 0;
    for (int y = y0; y < height; ++y) {
        for (int x = x0; x < x1; ++x) {
            whiteMean += field[y * width + x];
            ++count;
        }
    }
    whiteMean /= std::max<uint64_t>(1, count);
    double whiteVariance = 0.0;
    for (int y = y0; y < height; ++y) {
        for (int x = x0; x < x1; ++x) {
            const double value = field[y * width + x] - whiteMean;
            whiteVariance += value * value;
        }
    }
    whiteVariance /= std::max<uint64_t>(1, count);
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
            if (!std::isfinite(value) || std::abs(value) > 1e100) return { 1.0, 1e100 };
            field[y * width + x] = value;
        }
    }
    double mean = 0.0;
    count = 0;
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
    if (!(variance > 1e-12) || !std::isfinite(variance)
        || !(whiteVariance > 1e-12)) return { 0.0, 1.0 };
    const double h = horizontal / std::max<uint64_t>(1, horizontalCount) / variance;
    const double v = vertical / std::max<uint64_t>(1, verticalCount) / variance;
    return {
        std::clamp(0.5 * (h + v), -1.0, 1.0),
        std::sqrt(variance / whiteVariance)
    };
}

double implied_luma_correlation(const std::vector<double>& coeffs, const double scale) {
    return simulate_luma_template(coeffs, scale).correlation;
}

static LumaTemplateStats quantized_luma_stats(const std::vector<double>& coeffs,
    const double scale, const int arShift) {
    const double coefficientScale = static_cast<double>(1 << arShift);
    std::vector<double> quantized(coeffs.size(), 0.0);
    for (size_t i = 0; i < coeffs.size(); ++i) {
        quantized[i] = std::clamp(
            static_cast<int>(std::lround(coeffs[i] * scale * coefficientScale)),
            -128, 127) / coefficientScale;
    }
    return simulate_luma_template(quantized, 1.0);
}

static int choose_ar_shift(const std::array<FilmGrainSolvedPlane, 3>& solved) {
    double maxCoeff = 1e-4;
    double minCoeff = -1e-4;
    for (const auto& plane : solved) {
        if (!plane.valid) continue;
        for (int i = 0; i < FGS_AR_COEFFS; ++i) {
            maxCoeff = std::max(maxCoeff, plane.coeffs[i]);
            minCoeff = std::min(minCoeff, plane.coeffs[i]);
        }
    }
    for (int c = 1; c < 3; ++c) {
        if (!solved[c].valid) continue;
        maxCoeff = std::max(maxCoeff, solved[c].signalCorrelation);
        minCoeff = std::min(minCoeff, solved[c].signalCorrelation);
    }
    const int positiveExponent = 1 + static_cast<int>(
        std::floor(std::log2(std::max(maxCoeff, 1e-9))));
    const int negativeExponent = static_cast<int>(
        std::ceil(std::log2(std::max(-minCoeff, 1e-9))));
    return std::clamp(7 - std::max(positiveExponent, negativeExponent), 6, 9);
}

static bool regularize_source_luma(const FilmGrainGpuPlaneStats& stats,
    FilmGrainSolvedPlane& solved, const double maxCorrelation,
    const int arShift, NVEncFilmGrainDiagnostics& diagnostics) {
    diagnostics.sourceArScale = 1.0f;
    diagnostics.sourceStrengthGain = 1.0f;
    diagnostics.sourceRegularizationRejected = false;
    diagnostics.sourceModelCorrelation = 0.0f;
    // The shipping/default residual path must pay no simulator cost and must
    // remain byte-identical.  A negative ceiling means source regularisation
    // was not requested.
    if (maxCorrelation < 0.0) return true;
    double coefficientScale = 1.0;
    auto quantized = quantized_luma_stats(solved.coeffs, coefficientScale, arShift);
    if (quantized.correlation > maxCorrelation) {
        double low = 0.0;
        double high = 1.0;
        for (int iteration = 0; iteration < 10; ++iteration) {
            const double middle = 0.5 * (low + high);
            if (quantized_luma_stats(
                solved.coeffs, middle, arShift).correlation <= maxCorrelation) low = middle;
            else high = middle;
        }
        coefficientScale = low;
        quantized = quantized_luma_stats(solved.coeffs, coefficientScale, arShift);
    }

    // The regression gain describes continuous fitted coefficients over an
    // unbounded stationary process.  The decoder receives quantized taps and
    // realizes them over AV1's finite 82x73 template.  Use the gain of that
    // actual template for EVERY source fit, not only fits whose correlation
    // needed clamping; otherwise an ordinary quantization/template mismatch
    // lands directly on the delivered grain amplitude.
    const double strengthGain = solved.templateGain / std::max(1e-6, quantized.gain);
    diagnostics.sourceArScale = static_cast<float>(coefficientScale);
    diagnostics.sourceStrengthGain = static_cast<float>(strengthGain);
    diagnostics.sourceModelCorrelation = static_cast<float>(quantized.correlation);
    const double minStrengthGain = 1.0 / FGS_SOURCE_MAX_STRENGTH_GAIN;
    if (!std::isfinite(quantized.gain) || !std::isfinite(strengthGain)
        || quantized.gain > 16.0 || strengthGain < minStrengthGain
        || strengthGain > FGS_SOURCE_MAX_STRENGTH_GAIN) {
        diagnostics.sourceRegularizationRejected = true;
        return false;
    }

    if (coefficientScale < 1.0 - 1e-12) {
        for (auto& coefficient : solved.coeffs) coefficient *= coefficientScale;
    }
    solved.arGain = quantized.gain;
    solved.templateGain = quantized.gain;
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
        dst.temporalSourceVarSum[i] += src.temporalSourceVarSum[i];
        dst.temporalBaseVarSum[i] += src.temporalBaseVarSum[i];
        dst.temporalBlockCount[i] += src.temporalBlockCount[i];
        dst.rectifiedBlockCount[i] += src.rectifiedBlockCount[i];
    }
    dst.lumaPredVarSum += src.lumaPredVarSum;
    dst.lumaPredBlocks += src.lumaPredBlocks;
    dst.observations += src.observations;
}

void add_temporal_ar_stats(FilmGrainTemporalArStats& dst,
    const FilmGrainTemporalArStats& src) {
    for (int i = 0; i < FGS_TRI_Y; ++i) {
        dst.weightedAta[i] += src.weightedAta[i];
        dst.baseAta[i] += src.baseAta[i];
    }
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        dst.weightedAtb[i] += src.weightedAtb[i];
        dst.baseAtb[i] += src.baseAtb[i];
    }
    dst.weightedBtb += src.weightedBtb;
    dst.baseBtb += src.baseBtb;
    dst.observations += src.observations;
}

static int64_t divide_round_nearest(const int64_t value, const int64_t divisor) {
    const auto magnitude = value >= 0 ? value : -value;
    const auto rounded = (magnitude + divisor / 2) / divisor;
    return value >= 0 ? rounded : -rounded;
}

static int64_t temporal_covariance_target(const int64_t fixedWeighted,
    const int64_t base, const double baseWeight) {
    // Preserve the frozen 3/4 arm bit-for-bit.  The dynamic arm reconstructs
    // source from (4*source - 3*base), then subtracts the fraction of base
    // covariance predicted to survive the encoder deadzone.
    if (std::abs(baseWeight - 0.75) <= 1e-12) {
        return divide_round_nearest(
            fixedWeighted, FGS_TEXTURE_WEIGHT_DENOMINATOR);
    }
    const long double source = (
        static_cast<long double>(fixedWeighted)
        + FGS_TEXTURE_BASE_WEIGHT * static_cast<long double>(base)
    ) / FGS_TEXTURE_SOURCE_WEIGHT;
    return static_cast<int64_t>(std::llround(
        source - baseWeight * static_cast<long double>(base)));
}

static bool covariance_is_positive_definite(const std::vector<double>& matrix,
    const int n, double& minPivotRatio) {
    if (static_cast<int>(matrix.size()) != n * n) return false;
    double diagonalMean = 0.0;
    for (int i = 0; i < n; ++i) {
        const double diagonal = matrix[i * n + i];
        if (!std::isfinite(diagonal) || diagonal <= 0.0) return false;
        diagonalMean += diagonal;
    }
    diagonalMean /= n;
    if (!std::isfinite(diagonalMean) || diagonalMean <= 0.0) return false;

    std::vector<double> lower(n * n, 0.0);
    minPivotRatio = std::numeric_limits<double>::max();
    for (int row = 0; row < n; ++row) {
        for (int column = 0; column <= row; ++column) {
            double value = matrix[row * n + column];
            for (int k = 0; k < column; ++k) {
                value -= lower[row * n + k] * lower[column * n + k];
            }
            if (!std::isfinite(value)) return false;
            if (row == column) {
                const double pivotRatio = value / diagonalMean;
                minPivotRatio = std::min(minPivotRatio, pivotRatio);
                // The offline corpus bottomed out near 5e-3.  Reject a target
                // two orders of magnitude closer to singular instead of
                // silently manufacturing texture through regularisation.
                if (pivotRatio <= 1e-5) return false;
                lower[row * n + column] = std::sqrt(value);
            } else {
                const double divisor = lower[column * n + column];
                if (!(divisor > 0.0)) return false;
                lower[row * n + column] = value / divisor;
            }
        }
    }
    return std::isfinite(minPivotRatio);
}

bool apply_luma_texture_leak_closure(FilmGrainGpuStats& stats,
    const uint64_t minObservations, NVEncFilmGrainDiagnostics& diagnostics,
    const double baseCovarianceWeight) {
    const auto& temporal = stats.temporalLuma;
    diagnostics.temporalTextureObservations = temporal.observations;
    diagnostics.textureBaseCovarianceWeight = 0.0f;
    diagnostics.textureCovarianceMinPivotRatio = 0.0f;
    diagnostics.textureLeakCompensated = false;
    diagnostics.textureLeakRejected = false;
    if (!std::isfinite(baseCovarianceWeight)
        || baseCovarianceWeight < 0.0 || baseCovarianceWeight > 1.0) {
        diagnostics.textureLeakRejected = true;
        return false;
    }
    diagnostics.textureBaseCovarianceWeight =
        static_cast<float>(baseCovarianceWeight);
    if (temporal.observations < std::max<uint64_t>(256, minObservations)) return false;

    FilmGrainGpuPlaneStats candidate = stats.plane[0];
    for (int i = 0; i < FGS_TRI_Y; ++i) {
        candidate.ata[i] = temporal_covariance_target(
            temporal.weightedAta[i], temporal.baseAta[i],
            baseCovarianceWeight);
    }
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        candidate.atb[i] = temporal_covariance_target(
            temporal.weightedAtb[i], temporal.baseAtb[i],
            baseCovarianceWeight);
    }
    candidate.observations = temporal.observations;
    const int64_t btb = temporal_covariance_target(
        temporal.weightedBtb, temporal.baseBtb, baseCovarianceWeight);

    std::vector<double> matrix(FGS_AR_COEFFS * FGS_AR_COEFFS, 0.0);
    std::vector<double> rhs(FGS_AR_COEFFS, 0.0);
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        rhs[i] = static_cast<double>(candidate.atb[i]);
        for (int j = i; j < FGS_AR_COEFFS; ++j) {
            const double value = static_cast<double>(
                candidate.ata[tri_index(FGS_AR_COEFFS, i, j)]);
            matrix[i * FGS_AR_COEFFS + j] = value;
            matrix[j * FGS_AR_COEFFS + i] = value;
        }
    }
    double minPivotRatio = 0.0;
    if (btb <= 0 || !covariance_is_positive_definite(
        matrix, FGS_AR_COEFFS, minPivotRatio)) {
        diagnostics.textureLeakRejected = true;
        return false;
    }

    std::vector<double> coefficients;
    if (!solve_linear_system(matrix, rhs, coefficients, FGS_AR_COEFFS)) {
        diagnostics.textureLeakRejected = true;
        return false;
    }
    double explained = 0.0;
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        if (!std::isfinite(coefficients[i]) || std::abs(coefficients[i]) > 2.0) {
            diagnostics.textureLeakRejected = true;
            return false;
        }
        explained += rhs[i] * coefficients[i];
    }
    const double targetVariance = static_cast<double>(btb)
        / static_cast<double>(temporal.observations);
    const double innovationVariance = (static_cast<double>(btb) - explained)
        / static_cast<double>(temporal.observations);
    if (!std::isfinite(targetVariance) || !std::isfinite(innovationVariance)
        || targetVariance <= 0.0
        || innovationVariance <= targetVariance * 1e-5) {
        diagnostics.textureLeakRejected = true;
        return false;
    }

    // Exercise the exact downstream solver before mutating the live stats.
    // This also checks that the existing strength observations remain usable.
    if (!solve_plane(candidate, false, nullptr).valid) {
        diagnostics.textureLeakRejected = true;
        return false;
    }
    stats.plane[0] = candidate;
    diagnostics.textureCovarianceMinPivotRatio = static_cast<float>(minPivotRatio);
    diagnostics.textureLeakCompensated = true;
    return true;
}

bool apply_luma_leak_closure(FilmGrainGpuStats& stats, const double qvbr,
    const uint64_t minTemporalBlocks, const bool perBin,
    NVEncFilmGrainDiagnostics& diagnostics) {
    const auto& measured = stats.plane[0];
    diagnostics.strengthRectifiedBlocks = std::accumulate(
        std::begin(measured.rectifiedBlockCount), std::end(measured.rectifiedBlockCount), uint64_t{ 0 });
    if (!std::isfinite(qvbr) || qvbr < FGS_LEAK_QVBR_MIN || qvbr > FGS_LEAK_QVBR_MAX) return false;

    double sourceVariance = 0.0;
    double baseVariance = 0.0;
    uint64_t temporalBlocks = 0;
    int populatedBins = 0;
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        const auto count = measured.temporalBlockCount[bin];
        sourceVariance += measured.temporalSourceVarSum[bin];
        baseVariance += measured.temporalBaseVarSum[bin];
        temporalBlocks += count;
        populatedBins += count >= FGS_MIN_TEMPORAL_BIN_BLOCKS;
    }
    diagnostics.temporalLeakBlocks = temporalBlocks;
    if (temporalBlocks < minTemporalBlocks || populatedBins < 2 || sourceVariance <= 1e-9) return false;

    const double preLeak = std::sqrt(std::clamp(baseVariance / sourceVariance, 0.0, 1.0));
    const double theta = FGS_LEAK_THETA_INTERCEPT + FGS_LEAK_THETA_QVBR_SLOPE * qvbr;
    const double postLeak = std::max(0.0, preLeak - theta);
    const double synthesisFraction2 = std::max(0.0, 1.0 - postLeak * postLeak);

    auto& luma = stats.plane[0];
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        if (luma.temporalBlockCount[bin] >= FGS_MIN_TEMPORAL_BIN_BLOCKS) {
            double binSynthesisFraction2 = synthesisFraction2;
            if (perBin && luma.temporalSourceVarSum[bin] > 1e-9) {
                const double binPreLeak = std::sqrt(std::clamp(
                    luma.temporalBaseVarSum[bin] / luma.temporalSourceVarSum[bin],
                    0.0, 1.0));
                const double binPostLeak = std::max(0.0, binPreLeak - theta);
                binSynthesisFraction2 = std::max(
                    0.0, 1.0 - binPostLeak * binPostLeak);
            }
            luma.binVarSum[bin] =
                luma.temporalSourceVarSum[bin] * binSynthesisFraction2;
            luma.binBlockCount[bin] = luma.temporalBlockCount[bin];
        } else {
            luma.binVarSum[bin] = 0.0;
            luma.binBlockCount[bin] = 0;
        }
    }
    diagnostics.preEncodeLeak = static_cast<float>(preLeak);
    diagnostics.predictedPostEncodeLeak = static_cast<float>(postLeak);
    diagnostics.leakDeadzone = static_cast<float>(theta);
    diagnostics.leakCompensated = true;
    return true;
}

bool apply_chroma_leak_closure(FilmGrainGpuStats& stats, const double qvbr,
    const uint64_t minTemporalBlocks, const bool perBin,
    const bool planeSpecific) {
    if (!std::isfinite(qvbr) || qvbr < FGS_LEAK_QVBR_MIN || qvbr > FGS_LEAK_QVBR_MAX) return false;

    struct PlaneClosure {
        double sourceVariance;
        double baseVariance;
        uint64_t temporalBlocks;
        int populatedBins;
    };
    std::array<PlaneClosure, 2> closure = {};
    for (int chroma = 0; chroma < 2; ++chroma) {
        const auto& measured = stats.plane[chroma + 1];
        auto& plane = closure[chroma];
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            const auto count = measured.temporalBlockCount[bin];
            plane.sourceVariance += measured.temporalSourceVarSum[bin];
            plane.baseVariance += measured.temporalBaseVarSum[bin];
            plane.temporalBlocks += count;
            plane.populatedBins += count >= FGS_MIN_TEMPORAL_BIN_BLOCKS;
        }
        if (plane.temporalBlocks < minTemporalBlocks || plane.populatedBins < 2
            || plane.sourceVariance <= 1e-9) return false;
    }

    for (int chroma = 0; chroma < 2; ++chroma) {
        auto& measured = stats.plane[chroma + 1];
        const double theta = planeSpecific
            ? (chroma == 0
                ? FGS_CHROMA_U_LEAK_THETA_INTERCEPT
                    + FGS_CHROMA_U_LEAK_THETA_QVBR_SLOPE * qvbr
                : FGS_CHROMA_V_LEAK_THETA_INTERCEPT
                    + FGS_CHROMA_V_LEAK_THETA_QVBR_SLOPE * qvbr)
            : FGS_LEAK_THETA_INTERCEPT + FGS_LEAK_THETA_QVBR_SLOPE * qvbr;
        double globalSynthesisFraction2 = 0.0;
        if (!perBin) {
            const auto& plane = closure[chroma];
            const double preLeak = std::sqrt(std::clamp(
                plane.baseVariance / plane.sourceVariance, 0.0, 1.0));
            const double postLeak = std::max(0.0, preLeak - theta);
            globalSynthesisFraction2 = std::max(0.0, 1.0 - postLeak * postLeak);
        }
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            const auto count = measured.temporalBlockCount[bin];
            const double sourceVariance = measured.temporalSourceVarSum[bin];
            if (count < FGS_MIN_TEMPORAL_BIN_BLOCKS || sourceVariance <= 1e-9) {
                measured.binVarSum[bin] = 0.0;
                measured.binBlockCount[bin] = 0;
                continue;
            }
            double synthesisFraction2 = globalSynthesisFraction2;
            if (perBin) {
                const double preLeak = std::sqrt(std::clamp(
                    measured.temporalBaseVarSum[bin] / sourceVariance, 0.0, 1.0));
                const double postLeak = std::max(0.0, preLeak - theta);
                synthesisFraction2 = std::max(0.0, 1.0 - postLeak * postLeak);
            }
            measured.binVarSum[bin] = sourceVariance * synthesisFraction2;
            measured.binBlockCount[bin] = count;
        }
    }
    return true;
}

bool build_film_grain_params(const FilmGrainGpuStats& stats, const int bitDepth,
    const bool analyzeChroma, const bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics, const double maxLumaCorrelation) {
    std::array<FilmGrainSolvedPlane, 3> solved;
    solved[0] = solve_plane(stats.plane[0], false, nullptr);
    if (!solved[0].valid) return false;
    const auto solveChroma = [&]() {
        solved[1] = FilmGrainSolvedPlane();
        solved[2] = FilmGrainSolvedPlane();
        if (!analyzeChroma) return;
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
    };
    solveChroma();
    const int provisionalArShift = choose_ar_shift(solved);
    if (!regularize_source_luma(stats.plane[0], solved[0], maxLumaCorrelation,
        provisionalArShift, diagnostics)) return false;
    const bool sourceTemplateAdjusted = maxLumaCorrelation >= 0.0;
    if (sourceTemplateAdjusted) {
        // Chroma's final predictor is luma.  Refit it after replacing luma's
        // analytical regression gain with its realized quantized-template
        // gain (and, when needed, changing the luma coefficients), so its
        // normalization matches the table that will actually be emitted.
        solveChroma();
    }
    const int postRegularizationArShift = choose_ar_shift(solved);
    if (sourceTemplateAdjusted && postRegularizationArShift < provisionalArShift) {
        // A chroma refit may theoretically require a wider shared coefficient
        // range.  The luma decision was evaluated at the provisional shift;
        // reject instead of silently requantizing it more coarsely.
        diagnostics.sourceRegularizationRejected = true;
        return false;
    }
    // Scaling luma down can make a finer shift possible, but changing shifts
    // would move every coefficient onto a new quantization stair.  Keep the
    // shift at which the bounded model and its realised gain were measured.
    const int arShift = sourceTemplateAdjusted
        ? provisionalArShift : postRegularizationArShift;
    if (maxLumaCorrelation >= 0.0) {
        const auto quantized = quantized_luma_stats(
            solved[0].coeffs, 1.0, arShift);
        diagnostics.sourceModelCorrelation = static_cast<float>(quantized.correlation);
        if (sourceTemplateAdjusted
            && (std::abs(quantized.gain - solved[0].templateGain)
                    > 0.01 * std::max(1.0, solved[0].templateGain))) {
            diagnostics.sourceRegularizationRejected = true;
            return false;
        }
        if (diagnostics.sourceModelCorrelation > maxLumaCorrelation + 0.005) {
            // The quantized search is discrete.  Holding the prior valid
            // model is safer than emitting coefficients outside its measured
            // bound if a rounding boundary defeats the final safety check.
            diagnostics.sourceRegularizationRejected = true;
            return false;
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

bool build_source_film_grain_params_with_residual_fallback(
    const FilmGrainGpuStats& sourceStats, const FilmGrainGpuStats& residualStats,
    const int bitDepth, const bool analyzeChroma, const bool limitedRange,
    NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics, const double maxLumaCorrelation) {
    diagnostics.sourceModelFallback = false;
    if (build_film_grain_params(sourceStats, bitDepth, analyzeChroma,
        limitedRange, params, diagnostics, maxLumaCorrelation)) {
        return true;
    }

    // Preserve the rejected source fit's diagnostic fields. The residual
    // model is a conservative output choice, not evidence that the preferred
    // source model passed its representability checks.
    NVEncFilmGrainDiagnostics fallbackDiagnostics = diagnostics;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 fallbackParams = {};
    if (!build_film_grain_params(residualStats, bitDepth, analyzeChroma,
        limitedRange, fallbackParams, fallbackDiagnostics, -1.0)) {
        return false;
    }
    params = fallbackParams;
    diagnostics.sourceModelFallback = true;
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
