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
// is an independent CUDA implementation and does not require libaom at runtime.
// ------------------------------------------------------------------------------------------

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <deque>
#include <limits>
#include <numeric>
#include <utility>
#include <vector>

#include "NVEncFilterFilmGrain.h"

#pragma warning(push)
#pragma warning(disable: 4819)
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#pragma warning(pop)

namespace {

constexpr int FGS_BLOCK_SIZE = 32;
constexpr int FGS_AR_LAG = 3;
constexpr int FGS_AR_COEFFS = 24;
constexpr int FGS_AR_COEFFS_CHROMA = 25;
constexpr int FGS_STRENGTH_BINS = 20;
constexpr int FGS_TRI_Y = FGS_AR_COEFFS * (FGS_AR_COEFFS + 1) / 2;
constexpr int FGS_TRI_C = FGS_AR_COEFFS_CHROMA * (FGS_AR_COEFFS_CHROMA + 1) / 2;

struct FilmGrainBlockMetric {
    float mean;
    float sigma;
    float score;
    uint32_t flat;
};

struct FilmGrainGpuPlaneStats {
    int64_t ata[FGS_TRI_C];
    int64_t atb[FGS_AR_COEFFS_CHROMA];
    double binVarSum[FGS_STRENGTH_BINS];
    uint64_t binBlockCount[FGS_STRENGTH_BINS];
    double lumaPredVarSum;
    uint64_t lumaPredBlocks;
    uint64_t observations;
};

struct FilmGrainGpuStats {
    FilmGrainGpuPlaneStats plane[3];
};

static_assert(sizeof(FilmGrainGpuStats) < 16 * 1024, "FGS readback must stay compact");

__host__ __device__ constexpr int tri_index(const int n, const int i, const int j) {
    return i * n - i * (i + 1) / 2 + j;
}

__device__ inline void atomic_add_i64(int64_t *address, const int64_t value) {
    atomicAdd(reinterpret_cast<unsigned long long *>(address), static_cast<unsigned long long>(value));
}

__device__ inline void atomic_add_u64(uint64_t *address, const uint64_t value) {
    atomicAdd(reinterpret_cast<unsigned long long *>(address), static_cast<unsigned long long>(value));
}

template<typename Type, int shift>
__device__ inline int load_code(const uint8_t *ptr, const int pitch, const int x, const int y, const int component = 0, const int components = 1) {
    const auto row = reinterpret_cast<const Type *>(ptr + static_cast<size_t>(y) * pitch);
    return static_cast<int>(row[x * components + component]) >> shift;
}

template<typename Type, int shift>
__device__ inline void store_code(uint8_t *ptr, const int pitch, const int x, const int y, const int value,
    const int component = 0, const int components = 1) {
    auto row = reinterpret_cast<Type *>(ptr + static_cast<size_t>(y) * pitch);
    row[x * components + component] = static_cast<Type>(value << shift);
}

template<typename Type, int shift>
__global__ void kernel_fgs_flat_metrics(const uint8_t *__restrict__ src, const int pitch,
    const int width, const int height, const int blocksX, const int bitDepth,
    FilmGrainBlockMetric *__restrict__ metrics) {
    const int blockIndex = blockIdx.x * blockDim.x + threadIdx.x;
    const int blocksY = (height + FGS_BLOCK_SIZE - 1) / FGS_BLOCK_SIZE;
    if (blockIndex >= blocksX * blocksY) return;

    const int bx = blockIndex % blocksX;
    const int by = blockIndex / blocksX;
    const int x0 = bx * FGS_BLOCK_SIZE;
    const int y0 = by * FGS_BLOCK_SIZE;
    const int bw = min(FGS_BLOCK_SIZE, width - x0);
    const int bh = min(FGS_BLOCK_SIZE, height - y0);
    FilmGrainBlockMetric out = {};
    if (bw < 8 || bh < 8) {
        metrics[blockIndex] = out;
        return;
    }

    const int count = bw * bh;
    double sum = 0.0;
    double sumX = 0.0;
    double sumY = 0.0;
    double normX = 0.0;
    double normY = 0.0;
    for (int y = 0; y < bh; ++y) {
        const double yn = (2.0 * y - (bh - 1)) / bh;
        for (int x = 0; x < bw; ++x) {
            const double xn = (2.0 * x - (bw - 1)) / bw;
            const double value = load_code<Type, shift>(src, pitch, x0 + x, y0 + y);
            sum += value;
            sumX += value * xn;
            sumY += value * yn;
            normX += xn * xn;
            normY += yn * yn;
        }
    }
    const double mean = sum / count;
    const double planeX = sumX / fmax(normX, 1e-12);
    const double planeY = sumY / fmax(normY, 1e-12);

    double variance = 0.0;
    double gxx = 0.0;
    double gxy = 0.0;
    double gyy = 0.0;
    int gradientCount = 0;
    for (int y = 0; y < bh; ++y) {
        const double yn = (2.0 * y - (bh - 1)) / bh;
        for (int x = 0; x < bw; ++x) {
            const double xn = (2.0 * x - (bw - 1)) / bw;
            const double value = load_code<Type, shift>(src, pitch, x0 + x, y0 + y);
            const double residual = value - (mean + planeX * xn + planeY * yn);
            variance += residual * residual;
            if (x > 0 && x + 1 < bw && y > 0 && y + 1 < bh) {
                const double left = load_code<Type, shift>(src, pitch, x0 + x - 1, y0 + y);
                const double right = load_code<Type, shift>(src, pitch, x0 + x + 1, y0 + y);
                const double up = load_code<Type, shift>(src, pitch, x0 + x, y0 + y - 1);
                const double down = load_code<Type, shift>(src, pitch, x0 + x, y0 + y + 1);
                const double gx = (right - left) * 0.5 - planeX * (2.0 / bw);
                const double gy = (down - up) * 0.5 - planeY * (2.0 / bh);
                gxx += gx * gx;
                gxy += gx * gy;
                gyy += gy * gy;
                ++gradientCount;
            }
        }
    }
    variance /= count;
    gxx /= max(gradientCount, 1);
    gxy /= max(gradientCount, 1);
    gyy /= max(gradientCount, 1);

    const double maxValue = static_cast<double>((1 << bitDepth) - 1);
    const double scale2 = maxValue * maxValue;
    const double varNorm = variance / scale2;
    gxx /= scale2;
    gxy /= scale2;
    gyy /= scale2;
    const double trace = gxx + gyy;
    const double determinant = gxx * gyy - gxy * gxy;
    const double discriminant = fmax(0.0, trace * trace - 4.0 * determinant);
    const double e1 = (trace + sqrt(discriminant)) * 0.5;
    const double e2 = (trace - sqrt(discriminant)) * 0.5;
    const double ratio = e1 / fmax(e2, 1e-6);

    const double traceThreshold = 0.15 / (FGS_BLOCK_SIZE * FGS_BLOCK_SIZE);
    const double normThreshold = 0.08 / (FGS_BLOCK_SIZE * FGS_BLOCK_SIZE);
    const double varThreshold = 0.005 / count;
    const bool isFlat = trace < traceThreshold && ratio < 1.25 && e1 < normThreshold && varNorm > varThreshold;
    double scoreArg = -6682.0 * varNorm - 0.2056 * ratio + 13087.0 * trace - 12434.0 * e1 + 2.5694;
    scoreArg = fmin(100.0, fmax(-25.0, scoreArg));

    out.mean = static_cast<float>(mean);
    out.sigma = static_cast<float>(sqrt(fmax(variance, 0.0)));
    out.score = varNorm > varThreshold ? static_cast<float>(1.0 / (1.0 + exp(-scoreArg))) : 0.0f;
    out.flat = isFlat ? 1u : 0u;
    metrics[blockIndex] = out;
}

template<typename Type, int shift, int components>
__global__ void kernel_fgs_bilateral(uint8_t *__restrict__ dst, const int dstPitch,
    const uint8_t *__restrict__ src, const int srcPitch, const int width, const int height,
    const int maxValue, const float sigma, const float *__restrict__ sigmaMap,
    const int blocksX, const int blocksY, const int planeBlockSize) {
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;

    constexpr float spatial[5] = { 1.0f, 4.0f, 6.0f, 4.0f, 1.0f };
    float blockSigma = sigma;
    if (sigmaMap != nullptr) {
        // Grain strength varies across the frame (typically with intensity);
        // a range sigma from the global median under-removes strong grain.
        // Interpolate the per-block noise estimate between block centers.
        const float fx = (x + 0.5f) / planeBlockSize - 0.5f;
        const float fy = (y + 0.5f) / planeBlockSize - 0.5f;
        const int ix = max(0, min(blocksX - 1, static_cast<int>(floorf(fx))));
        const int iy = max(0, min(blocksY - 1, static_cast<int>(floorf(fy))));
        const int ix1 = min(blocksX - 1, ix + 1);
        const int iy1 = min(blocksY - 1, iy + 1);
        const float wx = fminf(1.0f, fmaxf(0.0f, fx - ix));
        const float wy = fminf(1.0f, fmaxf(0.0f, fy - iy));
        const float top = sigmaMap[iy * blocksX + ix] * (1.0f - wx) + sigmaMap[iy * blocksX + ix1] * wx;
        const float bottom = sigmaMap[iy1 * blocksX + ix] * (1.0f - wx) + sigmaMap[iy1 * blocksX + ix1] * wx;
        blockSigma = top * (1.0f - wy) + bottom * wy;
    }
    const float rangeSigma = fmaxf(1.0f, blockSigma * 2.35f);
    const float invRange2 = 1.0f / (rangeSigma * rangeSigma);
    for (int component = 0; component < components; ++component) {
        const int center = load_code<Type, shift>(src, srcPitch, x, y, component, components);
        float weighted = 0.0f;
        float weightSum = 0.0f;
        for (int dy = -2; dy <= 2; ++dy) {
            const int sy = min(height - 1, max(0, y + dy));
            for (int dx = -2; dx <= 2; ++dx) {
                const int sx = min(width - 1, max(0, x + dx));
                const int sample = load_code<Type, shift>(src, srcPitch, sx, sy, component, components);
                const float difference = static_cast<float>(sample - center);
                const float rangeWeight = 1.0f / (1.0f + difference * difference * invRange2);
                const float weight = spatial[dx + 2] * spatial[dy + 2] * rangeWeight;
                weighted += weight * sample;
                weightSum += weight;
            }
        }
        const int filtered = min(maxValue, max(0, static_cast<int>(weighted / fmaxf(weightSum, 1e-6f) + 0.5f)));
        store_code<Type, shift>(dst, dstPitch, x, y, filtered, component, components);
    }
}

template<typename Type, int shift, int components>
__device__ inline int residual_at(const uint8_t *src, const int srcPitch,
    const uint8_t *denoised, const int denoisedPitch, const int x, const int y, const int component) {
    return load_code<Type, shift>(src, srcPitch, x, y, component, components)
        - load_code<Type, shift>(denoised, denoisedPitch, x, y, component, components);
}

template<typename Type, int shift, int components, bool chroma>
__global__ void kernel_fgs_model_stats(const uint8_t *__restrict__ src, const int srcPitch,
    const uint8_t *__restrict__ denoised, const int denoisedPitch, const int width, const int height,
    const int component, const uint8_t *__restrict__ lumaSrc, const int lumaSrcPitch,
    const uint8_t *__restrict__ lumaDenoised, const int lumaDenoisedPitch,
    const int lumaWidth, const int lumaHeight, const int blocksX, const int bitDepth,
    const uint8_t *__restrict__ flatMask, const FilmGrainBlockMetric *__restrict__ metrics,
    FilmGrainGpuPlaneStats *__restrict__ output) {
    const int bx = blockIdx.x;
    const int by = blockIdx.y;
    const int blockIndex = by * blocksX + bx;
    if (flatMask[blockIndex] == 0) return;

    constexpr int coeffCount = chroma ? FGS_AR_COEFFS_CHROMA : FGS_AR_COEFFS;
    constexpr int triCount = chroma ? FGS_TRI_C : FGS_TRI_Y;
    __shared__ int64_t ata[triCount];
    __shared__ int64_t atb[coeffCount];
    __shared__ int64_t residualSum;
    __shared__ uint64_t residualSumSq;
    __shared__ int64_t predSum;
    __shared__ uint64_t predSumSq;
    __shared__ unsigned int sampleCount;

    const int tid = threadIdx.y * blockDim.x + threadIdx.x;
    const int threads = blockDim.x * blockDim.y;
    for (int i = tid; i < triCount; i += threads) ata[i] = 0;
    for (int i = tid; i < coeffCount; i += threads) atb[i] = 0;
    if (tid == 0) {
        residualSum = 0;
        residualSumSq = 0;
        predSum = 0;
        predSumSq = 0;
        sampleCount = 0;
    }
    __syncthreads();

    const int modelBlock = chroma ? FGS_BLOCK_SIZE / 2 : FGS_BLOCK_SIZE;
    const int x0 = bx * modelBlock;
    const int y0 = by * modelBlock;
    const int xEnd = min(width, x0 + modelBlock);
    const int yEnd = min(height, y0 + modelBlock);
    const int usableW = xEnd - x0 - FGS_AR_LAG;
    const int usableH = yEnd - y0 - FGS_AR_LAG;
    const int x = x0 + FGS_AR_LAG + (usableW > 0 ? (usableW - 1) * threadIdx.x / max(1, static_cast<int>(blockDim.x) - 1) : 0);
    const int y = y0 + FGS_AR_LAG + (usableH > 0 ? (usableH - 1) * threadIdx.y / max(1, static_cast<int>(blockDim.y) - 1) : 0);
    if (usableW > 0 && usableH > 0 && x < width && y < height) {
        int predictors[coeffCount];
        int index = 0;
        for (int dy = -FGS_AR_LAG; dy < 0; ++dy) {
            for (int dx = -FGS_AR_LAG; dx <= FGS_AR_LAG; ++dx) {
                predictors[index++] = residual_at<Type, shift, components>(
                    src, srcPitch, denoised, denoisedPitch, x + dx, y + dy, component);
            }
        }
        for (int dx = -FGS_AR_LAG; dx < 0; ++dx) {
            predictors[index++] = residual_at<Type, shift, components>(
                src, srcPitch, denoised, denoisedPitch, x + dx, y, component);
        }
        if (chroma) {
            const int lx = min(lumaWidth - 2, max(0, x * 2));
            const int ly = min(lumaHeight - 2, max(0, y * 2));
            int lumaResidual = 0;
            for (int dy = 0; dy < 2; ++dy) {
                for (int dx = 0; dx < 2; ++dx) {
                    lumaResidual += residual_at<Type, shift, 1>(lumaSrc, lumaSrcPitch,
                        lumaDenoised, lumaDenoisedPitch, lx + dx, ly + dy, 0);
                }
            }
            predictors[index++] = (lumaResidual + (lumaResidual >= 0 ? 2 : -2)) / 4;
        }

        const int value = residual_at<Type, shift, components>(src, srcPitch, denoised, denoisedPitch, x, y, component);
        for (int i = 0; i < coeffCount; ++i) {
            atomic_add_i64(atb + i, static_cast<int64_t>(predictors[i]) * value);
            for (int j = i; j < coeffCount; ++j) {
                atomic_add_i64(ata + tri_index(coeffCount, i, j),
                    static_cast<int64_t>(predictors[i]) * predictors[j]);
            }
        }

        atomic_add_i64(&residualSum, value);
        atomic_add_u64(&residualSumSq, static_cast<uint64_t>(static_cast<int64_t>(value) * value));
        if (chroma) {
            const int pred = predictors[coeffCount - 1];
            atomic_add_i64(&predSum, pred);
            atomic_add_u64(&predSumSq, static_cast<uint64_t>(static_cast<int64_t>(pred) * pred));
        }
        atomicAdd(&sampleCount, 1u);
    }
    __syncthreads();

    for (int i = tid; i < triCount; i += threads) atomic_add_i64(output->ata + i, ata[i]);
    for (int i = tid; i < coeffCount; i += threads) atomic_add_i64(output->atb + i, atb[i]);
    if (tid == 0 && sampleCount > 0) {
        // One strength observation per flat block: the block's residual
        // variance keyed by the block's mean luma, as in libaom
        // add_noise_std_observations.  Binning single pixels by their own
        // noisy value biases the strength curve.
        const double samples = static_cast<double>(sampleCount);
        const double meanResidual = static_cast<double>(residualSum) / samples;
        const double variance = fmax(0.0,
            static_cast<double>(residualSumSq) / samples - meanResidual * meanResidual);
        const int maxValue = (1 << bitDepth) - 1;
        const int bin = min(FGS_STRENGTH_BINS - 1, max(0,
            static_cast<int>(metrics[blockIndex].mean * FGS_STRENGTH_BINS / (maxValue + 1))));
        atomicAdd(output->binVarSum + bin, variance);
        atomic_add_u64(output->binBlockCount + bin, 1ULL);
        if (chroma) {
            const double meanPred = static_cast<double>(predSum) / samples;
            const double predVariance = fmax(0.0,
                static_cast<double>(predSumSq) / samples - meanPred * meanPred);
            atomicAdd(&output->lumaPredVarSum, predVariance);
            atomic_add_u64(&output->lumaPredBlocks, 1ULL);
        }
        atomic_add_u64(&output->observations, sampleCount);
    }
}

} // namespace

namespace {

struct FilmGrainHostStats {
    FilmGrainGpuStats gpu;
    float measuredNoise;
};

struct FilmGrainSolvedPlane {
    std::vector<double> coeffs;
    std::array<double, FGS_STRENGTH_BINS> strength;
    std::array<uint64_t, FGS_STRENGTH_BINS> strengthWeight;
    double arGain;
    double templateGain;
    double signalCorrelation;
    bool valid;

    FilmGrainSolvedPlane() : coeffs(), strength(), strengthWeight(), arGain(1.0), templateGain(1.0), signalCorrelation(0.0), valid(false) {}
};

static bool solve_linear_system(std::vector<double> matrix, std::vector<double> rhs, std::vector<double>& solution, const int n) {
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

static FilmGrainSolvedPlane solve_plane(const FilmGrainGpuPlaneStats& stats, const bool chroma,
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

using StrengthPoint = std::pair<double, double>;

static std::vector<StrengthPoint> fit_strength_points(const FilmGrainSolvedPlane& solved, const int bitDepth, const int maxPoints) {
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

static void add_plane_stats(FilmGrainGpuPlaneStats& dst, const FilmGrainGpuPlaneStats& src) {
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

static bool build_film_grain_params(const FilmGrainGpuStats& stats, const int bitDepth,
    const bool analyzeChroma, const bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics) {
    std::array<FilmGrainSolvedPlane, 3> solved;
    solved[0] = solve_plane(stats.plane[0], false, nullptr);
    if (!solved[0].valid) return false;
    if (analyzeChroma) {
        // A chroma plane without a solvable model (e.g. residuals are exactly
        // zero on clean chroma) degrades to luma-only grain instead of
        // invalidating the whole model.
        solved[1] = solve_plane(stats.plane[1], true, &solved[0]);
        solved[2] = solve_plane(stats.plane[2], true, &solved[0]);
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
    const int maxScalingLog2 = clamp(static_cast<int>(std::floor(std::log2(maxScaling)) + 1), 2, 5);
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
        params.pointYValue[i] = static_cast<uint8_t>(clamp(static_cast<int>(std::lround(points[0][i].first)), 0, 255));
        params.pointYScaling[i] = static_cast<uint8_t>(clamp(static_cast<int>(std::lround(points[0][i].second * scalingFactor)), 0, 255));
    }
    {
        params.numCbPoints = static_cast<uint32_t>(points[1].size());
        params.numCrPoints = static_cast<uint32_t>(points[2].size());
        for (size_t i = 0; i < points[1].size(); ++i) {
            params.pointCbValue[i] = static_cast<uint8_t>(clamp(static_cast<int>(std::lround(points[1][i].first)), 0, 255));
            params.pointCbScaling[i] = static_cast<uint8_t>(clamp(static_cast<int>(std::lround(points[1][i].second * scalingFactor)), 0, 255));
        }
        for (size_t i = 0; i < points[2].size(); ++i) {
            params.pointCrValue[i] = static_cast<uint8_t>(clamp(static_cast<int>(std::lround(points[2][i].first)), 0, 255));
            params.pointCrScaling[i] = static_cast<uint8_t>(clamp(static_cast<int>(std::lround(points[2][i].second * scalingFactor)), 0, 255));
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
    const int arShift = clamp(7 - std::max(positiveExponent, negativeExponent), 6, 9);
    params.arCoeffShiftMinus6 = arShift - 6;
    const double coeffScale = static_cast<double>(1 << arShift);
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        params.arCoeffsYPlus128[i] = static_cast<uint8_t>(
            clamp(static_cast<int>(std::lround(solved[0].coeffs[i] * coeffScale)), -128, 127) + 128);
        if (solved[1].valid) {
            params.arCoeffsCbPlus128[i] = static_cast<uint8_t>(
                clamp(static_cast<int>(std::lround(solved[1].coeffs[i] * coeffScale)), -128, 127) + 128);
        }
        if (solved[2].valid) {
            params.arCoeffsCrPlus128[i] = static_cast<uint8_t>(
                clamp(static_cast<int>(std::lround(solved[2].coeffs[i] * coeffScale)), -128, 127) + 128);
        }
    }
    if (solved[1].valid) {
        params.arCoeffsCbPlus128[FGS_AR_COEFFS] = static_cast<uint8_t>(
            clamp(static_cast<int>(std::lround(yCorrelation[0] * coeffScale)), -128, 127) + 128);
        params.cbMult = 128;
        params.cbLumaMult = 192;
        params.cbOffset = 256;
    }
    if (solved[2].valid) {
        params.arCoeffsCrPlus128[FGS_AR_COEFFS] = static_cast<uint8_t>(
            clamp(static_cast<int>(std::lround(yCorrelation[1] * coeffScale)), -128, 127) + 128);
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

static double eval_scaling_curve(const uint8_t *values, const uint8_t *scalings, const uint32_t count, const double x) {
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
static bool film_grain_params_close(const NV_ENC_FILM_GRAIN_PARAMS_AV1& a, const NV_ENC_FILM_GRAIN_PARAMS_AV1& b) {
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
    if (maxSigmaDiff > std::max(0.10, 0.05 * maxSigma)) return false;
    const double coeffScaleA = 1.0 / (1 << (a.arCoeffShiftMinus6 + 6));
    const double coeffScaleB = 1.0 / (1 << (b.arCoeffShiftMinus6 + 6));
    double maxCoeffDiff = 0.0;
    for (int i = 0; i < 24; ++i) {
        maxCoeffDiff = std::max(maxCoeffDiff, std::abs(
            (static_cast<int>(a.arCoeffsYPlus128[i]) - 128) * coeffScaleA
            - (static_cast<int>(b.arCoeffsYPlus128[i]) - 128) * coeffScaleB));
    }
    for (int i = 0; i < 25; ++i) {
        maxCoeffDiff = std::max(maxCoeffDiff, std::abs(
            (static_cast<int>(a.arCoeffsCbPlus128[i]) - 128) * coeffScaleA
            - (static_cast<int>(b.arCoeffsCbPlus128[i]) - 128) * coeffScaleB));
        maxCoeffDiff = std::max(maxCoeffDiff, std::abs(
            (static_cast<int>(a.arCoeffsCrPlus128[i]) - 128) * coeffScaleA
            - (static_cast<int>(b.arCoeffsCrPlus128[i]) - 128) * coeffScaleB));
    }
    return maxCoeffDiff <= 0.05;
}

template<typename Type, int shift>
static RGY_ERR launch_flat_metrics(const RGYFrameInfo& luma, FilmGrainBlockMetric *metrics,
    const int blocksX, const int blocksY, const int bitDepth, cudaStream_t stream) {
    constexpr int threads = 128;
    kernel_fgs_flat_metrics<Type, shift><<<divCeil(blocksX * blocksY, threads), threads, 0, stream>>>(
        luma.ptr[0], luma.pitch[0], luma.width, luma.height, blocksX, bitDepth, metrics);
    return err_to_rgy(cudaGetLastError());
}

template<typename Type, int shift, int components>
static RGY_ERR launch_bilateral(const RGYFrameInfo& dst, const RGYFrameInfo& src,
    const int width, const int height, const int bitDepth, const float sigma,
    const float *sigmaMap, const int blocksX, const int blocksY, const int planeBlockSize, cudaStream_t stream) {
    const dim3 block(32, 8);
    const dim3 grid(divCeil(width, static_cast<int>(block.x)), divCeil(height, static_cast<int>(block.y)));
    kernel_fgs_bilateral<Type, shift, components><<<grid, block, 0, stream>>>(
        dst.ptr[0], dst.pitch[0], src.ptr[0], src.pitch[0], width, height, (1 << bitDepth) - 1, sigma,
        sigmaMap, blocksX, blocksY, planeBlockSize);
    return err_to_rgy(cudaGetLastError());
}

template<typename Type, int shift, int components, bool chroma>
static RGY_ERR launch_model_stats(const RGYFrameInfo& src, const RGYFrameInfo& denoised,
    const int width, const int height, const int component, const RGYFrameInfo& lumaSrc,
    const RGYFrameInfo& lumaDenoised, const int blocksX, const int blocksY, const int bitDepth,
    const uint8_t *flatMask, const FilmGrainBlockMetric *metrics,
    FilmGrainGpuPlaneStats *stats, cudaStream_t stream) {
    const dim3 block(8, 8);
    const dim3 grid(blocksX, blocksY);
    kernel_fgs_model_stats<Type, shift, components, chroma><<<grid, block, 0, stream>>>(
        src.ptr[0], src.pitch[0], denoised.ptr[0], denoised.pitch[0], width, height, component,
        lumaSrc.ptr[0], lumaSrc.pitch[0], lumaDenoised.ptr[0], lumaDenoised.pitch[0],
        lumaSrc.width, lumaSrc.height, blocksX, bitDepth, flatMask, metrics, stats);
    return err_to_rgy(cudaGetLastError());
}

} // namespace

struct NVEncFilterFilmGrain::AnalyzerState {
    std::deque<FilmGrainHostStats> history;
    float stableNoise;
    int64_t lastTimestamp;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 lastParams;
    bool lastParamsValid;
    int heldStreak;

    AnalyzerState() : history(), stableNoise(0.0f), lastTimestamp(std::numeric_limits<int64_t>::min()),
        lastParams(), lastParamsValid(false), heldStreak(0) {}
    void clear() {
        history.clear();
        stableNoise = 0.0f;
        lastTimestamp = std::numeric_limits<int64_t>::min();
        std::memset(&lastParams, 0, sizeof(lastParams));
        lastParamsValid = false;
        heldStreak = 0;
    }
};

NVEncFilmGrainAnalyzerConfig::NVEncFilmGrainAnalyzerConfig() :
    enable(true), analyzeChroma(true), clipToRestrictedRange(true), denoiseLevel(0.0f),
    denoisePasses(2), modelWindow(8), minModelFrames(1), minFlatBlocks(8),
    minFlatFraction(0.02f), minNoiseLevel(0.5f), maxNoiseLevel(50.0f) {
}

bool NVEncFilmGrainAnalyzerConfig::operator==(const NVEncFilmGrainAnalyzerConfig& other) const {
    return enable == other.enable
        && analyzeChroma == other.analyzeChroma
        && clipToRestrictedRange == other.clipToRestrictedRange
        && denoiseLevel == other.denoiseLevel
        && denoisePasses == other.denoisePasses
        && modelWindow == other.modelWindow
        && minModelFrames == other.minModelFrames
        && minFlatBlocks == other.minFlatBlocks
        && minFlatFraction == other.minFlatFraction
        && minNoiseLevel == other.minNoiseLevel
        && maxNoiseLevel == other.maxNoiseLevel;
}

tstring NVEncFilmGrainAnalyzerConfig::print() const {
    return strsprintf(_T("film-grain: denoise=%s%s, chroma=%s, passes=%d, window=%d"),
        denoiseLevel <= 0.0f ? _T("auto") : _T(""),
        denoiseLevel <= 0.0f ? _T("") : strsprintf(_T("%.2f"), denoiseLevel).c_str(),
        analyzeChroma ? _T("on") : _T("off"), denoisePasses, modelWindow);
}

NVEncFilmGrainDiagnostics::NVEncFilmGrainDiagnostics() :
    flatBlocks(0), totalBlocks(0), modelFrames(0), noiseStdDev(), observations(),
    reliable(false), sceneReset(false), modelHeld(false) {
}

RGYFrameDataFilmGrain::RGYFrameDataFilmGrain() :
    RGYFrameData(), m_params(), m_diagnostics(), m_timestamp(-1), m_inputFrameId(-1) {
    std::memset(&m_params, 0, sizeof(m_params));
}

RGYFrameDataFilmGrain::RGYFrameDataFilmGrain(const NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    const NVEncFilmGrainDiagnostics& diagnostics, const int64_t timestamp, const int inputFrameId) :
    RGYFrameData(), m_params(params), m_diagnostics(diagnostics), m_timestamp(timestamp), m_inputFrameId(inputFrameId) {
}

RGYFrameDataFilmGrain::~RGYFrameDataFilmGrain() {
}

std::shared_ptr<RGYFrameDataFilmGrain> nvenc_film_grain_get_frame_data(const RGYFrameInfo *frame) {
    if (!frame) return nullptr;
    const auto found = std::find_if(frame->dataList.begin(), frame->dataList.end(),
        [](const std::shared_ptr<RGYFrameData>& data) {
            return std::dynamic_pointer_cast<RGYFrameDataFilmGrain>(data) != nullptr;
        });
    return found == frame->dataList.end() ? nullptr : std::dynamic_pointer_cast<RGYFrameDataFilmGrain>(*found);
}

void nvenc_film_grain_erase_frame_data(std::vector<std::shared_ptr<RGYFrameData>>& dataList) {
    dataList.erase(std::remove_if(dataList.begin(), dataList.end(),
        [](const std::shared_ptr<RGYFrameData>& data) {
            return std::dynamic_pointer_cast<RGYFrameDataFilmGrain>(data) != nullptr;
        }), dataList.end());
}

NVEncFilterParamFilmGrain::NVEncFilterParamFilmGrain() : filmGrain() {
}

NVEncFilterParamFilmGrain::~NVEncFilterParamFilmGrain() {
}

tstring NVEncFilterParamFilmGrain::print() const {
    return filmGrain.print();
}

NVEncFilterFilmGrain::NVEncFilterFilmGrain() :
    m_denoiseWork(), m_blockMetrics(), m_blockMask(), m_sigmaMap(), m_modelStats(),
    m_state(std::make_unique<AnalyzerState>()), m_blocksX(0), m_blocksY(0) {
    m_name = _T("film-grain");
    m_pathThrough = FILTER_PATHTHROUGH_NONE;
}

NVEncFilterFilmGrain::~NVEncFilterFilmGrain() {
    close();
}

void NVEncFilterFilmGrain::resetTemporalState() {
    if (m_state) m_state->clear();
}

namespace {

template<typename Type, int shift>
static RGY_ERR denoise_frame_typed(RGYFrameInfo *dst, RGYFrameInfo *work, const RGYFrameInfo *src,
    const bool chroma, const int passes, const int bitDepth, const float sigma,
    const float *sigmaMap, const int blocksX, const int blocksY, cudaStream_t stream) {
    for (int pass = 0; pass < passes; ++pass) {
        const RGYFrameInfo *passSrc = pass == 0 ? src : work;
        RGYFrameInfo *passDst = pass + 1 == passes ? dst : work;
        auto srcY = getPlane(passSrc, RGY_PLANE_Y);
        auto dstY = getPlane(passDst, RGY_PLANE_Y);
        auto sts = launch_bilateral<Type, shift, 1>(dstY, srcY, srcY.width, srcY.height, bitDepth, sigma,
            sigmaMap, blocksX, blocksY, FGS_BLOCK_SIZE, stream);
        if (sts != RGY_ERR_NONE) return sts;
        if (!chroma) continue;
        const bool semiPlanar = src->csp == RGY_CSP_NV12 || src->csp == RGY_CSP_P010;
        if (semiPlanar) {
            auto srcUV = getPlane(passSrc, RGY_PLANE_U);
            auto dstUV = getPlane(passDst, RGY_PLANE_U);
            sts = launch_bilateral<Type, shift, 2>(dstUV, srcUV, src->width / 2, src->height / 2, bitDepth, sigma,
                sigmaMap, blocksX, blocksY, FGS_BLOCK_SIZE / 2, stream);
            if (sts != RGY_ERR_NONE) return sts;
        } else {
            for (int plane = RGY_PLANE_U; plane <= RGY_PLANE_V; ++plane) {
                auto srcC = getPlane(passSrc, static_cast<RGY_PLANE>(plane));
                auto dstC = getPlane(passDst, static_cast<RGY_PLANE>(plane));
                sts = launch_bilateral<Type, shift, 1>(dstC, srcC, srcC.width, srcC.height, bitDepth, sigma,
                    sigmaMap, blocksX, blocksY, FGS_BLOCK_SIZE / 2, stream);
                if (sts != RGY_ERR_NONE) return sts;
            }
        }
    }
    return RGY_ERR_NONE;
}

static RGY_ERR denoise_frame(RGYFrameInfo *dst, RGYFrameInfo *work, const RGYFrameInfo *src,
    const bool chroma, const int passes, const int bitDepth, const float sigma,
    const float *sigmaMap, const int blocksX, const int blocksY, cudaStream_t stream) {
    switch (src->csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        return denoise_frame_typed<uint8_t, 0>(dst, work, src, chroma, passes, bitDepth, sigma, sigmaMap, blocksX, blocksY, stream);
    case RGY_CSP_YV12_10:
        return denoise_frame_typed<uint16_t, 0>(dst, work, src, chroma, passes, bitDepth, sigma, sigmaMap, blocksX, blocksY, stream);
    case RGY_CSP_P010:
        return denoise_frame_typed<uint16_t, 6>(dst, work, src, chroma, passes, bitDepth, sigma, sigmaMap, blocksX, blocksY, stream);
    default:
        return RGY_ERR_UNSUPPORTED;
    }
}

template<typename Type, int shift>
static RGY_ERR collect_model_stats_typed(const RGYFrameInfo *src, const RGYFrameInfo *denoised,
    const bool chroma, const int blocksX, const int blocksY, const int bitDepth, const uint8_t *mask,
    const FilmGrainBlockMetric *metrics, FilmGrainGpuStats *stats, cudaStream_t stream) {
    const auto srcY = getPlane(src, RGY_PLANE_Y);
    const auto dstY = getPlane(denoised, RGY_PLANE_Y);
    auto sts = launch_model_stats<Type, shift, 1, false>(srcY, dstY, srcY.width, srcY.height, 0,
        srcY, dstY, blocksX, blocksY, bitDepth, mask, metrics, &stats->plane[0], stream);
    if (sts != RGY_ERR_NONE || !chroma) return sts;
    const bool semiPlanar = src->csp == RGY_CSP_NV12 || src->csp == RGY_CSP_P010;
    if (semiPlanar) {
        const auto srcUV = getPlane(src, RGY_PLANE_U);
        const auto dstUV = getPlane(denoised, RGY_PLANE_U);
        for (int component = 0; component < 2; ++component) {
            sts = launch_model_stats<Type, shift, 2, true>(srcUV, dstUV, src->width / 2, src->height / 2,
                component, srcY, dstY, blocksX, blocksY, bitDepth, mask, metrics, &stats->plane[component + 1], stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
    } else {
        for (int plane = RGY_PLANE_U; plane <= RGY_PLANE_V; ++plane) {
            const auto srcC = getPlane(src, static_cast<RGY_PLANE>(plane));
            const auto dstC = getPlane(denoised, static_cast<RGY_PLANE>(plane));
            sts = launch_model_stats<Type, shift, 1, true>(srcC, dstC, srcC.width, srcC.height, 0,
                srcY, dstY, blocksX, blocksY, bitDepth, mask, metrics, &stats->plane[plane], stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
    }
    return RGY_ERR_NONE;
}

static RGY_ERR collect_model_stats(const RGYFrameInfo *src, const RGYFrameInfo *denoised,
    const bool chroma, const int blocksX, const int blocksY, const int bitDepth, const uint8_t *mask,
    const FilmGrainBlockMetric *metrics, FilmGrainGpuStats *stats, cudaStream_t stream) {
    switch (src->csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        return collect_model_stats_typed<uint8_t, 0>(src, denoised, chroma, blocksX, blocksY, bitDepth, mask, metrics, stats, stream);
    case RGY_CSP_YV12_10:
        return collect_model_stats_typed<uint16_t, 0>(src, denoised, chroma, blocksX, blocksY, bitDepth, mask, metrics, stats, stream);
    case RGY_CSP_P010:
        return collect_model_stats_typed<uint16_t, 6>(src, denoised, chroma, blocksX, blocksY, bitDepth, mask, metrics, stats, stream);
    default:
        return RGY_ERR_UNSUPPORTED;
    }
}

} // namespace

RGY_ERR NVEncFilterFilmGrain::init(std::shared_ptr<NVEncFilterParam> pParam, std::shared_ptr<RGYLog> pPrintMes) {
    m_pLog = pPrintMes;
    auto prm = std::dynamic_pointer_cast<NVEncFilterParamFilmGrain>(pParam);
    if (!prm) {
        AddMessage(RGY_LOG_ERROR, _T("Invalid parameter type.\n"));
        return RGY_ERR_INVALID_PARAM;
    }
    if (prm->frameIn.width <= 0 || prm->frameIn.height <= 0
        || cmpFrameInfoCspResolution(&prm->frameIn, &prm->frameOut)) {
        AddMessage(RGY_LOG_ERROR, _T("Input and output format must match.\n"));
        return RGY_ERR_INVALID_PARAM;
    }
    switch (prm->frameIn.csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
    case RGY_CSP_YV12_10:
    case RGY_CSP_P010:
        break;
    default:
        AddMessage(RGY_LOG_ERROR, _T("Unsupported colorspace: %s.\n"), RGY_CSP_NAMES[prm->frameIn.csp]);
        return RGY_ERR_UNSUPPORTED;
    }
    auto& config = prm->filmGrain;
    config.denoisePasses = clamp(config.denoisePasses, 1, 2);
    config.modelWindow = clamp(config.modelWindow, 1, 32);
    config.minModelFrames = clamp(config.minModelFrames, 1, config.modelWindow);
    config.minFlatBlocks = std::max(2, config.minFlatBlocks);
    config.minFlatFraction = clamp(config.minFlatFraction, 0.0f, 1.0f);
    config.minNoiseLevel = std::max(0.05f, config.minNoiseLevel);
    config.maxNoiseLevel = std::max(config.minNoiseLevel, config.maxNoiseLevel);
    config.denoiseLevel = clamp(config.denoiseLevel, 0.0f, 50.0f);

    auto sts = AllocFrameBuf(prm->frameOut, 2);
    if (sts != RGY_ERR_NONE) return sts;
    for (int plane = 0; plane < RGY_CSP_PLANES[prm->frameOut.csp]; ++plane) {
        prm->frameOut.pitch[plane] = m_frameBuf[0]->frame.pitch[plane];
    }
    m_denoiseWork = std::make_unique<CUFrameBuf>(prm->frameOut);
    m_denoiseWork->releasePtr();
    if ((sts = m_denoiseWork->alloc()) != RGY_ERR_NONE) return sts;

    m_blocksX = divCeil(prm->frameIn.width, FGS_BLOCK_SIZE);
    m_blocksY = divCeil(prm->frameIn.height, FGS_BLOCK_SIZE);
    m_blockMetrics = std::make_unique<CUMemBufPair>(
        static_cast<size_t>(m_blocksX) * m_blocksY * sizeof(FilmGrainBlockMetric));
    m_blockMask = std::make_unique<CUMemBufPair>(static_cast<size_t>(m_blocksX) * m_blocksY);
    m_sigmaMap = std::make_unique<CUMemBufPair>(static_cast<size_t>(m_blocksX) * m_blocksY * sizeof(float));
    m_modelStats = std::make_unique<CUMemBufPair>(sizeof(FilmGrainGpuStats));
    if ((sts = m_blockMetrics->alloc()) != RGY_ERR_NONE
        || (sts = m_blockMask->alloc()) != RGY_ERR_NONE
        || (sts = m_sigmaMap->alloc()) != RGY_ERR_NONE
        || (sts = m_modelStats->alloc()) != RGY_ERR_NONE) {
        AddMessage(RGY_LOG_ERROR, _T("Failed to allocate film-grain analysis buffers: %s.\n"), get_err_mes(sts));
        return sts;
    }
    if (!m_state) m_state = std::make_unique<AnalyzerState>();
    m_state->clear();
    setFilterInfo(prm->print());
    m_param = prm;
    return RGY_ERR_NONE;
}

RGY_ERR NVEncFilterFilmGrain::run_filter(const RGYFrameInfo *pInputFrame, RGYFrameInfo **ppOutputFrames,
    int *pOutputFrameNum, cudaStream_t stream) {
    if (!pOutputFrameNum || !ppOutputFrames) return RGY_ERR_INVALID_PARAM;
    if (!pInputFrame) {
        *pOutputFrameNum = 0;
        ppOutputFrames[0] = nullptr;
        return RGY_ERR_NONE;
    }
    if (!pInputFrame->ptr[0]) {
        *pOutputFrameNum = 0;
        return RGY_ERR_NONE;
    }
    auto prm = std::dynamic_pointer_cast<NVEncFilterParamFilmGrain>(m_param);
    if (!prm) return RGY_ERR_INVALID_PARAM;
    *pOutputFrameNum = 1;
    if (!ppOutputFrames[0]) {
        ppOutputFrames[0] = &m_frameBuf[m_nFrameIdx]->frame;
        m_nFrameIdx = (m_nFrameIdx + 1) % m_frameBuf.size();
    }
    auto *output = ppOutputFrames[0];
    auto sts = copyFrameAsync(output, pInputFrame, stream);
    if (sts != RGY_ERR_NONE) return sts;
    copyFramePropWithoutRes(output, pInputFrame);
    nvenc_film_grain_erase_frame_data(output->dataList);

    NVEncFilmGrainDiagnostics diagnostics;
    diagnostics.totalBlocks = m_blocksX * m_blocksY;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params = {};
    auto attachResult = [&]() {
        output->dataList.push_back(std::make_shared<RGYFrameDataFilmGrain>(
            params, diagnostics, pInputFrame->timestamp, pInputFrame->inputFrameId));
    };
    if (!prm->filmGrain.enable || interlaced(*pInputFrame)
        || getCudaMemcpyKind(pInputFrame->mem_type, output->mem_type) != cudaMemcpyDeviceToDevice) {
        attachResult();
        return RGY_ERR_NONE;
    }

    const int bitDepth = (pInputFrame->csp == RGY_CSP_NV12 || pInputFrame->csp == RGY_CSP_YV12) ? 8 : 10;
    const int depthScale = 1 << (bitDepth - 8);
    const auto luma = getPlane(pInputFrame, RGY_PLANE_Y);
    switch (pInputFrame->csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        sts = launch_flat_metrics<uint8_t, 0>(luma,
            static_cast<FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice), m_blocksX, m_blocksY, bitDepth, stream);
        break;
    case RGY_CSP_YV12_10:
        sts = launch_flat_metrics<uint16_t, 0>(luma,
            static_cast<FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice), m_blocksX, m_blocksY, bitDepth, stream);
        break;
    case RGY_CSP_P010:
        sts = launch_flat_metrics<uint16_t, 6>(luma,
            static_cast<FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice), m_blocksX, m_blocksY, bitDepth, stream);
        break;
    default:
        return RGY_ERR_UNSUPPORTED;
    }
    if (sts != RGY_ERR_NONE || (sts = m_blockMetrics->copyDtoHAsync(stream)) != RGY_ERR_NONE) return sts;
    auto cudaerr = cudaStreamSynchronize(stream);
    if (cudaerr != cudaSuccess) return err_to_rgy(cudaerr);

    const int blockCount = m_blocksX * m_blocksY;
    const auto metrics = static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrHost);
    auto mask = static_cast<uint8_t *>(m_blockMask->ptrHost);
    std::memset(mask, 0, blockCount);
    std::vector<int> candidates;
    candidates.reserve(blockCount);
    const float minSigma = prm->filmGrain.minNoiseLevel * depthScale;
    const float maxSigma = prm->filmGrain.maxNoiseLevel * depthScale;
    const int requiredBlocks = std::max(prm->filmGrain.minFlatBlocks,
        static_cast<int>(std::ceil(blockCount * prm->filmGrain.minFlatFraction)));
    for (int i = 0; i < blockCount; ++i) {
        if (metrics[i].sigma >= minSigma && metrics[i].sigma <= maxSigma && metrics[i].score > 0.0f) {
            if (metrics[i].flat) mask[i] = 1;
            if (metrics[i].score >= 0.5f) candidates.push_back(i);
        }
    }
    std::sort(candidates.begin(), candidates.end(), [metrics](const int a, const int b) {
        return metrics[a].score > metrics[b].score;
    });
    int selected = static_cast<int>(std::count(mask, mask + blockCount, static_cast<uint8_t>(1)));
    // Always take the top decile of scored blocks in addition to the blocks
    // passing the strict gradient thresholds (libaom flat_block_finder_run
    // marks the 90th score percentile as flat).  Strong grain inflates the
    // gradient metrics, so strict-threshold selection alone samples only the
    // weakest-grain regions and biases the strength curve.
    const int topDecile = blockCount / 10;
    int examined = 0;
    for (const auto index : candidates) {
        if (examined >= topDecile && selected >= requiredBlocks) break;
        if (!mask[index]) { mask[index] = 1; ++selected; }
        ++examined;
    }
    diagnostics.flatBlocks = selected;
    if (selected < requiredBlocks) {
        // Do not allow a model from before a low-confidence gap to reappear on
        // later frames.  The next reliable region must build a fresh window.
        diagnostics.sceneReset = !m_state->history.empty();
        m_state->clear();
        AddMessage(RGY_LOG_DEBUG, _T("fgs-model frame=%d pts=%lld reliable=0 reset=%d flat=%d/%d window=0\n"),
            pInputFrame->inputFrameId, static_cast<long long>(pInputFrame->timestamp),
            diagnostics.sceneReset ? 1 : 0, diagnostics.flatBlocks, diagnostics.totalBlocks);
        attachResult();
        return RGY_ERR_NONE;
    }
    std::vector<float> noiseSamples;
    noiseSamples.reserve(selected);
    for (int i = 0; i < blockCount; ++i) if (mask[i]) noiseSamples.push_back(metrics[i].sigma);
    const auto middle = noiseSamples.begin() + noiseSamples.size() / 2;
    std::nth_element(noiseSamples.begin(), middle, noiseSamples.end());
    const float measuredNoise = *middle;
    const bool adaptiveSigma = prm->filmGrain.denoiseLevel <= 0.0f;
    const float denoiseSigma = adaptiveSigma
        ? measuredNoise : prm->filmGrain.denoiseLevel * depthScale;
    if (adaptiveSigma) {
        // Selected blocks denoise with their own measured noise level;
        // unselected (textured) blocks fall back to the median so their own
        // texture variance does not turn the denoiser into a blur.
        auto sigmaMap = static_cast<float *>(m_sigmaMap->ptrHost);
        for (int i = 0; i < blockCount; ++i) {
            sigmaMap[i] = mask[i] ? clamp(metrics[i].sigma, minSigma, maxSigma) : measuredNoise;
        }
        if ((sts = m_sigmaMap->copyHtoDAsync(stream)) != RGY_ERR_NONE) return sts;
    }
    if ((sts = m_blockMask->copyHtoDAsync(stream)) != RGY_ERR_NONE) return sts;
    sts = denoise_frame(output, &m_denoiseWork->frame, pInputFrame, prm->filmGrain.analyzeChroma,
        prm->filmGrain.denoisePasses, bitDepth, denoiseSigma,
        adaptiveSigma ? static_cast<const float *>(m_sigmaMap->ptrDevice) : nullptr,
        m_blocksX, m_blocksY, stream);
    if (sts != RGY_ERR_NONE) return sts;

    cudaerr = cudaMemsetAsync(m_modelStats->ptrDevice, 0, m_modelStats->nSize, stream);
    if (cudaerr != cudaSuccess) return err_to_rgy(cudaerr);
    sts = collect_model_stats(pInputFrame, output, prm->filmGrain.analyzeChroma, m_blocksX, m_blocksY,
        bitDepth, static_cast<const uint8_t *>(m_blockMask->ptrDevice),
        static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice),
        static_cast<FilmGrainGpuStats *>(m_modelStats->ptrDevice), stream);
    if (sts != RGY_ERR_NONE || (sts = m_modelStats->copyDtoHAsync(stream)) != RGY_ERR_NONE) return sts;
    cudaerr = cudaStreamSynchronize(stream);
    if (cudaerr != cudaSuccess) return err_to_rgy(cudaerr);

    bool sceneReset = false;
    if (!m_state->history.empty()) {
        const float ratio = measuredNoise / std::max(0.01f, m_state->stableNoise);
        if (ratio < 0.55f || ratio > 1.80f || pInputFrame->timestamp <= m_state->lastTimestamp) {
            m_state->clear();
            sceneReset = true;
        }
    }
    FilmGrainHostStats current = {};
    std::memcpy(&current.gpu, m_modelStats->ptrHost, sizeof(current.gpu));
    current.measuredNoise = measuredNoise;
    m_state->history.push_back(current);
    while (static_cast<int>(m_state->history.size()) > prm->filmGrain.modelWindow) m_state->history.pop_front();
    m_state->stableNoise = 0.0f;
    for (const auto& frame : m_state->history) m_state->stableNoise += frame.measuredNoise;
    m_state->stableNoise /= m_state->history.size();
    m_state->lastTimestamp = pInputFrame->timestamp;
    diagnostics.modelFrames = static_cast<int>(m_state->history.size());
    diagnostics.sceneReset = sceneReset;

    FilmGrainGpuStats combined = {};
    for (const auto& frame : m_state->history) {
        for (int plane = 0; plane < 3; ++plane) add_plane_stats(combined.plane[plane], frame.gpu.plane[plane]);
    }
    bool modelValid = diagnostics.modelFrames >= prm->filmGrain.minModelFrames
        && build_film_grain_params(combined, bitDepth, prm->filmGrain.analyzeChroma,
            prm->filmGrain.clipToRestrictedRange, params, diagnostics);
    if (modelValid) {
        if (m_state->lastParamsValid && film_grain_params_close(params, m_state->lastParams)) {
            // Hold the previously signalled model while the fresh fit only
            // jitters around it; requantizing every frame makes the grain
            // character twinkle.  NVENC still varies the grain seed per frame.
            params = m_state->lastParams;
            diagnostics.modelHeld = true;
        } else {
            m_state->lastParams = params;
            m_state->lastParamsValid = true;
        }
        m_state->heldStreak = 0;
    } else if (m_state->lastParamsValid && m_state->heldStreak < prm->filmGrain.modelWindow) {
        // A transiently unsolvable frame keeps the last model rather than
        // dropping grain for a single frame; bounded so a persistent failure
        // cannot pin a stale model.
        params = m_state->lastParams;
        diagnostics.modelHeld = true;
        modelValid = true;
        ++m_state->heldStreak;
    } else {
        std::memset(&params, 0, sizeof(params));
        sts = copyFrameAsync(output, pInputFrame, stream);
        if (sts != RGY_ERR_NONE) return sts;
    }
    diagnostics.reliable = modelValid;
    if (m_pLog != nullptr && m_pLog->getLogLevel(RGY_LOGT_VPP) <= RGY_LOG_DEBUG) {
        tstring pointsY, pointsCb, pointsCr;
        for (uint32_t i = 0; i < params.numYPoints; ++i) {
            pointsY += strsprintf(_T(" %d:%d"), params.pointYValue[i], params.pointYScaling[i]);
        }
        for (uint32_t i = 0; i < params.numCbPoints; ++i) {
            pointsCb += strsprintf(_T(" %d:%d"), params.pointCbValue[i], params.pointCbScaling[i]);
        }
        for (uint32_t i = 0; i < params.numCrPoints; ++i) {
            pointsCr += strsprintf(_T(" %d:%d"), params.pointCrValue[i], params.pointCrScaling[i]);
        }
        AddMessage(RGY_LOG_DEBUG, _T("fgs-model frame=%d pts=%lld reliable=%d reset=%d held=%d flat=%d/%d window=%d ")
            _T("noise=%.2f/%.2f/%.2f scaleShift=%d arShift=%d corrCb=%d corrCr=%d y=[%s] cb=[%s] cr=[%s]\n"),
            pInputFrame->inputFrameId, static_cast<long long>(pInputFrame->timestamp),
            modelValid ? 1 : 0, diagnostics.sceneReset ? 1 : 0, diagnostics.modelHeld ? 1 : 0,
            diagnostics.flatBlocks, diagnostics.totalBlocks, diagnostics.modelFrames,
            diagnostics.noiseStdDev[0], diagnostics.noiseStdDev[1], diagnostics.noiseStdDev[2],
            params.grainScalingMinus8 + 8, params.arCoeffShiftMinus6 + 6,
            static_cast<int>(params.arCoeffsCbPlus128[FGS_AR_COEFFS]) - 128,
            static_cast<int>(params.arCoeffsCrPlus128[FGS_AR_COEFFS]) - 128,
            pointsY.c_str(), pointsCb.c_str(), pointsCr.c_str());
    }
    attachResult();
    return RGY_ERR_NONE;
}

void NVEncFilterFilmGrain::close() {
    m_frameBuf.clear();
    m_denoiseWork.reset();
    m_blockMetrics.reset();
    m_blockMask.reset();
    m_sigmaMap.reset();
    m_modelStats.reset();
    if (m_state) m_state->clear();
    m_blocksX = 0;
    m_blocksY = 0;
    m_nFrameIdx = 0;
    m_param.reset();
}
