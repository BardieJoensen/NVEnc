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
#include <cstdlib>
#include <cstring>
#include <deque>
#include <limits>
#include <numeric>
#include <utility>
#include <vector>

#include "NVEncFilterFilmGrain.h"
#include "NVEncFilmGrainModel.h"
#include "NVEncFilterDegrain.h"
#include "NVEncFilterDenoiseFFT3D.h"
#include "NVEncUtil.h"

#pragma warning(push)
#pragma warning(disable: 4819)
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#pragma warning(pop)

using namespace fgsmodel;

namespace {

constexpr float FGS_DETAIL_COHERENCE_LOW = 0.12f;
constexpr float FGS_DETAIL_COHERENCE_HIGH = 0.18f;
constexpr float FGS_AUTO_RETAIN_SCALE = 1.5f;
constexpr float FGS_AUTO_RETAIN_MAX = 0.5f;
constexpr float FGS_AUTO_RETAIN_STEP = 0.05f;
constexpr int FGS_MODEL_CANDIDATE_FRAMES = 3;
constexpr int FGS_MODEL_MIN_UPDATE_FRAMES = 24;
constexpr float FGS_SCENE_MEAN_DELTA_8BIT = 12.0f;
constexpr float FGS_SCENE_BLOCK_DELTA_8BIT = 20.0f;
constexpr float FGS_SCENE_CHANGED_BLOCK_FRACTION = 0.65f;
constexpr int FGS_FLAT_THREADS = 128;
constexpr int FGS_BILATERAL_BLOCK_X = 32;
constexpr int FGS_BILATERAL_BLOCK_Y = 8;
constexpr int FGS_BILATERAL_RADIUS = 2;

struct FilmGrainBlockMetric {
    float mean;
    float sigma;
    float score;
    float coherence;
    float spatialCorrelation;
    uint32_t flat;
};

__device__ inline void atomic_add_i64(int64_t *address, const int64_t value) {
    atomicAdd(reinterpret_cast<unsigned long long *>(address), static_cast<unsigned long long>(value));
}

__device__ inline void atomic_add_u64(uint64_t *address, const uint64_t value) {
    atomicAdd(reinterpret_cast<unsigned long long *>(address), static_cast<unsigned long long>(value));
}

__device__ inline void atomic_add_f64(double *address, const double value) {
#if !defined(__CUDA_ARCH__) || __CUDA_ARCH__ >= 600
    atomicAdd(address, value);
#else
    auto addr = reinterpret_cast<unsigned long long *>(address);
    auto old = *addr;
    unsigned long long assumed;
    do {
        assumed = old;
        old = atomicCAS(addr, assumed,
            __double_as_longlong(value + __longlong_as_double(assumed)));
    } while (assumed != old);
#endif
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
    const int blockIndex = blockIdx.x;
    const int tid = threadIdx.x;
    const int bx = blockIndex % blocksX;
    const int by = blockIndex / blocksX;
    const int x0 = bx * FGS_BLOCK_SIZE;
    const int y0 = by * FGS_BLOCK_SIZE;
    const int bw = min(FGS_BLOCK_SIZE, width - x0);
    const int bh = min(FGS_BLOCK_SIZE, height - y0);
    if (bw < 8 || bh < 8) {
        if (tid == 0) metrics[blockIndex] = {};
        return;
    }

    const int count = bw * bh;
    // Both passes below walk the same block, and the gradient pass adds four
    // neighbour taps per pixel -- about six global loads per pixel in total.
    // Those taps are guarded to stay strictly inside the block, so the whole
    // working set is bw*bh with no halo.  Stage it in shared memory once and
    // read every later tap from there, preserving the sample values and the
    // arithmetic order used below.
    __shared__ int tile[FGS_BLOCK_SIZE * FGS_BLOCK_SIZE];
    for (int index = tid; index < count; index += FGS_FLAT_THREADS) {
        tile[index] = load_code<Type, shift>(src, pitch, x0 + index % bw, y0 + index / bw);
    }
    __syncthreads();

    // Consumer NVIDIA GPUs have very low FP64 throughput. None of these
    // per-32x32-block values needs double precision: variance is accumulated
    // from the fitted residual directly, so there is no large mean-square
    // cancellation even with 10-bit input.
    float localSum = 0.0f;
    float localSumX = 0.0f;
    float localSumY = 0.0f;
    float localNormX = 0.0f;
    float localNormY = 0.0f;
    for (int index = tid; index < count; index += FGS_FLAT_THREADS) {
        const int x = index % bw;
        const int y = index / bw;
        const float yn = (2.0f * y - (bh - 1)) / bh;
        const float xn = (2.0f * x - (bw - 1)) / bw;
        const float value = static_cast<float>(tile[index]);
        localSum += value;
        localSumX += value * xn;
        localSumY += value * yn;
        localNormX += xn * xn;
        localNormY += yn * yn;
    }
    __shared__ float reduce0[FGS_FLAT_THREADS];
    __shared__ float reduce1[FGS_FLAT_THREADS];
    __shared__ float reduce2[FGS_FLAT_THREADS];
    __shared__ float reduce3[FGS_FLAT_THREADS];
    __shared__ float reduce4[FGS_FLAT_THREADS];
    __shared__ float reduce5[FGS_FLAT_THREADS];
    __shared__ int reduceCount[FGS_FLAT_THREADS];
    __shared__ float mean;
    __shared__ float planeX;
    __shared__ float planeY;
    reduce0[tid] = localSum;
    reduce1[tid] = localSumX;
    reduce2[tid] = localSumY;
    reduce3[tid] = localNormX;
    reduce4[tid] = localNormY;
    __syncthreads();
    for (int stride = FGS_FLAT_THREADS / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            reduce0[tid] += reduce0[tid + stride];
            reduce1[tid] += reduce1[tid + stride];
            reduce2[tid] += reduce2[tid + stride];
            reduce3[tid] += reduce3[tid + stride];
            reduce4[tid] += reduce4[tid + stride];
        }
        __syncthreads();
    }
    if (tid == 0) {
        mean = reduce0[0] / count;
        planeX = reduce1[0] / fmaxf(reduce3[0], 1e-12f);
        planeY = reduce2[0] / fmaxf(reduce4[0], 1e-12f);
    }
    __syncthreads();

    float localVariance = 0.0f;
    float localGxx = 0.0f;
    float localGxy = 0.0f;
    float localGyy = 0.0f;
    float localCorrelationProduct = 0.0f;
    float localCorrelationEnergy = 0.0f;
    int localGradientCount = 0;
    for (int index = tid; index < count; index += FGS_FLAT_THREADS) {
        const int x = index % bw;
        const int y = index / bw;
        const float yn = (2.0f * y - (bh - 1)) / bh;
        const float xn = (2.0f * x - (bw - 1)) / bw;
        const float value = static_cast<float>(tile[index]);
        const float residual = value - (mean + planeX * xn + planeY * yn);
        localVariance += residual * residual;
        if (x > 0 && x + 1 < bw && y > 0 && y + 1 < bh) {
            const float left = static_cast<float>(tile[index - 1]);
            const float right = static_cast<float>(tile[index + 1]);
            const float up = static_cast<float>(tile[index - bw]);
            const float down = static_cast<float>(tile[index + bw]);
            const float gx = (right - left) * 0.5f - planeX * (2.0f / bw);
            const float gy = (down - up) * 0.5f - planeY * (2.0f / bh);
            localGxx += gx * gx;
            localGxy += gx * gy;
            localGyy += gy * gy;
            const float rightXn = (2.0f * (x + 1) - (bw - 1)) / bw;
            const float downYn = (2.0f * (y + 1) - (bh - 1)) / bh;
            const float rightResidual = right - (mean + planeX * rightXn + planeY * yn);
            const float downResidual = down - (mean + planeX * xn + planeY * downYn);
            localCorrelationProduct += residual * (rightResidual + downResidual);
            localCorrelationEnergy += 0.5f * (
                2.0f * residual * residual
                + rightResidual * rightResidual
                + downResidual * downResidual);
            ++localGradientCount;
        }
    }
    reduce0[tid] = localVariance;
    reduce1[tid] = localGxx;
    reduce2[tid] = localGxy;
    reduce3[tid] = localGyy;
    reduce4[tid] = localCorrelationProduct;
    reduce5[tid] = localCorrelationEnergy;
    reduceCount[tid] = localGradientCount;
    __syncthreads();
    for (int stride = FGS_FLAT_THREADS / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            reduce0[tid] += reduce0[tid + stride];
            reduce1[tid] += reduce1[tid + stride];
            reduce2[tid] += reduce2[tid + stride];
            reduce3[tid] += reduce3[tid + stride];
            reduce4[tid] += reduce4[tid + stride];
            reduce5[tid] += reduce5[tid + stride];
            reduceCount[tid] += reduceCount[tid + stride];
        }
        __syncthreads();
    }
    if (tid != 0) return;
    const float variance = reduce0[0] / count;
    float gxx = reduce1[0] / max(reduceCount[0], 1);
    float gxy = reduce2[0] / max(reduceCount[0], 1);
    float gyy = reduce3[0] / max(reduceCount[0], 1);

    const float maxValue = static_cast<float>((1 << bitDepth) - 1);
    const float scale2 = maxValue * maxValue;
    const float varNorm = variance / scale2;
    gxx /= scale2;
    gxy /= scale2;
    gyy /= scale2;
    const float trace = gxx + gyy;
    const float determinant = gxx * gyy - gxy * gxy;
    const float discriminant = fmaxf(0.0f, trace * trace - 4.0f * determinant);
    const float e1 = (trace + sqrtf(discriminant)) * 0.5f;
    const float e2 = (trace - sqrtf(discriminant)) * 0.5f;
    const float ratio = e1 / fmaxf(e2, 1e-6f);

    const float traceThreshold = 0.15f / (FGS_BLOCK_SIZE * FGS_BLOCK_SIZE);
    const float normThreshold = 0.08f / (FGS_BLOCK_SIZE * FGS_BLOCK_SIZE);
    const float varThreshold = 0.005f / count;
    const bool isFlat = trace < traceThreshold && ratio < 1.25 && e1 < normThreshold && varNorm > varThreshold;
    float scoreArg = -6682.0f * varNorm - 0.2056f * ratio + 13087.0f * trace - 12434.0f * e1 + 2.5694f;
    scoreArg = fminf(100.0f, fmaxf(-25.0f, scoreArg));

    FilmGrainBlockMetric out = {};
    out.mean = mean;
    out.sigma = sqrtf(fmaxf(variance, 0.0f));
    out.score = varNorm > varThreshold ? 1.0f / (1.0f + expf(-scoreArg)) : 0.0f;
    // Random grain has similar gradient energy in every direction, while
    // edges and line-like texture concentrate it along one eigenvector.  Keep
    // this continuous confidence so the refinement mask can be interpolated
    // without introducing visible 32x32 block boundaries.
    out.coherence = (e1 - e2) / fmaxf(trace, 1e-12f);
    // Lag-one correlation distinguishes fine, nearly white grain from coarse
    // grain whose spatial scale the compact AV1 AR model may not reproduce.
    // The symmetric energy denominator keeps the diagnostic bounded.
    out.spatialCorrelation = fminf(1.0f, fmaxf(-1.0f,
        reduce4[0] / fmaxf(reduce5[0], 1e-12f)));
    out.flat = isFlat ? 1u : 0u;
    metrics[blockIndex] = out;
}

__global__ void kernel_fgs_motion_confidence(uint8_t *__restrict__ flatMask,
    const int fgsBlocksX, const int fgsBlocksY,
    const RGYDegrainSAD *__restrict__ sad,
    const int mvBlocksX, const int mvBlocksY, const int mvStep, const int temporalDirections,
    const uint32_t enabledReferenceMask, const uint32_t sadThreshold) {
    const int blockIndex = blockIdx.x * blockDim.x + threadIdx.x;
    if (blockIndex >= fgsBlocksX * fgsBlocksY || !flatMask[blockIndex]) return;

    const int bx = blockIndex % fgsBlocksX;
    const int by = blockIndex / fgsBlocksX;
    const int centerX = bx * FGS_BLOCK_SIZE + FGS_BLOCK_SIZE / 2;
    const int centerY = by * FGS_BLOCK_SIZE + FGS_BLOCK_SIZE / 2;
    const int mvX = min(mvBlocksX - 1, max(0, centerX / max(1, mvStep)));
    const int mvY = min(mvBlocksY - 1, max(0, centerY / max(1, mvStep)));
    const size_t mvBlockIndex = static_cast<size_t>(mvY) * mvBlocksX + mvX;

    uint32_t bestSad = 0xffffffffu;
    bool hasReference = false;
    // Odd slots are the already-seen reference frames in the causal motion
    // layout (d1f, d2f, ...).  Ignore unavailable scene-boundary slots.
    for (int direction = 1; direction < temporalDirections; direction += 2) {
        if ((enabledReferenceMask & (1u << direction)) == 0) continue;
        bestSad = min(bestSad, sad[mvBlockIndex * temporalDirections + direction].sad);
        hasReference = true;
    }
    // With no temporal reference (first frame or a cut), retain the spatial
    // flat-block decision as the safe fallback.  Reject only a reference that
    // exists but does not match the current block.
    if (hasReference && bestSad > sadThreshold) {
        flatMask[blockIndex] = 0;
    }
}

template<typename Type, int shift, int components>
__global__ void kernel_fgs_bilateral(uint8_t *__restrict__ dst, const int dstPitch,
    const uint8_t *__restrict__ src, const int srcPitch, const int width, const int height,
    const int maxValue, const float sigma, const float *__restrict__ sigmaMap,
    const FilmGrainBlockMetric *__restrict__ detailMetrics,
    const int blocksX, const int blocksY, const int planeBlockSize) {
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    constexpr int tileWidth = FGS_BILATERAL_BLOCK_X + FGS_BILATERAL_RADIUS * 2;
    constexpr int tileHeight = FGS_BILATERAL_BLOCK_Y + FGS_BILATERAL_RADIUS * 2;
    constexpr int tilePixels = tileWidth * tileHeight;
    constexpr int blockThreads = FGS_BILATERAL_BLOCK_X * FGS_BILATERAL_BLOCK_Y;
    __shared__ int tile[tilePixels * components];

    // Neighbourhoods overlap heavily: the original implementation issued 25
    // global source loads per output component.  Cooperatively cache this
    // block's 5x5 halo once, preserving the exact sample values and arithmetic
    // order used by the filter below.
    const int tid = threadIdx.y * FGS_BILATERAL_BLOCK_X + threadIdx.x;
    for (int index = tid; index < tilePixels * components; index += blockThreads) {
        const int component = index % components;
        const int pixel = index / components;
        const int tx = pixel % tileWidth;
        const int ty = pixel / tileWidth;
        const int sx = min(width - 1, max(0,
            static_cast<int>(blockIdx.x) * FGS_BILATERAL_BLOCK_X + tx - FGS_BILATERAL_RADIUS));
        const int sy = min(height - 1, max(0,
            static_cast<int>(blockIdx.y) * FGS_BILATERAL_BLOCK_Y + ty - FGS_BILATERAL_RADIUS));
        tile[index] = load_code<Type, shift>(src, srcPitch, sx, sy, component, components);
    }
    __syncthreads();
    if (x >= width || y >= height) return;

    constexpr float spatial[5] = { 1.0f, 4.0f, 6.0f, 4.0f, 1.0f };
    int ix = 0;
    int iy = 0;
    int ix1 = 0;
    int iy1 = 0;
    float wx = 0.0f;
    float wy = 0.0f;
    if (sigmaMap != nullptr || detailMetrics != nullptr) {
        const float fx = (x + 0.5f) / planeBlockSize - 0.5f;
        const float fy = (y + 0.5f) / planeBlockSize - 0.5f;
        ix = max(0, min(blocksX - 1, static_cast<int>(floorf(fx))));
        iy = max(0, min(blocksY - 1, static_cast<int>(floorf(fy))));
        ix1 = min(blocksX - 1, ix + 1);
        iy1 = min(blocksY - 1, iy + 1);
        wx = fminf(1.0f, fmaxf(0.0f, fx - ix));
        wy = fminf(1.0f, fmaxf(0.0f, fy - iy));
    }
    float blockSigma = sigma;
    if (sigmaMap != nullptr) {
        // Grain strength varies across the frame (typically with intensity);
        // a range sigma from the global median under-removes strong grain.
        // Interpolate the per-block noise estimate between block centers.
        const float top = sigmaMap[iy * blocksX + ix] * (1.0f - wx) + sigmaMap[iy * blocksX + ix1] * wx;
        const float bottom = sigmaMap[iy1 * blocksX + ix] * (1.0f - wx) + sigmaMap[iy1 * blocksX + ix1] * wx;
        blockSigma = top * (1.0f - wy) + bottom * wy;
    }
    const float rangeSigma = fmaxf(1.0f, blockSigma * 2.35f);
    const float invRange2 = 1.0f / (rangeSigma * rangeSigma);
    float refinementWeight = 1.0f;
    if (detailMetrics != nullptr) {
        const float top = detailMetrics[iy * blocksX + ix].coherence * (1.0f - wx)
            + detailMetrics[iy * blocksX + ix1].coherence * wx;
        const float bottom = detailMetrics[iy1 * blocksX + ix].coherence * (1.0f - wx)
            + detailMetrics[iy1 * blocksX + ix1].coherence * wx;
        const float coherence = top * (1.0f - wy) + bottom * wy;
        // Below the low threshold is normally isotropic grain; above the high
        // threshold is strongly directional picture detail.  Fade the local
        // correction between the two instead of making the block classifier
        // a hard render boundary.
        refinementWeight = 1.0f - fminf(1.0f, fmaxf(0.0f,
            (coherence - FGS_DETAIL_COHERENCE_LOW)
            / (FGS_DETAIL_COHERENCE_HIGH - FGS_DETAIL_COHERENCE_LOW)));
    }
    for (int component = 0; component < components; ++component) {
        const int centerIndex = (
            (threadIdx.y + FGS_BILATERAL_RADIUS) * tileWidth
            + threadIdx.x + FGS_BILATERAL_RADIUS) * components + component;
        const int center = tile[centerIndex];
        float weighted = 0.0f;
        float weightSum = 0.0f;
        for (int dy = -2; dy <= 2; ++dy) {
            for (int dx = -2; dx <= 2; ++dx) {
                const int sampleIndex = (
                    (threadIdx.y + FGS_BILATERAL_RADIUS + dy) * tileWidth
                    + threadIdx.x + FGS_BILATERAL_RADIUS + dx) * components + component;
                const int sample = tile[sampleIndex];
                if (dx == 0 && dy == 0) {
                    constexpr float centerWeight = spatial[2] * spatial[2];
                    weighted += centerWeight * center;
                    weightSum += centerWeight;
                    continue;
                }
                const float difference = static_cast<float>(sample - center);
                const float rangeWeight = 1.0f / (1.0f + difference * difference * invRange2);
                const float weight = spatial[dx + 2] * spatial[dy + 2] * rangeWeight;
                weighted += weight * sample;
                weightSum += weight;
            }
        }
        const float filteredValue = weighted / fmaxf(weightSum, 1e-6f);
        const int filtered = min(maxValue, max(0, __float2int_rn(
            center + refinementWeight * (filteredValue - center))));
        store_code<Type, shift>(dst, dstPitch, x, y, filtered, component, components);
    }
}

template<typename Type, int shift, int components>
__device__ inline int residual_at(const uint8_t *src, const int srcPitch,
    const uint8_t *denoised, const int denoisedPitch, const int x, const int y, const int component) {
    return load_code<Type, shift>(src, srcPitch, x, y, component, components)
        - load_code<Type, shift>(denoised, denoisedPitch, x, y, component, components);
}

// One block's mean-plus-plane, fitted cooperatively over the whole block.
//
// This is what lets the AR model be estimated from the source rather than from
// the denoiser's residual.  It is a three-term least-squares fit over a single
// 32x32 block, so it can only remove a trend at block scale; the grain band is
// far above that and passes through untouched.  The denoiser cannot be this
// gentle, because it has to produce a clean base at every pixel rather than
// statistics over selected flat blocks -- which is exactly why its residual
// comes back whitened.
//
// The basis is zero-mean over the block by construction (sum of xn is exactly
// zero), so the slopes are independent of the mean and of each other and the
// normal equations reduce to three ratios.
struct FilmGrainBlockPlane {
    float mean;
    float slopeX;
    float slopeY;
    // Detrended variance over EVERY pixel of the block, not just the AR
    // samples.  The AR solve can only afford 64 sparse observations per block
    // -- it costs 25 predictor loads each -- but a variance costs one load, and
    // taking it from the same 64 samples throws away 94% of the evidence for
    // no saving.  In the independent-sample reference case, 64 samples give a
    // variance estimate about four times noisier than all 1024.  That noise
    // lands directly on the strength curve after subtracting the base variance
    // and clamping the result at zero.
    float variance;
    int x0, y0, width, height;
};

template<typename Type, int shift, int components>
__device__ inline void fit_block_plane(const uint8_t *src, const int srcPitch,
    const int x0, const int y0, const int blockW, const int blockH, const int component,
    const int tid, const int threads, float *reduce, FilmGrainBlockPlane& plane) {
    const int count = blockW * blockH;
    float sum = 0.0f, sumX = 0.0f, sumY = 0.0f, sumXX = 0.0f, sumYY = 0.0f, sumVV = 0.0f;
    for (int index = tid; index < count; index += threads) {
        const int lx = index % blockW;
        const int ly = index / blockW;
        const float value = static_cast<float>(
            load_code<Type, shift>(src, srcPitch, x0 + lx, y0 + ly, component, components));
        const float xn = (2.0f * lx - (blockW - 1)) / blockW;
        const float yn = (2.0f * ly - (blockH - 1)) / blockH;
        sum += value;
        sumX += value * xn;
        sumY += value * yn;
        sumXX += xn * xn;
        sumYY += yn * yn;
        sumVV += value * value;
    }
    reduce[tid] = sum;
    reduce[threads + tid] = sumX;
    reduce[2 * threads + tid] = sumY;
    reduce[3 * threads + tid] = sumXX;
    reduce[4 * threads + tid] = sumYY;
    reduce[5 * threads + tid] = sumVV;
    __syncthreads();
    for (int stride = threads / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            for (int k = 0; k < 6; ++k) {
                reduce[k * threads + tid] += reduce[k * threads + tid + stride];
            }
        }
        __syncthreads();
    }
    plane.mean = reduce[0] / fmaxf(static_cast<float>(count), 1.0f);
    plane.slopeX = reduce[threads] / fmaxf(reduce[3 * threads], 1e-6f);
    plane.slopeY = reduce[2 * threads] / fmaxf(reduce[4 * threads], 1e-6f);
    // The basis {1, xn, yn} is orthogonal over the block -- sum(xn), sum(yn)
    // and sum(xn*yn) are all exactly zero -- so the detrended variance follows
    // from the same accumulators without a second pass over the pixels:
    //   E[d^2] = E[v^2] - mean^2 - slopeX^2 E[xn^2] - slopeY^2 E[yn^2]
    const float invCount = 1.0f / fmaxf(static_cast<float>(count), 1.0f);
    plane.variance = fmaxf(0.0f, reduce[5 * threads] * invCount - plane.mean * plane.mean
        - plane.slopeX * plane.slopeX * reduce[3 * threads] * invCount
        - plane.slopeY * plane.slopeY * reduce[4 * threads] * invCount);
    plane.x0 = x0;
    plane.y0 = y0;
    plane.width = blockW;
    plane.height = blockH;
    __syncthreads();
}

template<typename Type, int shift, int components>
__device__ inline int detrended_at(const uint8_t *src, const int srcPitch,
    const int x, const int y, const int component, const FilmGrainBlockPlane& plane) {
    const float xn = (2.0f * (x - plane.x0) - (plane.width - 1)) / plane.width;
    const float yn = (2.0f * (y - plane.y0) - (plane.height - 1)) / plane.height;
    const float value = static_cast<float>(
        load_code<Type, shift>(src, srcPitch, x, y, component, components));
    return __float2int_rn(value - (plane.mean + plane.slopeX * xn + plane.slopeY * yn));
}

template<typename Type, int shift, int components, bool chroma>
__global__ void kernel_fgs_model_stats(const uint8_t *__restrict__ src, const int srcPitch,
    const uint8_t *__restrict__ denoised, const int denoisedPitch, const int width, const int height,
    const int component, const uint8_t *__restrict__ lumaSrc, const int lumaSrcPitch,
    const uint8_t *__restrict__ lumaDenoised, const int lumaDenoisedPitch,
    const int lumaWidth, const int lumaHeight, const int blocksX, const int bitDepth,
    const uint8_t *__restrict__ flatMask, const FilmGrainBlockMetric *__restrict__ metrics,
    FilmGrainGpuPlaneStats *__restrict__ output, const bool modelFromSource) {
    const int bx = blockIdx.x;
    const int by = blockIdx.y;
    const int blockIndex = by * blocksX + bx;
    if (flatMask[blockIndex] == 0) return;

    constexpr int coeffCount = chroma ? FGS_AR_COEFFS_CHROMA : FGS_AR_COEFFS;
    constexpr int triCount = chroma ? FGS_TRI_C : FGS_TRI_Y;
    const int tid = threadIdx.y * blockDim.x + threadIdx.x;
    const int threads = blockDim.x * blockDim.y;
    __shared__ int predictors[64][coeffCount];
    __shared__ int values[64];
    __shared__ uint8_t valid[64];
    __shared__ float planeReduce[6 * 64];
    __shared__ FilmGrainBlockPlane blockPlane;
    __shared__ FilmGrainBlockPlane lumaPlane;
    __shared__ FilmGrainBlockPlane basePlane;

    const int modelBlock = chroma ? FGS_BLOCK_SIZE / 2 : FGS_BLOCK_SIZE;
    const int x0 = bx * modelBlock;
    const int y0 = by * modelBlock;
    const int xEnd = min(width, x0 + modelBlock);
    const int yEnd = min(height, y0 + modelBlock);
    const int blockW = xEnd - x0;
    const int blockH = yEnd - y0;
    if (modelFromSource) {
        fit_block_plane<Type, shift, components>(src, srcPitch, x0, y0, blockW, blockH,
            component, tid, threads, planeReduce, blockPlane);
        // The same fit on the clean base.  A source-derived strength curve
        // measures the TOTAL grain, but the base still carries whatever the
        // denoiser failed to remove, and synthesising the total on top of that
        // over-delivers.  Subtracting the base's own detrended variance leaves
        // exactly the variance that is missing and has to be put back.
        //
        // It removes the source fit's picture contamination for free: whatever
        // structure survives the plane fit is present in both planes -- the
        // denoiser preserves picture, that is its job -- so it cancels in the
        // difference instead of inflating the curve.
        fit_block_plane<Type, shift, components>(denoised, denoisedPitch, x0, y0,
            blockW, blockH, component, tid, threads, planeReduce, basePlane);
        if (chroma) {
            // The chroma model carries one extra tap for the co-located luma
            // sample, so that tap has to come from the same domain as the rest
            // -- mixing a detrended chroma target with a denoised luma
            // predictor would corrupt the fitted cross-plane correlation.
            fit_block_plane<Type, shift, 1>(lumaSrc, lumaSrcPitch, x0 * 2, y0 * 2,
                min(blockW * 2, lumaWidth - x0 * 2), min(blockH * 2, lumaHeight - y0 * 2),
                0, tid, threads, planeReduce, lumaPlane);
        }
    }
    const uint32_t sampleHash = fgs_sample_hash(static_cast<uint32_t>(blockIndex * 64 + tid));
    // The AR template reaches three pixels left/right and three rows upward.
    // Stagger one observation within each 8x8 stratum instead of sampling the
    // same 4-pixel lattice in every block.  The fixed lattice aliases coarse
    // film grain and can nearly double the fitted AR gain, which halves the
    // signalled grain strength.
    const int x = x0 + fgs_stratified_sample_offset(
        blockW, FGS_AR_LAG, FGS_AR_LAG, threadIdx.x, sampleHash);
    const int y = y0 + fgs_stratified_sample_offset(
        blockH, FGS_AR_LAG, 0, threadIdx.y, sampleHash >> 8);
    valid[tid] = blockW > FGS_AR_LAG * 2 && blockH > FGS_AR_LAG
        && x >= FGS_AR_LAG && x + FGS_AR_LAG < width
        && y >= FGS_AR_LAG && y < height;
    if (valid[tid]) {
        int index = 0;
        for (int dy = -FGS_AR_LAG; dy < 0; ++dy) {
            for (int dx = -FGS_AR_LAG; dx <= FGS_AR_LAG; ++dx) {
                predictors[tid][index++] = modelFromSource
                    ? detrended_at<Type, shift, components>(
                        src, srcPitch, x + dx, y + dy, component, blockPlane)
                    : residual_at<Type, shift, components>(
                        src, srcPitch, denoised, denoisedPitch, x + dx, y + dy, component);
            }
        }
        for (int dx = -FGS_AR_LAG; dx < 0; ++dx) {
            predictors[tid][index++] = modelFromSource
                ? detrended_at<Type, shift, components>(
                    src, srcPitch, x + dx, y, component, blockPlane)
                : residual_at<Type, shift, components>(
                    src, srcPitch, denoised, denoisedPitch, x + dx, y, component);
        }
        if (chroma) {
            const int lx = min(lumaWidth - 2, max(0, x * 2));
            const int ly = min(lumaHeight - 2, max(0, y * 2));
            int lumaResidual = 0;
            for (int dy = 0; dy < 2; ++dy) {
                for (int dx = 0; dx < 2; ++dx) {
                    lumaResidual += modelFromSource
                        ? detrended_at<Type, shift, 1>(lumaSrc, lumaSrcPitch,
                            lx + dx, ly + dy, 0, lumaPlane)
                        : residual_at<Type, shift, 1>(lumaSrc, lumaSrcPitch,
                            lumaDenoised, lumaDenoisedPitch, lx + dx, ly + dy, 0);
                }
            }
            predictors[tid][index++] = (lumaResidual + (lumaResidual >= 0 ? 2 : -2)) / 4;
        }
        values[tid] = modelFromSource
            ? detrended_at<Type, shift, components>(src, srcPitch, x, y, component, blockPlane)
            : residual_at<Type, shift, components>(
                src, srcPitch, denoised, denoisedPitch, x, y, component);
    } else {
        // Zero an unusable sample instead of testing valid[] inside the
        // accumulation loops below.  A zero predictor contributes exactly
        // zero to every normal-equation product, so the statistics are
        // unchanged while the inner loops lose a per-sample branch.
        for (int i = 0; i < coeffCount; ++i) {
            predictors[tid][i] = 0;
        }
        values[tid] = 0;
    }
    __syncthreads();

    // The old implementation issued one shared-memory 64-bit atomic for
    // every sample/coefficient product (more than 22,000 per chroma block).
    // Give each normal-equation element to one thread instead. It sums all
    // samples locally and performs the same single global accumulation.
    // Inputs and sums stay integer, so this produces identical statistics.
    //
    // The block-local sums are accumulated in 32 bits.  Residuals are
    // differences of two same-plane samples, so |residual| <= 1023 at the
    // deepest supported bit depth; a product is at most 1023*1023 and the
    // sum spans exactly `threads` (64) samples, so the magnitude cannot
    // exceed 66,977,856 -- about 32x inside int32.  The global accumulators
    // stay 64-bit because they sum every block in the frame.  A 64-bit
    // block-local sum costs widening multiplies plus carry fix-up on every
    // one of the 300+ elements, which dominated this kernel.
    // predictors[]/values[] are sized for 64 samples, so `threads` is 64.
    static_assert(64LL * 1023 * 1023 <= 2147483647LL,
        "block-local int32 accumulation must not overflow at 10-bit residuals");
    for (int packed = tid; packed < triCount; packed += threads) {
        int i = 0;
        int j = packed;
        for (int rowLength = coeffCount; j >= rowLength; --rowLength) {
            j -= rowLength;
            ++i;
        }
        j += i;
        int32_t sum = 0;
        for (int sample = 0; sample < threads; ++sample) {
            sum += predictors[sample][i] * predictors[sample][j];
        }
        atomic_add_i64(output->ata + packed, static_cast<int64_t>(sum));
    }
    for (int i = tid; i < coeffCount; i += threads) {
        int32_t sum = 0;
        for (int sample = 0; sample < threads; ++sample) {
            sum += predictors[sample][i] * values[sample];
        }
        atomic_add_i64(output->atb + i, static_cast<int64_t>(sum));
    }
    if (tid == 0) {
        int64_t residualSum = 0;
        uint64_t residualSumSq = 0;
        int64_t predSum = 0;
        uint64_t predSumSq = 0;
        unsigned int sampleCount = 0;
        for (int sample = 0; sample < threads; ++sample) {
            if (!valid[sample]) continue;
            const int value = values[sample];
            residualSum += value;
            residualSumSq += static_cast<uint64_t>(static_cast<int64_t>(value) * value);
            if (chroma) {
                const int pred = predictors[sample][coeffCount - 1];
                predSum += pred;
                predSumSq += static_cast<uint64_t>(static_cast<int64_t>(pred) * pred);
            }
            ++sampleCount;
        }
        if (sampleCount == 0) return;
        // One strength observation per flat block: the block's residual
        // variance keyed by the block's mean luma, as in libaom
        // add_noise_std_observations.  Binning single pixels by their own
        // noisy value biases the strength curve.
        const double samples = static_cast<double>(sampleCount);
        const double meanResidual = static_cast<double>(residualSum) / samples;
        double variance = fmax(0.0,
            static_cast<double>(residualSumSq) / samples - meanResidual * meanResidual);
        bool strengthRectified = false;
        if (modelFromSource) {
            // Strength comes from every pixel of the block, not from the 64 AR
            // samples.  The AR fit has to stay sparse because each observation
            // costs 25 predictor loads, but a variance costs one, so there is
            // no reason to keep the much noisier sparse estimator for the one
            // quantity that sets the signalled grain amplitude.
            const double varianceDifference = static_cast<double>(blockPlane.variance)
                - static_cast<double>(basePlane.variance);
            strengthRectified = varianceDifference <= 0.0;
            variance = fmax(0.0, varianceDifference);
        }
        const int maxValue = (1 << bitDepth) - 1;
        const int bin = min(FGS_STRENGTH_BINS - 1, max(0,
            static_cast<int>(metrics[blockIndex].mean * FGS_STRENGTH_BINS / (maxValue + 1))));
        atomic_add_f64(output->binVarSum + bin, variance);
        atomic_add_u64(output->binBlockCount + bin, 1ULL);
        if (strengthRectified) {
            atomic_add_u64(output->rectifiedBlockCount + bin, 1ULL);
        }
        if (chroma) {
            const double meanPred = static_cast<double>(predSum) / samples;
            const double predVariance = fmax(0.0,
                static_cast<double>(predSumSq) / samples - meanPred * meanPred);
            atomic_add_f64(&output->lumaPredVarSum, predVariance);
            atomic_add_u64(&output->lumaPredBlocks, 1ULL);
        }
        atomic_add_u64(&output->observations, sampleCount);
    }
}

// Consecutive-frame differencing removes static picture content before the
// strength fit.  This measures two quantities that a single spatial frame
// cannot separate: total source grain and grain still moving in the clean
// base.  Only blocks whose temporal/spatial source variance agrees are used;
// motion and cuts fall outside the same 0.8..1.3 gate validated by the offline
// production_static corpus.
template<typename Type, int shift>
__global__ void kernel_fgs_temporal_strength(
    const uint8_t *__restrict__ source, const int sourcePitch,
    const uint8_t *__restrict__ previousSource, const int previousSourcePitch,
    const uint8_t *__restrict__ base, const int basePitch,
    const uint8_t *__restrict__ previousBase, const int previousBasePitch,
    const int width, const int height, const int blocksX, const int bitDepth,
    const uint8_t *__restrict__ flatMask,
    const FilmGrainBlockMetric *__restrict__ metrics,
    FilmGrainGpuPlaneStats *__restrict__ output) {
    const int bx = blockIdx.x;
    const int by = blockIdx.y;
    const int blockIndex = by * blocksX + bx;
    if (flatMask[blockIndex] == 0) return;

    const int tid = threadIdx.y * blockDim.x + threadIdx.x;
    const int threads = blockDim.x * blockDim.y;
    __shared__ float reduce[10 * 64];
    const int x0 = bx * FGS_BLOCK_SIZE;
    const int y0 = by * FGS_BLOCK_SIZE;
    const int blockW = min(FGS_BLOCK_SIZE, width - x0);
    const int blockH = min(FGS_BLOCK_SIZE, height - y0);
    const int count = blockW * blockH;
    float sourceSum = 0.0f, sourceX = 0.0f, sourceY = 0.0f, sourceSq = 0.0f;
    float baseSum = 0.0f, baseX = 0.0f, baseY = 0.0f, baseSq = 0.0f;
    float sumXX = 0.0f, sumYY = 0.0f;
    for (int index = tid; index < count; index += threads) {
        const int lx = index % blockW;
        const int ly = index / blockW;
        const int x = x0 + lx;
        const int y = y0 + ly;
        const float xn = (2.0f * lx - (blockW - 1)) / blockW;
        const float yn = (2.0f * ly - (blockH - 1)) / blockH;
        const float sourceDifference = static_cast<float>(
            load_code<Type, shift>(source, sourcePitch, x, y, 0, 1)
            - load_code<Type, shift>(previousSource, previousSourcePitch, x, y, 0, 1));
        const float baseDifference = static_cast<float>(
            load_code<Type, shift>(base, basePitch, x, y, 0, 1)
            - load_code<Type, shift>(previousBase, previousBasePitch, x, y, 0, 1));
        sourceSum += sourceDifference;
        sourceX += sourceDifference * xn;
        sourceY += sourceDifference * yn;
        sourceSq += sourceDifference * sourceDifference;
        baseSum += baseDifference;
        baseX += baseDifference * xn;
        baseY += baseDifference * yn;
        baseSq += baseDifference * baseDifference;
        sumXX += xn * xn;
        sumYY += yn * yn;
    }
    reduce[tid] = sourceSum;
    reduce[threads + tid] = sourceX;
    reduce[2 * threads + tid] = sourceY;
    reduce[3 * threads + tid] = sourceSq;
    reduce[4 * threads + tid] = baseSum;
    reduce[5 * threads + tid] = baseX;
    reduce[6 * threads + tid] = baseY;
    reduce[7 * threads + tid] = baseSq;
    reduce[8 * threads + tid] = sumXX;
    reduce[9 * threads + tid] = sumYY;
    __syncthreads();
    for (int stride = threads / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            for (int item = 0; item < 10; ++item) {
                reduce[item * threads + tid] += reduce[item * threads + tid + stride];
            }
        }
        __syncthreads();
    }
    if (tid != 0 || count == 0) return;

    const double invCount = 1.0 / static_cast<double>(count);
    const double sourceMean = reduce[0] * invCount;
    const double sourceSlopeX = reduce[threads] / fmax(static_cast<double>(reduce[8 * threads]), 1e-6);
    const double sourceSlopeY = reduce[2 * threads] / fmax(static_cast<double>(reduce[9 * threads]), 1e-6);
    const double sourceUnplanedVariance = fmax(0.0,
        (reduce[3 * threads] * invCount - sourceMean * sourceMean) * 0.5);
    const double sourceVariance = fmax(0.0, sourceUnplanedVariance
        - sourceSlopeX * sourceSlopeX * reduce[8 * threads] * invCount * 0.5
        - sourceSlopeY * sourceSlopeY * reduce[9 * threads] * invCount * 0.5);
    const double spatialVariance = static_cast<double>(metrics[blockIndex].sigma)
        * metrics[blockIndex].sigma;
    const double staticRatio = sourceUnplanedVariance / fmax(spatialVariance, 1e-6);
    if (staticRatio < 0.8 || staticRatio > 1.3 || sourceVariance <= 1e-6) return;

    const double baseMean = reduce[4 * threads] * invCount;
    const double baseSlopeX = reduce[5 * threads] / fmax(static_cast<double>(reduce[8 * threads]), 1e-6);
    const double baseSlopeY = reduce[6 * threads] / fmax(static_cast<double>(reduce[9 * threads]), 1e-6);
    const double baseVariance = fmax(0.0,
        (reduce[7 * threads] * invCount - baseMean * baseMean) * 0.5
        - baseSlopeX * baseSlopeX * reduce[8 * threads] * invCount * 0.5
        - baseSlopeY * baseSlopeY * reduce[9 * threads] * invCount * 0.5);
    const int maxValue = (1 << bitDepth) - 1;
    const int bin = min(FGS_STRENGTH_BINS - 1, max(0,
        static_cast<int>(metrics[blockIndex].mean * FGS_STRENGTH_BINS / (maxValue + 1))));
    atomic_add_f64(output->temporalSourceVarSum + bin, sourceVariance);
    atomic_add_f64(output->temporalBaseVarSum + bin, baseVariance);
    atomic_add_u64(output->temporalBlockCount + bin, 1ULL);
}

template<typename Type, int shift>
__device__ inline int temporal_detrended_at(
    const uint8_t *current, const int currentPitch,
    const uint8_t *previous, const int previousPitch,
    const int x, const int y, const FilmGrainBlockPlane& plane) {
    const float xn = (2.0f * (x - plane.x0) - (plane.width - 1)) / plane.width;
    const float yn = (2.0f * (y - plane.y0) - (plane.height - 1)) / plane.height;
    const float difference = static_cast<float>(
        load_code<Type, shift>(current, currentPitch, x, y, 0, 1)
        - load_code<Type, shift>(previous, previousPitch, x, y, 0, 1));
    return __float2int_rn(
        difference - (plane.mean + plane.slopeX * xn + plane.slopeY * yn));
}

// Test-only texture composition.  Strength closure already subtracts the
// amount of grain energy retained by the clean base, but a source AR fit still
// describes the source's complete covariance.  Adding that full texture on
// top of the correlated texture left in the base makes playback too coarse.
// Measure the missing covariance directly on consecutive-frame differences:
//
//   C_synth = C_source - 0.75 * C_base
//
// The 4:3 integer weights are the frozen eight-film result.  The common factor
// of two introduced by temporal differencing cancels from the AR solve.  This
// kernel is never launched unless NVENC_FGS_TEST_TEXTURE_LEAK=on.
template<typename Type, int shift>
__global__ void kernel_fgs_temporal_texture_stats(
    const uint8_t *__restrict__ source, const int sourcePitch,
    const uint8_t *__restrict__ previousSource, const int previousSourcePitch,
    const uint8_t *__restrict__ base, const int basePitch,
    const uint8_t *__restrict__ previousBase, const int previousBasePitch,
    const int width, const int height, const int blocksX,
    const uint8_t *__restrict__ temporalMask,
    FilmGrainTemporalArStats *__restrict__ output) {
    const int bx = blockIdx.x;
    const int by = blockIdx.y;
    const int blockIndex = by * blocksX + bx;
    if (temporalMask[blockIndex] == 0) return;

    const int tid = threadIdx.y * blockDim.x + threadIdx.x;
    const int threads = blockDim.x * blockDim.y;
    __shared__ int sourcePredictors[64][FGS_AR_COEFFS];
    __shared__ int basePredictors[64][FGS_AR_COEFFS];
    __shared__ int sourceValues[64];
    __shared__ int baseValues[64];
    __shared__ uint8_t valid[64];
    __shared__ float reduce[10 * 64];
    __shared__ FilmGrainBlockPlane sourcePlane;
    __shared__ FilmGrainBlockPlane basePlane;

    const int x0 = bx * FGS_BLOCK_SIZE;
    const int y0 = by * FGS_BLOCK_SIZE;
    const int blockW = min(FGS_BLOCK_SIZE, width - x0);
    const int blockH = min(FGS_BLOCK_SIZE, height - y0);
    const int count = blockW * blockH;
    float sourceSum = 0.0f, sourceX = 0.0f, sourceY = 0.0f;
    float baseSum = 0.0f, baseX = 0.0f, baseY = 0.0f;
    float sumXX = 0.0f, sumYY = 0.0f;
    for (int index = tid; index < count; index += threads) {
        const int lx = index % blockW;
        const int ly = index / blockW;
        const int x = x0 + lx;
        const int y = y0 + ly;
        const float xn = (2.0f * lx - (blockW - 1)) / blockW;
        const float yn = (2.0f * ly - (blockH - 1)) / blockH;
        const float sourceDifference = static_cast<float>(
            load_code<Type, shift>(source, sourcePitch, x, y, 0, 1)
            - load_code<Type, shift>(previousSource, previousSourcePitch, x, y, 0, 1));
        const float baseDifference = static_cast<float>(
            load_code<Type, shift>(base, basePitch, x, y, 0, 1)
            - load_code<Type, shift>(previousBase, previousBasePitch, x, y, 0, 1));
        sourceSum += sourceDifference;
        sourceX += sourceDifference * xn;
        sourceY += sourceDifference * yn;
        baseSum += baseDifference;
        baseX += baseDifference * xn;
        baseY += baseDifference * yn;
        sumXX += xn * xn;
        sumYY += yn * yn;
    }
    reduce[tid] = sourceSum;
    reduce[threads + tid] = sourceX;
    reduce[2 * threads + tid] = sourceY;
    reduce[3 * threads + tid] = baseSum;
    reduce[4 * threads + tid] = baseX;
    reduce[5 * threads + tid] = baseY;
    reduce[6 * threads + tid] = sumXX;
    reduce[7 * threads + tid] = sumYY;
    __syncthreads();
    for (int stride = threads / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            for (int item = 0; item < 8; ++item) {
                reduce[item * threads + tid] += reduce[item * threads + tid + stride];
            }
        }
        __syncthreads();
    }
    if (tid == 0) {
        const float invCount = 1.0f / fmaxf(static_cast<float>(count), 1.0f);
        sourcePlane.mean = reduce[0] * invCount;
        sourcePlane.slopeX = reduce[threads] / fmaxf(reduce[6 * threads], 1e-6f);
        sourcePlane.slopeY = reduce[2 * threads] / fmaxf(reduce[7 * threads], 1e-6f);
        sourcePlane.variance = 0.0f;
        sourcePlane.x0 = x0;
        sourcePlane.y0 = y0;
        sourcePlane.width = blockW;
        sourcePlane.height = blockH;
        basePlane.mean = reduce[3 * threads] * invCount;
        basePlane.slopeX = reduce[4 * threads] / fmaxf(reduce[6 * threads], 1e-6f);
        basePlane.slopeY = reduce[5 * threads] / fmaxf(reduce[7 * threads], 1e-6f);
        basePlane.variance = 0.0f;
        basePlane.x0 = x0;
        basePlane.y0 = y0;
        basePlane.width = blockW;
        basePlane.height = blockH;
    }
    __syncthreads();

    const uint32_t sampleHash = fgs_sample_hash(
        static_cast<uint32_t>(blockIndex * 64 + tid));
    const int x = x0 + fgs_stratified_sample_offset(
        blockW, FGS_AR_LAG, FGS_AR_LAG, threadIdx.x, sampleHash);
    const int y = y0 + fgs_stratified_sample_offset(
        blockH, FGS_AR_LAG, 0, threadIdx.y, sampleHash >> 8);
    valid[tid] = blockW > FGS_AR_LAG * 2 && blockH > FGS_AR_LAG
        && x >= FGS_AR_LAG && x + FGS_AR_LAG < width
        && y >= FGS_AR_LAG && y < height;
    if (valid[tid]) {
        int coefficient = 0;
        for (int dy = -FGS_AR_LAG; dy < 0; ++dy) {
            for (int dx = -FGS_AR_LAG; dx <= FGS_AR_LAG; ++dx) {
                sourcePredictors[tid][coefficient] = temporal_detrended_at<Type, shift>(
                    source, sourcePitch, previousSource, previousSourcePitch,
                    x + dx, y + dy, sourcePlane);
                basePredictors[tid][coefficient] = temporal_detrended_at<Type, shift>(
                    base, basePitch, previousBase, previousBasePitch,
                    x + dx, y + dy, basePlane);
                ++coefficient;
            }
        }
        for (int dx = -FGS_AR_LAG; dx < 0; ++dx) {
            sourcePredictors[tid][coefficient] = temporal_detrended_at<Type, shift>(
                source, sourcePitch, previousSource, previousSourcePitch,
                x + dx, y, sourcePlane);
            basePredictors[tid][coefficient] = temporal_detrended_at<Type, shift>(
                base, basePitch, previousBase, previousBasePitch,
                x + dx, y, basePlane);
            ++coefficient;
        }
        sourceValues[tid] = temporal_detrended_at<Type, shift>(
            source, sourcePitch, previousSource, previousSourcePitch,
            x, y, sourcePlane);
        baseValues[tid] = temporal_detrended_at<Type, shift>(
            base, basePitch, previousBase, previousBasePitch,
            x, y, basePlane);
    } else {
        for (int coefficient = 0; coefficient < FGS_AR_COEFFS; ++coefficient) {
            sourcePredictors[tid][coefficient] = 0;
            basePredictors[tid][coefficient] = 0;
        }
        sourceValues[tid] = 0;
        baseValues[tid] = 0;
    }
    __syncthreads();

    for (int packed = tid; packed < FGS_TRI_Y; packed += threads) {
        int i = 0;
        int j = packed;
        for (int rowLength = FGS_AR_COEFFS; j >= rowLength; --rowLength) {
            j -= rowLength;
            ++i;
        }
        j += i;
        int64_t sum = 0;
        for (int sample = 0; sample < threads; ++sample) {
            sum += static_cast<int64_t>(FGS_TEXTURE_SOURCE_WEIGHT)
                    * sourcePredictors[sample][i] * sourcePredictors[sample][j]
                - static_cast<int64_t>(FGS_TEXTURE_BASE_WEIGHT)
                    * basePredictors[sample][i] * basePredictors[sample][j];
        }
        atomic_add_i64(output->weightedAta + packed, sum);
    }
    for (int i = tid; i < FGS_AR_COEFFS; i += threads) {
        int64_t sum = 0;
        for (int sample = 0; sample < threads; ++sample) {
            sum += static_cast<int64_t>(FGS_TEXTURE_SOURCE_WEIGHT)
                    * sourcePredictors[sample][i] * sourceValues[sample]
                - static_cast<int64_t>(FGS_TEXTURE_BASE_WEIGHT)
                    * basePredictors[sample][i] * baseValues[sample];
        }
        atomic_add_i64(output->weightedAtb + i, sum);
    }
    if (tid == 0) {
        int64_t btb = 0;
        uint64_t observations = 0;
        for (int sample = 0; sample < threads; ++sample) {
            if (!valid[sample]) continue;
            btb += static_cast<int64_t>(FGS_TEXTURE_SOURCE_WEIGHT)
                    * sourceValues[sample] * sourceValues[sample]
                - static_cast<int64_t>(FGS_TEXTURE_BASE_WEIGHT)
                    * baseValues[sample] * baseValues[sample];
            ++observations;
        }
        atomic_add_i64(&output->weightedBtb, btb);
        atomic_add_u64(&output->observations, observations);
    }
}

// Chroma closure is test-only and must not perturb the established luma
// kernel above.  Build its luma-static population in a separate launch, then
// measure the corresponding 16x16 U/V blocks.  Keeping the original luma
// launch byte-for-byte intact is important: its FP64 atomics can otherwise
// cross a strength quantization boundary solely from a scheduling change.
template<typename Type, int shift>
__global__ void kernel_fgs_temporal_chroma_mask(
    const uint8_t *__restrict__ source, const int sourcePitch,
    const uint8_t *__restrict__ previousSource, const int previousSourcePitch,
    const int width, const int height, const int blocksX,
    const uint8_t *__restrict__ flatMask,
    const FilmGrainBlockMetric *__restrict__ metrics,
    uint8_t *__restrict__ temporalMask) {
    const int bx = blockIdx.x;
    const int by = blockIdx.y;
    const int blockIndex = by * blocksX + bx;
    if (flatMask[blockIndex] == 0) return;

    const int tid = threadIdx.y * blockDim.x + threadIdx.x;
    const int threads = blockDim.x * blockDim.y;
    __shared__ float reduce[6 * 64];
    const int x0 = bx * FGS_BLOCK_SIZE;
    const int y0 = by * FGS_BLOCK_SIZE;
    const int blockW = min(FGS_BLOCK_SIZE, width - x0);
    const int blockH = min(FGS_BLOCK_SIZE, height - y0);
    const int count = blockW * blockH;
    float sourceSum = 0.0f, sourceX = 0.0f, sourceY = 0.0f, sourceSq = 0.0f;
    float sumXX = 0.0f, sumYY = 0.0f;
    for (int index = tid; index < count; index += threads) {
        const int lx = index % blockW;
        const int ly = index / blockW;
        const int x = x0 + lx;
        const int y = y0 + ly;
        const float xn = (2.0f * lx - (blockW - 1)) / blockW;
        const float yn = (2.0f * ly - (blockH - 1)) / blockH;
        const float sourceDifference = static_cast<float>(
            load_code<Type, shift>(source, sourcePitch, x, y, 0, 1)
            - load_code<Type, shift>(previousSource, previousSourcePitch, x, y, 0, 1));
        sourceSum += sourceDifference;
        sourceX += sourceDifference * xn;
        sourceY += sourceDifference * yn;
        sourceSq += sourceDifference * sourceDifference;
        sumXX += xn * xn;
        sumYY += yn * yn;
    }
    reduce[tid] = sourceSum;
    reduce[threads + tid] = sourceX;
    reduce[2 * threads + tid] = sourceY;
    reduce[3 * threads + tid] = sourceSq;
    reduce[4 * threads + tid] = sumXX;
    reduce[5 * threads + tid] = sumYY;
    __syncthreads();
    for (int stride = threads / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            for (int item = 0; item < 6; ++item) {
                reduce[item * threads + tid] += reduce[item * threads + tid + stride];
            }
        }
        __syncthreads();
    }
    if (tid != 0 || count == 0) return;

    const double invCount = 1.0 / static_cast<double>(count);
    const double sourceMean = reduce[0] * invCount;
    const double sourceSlopeX = reduce[threads]
        / fmax(static_cast<double>(reduce[4 * threads]), 1e-6);
    const double sourceSlopeY = reduce[2 * threads]
        / fmax(static_cast<double>(reduce[5 * threads]), 1e-6);
    const double sourceUnplanedVariance = fmax(0.0,
        (reduce[3 * threads] * invCount - sourceMean * sourceMean) * 0.5);
    const double sourceVariance = fmax(0.0, sourceUnplanedVariance
        - sourceSlopeX * sourceSlopeX * reduce[4 * threads] * invCount * 0.5
        - sourceSlopeY * sourceSlopeY * reduce[5 * threads] * invCount * 0.5);
    const double spatialVariance = static_cast<double>(metrics[blockIndex].sigma)
        * metrics[blockIndex].sigma;
    const double staticRatio = sourceUnplanedVariance / fmax(spatialVariance, 1e-6);
    if (staticRatio >= 0.8 && staticRatio <= 1.3 && sourceVariance > 1e-6) {
        temporalMask[blockIndex] = 1;
    }
}

template<typename Type, int shift, int components>
__global__ void kernel_fgs_temporal_chroma_strength(
    const uint8_t *__restrict__ source, const int sourcePitch,
    const uint8_t *__restrict__ previousSource, const int previousSourcePitch,
    const uint8_t *__restrict__ base, const int basePitch,
    const uint8_t *__restrict__ previousBase, const int previousBasePitch,
    const int width, const int height, const int component,
    const int blocksX, const int bitDepth,
    const uint8_t *__restrict__ temporalMask,
    const FilmGrainBlockMetric *__restrict__ metrics,
    FilmGrainGpuPlaneStats *__restrict__ output) {
    const int bx = blockIdx.x;
    const int by = blockIdx.y;
    const int blockIndex = by * blocksX + bx;
    if (temporalMask[blockIndex] == 0) return;

    const int tid = threadIdx.y * blockDim.x + threadIdx.x;
    const int threads = blockDim.x * blockDim.y;
    __shared__ float reduce[10 * 64];
    constexpr int chromaBlock = FGS_BLOCK_SIZE / 2;
    const int x0 = bx * chromaBlock;
    const int y0 = by * chromaBlock;
    const int blockW = min(chromaBlock, width - x0);
    const int blockH = min(chromaBlock, height - y0);
    const int count = blockW * blockH;
    float sourceSum = 0.0f, sourceX = 0.0f, sourceY = 0.0f, sourceSq = 0.0f;
    float baseSum = 0.0f, baseX = 0.0f, baseY = 0.0f, baseSq = 0.0f;
    float sumXX = 0.0f, sumYY = 0.0f;
    for (int index = tid; index < count; index += threads) {
        const int lx = index % blockW;
        const int ly = index / blockW;
        const int x = x0 + lx;
        const int y = y0 + ly;
        const float xn = (2.0f * lx - (blockW - 1)) / blockW;
        const float yn = (2.0f * ly - (blockH - 1)) / blockH;
        const float sourceDifference = static_cast<float>(
            load_code<Type, shift>(source, sourcePitch, x, y, component, components)
            - load_code<Type, shift>(previousSource, previousSourcePitch,
                x, y, component, components));
        const float baseDifference = static_cast<float>(
            load_code<Type, shift>(base, basePitch, x, y, component, components)
            - load_code<Type, shift>(previousBase, previousBasePitch,
                x, y, component, components));
        sourceSum += sourceDifference;
        sourceX += sourceDifference * xn;
        sourceY += sourceDifference * yn;
        sourceSq += sourceDifference * sourceDifference;
        baseSum += baseDifference;
        baseX += baseDifference * xn;
        baseY += baseDifference * yn;
        baseSq += baseDifference * baseDifference;
        sumXX += xn * xn;
        sumYY += yn * yn;
    }
    reduce[tid] = sourceSum;
    reduce[threads + tid] = sourceX;
    reduce[2 * threads + tid] = sourceY;
    reduce[3 * threads + tid] = sourceSq;
    reduce[4 * threads + tid] = baseSum;
    reduce[5 * threads + tid] = baseX;
    reduce[6 * threads + tid] = baseY;
    reduce[7 * threads + tid] = baseSq;
    reduce[8 * threads + tid] = sumXX;
    reduce[9 * threads + tid] = sumYY;
    __syncthreads();
    for (int stride = threads / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            for (int item = 0; item < 10; ++item) {
                reduce[item * threads + tid] += reduce[item * threads + tid + stride];
            }
        }
        __syncthreads();
    }
    if (tid != 0 || count == 0) return;

    const double invCount = 1.0 / static_cast<double>(count);
    const double sourceMean = reduce[0] * invCount;
    const double sourceSlopeX = reduce[threads]
        / fmax(static_cast<double>(reduce[8 * threads]), 1e-6);
    const double sourceSlopeY = reduce[2 * threads]
        / fmax(static_cast<double>(reduce[9 * threads]), 1e-6);
    const double sourceVariance = fmax(0.0,
        (reduce[3 * threads] * invCount - sourceMean * sourceMean) * 0.5
        - sourceSlopeX * sourceSlopeX * reduce[8 * threads] * invCount * 0.5
        - sourceSlopeY * sourceSlopeY * reduce[9 * threads] * invCount * 0.5);
    if (sourceVariance <= 1e-6) return;

    const double baseMean = reduce[4 * threads] * invCount;
    const double baseSlopeX = reduce[5 * threads]
        / fmax(static_cast<double>(reduce[8 * threads]), 1e-6);
    const double baseSlopeY = reduce[6 * threads]
        / fmax(static_cast<double>(reduce[9 * threads]), 1e-6);
    const double baseVariance = fmax(0.0,
        (reduce[7 * threads] * invCount - baseMean * baseMean) * 0.5
        - baseSlopeX * baseSlopeX * reduce[8 * threads] * invCount * 0.5
        - baseSlopeY * baseSlopeY * reduce[9 * threads] * invCount * 0.5);
    const int maxValue = (1 << bitDepth) - 1;
    const int bin = min(FGS_STRENGTH_BINS - 1, max(0,
        static_cast<int>(metrics[blockIndex].mean * FGS_STRENGTH_BINS / (maxValue + 1))));
    atomic_add_f64(output->temporalSourceVarSum + bin, sourceVariance);
    atomic_add_f64(output->temporalBaseVarSum + bin, baseVariance);
    atomic_add_u64(output->temporalBlockCount + bin, 1ULL);
}

} // namespace

namespace {

struct FilmGrainHostStats {
    FilmGrainGpuStats gpu;
    FilmGrainGpuStats fallbackGpu;
    float measuredNoise;
    float detailRisk;
    float grainCorrelation;
};

static float auto_retain_from_detail_risk(const float detailRisk) {
    const float unquantized = clamp(detailRisk * FGS_AUTO_RETAIN_SCALE, 0.0f, FGS_AUTO_RETAIN_MAX);
    return std::round(unquantized / FGS_AUTO_RETAIN_STEP) * FGS_AUTO_RETAIN_STEP;
}

template<typename Type, int shift>
static RGY_ERR launch_flat_metrics(const RGYFrameInfo& luma, FilmGrainBlockMetric *metrics,
    const int blocksX, const int blocksY, const int bitDepth, cudaStream_t stream) {
    kernel_fgs_flat_metrics<Type, shift><<<blocksX * blocksY, FGS_FLAT_THREADS, 0, stream>>>(
        luma.ptr[0], luma.pitch[0], luma.width, luma.height, blocksX, bitDepth, metrics);
    return err_to_rgy(cudaGetLastError());
}

static RGY_ERR launch_motion_confidence(uint8_t *flatMask, const int fgsBlocksX, const int fgsBlocksY,
    const RGYDegrainAnalyzeResult& analysis, const uint32_t enabledReferenceMask,
    const uint32_t sadThreshold, cudaStream_t stream) {
    constexpr int threads = 128;
    kernel_fgs_motion_confidence<<<divCeil(fgsBlocksX * fgsBlocksY, threads), threads, 0, stream>>>(
        flatMask, fgsBlocksX, fgsBlocksY,
        reinterpret_cast<const RGYDegrainSAD *>(analysis.sad->ptr),
        analysis.layout.blocksX, analysis.layout.blocksY, analysis.layout.step,
        analysis.layout.temporalDirections, enabledReferenceMask, sadThreshold);
    return err_to_rgy(cudaGetLastError());
}

// Per-direction count of motion blocks whose SAD exceeds the scene-change
// threshold, on the full mv grid.  The host compares against the thscd2 block
// fraction to detect hard cuts synchronously with this frame, so the model
// history can be cleared at the cut (the degrainer's own scene readback is
// pipelined and not exposed).
__global__ void kernel_fgs_scene_sad_count(uint32_t *__restrict__ counts,
    const RGYDegrainSAD *__restrict__ sad, const int mvBlockCount, const int temporalDirections,
    const uint32_t enabledReferenceMask, const uint32_t sceneSadThreshold) {
    const int index = blockIdx.x * blockDim.x + threadIdx.x;
    if (index >= mvBlockCount) return;
    for (int direction = 1; direction < temporalDirections; direction += 2) {
        if ((enabledReferenceMask & (1u << direction)) == 0) continue;
        if (sad[static_cast<size_t>(index) * temporalDirections + direction].sad > sceneSadThreshold) {
            atomicAdd(counts + direction, 1u);
        }
    }
}

static RGY_ERR launch_scene_sad_count(uint32_t *counts, const RGYDegrainAnalyzeResult& analysis,
    const uint32_t enabledReferenceMask, const uint32_t sceneSadThreshold, cudaStream_t stream) {
    const int mvBlockCount = analysis.layout.blocksX * analysis.layout.blocksY;
    constexpr int threads = 128;
    kernel_fgs_scene_sad_count<<<divCeil(mvBlockCount, threads), threads, 0, stream>>>(
        counts, reinterpret_cast<const RGYDegrainSAD *>(analysis.sad->ptr),
        mvBlockCount, analysis.layout.temporalDirections, enabledReferenceMask, sceneSadThreshold);
    return err_to_rgy(cudaGetLastError());
}

// The decoder adds synthesized grain to the base and clips to the legal
// range; near the floor/ceiling that clip shifts the mean (censored-normal
// lift), brightening deep shadows that the grainy source only reached through
// its own, already-present clip lift.  Darken the base by the lift the decoder
// will add back so the played-out mean matches the source (measured on the
// dark_luma fixture: +4.0/+2.2/+0.8 code values in the three darkest bands
// before compensation).  Solved as v' = v - lift(v') by two fixed-point steps.
template<typename Type, int shift>
__global__ void kernel_fgs_level_compensate(uint8_t *__restrict__ ptr, const int pitch,
    const int width, const int height, const int rangeMin, const int rangeMax,
    const int bitDepth, const float *__restrict__ strengthLut) {
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;
    const int value = load_code<Type, shift>(ptr, pitch, x, y);
    if (value <= rangeMin || value >= rangeMax) return; // leave out-of-range/boundary pixels alone
    const int lutIndex = min(FGS_STRENGTH_LUT_SIZE - 1, max(0, value >> (bitDepth - 8)));
    const float sigma = strengthLut[lutIndex];
    if (sigma <= 0.01f) return;
    auto clipLift = [](const float d) {
        // E[clip(N(0,1), -d, inf)] = phi(d) - d * PHI(-d)
        return (d > 3.5f) ? 0.0f : 0.39894228f * __expf(-0.5f * d * d) - d * 0.5f * erfcf(d * 0.70710678f);
    };
    float compensated = static_cast<float>(value);
    for (int iter = 0; iter < 2; ++iter) {
        const float dLo = (compensated - rangeMin) / sigma;
        const float dHi = (rangeMax - compensated) / sigma;
        if (dLo > 3.5f && dHi > 3.5f) return;
        compensated = static_cast<float>(value) - sigma * (clipLift(dLo) - clipLift(dHi));
    }
    const int out = min(rangeMax, max(rangeMin, __float2int_rn(compensated)));
    store_code<Type, shift>(ptr, pitch, x, y, out);
}

template<typename Type, int shift>
static RGY_ERR launch_level_compensate(const RGYFrameInfo& luma, const int rangeMin, const int rangeMax,
    const int bitDepth, const float *strengthLut, cudaStream_t stream) {
    const dim3 block(32, 8);
    const dim3 grid(divCeil(luma.width, static_cast<int>(block.x)), divCeil(luma.height, static_cast<int>(block.y)));
    kernel_fgs_level_compensate<Type, shift><<<grid, block, 0, stream>>>(
        luma.ptr[0], luma.pitch[0], luma.width, luma.height, rangeMin, rangeMax, bitDepth, strengthLut);
    return err_to_rgy(cudaGetLastError());
}

// Blend a fraction of the measured residual (source - clean base) back into
// the base layer's luma.  The retained residual and the decoder's synthesis
// are statistically independent, so the caller scales the signalled luma
// curve by sqrt(1 - retain^2) to keep the played-out grain variance equal to
// the measured one.
template<typename Type, int shift>
__global__ void kernel_fgs_residual_retain(uint8_t *__restrict__ dst, const int dstPitch,
    const uint8_t *__restrict__ src, const int srcPitch, const int width, const int height,
    const int maxVal, const float retain) {
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;
    const float clean = static_cast<float>(load_code<Type, shift>(dst, dstPitch, x, y));
    const float orig = static_cast<float>(load_code<Type, shift>(src, srcPitch, x, y));
    const int out = min(maxVal, max(0, __float2int_rn(clean + retain * (orig - clean))));
    store_code<Type, shift>(dst, dstPitch, x, y, out);
}

template<typename Type, int shift>
static RGY_ERR launch_residual_retain(const RGYFrameInfo& lumaDst, const RGYFrameInfo& lumaSrc,
    const int bitDepth, const float retain, cudaStream_t stream) {
    const dim3 block(32, 8);
    const dim3 grid(divCeil(lumaDst.width, static_cast<int>(block.x)), divCeil(lumaDst.height, static_cast<int>(block.y)));
    kernel_fgs_residual_retain<Type, shift><<<grid, block, 0, stream>>>(
        lumaDst.ptr[0], lumaDst.pitch[0], lumaSrc.ptr[0], lumaSrc.pitch[0],
        lumaDst.width, lumaDst.height, (1 << bitDepth) - 1, retain);
    return err_to_rgy(cudaGetLastError());
}

template<typename Type, int shift, int components>
static RGY_ERR launch_bilateral(const RGYFrameInfo& dst, const RGYFrameInfo& src,
    const int width, const int height, const int bitDepth, const float sigma,
    const float *sigmaMap, const FilmGrainBlockMetric *detailMetrics,
    const int blocksX, const int blocksY, const int planeBlockSize, cudaStream_t stream) {
    const dim3 block(FGS_BILATERAL_BLOCK_X, FGS_BILATERAL_BLOCK_Y);
    const dim3 grid(divCeil(width, static_cast<int>(block.x)), divCeil(height, static_cast<int>(block.y)));
    kernel_fgs_bilateral<Type, shift, components><<<grid, block, 0, stream>>>(
        dst.ptr[0], dst.pitch[0], src.ptr[0], src.pitch[0], width, height, (1 << bitDepth) - 1, sigma,
        sigmaMap, detailMetrics, blocksX, blocksY, planeBlockSize);
    return err_to_rgy(cudaGetLastError());
}

template<typename Type, int shift, int components, bool chroma>
static RGY_ERR launch_model_stats(const RGYFrameInfo& src, const RGYFrameInfo& denoised,
    const int width, const int height, const int component, const RGYFrameInfo& lumaSrc,
    const RGYFrameInfo& lumaDenoised, const int blocksX, const int blocksY, const int bitDepth,
    const uint8_t *flatMask, const FilmGrainBlockMetric *metrics,
    FilmGrainGpuPlaneStats *stats, const bool modelFromSource, cudaStream_t stream) {
    const dim3 block(8, 8);
    const dim3 grid(blocksX, blocksY);
    kernel_fgs_model_stats<Type, shift, components, chroma><<<grid, block, 0, stream>>>(
        src.ptr[0], src.pitch[0], denoised.ptr[0], denoised.pitch[0], width, height, component,
        lumaSrc.ptr[0], lumaSrc.pitch[0], lumaDenoised.ptr[0], lumaDenoised.pitch[0],
        lumaSrc.width, lumaSrc.height, blocksX, bitDepth, flatMask, metrics, stats,
        modelFromSource);
    return err_to_rgy(cudaGetLastError());
}

template<typename Type, int shift>
static RGY_ERR launch_temporal_strength(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const RGYFrameInfo& base,
    const RGYFrameInfo& previousBase, const int blocksX, const int blocksY,
    const int bitDepth, const uint8_t *flatMask, const FilmGrainBlockMetric *metrics,
    FilmGrainGpuPlaneStats *stats, cudaStream_t stream) {
    const auto sourceY = getPlane(&source, RGY_PLANE_Y);
    const auto previousSourceY = getPlane(&previousSource, RGY_PLANE_Y);
    const auto baseY = getPlane(&base, RGY_PLANE_Y);
    const auto previousBaseY = getPlane(&previousBase, RGY_PLANE_Y);
    const dim3 block(8, 8);
    const dim3 grid(blocksX, blocksY);
    kernel_fgs_temporal_strength<Type, shift><<<grid, block, 0, stream>>>(
        sourceY.ptr[0], sourceY.pitch[0], previousSourceY.ptr[0], previousSourceY.pitch[0],
        baseY.ptr[0], baseY.pitch[0], previousBaseY.ptr[0], previousBaseY.pitch[0],
        sourceY.width, sourceY.height, blocksX, bitDepth, flatMask, metrics, stats);
    return err_to_rgy(cudaGetLastError());
}

static RGY_ERR collect_temporal_strength(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const RGYFrameInfo& base,
    const RGYFrameInfo& previousBase, const int blocksX, const int blocksY,
    const int bitDepth, const uint8_t *flatMask, const FilmGrainBlockMetric *metrics,
    FilmGrainGpuPlaneStats *stats, cudaStream_t stream) {
    switch (source.csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        return launch_temporal_strength<uint8_t, 0>(source, previousSource, base,
            previousBase, blocksX, blocksY, bitDepth, flatMask, metrics, stats, stream);
    case RGY_CSP_YV12_10:
        return launch_temporal_strength<uint16_t, 0>(source, previousSource, base,
            previousBase, blocksX, blocksY, bitDepth, flatMask, metrics, stats, stream);
    case RGY_CSP_P010:
        return launch_temporal_strength<uint16_t, 6>(source, previousSource, base,
            previousBase, blocksX, blocksY, bitDepth, flatMask, metrics, stats, stream);
    default:
        return RGY_ERR_UNSUPPORTED;
    }
}

template<typename Type, int shift>
static RGY_ERR launch_temporal_texture_stats(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const RGYFrameInfo& base,
    const RGYFrameInfo& previousBase, const int blocksX, const int blocksY,
    const uint8_t *temporalMask, FilmGrainTemporalArStats *stats,
    cudaStream_t stream) {
    const auto sourceY = getPlane(&source, RGY_PLANE_Y);
    const auto previousSourceY = getPlane(&previousSource, RGY_PLANE_Y);
    const auto baseY = getPlane(&base, RGY_PLANE_Y);
    const auto previousBaseY = getPlane(&previousBase, RGY_PLANE_Y);
    const dim3 block(8, 8);
    const dim3 grid(blocksX, blocksY);
    kernel_fgs_temporal_texture_stats<Type, shift><<<grid, block, 0, stream>>>(
        sourceY.ptr[0], sourceY.pitch[0], previousSourceY.ptr[0], previousSourceY.pitch[0],
        baseY.ptr[0], baseY.pitch[0], previousBaseY.ptr[0], previousBaseY.pitch[0],
        sourceY.width, sourceY.height, blocksX, temporalMask, stats);
    return err_to_rgy(cudaGetLastError());
}

static RGY_ERR collect_temporal_texture_stats(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const RGYFrameInfo& base,
    const RGYFrameInfo& previousBase, const int blocksX, const int blocksY,
    const uint8_t *temporalMask, FilmGrainTemporalArStats *stats,
    cudaStream_t stream) {
    switch (source.csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        return launch_temporal_texture_stats<uint8_t, 0>(source, previousSource,
            base, previousBase, blocksX, blocksY, temporalMask, stats, stream);
    case RGY_CSP_YV12_10:
        return launch_temporal_texture_stats<uint16_t, 0>(source, previousSource,
            base, previousBase, blocksX, blocksY, temporalMask, stats, stream);
    case RGY_CSP_P010:
        return launch_temporal_texture_stats<uint16_t, 6>(source, previousSource,
            base, previousBase, blocksX, blocksY, temporalMask, stats, stream);
    default:
        return RGY_ERR_UNSUPPORTED;
    }
}

template<typename Type, int shift, int components>
static RGY_ERR launch_temporal_chroma_plane(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const RGYFrameInfo& base,
    const RGYFrameInfo& previousBase, const int width, const int height,
    const int component, const int blocksX, const int blocksY, const int bitDepth,
    const uint8_t *temporalMask, const FilmGrainBlockMetric *metrics,
    FilmGrainGpuPlaneStats *stats, cudaStream_t stream) {
    const dim3 block(8, 8);
    const dim3 grid(blocksX, blocksY);
    kernel_fgs_temporal_chroma_strength<Type, shift, components><<<grid, block, 0, stream>>>(
        source.ptr[0], source.pitch[0], previousSource.ptr[0], previousSource.pitch[0],
        base.ptr[0], base.pitch[0], previousBase.ptr[0], previousBase.pitch[0],
        width, height, component, blocksX, bitDepth, temporalMask, metrics, stats);
    return err_to_rgy(cudaGetLastError());
}

template<typename Type, int shift>
static RGY_ERR launch_temporal_static_mask(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const int blocksX, const int blocksY,
    const uint8_t *flatMask, uint8_t *temporalMask,
    const FilmGrainBlockMetric *metrics, cudaStream_t stream) {
    auto cudaerr = cudaMemsetAsync(
        temporalMask, 0, static_cast<size_t>(blocksX) * blocksY, stream);
    if (cudaerr != cudaSuccess) return err_to_rgy(cudaerr);

    const auto sourceY = getPlane(&source, RGY_PLANE_Y);
    const auto previousSourceY = getPlane(&previousSource, RGY_PLANE_Y);
    const dim3 block(8, 8);
    const dim3 grid(blocksX, blocksY);
    kernel_fgs_temporal_chroma_mask<Type, shift><<<grid, block, 0, stream>>>(
        sourceY.ptr[0], sourceY.pitch[0], previousSourceY.ptr[0], previousSourceY.pitch[0],
        sourceY.width, sourceY.height, blocksX, flatMask, metrics, temporalMask);
    return err_to_rgy(cudaGetLastError());
}

static RGY_ERR collect_temporal_static_mask(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const int blocksX, const int blocksY,
    const uint8_t *flatMask, uint8_t *temporalMask,
    const FilmGrainBlockMetric *metrics, cudaStream_t stream) {
    switch (source.csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        return launch_temporal_static_mask<uint8_t, 0>(
            source, previousSource, blocksX, blocksY,
            flatMask, temporalMask, metrics, stream);
    case RGY_CSP_YV12_10:
        return launch_temporal_static_mask<uint16_t, 0>(
            source, previousSource, blocksX, blocksY,
            flatMask, temporalMask, metrics, stream);
    case RGY_CSP_P010:
        return launch_temporal_static_mask<uint16_t, 6>(
            source, previousSource, blocksX, blocksY,
            flatMask, temporalMask, metrics, stream);
    default:
        return RGY_ERR_UNSUPPORTED;
    }
}

template<typename Type, int shift>
static RGY_ERR launch_temporal_chroma_strength(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const RGYFrameInfo& base,
    const RGYFrameInfo& previousBase, const int blocksX, const int blocksY,
    const int bitDepth, const uint8_t *flatMask, uint8_t *temporalMask,
    const FilmGrainBlockMetric *metrics, FilmGrainGpuStats *stats,
    cudaStream_t stream) {
    auto sts = launch_temporal_static_mask<Type, shift>(
        source, previousSource, blocksX, blocksY,
        flatMask, temporalMask, metrics, stream);
    if (sts != RGY_ERR_NONE) return sts;

    const bool semiPlanar = source.csp == RGY_CSP_NV12 || source.csp == RGY_CSP_P010;
    if (semiPlanar) {
        const auto sourceUV = getPlane(&source, RGY_PLANE_U);
        const auto previousSourceUV = getPlane(&previousSource, RGY_PLANE_U);
        const auto baseUV = getPlane(&base, RGY_PLANE_U);
        const auto previousBaseUV = getPlane(&previousBase, RGY_PLANE_U);
        for (int component = 0; component < 2; ++component) {
            sts = launch_temporal_chroma_plane<Type, shift, 2>(
                sourceUV, previousSourceUV, baseUV, previousBaseUV,
                source.width / 2, source.height / 2, component,
                blocksX, blocksY, bitDepth, temporalMask, metrics,
                &stats->plane[component + 1], stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
    } else {
        for (int plane = RGY_PLANE_U; plane <= RGY_PLANE_V; ++plane) {
            const auto sourceC = getPlane(&source, static_cast<RGY_PLANE>(plane));
            const auto previousSourceC = getPlane(
                &previousSource, static_cast<RGY_PLANE>(plane));
            const auto baseC = getPlane(&base, static_cast<RGY_PLANE>(plane));
            const auto previousBaseC = getPlane(
                &previousBase, static_cast<RGY_PLANE>(plane));
            sts = launch_temporal_chroma_plane<Type, shift, 1>(
                sourceC, previousSourceC, baseC, previousBaseC,
                sourceC.width, sourceC.height, 0, blocksX, blocksY, bitDepth,
                temporalMask, metrics, &stats->plane[plane], stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
    }
    return RGY_ERR_NONE;
}

static RGY_ERR collect_temporal_chroma_strength(const RGYFrameInfo& source,
    const RGYFrameInfo& previousSource, const RGYFrameInfo& base,
    const RGYFrameInfo& previousBase, const int blocksX, const int blocksY, const int bitDepth,
    const uint8_t *flatMask, uint8_t *temporalMask,
    const FilmGrainBlockMetric *metrics, FilmGrainGpuStats *stats,
    cudaStream_t stream) {
    switch (source.csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        return launch_temporal_chroma_strength<uint8_t, 0>(source, previousSource, base,
            previousBase, blocksX, blocksY, bitDepth, flatMask,
            temporalMask, metrics, stats, stream);
    case RGY_CSP_YV12_10:
        return launch_temporal_chroma_strength<uint16_t, 0>(source, previousSource, base,
            previousBase, blocksX, blocksY, bitDepth, flatMask,
            temporalMask, metrics, stats, stream);
    case RGY_CSP_P010:
        return launch_temporal_chroma_strength<uint16_t, 6>(source, previousSource, base,
            previousBase, blocksX, blocksY, bitDepth, flatMask,
            temporalMask, metrics, stats, stream);
    default:
        return RGY_ERR_UNSUPPORTED;
    }
}

} // namespace

struct NVEncFilterFilmGrain::AnalyzerState {
    std::deque<FilmGrainHostStats> history;
    std::vector<float> previousBlockMeans;
    float stableNoise;
    float autoRetain;
    int64_t lastTimestamp;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 lastParams;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 pendingParams;
    bool lastParamsValid;
    bool lastParamsFallback;
    bool pendingParamsValid;
    bool pendingParamsFallback;
    bool modelWindowSettled;
    int pendingStreak;
    int framesSinceModelUpdate;
    int heldStreak;

    AnalyzerState() : history(), previousBlockMeans(), stableNoise(0.0f), autoRetain(0.0f),
        lastTimestamp(std::numeric_limits<int64_t>::min()), lastParams(), pendingParams(),
        lastParamsValid(false), lastParamsFallback(false),
        pendingParamsValid(false), pendingParamsFallback(false), modelWindowSettled(false),
        pendingStreak(0), framesSinceModelUpdate(0), heldStreak(0) {}
    void advanceModelAge() {
        if (framesSinceModelUpdate < std::numeric_limits<int>::max()) ++framesSinceModelUpdate;
    }
    void clear() {
        history.clear();
        previousBlockMeans.clear();
        stableNoise = 0.0f;
        autoRetain = 0.0f;
        lastTimestamp = std::numeric_limits<int64_t>::min();
        std::memset(&lastParams, 0, sizeof(lastParams));
        std::memset(&pendingParams, 0, sizeof(pendingParams));
        lastParamsValid = false;
        lastParamsFallback = false;
        pendingParamsValid = false;
        pendingParamsFallback = false;
        modelWindowSettled = false;
        pendingStreak = 0;
        framesSinceModelUpdate = 0;
        heldStreak = 0;
    }
};

NVEncFilmGrainAnalyzerConfig::NVEncFilmGrainAnalyzerConfig() :
    enable(true), analyzeChroma(true), clipToRestrictedRange(true),
    denoiser(FGS_DENOISE_FFT3D), fft3dTemporal(1), motionRefs(2), residualRetain(0.0f),
    modelFromSource(false), denoiseLevel(0.0f),
    denoisePasses(2), modelWindow(8), minModelFrames(1), minFlatBlocks(8),
    minFlatFraction(0.02f), minNoiseLevel(0.5f), maxNoiseLevel(50.0f) {
}

bool NVEncFilmGrainAnalyzerConfig::operator==(const NVEncFilmGrainAnalyzerConfig& other) const {
    return enable == other.enable
        && analyzeChroma == other.analyzeChroma
        && clipToRestrictedRange == other.clipToRestrictedRange
        && denoiser == other.denoiser
        && fft3dTemporal == other.fft3dTemporal
        && motionRefs == other.motionRefs
        && residualRetain == other.residualRetain
        && modelFromSource == other.modelFromSource
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
    return strsprintf(_T("film-grain: denoise=%s%s, denoiser=%s, chroma=%s, window=%d%s%s%s"),
        denoiseLevel <= 0.0f ? _T("auto") : _T(""),
        denoiseLevel <= 0.0f ? _T("") : strsprintf(_T("%.2f"), denoiseLevel).c_str(),
        denoiser == FGS_DENOISE_FFT3D
            ? (fft3dTemporal >= 2 ? _T("fft3d(bt2)") : _T("fft3d"))
            : (denoiser == FGS_DENOISE_MOTION ? _T("motion") : _T("bilateral")),
        analyzeChroma ? _T("on") : _T("off"), modelWindow,
        denoiser == FGS_DENOISE_MOTION ? strsprintf(_T(", motion-refs=%d"), motionRefs).c_str() : _T(""),
        residualRetain < 0.0f ? _T(", retain=auto")
            : (residualRetain > 0.0f ? strsprintf(_T(", retain=%.2f"), residualRetain).c_str() : _T("")),
        modelFromSource ? _T(", modelsrc=on") : _T(""));
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

NVEncFilterParamFilmGrain::NVEncFilterParamFilmGrain() : filmGrain(), leakTargetQuality(-1.0f) {
}

NVEncFilterParamFilmGrain::~NVEncFilterParamFilmGrain() {
}

tstring NVEncFilterParamFilmGrain::print() const {
    return filmGrain.print() + (leakTargetQuality >= 0.0f
        ? strsprintf(_T(", leak-qvbr=%.2f"), leakTargetQuality) : tstring());
}

NVEncFilterFilmGrain::NVEncFilterFilmGrain() :
    m_denoiseWork(), m_previousSource(), m_previousBase(),
    m_fft3d(), m_fft3dParam(), m_fft3dSigma(-1.0f),
    m_motionDegrain(), m_motionDegrainParam(), m_motionFinishMode(MotionFinishMode::Uniform),
    m_chromaLeakMode(ChromaLeakMode::Off), m_lumaLeakLocal(false), m_sourceTemporalMask(false),
    m_textureLeakClosure(false),
    m_blockMetrics(), m_blockMask(), m_sigmaMap(), m_strengthLut(), m_sceneCounts(), m_modelStats(),
    m_fallbackModelStats(),
    m_tableOutPath(), m_tableTimebase(), m_tableFrameDuration10MHz(0), m_tableEntries(), m_tableWritten(false),
    m_temporalLeakValid(false),
    m_state(std::make_unique<AnalyzerState>()), m_blocksX(0), m_blocksY(0) {
    m_name = _T("film-grain");
    m_pathThrough = FILTER_PATHTHROUGH_NONE;
}

NVEncFilterFilmGrain::~NVEncFilterFilmGrain() {
    close();
}

void NVEncFilterFilmGrain::resetTemporalState() {
    if (m_state) m_state->clear();
    m_temporalLeakValid = false;
    if (m_fft3d) m_fft3d->resetTemporalState();
    if (m_motionDegrain) m_motionDegrain->resetTemporalState();
}

namespace {

// includeLuma selects between an all-plane pass and a chroma-only pass.
// detailMetrics optionally fades luma refinement around structured detail;
// chroma is always filtered because the metrics describe luma blocks.
template<typename Type, int shift>
static RGY_ERR denoise_frame_typed(RGYFrameInfo *dst, RGYFrameInfo *work, const RGYFrameInfo *src,
    const bool chroma, const bool includeLuma, const int passes, const int bitDepth, const float sigma,
    const float *sigmaMap, const FilmGrainBlockMetric *detailMetrics,
    const int blocksX, const int blocksY, cudaStream_t stream) {
    for (int pass = 0; pass < passes; ++pass) {
        const RGYFrameInfo *passSrc = pass == 0 ? src : work;
        RGYFrameInfo *passDst = pass + 1 == passes ? dst : work;
        if (includeLuma) {
            auto srcY = getPlane(passSrc, RGY_PLANE_Y);
            auto dstY = getPlane(passDst, RGY_PLANE_Y);
            auto sts = launch_bilateral<Type, shift, 1>(dstY, srcY, srcY.width, srcY.height, bitDepth, sigma,
                sigmaMap, detailMetrics, blocksX, blocksY, FGS_BLOCK_SIZE, stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
        if (!chroma) continue;
        const bool semiPlanar = src->csp == RGY_CSP_NV12 || src->csp == RGY_CSP_P010;
        if (semiPlanar) {
            auto srcUV = getPlane(passSrc, RGY_PLANE_U);
            auto dstUV = getPlane(passDst, RGY_PLANE_U);
            auto sts = launch_bilateral<Type, shift, 2>(dstUV, srcUV, src->width / 2, src->height / 2, bitDepth, sigma,
                sigmaMap, nullptr, blocksX, blocksY, FGS_BLOCK_SIZE / 2, stream);
            if (sts != RGY_ERR_NONE) return sts;
        } else {
            for (int plane = RGY_PLANE_U; plane <= RGY_PLANE_V; ++plane) {
                auto srcC = getPlane(passSrc, static_cast<RGY_PLANE>(plane));
                auto dstC = getPlane(passDst, static_cast<RGY_PLANE>(plane));
                auto sts = launch_bilateral<Type, shift, 1>(dstC, srcC, srcC.width, srcC.height, bitDepth, sigma,
                    sigmaMap, nullptr, blocksX, blocksY, FGS_BLOCK_SIZE / 2, stream);
                if (sts != RGY_ERR_NONE) return sts;
            }
        }
    }
    return RGY_ERR_NONE;
}

static RGY_ERR denoise_frame(RGYFrameInfo *dst, RGYFrameInfo *work, const RGYFrameInfo *src,
    const bool chroma, const bool includeLuma, const int passes, const int bitDepth, const float sigma,
    const float *sigmaMap, const FilmGrainBlockMetric *detailMetrics,
    const int blocksX, const int blocksY, cudaStream_t stream) {
    switch (src->csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        return denoise_frame_typed<uint8_t, 0>(dst, work, src, chroma, includeLuma, passes, bitDepth, sigma, sigmaMap, detailMetrics, blocksX, blocksY, stream);
    case RGY_CSP_YV12_10:
        return denoise_frame_typed<uint16_t, 0>(dst, work, src, chroma, includeLuma, passes, bitDepth, sigma, sigmaMap, detailMetrics, blocksX, blocksY, stream);
    case RGY_CSP_P010:
        return denoise_frame_typed<uint16_t, 6>(dst, work, src, chroma, includeLuma, passes, bitDepth, sigma, sigmaMap, detailMetrics, blocksX, blocksY, stream);
    default:
        return RGY_ERR_UNSUPPORTED;
    }
}

template<typename Type, int shift>
static RGY_ERR collect_model_stats_typed(const RGYFrameInfo *src, const RGYFrameInfo *denoised,
    const bool chroma, const int blocksX, const int blocksY, const int bitDepth,
    const uint8_t *lumaMask, const uint8_t *chromaMask,
    const FilmGrainBlockMetric *metrics, FilmGrainGpuStats *stats, const bool modelFromSource,
    cudaStream_t stream) {
    const auto srcY = getPlane(src, RGY_PLANE_Y);
    const auto dstY = getPlane(denoised, RGY_PLANE_Y);
    auto sts = launch_model_stats<Type, shift, 1, false>(srcY, dstY, srcY.width, srcY.height, 0,
        srcY, dstY, blocksX, blocksY, bitDepth, lumaMask, metrics, &stats->plane[0],
        modelFromSource, stream);
    if (sts != RGY_ERR_NONE || !chroma) return sts;
    const bool semiPlanar = src->csp == RGY_CSP_NV12 || src->csp == RGY_CSP_P010;
    if (semiPlanar) {
        const auto srcUV = getPlane(src, RGY_PLANE_U);
        const auto dstUV = getPlane(denoised, RGY_PLANE_U);
        for (int component = 0; component < 2; ++component) {
            sts = launch_model_stats<Type, shift, 2, true>(srcUV, dstUV, src->width / 2, src->height / 2,
                component, srcY, dstY, blocksX, blocksY, bitDepth, chromaMask, metrics,
                &stats->plane[component + 1], modelFromSource, stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
    } else {
        for (int plane = RGY_PLANE_U; plane <= RGY_PLANE_V; ++plane) {
            const auto srcC = getPlane(src, static_cast<RGY_PLANE>(plane));
            const auto dstC = getPlane(denoised, static_cast<RGY_PLANE>(plane));
            sts = launch_model_stats<Type, shift, 1, true>(srcC, dstC, srcC.width, srcC.height, 0,
                srcY, dstY, blocksX, blocksY, bitDepth, chromaMask, metrics, &stats->plane[plane],
                modelFromSource, stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
    }
    return RGY_ERR_NONE;
}

static RGY_ERR collect_model_stats(const RGYFrameInfo *src, const RGYFrameInfo *denoised,
    const bool chroma, const int blocksX, const int blocksY, const int bitDepth,
    const uint8_t *lumaMask, const uint8_t *chromaMask,
    const FilmGrainBlockMetric *metrics, FilmGrainGpuStats *stats, const bool modelFromSource,
    cudaStream_t stream) {
    switch (src->csp) {
    case RGY_CSP_NV12:
    case RGY_CSP_YV12:
        return collect_model_stats_typed<uint8_t, 0>(src, denoised, chroma, blocksX, blocksY, bitDepth, lumaMask, chromaMask, metrics, stats, modelFromSource, stream);
    case RGY_CSP_YV12_10:
        return collect_model_stats_typed<uint16_t, 0>(src, denoised, chroma, blocksX, blocksY, bitDepth, lumaMask, chromaMask, metrics, stats, modelFromSource, stream);
    case RGY_CSP_P010:
        return collect_model_stats_typed<uint16_t, 6>(src, denoised, chroma, blocksX, blocksY, bitDepth, lumaMask, chromaMask, metrics, stats, modelFromSource, stream);
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
    config.motionRefs = clamp(config.motionRefs, 1, 2);
    config.residualRetain = config.residualRetain < 0.0f
        ? -1.0f : clamp(config.residualRetain, 0.0f, 0.9f);
    if (!config.modelFromSource || config.residualRetain != 0.0f
        || prm->leakTargetQuality < FGS_LEAK_QVBR_MIN
        || prm->leakTargetQuality > FGS_LEAK_QVBR_MAX) {
        prm->leakTargetQuality = -1.0f;
    }
    m_chromaLeakMode = ChromaLeakMode::Off;
    if (const auto value = std::getenv("NVENC_FGS_TEST_CHROMA_LEAK"); value && value[0] != '\0') {
        if (!config.modelFromSource || !config.analyzeChroma || prm->leakTargetQuality < 0.0f) {
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: ignoring NVENC_FGS_TEST_CHROMA_LEAK=%s (requires modelsrc=on, chroma analysis, QVBR 25..39, and retain=0).\n"),
                char_to_tstring(value).c_str());
        } else if (strcmp(value, "global") == 0) {
            m_chromaLeakMode = ChromaLeakMode::Global;
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: applying test-only global temporal chroma leak closure.\n"));
        } else if (strcmp(value, "local") == 0) {
            m_chromaLeakMode = ChromaLeakMode::Local;
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: applying test-only per-bin temporal chroma leak closure.\n"));
        } else if (strcmp(value, "independent") == 0) {
            m_chromaLeakMode = ChromaLeakMode::Independent;
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: applying test-only per-plane chroma amplitude transfer.\n"));
        } else {
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: ignoring invalid NVENC_FGS_TEST_CHROMA_LEAK=%s (expected global, local, or independent).\n"),
                char_to_tstring(value).c_str());
        }
    }
    m_lumaLeakLocal = false;
    if (const auto value = std::getenv("NVENC_FGS_TEST_LUMA_LEAK"); value && value[0] != '\0') {
        if (strcmp(value, "local") != 0) {
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: ignoring invalid NVENC_FGS_TEST_LUMA_LEAK=%s (expected local).\n"),
                char_to_tstring(value).c_str());
        } else if (!config.modelFromSource || prm->leakTargetQuality < 0.0f) {
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: ignoring NVENC_FGS_TEST_LUMA_LEAK=local (requires modelsrc=on, QVBR 25..39, and retain=0).\n"));
        } else {
            m_lumaLeakLocal = true;
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: applying test-only per-bin temporal luma leak closure.\n"));
        }
    }
    m_sourceTemporalMask = false;
    if (const auto value = std::getenv("NVENC_FGS_TEST_SOURCE_STATIC");
        value && value[0] != '\0') {
        if (strcmp(value, "on") != 0) {
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: ignoring invalid NVENC_FGS_TEST_SOURCE_STATIC=%s (expected on).\n"),
                char_to_tstring(value).c_str());
        } else if (!config.modelFromSource || prm->leakTargetQuality < 0.0f) {
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: ignoring NVENC_FGS_TEST_SOURCE_STATIC=on (requires modelsrc=on, QVBR 25..39, and retain=0).\n"));
        } else {
            m_sourceTemporalMask = true;
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: fitting the test-only source model from temporally static blocks.\n"));
        }
    }
    m_textureLeakClosure = false;
    if (const auto value = std::getenv("NVENC_FGS_TEST_TEXTURE_LEAK");
        value && value[0] != '\0') {
        if (strcmp(value, "on") != 0) {
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: ignoring invalid NVENC_FGS_TEST_TEXTURE_LEAK=%s (expected on).\n"),
                char_to_tstring(value).c_str());
        } else if (!config.modelFromSource || prm->leakTargetQuality < 0.0f
            || !m_sourceTemporalMask) {
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: ignoring NVENC_FGS_TEST_TEXTURE_LEAK=on (requires modelsrc=on, QVBR 25..39, retain=0, and NVENC_FGS_TEST_SOURCE_STATIC=on).\n"));
        } else {
            m_textureLeakClosure = true;
            AddMessage(RGY_LOG_WARN,
                _T("film-grain: applying test-only 3/4 temporal luma covariance closure.\n"));
        }
    }

    auto sts = AllocFrameBuf(prm->frameOut, 2);
    if (sts != RGY_ERR_NONE) return sts;
    for (int plane = 0; plane < RGY_CSP_PLANES[prm->frameOut.csp]; ++plane) {
        prm->frameOut.pitch[plane] = m_frameBuf[0]->frame.pitch[plane];
    }
    m_denoiseWork = std::make_unique<CUFrameBuf>(prm->frameOut);
    m_denoiseWork->releasePtr();
    if ((sts = m_denoiseWork->alloc()) != RGY_ERR_NONE) return sts;
    if (prm->leakTargetQuality >= 0.0f) {
        m_previousSource = std::make_unique<CUFrameBuf>(prm->frameOut);
        m_previousBase = std::make_unique<CUFrameBuf>(prm->frameOut);
        m_previousSource->releasePtr();
        m_previousBase->releasePtr();
        if ((sts = m_previousSource->alloc()) != RGY_ERR_NONE
            || (sts = m_previousBase->alloc()) != RGY_ERR_NONE) return sts;
    } else {
        m_previousSource.reset();
        m_previousBase.reset();
    }
    m_temporalLeakValid = false;

    m_blocksX = divCeil(prm->frameIn.width, FGS_BLOCK_SIZE);
    m_blocksY = divCeil(prm->frameIn.height, FGS_BLOCK_SIZE);
    m_blockMetrics = std::make_unique<CUMemBufPair>(
        static_cast<size_t>(m_blocksX) * m_blocksY * sizeof(FilmGrainBlockMetric));
    m_blockMask = std::make_unique<CUMemBufPair>(static_cast<size_t>(m_blocksX) * m_blocksY);
    m_sigmaMap = std::make_unique<CUMemBufPair>(static_cast<size_t>(m_blocksX) * m_blocksY * sizeof(float));
    m_strengthLut = std::make_unique<CUMemBufPair>(FGS_STRENGTH_LUT_SIZE * sizeof(float));
    m_sceneCounts = std::make_unique<CUMemBufPair>(8 * sizeof(uint32_t));
    m_modelStats = std::make_unique<CUMemBufPair>(sizeof(FilmGrainGpuStats));
    m_fallbackModelStats.reset();
    if ((sts = m_blockMetrics->alloc()) != RGY_ERR_NONE
        || (sts = m_blockMask->alloc()) != RGY_ERR_NONE
        || (sts = m_sigmaMap->alloc()) != RGY_ERR_NONE
        || (sts = m_strengthLut->alloc()) != RGY_ERR_NONE
        || (sts = m_sceneCounts->alloc()) != RGY_ERR_NONE
        || (sts = m_modelStats->alloc()) != RGY_ERR_NONE) {
        AddMessage(RGY_LOG_ERROR, _T("Failed to allocate film-grain analysis buffers: %s.\n"), get_err_mes(sts));
        return sts;
    }
    if (config.modelFromSource) {
        m_fallbackModelStats = std::make_unique<CUMemBufPair>(sizeof(FilmGrainGpuStats));
        if ((sts = m_fallbackModelStats->alloc()) != RGY_ERR_NONE) {
            AddMessage(RGY_LOG_ERROR, _T("Failed to allocate film-grain fallback statistics: %s.\n"), get_err_mes(sts));
            return sts;
        }
    }
    config.fft3dTemporal = clamp(config.fft3dTemporal, 1, 2);
    m_motionFinishMode = MotionFinishMode::Uniform;
    if (config.denoiser == FGS_DENOISE_FFT3D) {
        m_motionDegrain.reset();
        m_motionDegrainParam.reset();
        m_fft3dParam = std::make_shared<NVEncFilterParamDenoiseFFT3D>();
        m_fft3dParam->frameIn = prm->frameIn;
        m_fft3dParam->frameOut = prm->frameOut;
        m_fft3dParam->baseFps = prm->baseFps;
        m_fft3dParam->bOutOverwrite = false;
        m_fft3dParam->compute_capability = prm->compute_capability;
        // This filter runs with the encoder csp (NV12/P010); the FFT3D chroma
        // path needs planar U/V, so the child denoises luma only and chroma is
        // handled by the bilateral pass.
        m_fft3dParam->processChroma = false;
        auto& fft3d = m_fft3dParam->fft3d;
        fft3d.enable = true;
        fft3d.sigma = std::max(1.0f, config.denoiseLevel); // reprogrammed from the measured noise per frame
        fft3d.amount = 1.0f;
        fft3d.method = 0;
        fft3d.temporal = 0;
        fft3d.bt = config.fft3dTemporal;
        fft3d.degrid = 0.0f;
        fft3d.signorm = true; // sigma in real 8-bit noise-std units
        m_fft3d = std::make_unique<NVEncFilterDenoiseFFT3D>();
        if ((sts = m_fft3d->init(m_fft3dParam, pPrintMes)) != RGY_ERR_NONE) {
            AddMessage(RGY_LOG_ERROR, _T("Failed to init FFT3D denoiser for film-grain: %s.\n"), get_err_mes(sts));
            return sts;
        }
        m_fft3dSigma = fft3d.sigma;
    } else if (config.denoiser == FGS_DENOISE_MOTION) {
        m_fft3d.reset();
        m_fft3dParam.reset();
        m_fft3dSigma = -1.0f;
        m_motionDegrainParam = std::make_shared<NVEncFilterParamDegrain>();
        m_motionDegrainParam->frameIn = prm->frameIn;
        m_motionDegrainParam->frameOut = prm->frameOut;
        m_motionDegrainParam->baseFps = prm->baseFps;
        m_motionDegrainParam->bOutOverwrite = false;
        m_motionDegrainParam->attachAnalysisData = false;
        // Test-only isolation of the spatial luma pass which follows motion
        // compensation.  Keep chroma on in every arm: the motion child only
        // handles luma, so disabling the whole pass would change two
        // independent questions at once.  The default remains byte-stable.
        if (const auto value = std::getenv("NVENC_FGS_TEST_MOTION_FINISH"); value && value[0] != '\0') {
            if (strcmp(value, "detail") == 0) {
                m_motionFinishMode = MotionFinishMode::DetailAware;
                AddMessage(RGY_LOG_WARN,
                    _T("film-grain: applying test-only detail-aware motion luma finish.\n"));
            } else if (strcmp(value, "off") == 0) {
                m_motionFinishMode = MotionFinishMode::ChromaOnly;
                AddMessage(RGY_LOG_WARN,
                    _T("film-grain: applying test-only chroma-only motion finish.\n"));
            } else {
                AddMessage(RGY_LOG_WARN,
                    _T("film-grain: ignoring invalid NVENC_FGS_TEST_MOTION_FINISH=%s (expected detail or off).\n"),
                    char_to_tstring(value).c_str());
            }
        }
        // Deliberately environment-only while the centred scheduler is under
        // corpus evaluation; do not expose an unvalidated production option.
        bool testCenteredPaired = false;
        bool testMatchedTemporalExposure = false;
        bool testRobustTemporalMedian = false;
        if (const auto value = std::getenv("NVENC_FGS_TEST_MOTION_CENTERED"); value && value[0] != '\0') {
            if ((strcmp(value, "paired") == 0
                    || strcmp(value, "paired-balanced") == 0
                    || strcmp(value, "paired-balanced-median") == 0)
                && config.motionRefs == 1) {
                testCenteredPaired = true;
                testMatchedTemporalExposure = strcmp(value, "paired") != 0;
                testRobustTemporalMedian = strcmp(value, "paired-balanced-median") == 0;
                if (testRobustTemporalMedian) {
                    AddMessage(RGY_LOG_WARN,
                        _T("film-grain: applying test-only centered motion with paired confidence, causal-matched exposure, and robust temporal median.\n"));
                } else {
                    AddMessage(RGY_LOG_WARN, testMatchedTemporalExposure
                        ? _T("film-grain: applying test-only centered motion with paired confidence and causal-matched temporal exposure.\n")
                        : _T("film-grain: applying test-only centered motion with paired confidence.\n"));
                }
            } else {
                AddMessage(RGY_LOG_WARN,
                    _T("film-grain: ignoring NVENC_FGS_TEST_MOTION_CENTERED=%s (expected paired, paired-balanced, or paired-balanced-median with motion-refs=1).\n"),
                    char_to_tstring(value).c_str());
            }
        }
        m_motionDegrainParam->causal = !testCenteredPaired;
        m_motionDegrainParam->pairedTemporalConfidence = testCenteredPaired;
        m_motionDegrainParam->matchedTemporalExposure = testMatchedTemporalExposure;
        m_motionDegrainParam->robustTemporalMedian = testRobustTemporalMedian;
        auto& degrain = m_motionDegrainParam->degrain;
        degrain.enable = true;
        degrain.mode = VppDegrainMode::Degrain;
        degrain.stage = VppDegrainStage::TR1;
        degrain.delta = testCenteredPaired ? 1 : config.motionRefs;
        degrain.levels = 2;
        degrain.blksize = 32;
        degrain.overlap = 16;
        // General-purpose degrain defaults are intentionally conservative
        // (thsad=640).  Grain extraction needs the temporally random component
        // to participate in the blend, so the render threshold is raised.
        degrain.thsad = 4000;
        // Test-only threshold sweep.  This is intentionally not a public
        // option: once the real-film response is measured, replace the fixed
        // policy in code and remove the override before production.
        if (const auto value = std::getenv("NVENC_FGS_TEST_MOTION_THSAD"); value && value[0] != '\0') {
            char *end = nullptr;
            const auto parsed = std::strtol(value, &end, 10);
            if (end && end[0] == '\0' && parsed > 0 && parsed <= 65535) {
                degrain.thsad = static_cast<int>(parsed);
                AddMessage(RGY_LOG_WARN, _T("film-grain: applying test-only motion thsad=%d override.\n"), degrain.thsad);
            } else {
                AddMessage(RGY_LOG_WARN, _T("film-grain: ignoring invalid NVENC_FGS_TEST_MOTION_THSAD=%s.\n"), char_to_tstring(value).c_str());
            }
        }
        // The scene-change threshold must stay SEPARATE and far lower: reusing
        // the render value here disabled scene gating entirely and blended
        // straight across hard cuts (the Taxi Driver f388 ghost).  It cannot
        // be a constant either -- grain-only SAD is ~1.6*sigma*blockArea, so a
        // fixed low value scene-disables every frame on heavy grain.  Start at
        // the library default; run_filter retunes it each frame from the
        // measured noise level (the degrainer re-reads the shared param).
        degrain.thscd1 = FILTER_DEFAULT_DEGRAIN_THSCD1;
        // Keep the final encoder-surface filter one-in/one-out.  Direction 2
        // retains only already available reference frames; a later pipeline
        // stage can enable bidirectional lookahead without changing O/B/R.
        degrain.useFlag = testCenteredPaired ? 0 : 2;
        // Encoder surfaces are semi-planar.  The motion filter handles luma;
        // chroma remains in the retained source and receives the existing
        // edge-aware local denoise below before residual modelling.
        degrain.chroma = false;
        m_motionDegrain = std::make_unique<NVEncFilterDegrain>();
        if ((sts = m_motionDegrain->init(m_motionDegrainParam, pPrintMes)) != RGY_ERR_NONE) {
            AddMessage(RGY_LOG_ERROR, _T("Failed to init motion degrain for film-grain: %s.\n"), get_err_mes(sts));
            return sts;
        }
    } else {
        m_fft3d.reset();
        m_fft3dParam.reset();
        m_fft3dSigma = -1.0f;
        m_motionDegrain.reset();
        m_motionDegrainParam.reset();
    }
    m_tableOutPath = prm->tableOutPath;
    m_tableTimebase = prm->timebase.is_valid() ? prm->timebase
        : rgy_rational<int>(prm->baseFps.d(), prm->baseFps.n());
    m_tableFrameDuration10MHz = std::max<int64_t>(1,
        rational_rescale(1, rgy_rational<int>(prm->baseFps.d(), prm->baseFps.n()), rgy_rational<int>(1, 10000000)));
    m_tableEntries.clear();
    m_tableWritten = false;
    if (!m_state) m_state = std::make_unique<AnalyzerState>();
    m_state->clear();
    setFilterInfo(prm->print());
    m_param = prm;
    return RGY_ERR_NONE;
}

void NVEncFilterFilmGrain::recordTableEntry(const int64_t timestamp, const int64_t duration,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params) {
    const auto to10MHz = rgy_rational<int>(1, 10000000);
    const int64_t start = rational_rescale(timestamp, m_tableTimebase, to10MHz);
    int64_t end = (duration > 0)
        ? rational_rescale(timestamp + duration, m_tableTimebase, to10MHz)
        : start + m_tableFrameDuration10MHz;
    if (end <= start) end = start + 1;
    if (!m_tableEntries.empty()) {
        auto& last = m_tableEntries.back();
        if (start <= last.startTime) return; // out-of-order timestamp; keep the table monotonic
        if (start <= last.endTime && std::memcmp(&last.params, &params, sizeof(params)) == 0) {
            last.endTime = std::max(last.endTime, end);
            return;
        }
        last.endTime = std::min(last.endTime, start); // guard rounding overlap between entries
    }
    NVEncFilmGrainTableEntry entry = {};
    entry.startTime = start;
    entry.endTime = end;
    entry.randomSeed = static_cast<uint16_t>((m_tableEntries.size() * 7919u + 12345u) & 0xffffu);
    entry.sourceUpdateParameters = true;
    entry.params = params;
    m_tableEntries.push_back(entry);
}

void NVEncFilterFilmGrain::writeTableFile() {
    if (m_tableOutPath.empty() || m_tableWritten) return;
    m_tableWritten = true;
    if (m_tableEntries.empty()) {
        AddMessage(RGY_LOG_WARN, _T("film-grain: no grain was detected, table not written: %s\n"), m_tableOutPath.c_str());
        return;
    }
    tstring error;
    if (nvenc_film_grain_table_write(m_tableOutPath, m_tableEntries, error)) {
        AddMessage(RGY_LOG_INFO, _T("film-grain: wrote grain table (%d entries): %s\n"),
            static_cast<int>(m_tableEntries.size()), m_tableOutPath.c_str());
    } else {
        AddMessage(RGY_LOG_ERROR, _T("film-grain: %s\n"), error.c_str());
    }
}

RGY_ERR NVEncFilterFilmGrain::run_filter(const RGYFrameInfo *pInputFrame, RGYFrameInfo **ppOutputFrames,
    int *pOutputFrameNum, cudaStream_t stream) {
    if (!pOutputFrameNum || !ppOutputFrames) return RGY_ERR_INVALID_PARAM;
    auto prm = std::dynamic_pointer_cast<NVEncFilterParamFilmGrain>(m_param);
    if (!prm) return RGY_ERR_INVALID_PARAM;

    auto *requestedOutput = ppOutputFrames[0];
    *pOutputFrameNum = 0;
    ppOutputFrames[0] = nullptr;
    const RGYFrameInfo *source = pInputFrame;
    const RGYFrameInfo *cleanBase = pInputFrame;
    RGYFrameInfo *motionOutput[1] = { nullptr };
    int motionOutputCount = 0;
    auto sts = RGY_ERR_NONE;
    if (prm->filmGrain.denoiser == FGS_DENOISE_MOTION) {
        if (!m_motionDegrain) return RGY_ERR_INVALID_CALL;
        if (m_state->stableNoise > 0.0f) {
            // Grain-only SAD is ~1.6*sigma*blockArea, so a useful scene-change
            // threshold must scale with the measured noise: high enough that
            // same-scene grain never trips it, low enough that a hard cut
            // does.  ~2.2x the expected grain SAD -> thscd1 ~ 225*sigma8.
            // The degrainer re-reads the shared param every frame.
            const int bitDepthIn = (pInputFrame->csp == RGY_CSP_NV12 || pInputFrame->csp == RGY_CSP_YV12) ? 8 : 10;
            const float sigma8 = m_state->stableNoise / static_cast<float>(1 << (bitDepthIn - 8));
            m_motionDegrainParam->degrain.thscd1 = clamp(static_cast<int>(225.0f * sigma8),
                FILTER_DEFAULT_DEGRAIN_THSCD1, 2000);
        }
        sts = m_motionDegrain->filter(const_cast<RGYFrameInfo *>(pInputFrame), motionOutput, &motionOutputCount, stream);
        if (sts != RGY_ERR_NONE) return sts;
        if (motionOutputCount == 0) return RGY_ERR_NONE;
        if (motionOutputCount != 1 || !motionOutput[0] || !motionOutput[0]->ptr[0]) {
            AddMessage(RGY_LOG_ERROR, _T("Motion degrain returned an invalid film-grain base frame.\n"));
            return RGY_ERR_INVALID_CALL;
        }
        cleanBase = motionOutput[0];
        source = m_motionDegrain->cachedSourceFrame(cleanBase->inputFrameId, cleanBase->timestamp);
        if (!source) {
            AddMessage(RGY_LOG_ERROR, _T("Could not pair motion-degrained frame id=%d pts=%lld with its retained source.\n"),
                cleanBase->inputFrameId, static_cast<long long>(cleanBase->timestamp));
            return RGY_ERR_INVALID_CALL;
        }
    } else if (!pInputFrame || !pInputFrame->ptr[0]) {
        return RGY_ERR_NONE;
    }

    *pOutputFrameNum = 1;
    ppOutputFrames[0] = requestedOutput;
    if (!ppOutputFrames[0]) {
        ppOutputFrames[0] = &m_frameBuf[m_nFrameIdx]->frame;
        m_nFrameIdx = (m_nFrameIdx + 1) % m_frameBuf.size();
    }
    auto *output = ppOutputFrames[0];
    sts = copyFrameAsync(output, cleanBase, stream);
    if (sts != RGY_ERR_NONE) return sts;
    copyFramePropWithoutRes(output, source);
    nvenc_film_grain_erase_frame_data(output->dataList);

    NVEncFilmGrainDiagnostics diagnostics;
    diagnostics.totalBlocks = m_blocksX * m_blocksY;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params = {};
    auto attachResult = [&]() {
        output->dataList.push_back(std::make_shared<RGYFrameDataFilmGrain>(
            params, diagnostics, source->timestamp, source->inputFrameId));
    };
    if (!prm->filmGrain.enable || interlaced(*source)
        || getCudaMemcpyKind(source->mem_type, output->mem_type) != cudaMemcpyDeviceToDevice) {
        if (cleanBase != source && (sts = copyFrameAsync(output, source, stream)) != RGY_ERR_NONE) return sts;
        attachResult();
        return RGY_ERR_NONE;
    }

    const int bitDepth = (source->csp == RGY_CSP_NV12 || source->csp == RGY_CSP_YV12) ? 8 : 10;
    const int depthScale = 1 << (bitDepth - 8);
    const auto luma = getPlane(source, RGY_PLANE_Y);
    switch (source->csp) {
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
        m_temporalLeakValid = false;
        AddMessage(RGY_LOG_DEBUG, _T("fgs-model frame=%d pts=%lld reliable=0 reset=%d flat=%d/%d window=0\n"),
            source->inputFrameId, static_cast<long long>(source->timestamp),
            diagnostics.sceneReset ? 1 : 0, diagnostics.flatBlocks, diagnostics.totalBlocks);
        if (cleanBase != source && (sts = copyFrameAsync(output, source, stream)) != RGY_ERR_NONE) return sts;
        attachResult();
        return RGY_ERR_NONE;
    }
    std::vector<float> noiseSamples;
    noiseSamples.reserve(selected);
    for (int i = 0; i < blockCount; ++i) if (mask[i]) noiseSamples.push_back(metrics[i].sigma);
    const auto middle = noiseSamples.begin() + noiseSamples.size() / 2;
    std::nth_element(noiseSamples.begin(), middle, noiseSamples.end());
    const float measuredNoise = *middle;
    std::vector<float> grainCorrelationSamples;
    grainCorrelationSamples.reserve(selected);
    for (int i = 0; i < blockCount; ++i) {
        if (mask[i]) grainCorrelationSamples.push_back(metrics[i].spatialCorrelation);
    }
    const auto correlationMiddle = grainCorrelationSamples.begin() + grainCorrelationSamples.size() / 2;
    std::nth_element(grainCorrelationSamples.begin(), correlationMiddle, grainCorrelationSamples.end());
    const float measuredGrainCorrelation = *correlationMiddle;
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
    uint64_t sceneCutBlockThreshold = 0;
    uint32_t sceneCutNearestDirection = 0;
    if (prm->filmGrain.denoiser == FGS_DENOISE_MOTION) {
        const auto analysis = m_motionDegrain->analyzeResult();
        if (analysis.valid() && analysis.inputFrameId == source->inputFrameId) {
            uint32_t enabledReferenceMask = 0;
            for (int direction = 1; direction < analysis.layout.temporalDirections; direction += 2) {
                if (!analysis.availabilityDisableRefs[direction]) {
                    enabledReferenceMask |= 1u << direction;
                }
            }
            // This is a modelling confidence threshold, not the much looser
            // render threshold.  Exclude residuals from mismatched motion or
            // occlusions so they cannot be learned as synthetic grain.
            const uint32_t confidenceSad = rgy_degrain_scale_sad_threshold(
                m_motionDegrainParam->degrain, *source, 1600, false);
            sts = launch_motion_confidence(static_cast<uint8_t *>(m_blockMask->ptrDevice),
                m_blocksX, m_blocksY, analysis, enabledReferenceMask, confidenceSad, stream);
            if (sts != RGY_ERR_NONE) return sts;
            // Synchronous scene-cut detection for the model: the nearest
            // enabled reference's over-threshold block count is compared
            // against the thscd2 fraction after the stats sync, and a cut
            // clears the model history (the degrainer's own scene gating only
            // protects the rendered base, not the rolling model window).
            sceneCutNearestDirection = enabledReferenceMask & 2u; // direction 1 = t-1
            if (sceneCutNearestDirection) {
                const uint32_t sceneSad = rgy_degrain_scale_sad_threshold(
                    m_motionDegrainParam->degrain, *source, m_motionDegrainParam->degrain.thscd1, false);
                auto cudaerrScene = cudaMemsetAsync(m_sceneCounts->ptrDevice, 0, m_sceneCounts->nSize, stream);
                if (cudaerrScene != cudaSuccess) return err_to_rgy(cudaerrScene);
                sts = launch_scene_sad_count(static_cast<uint32_t *>(m_sceneCounts->ptrDevice),
                    analysis, enabledReferenceMask, sceneSad, stream);
                if (sts != RGY_ERR_NONE) return sts;
                if ((sts = m_sceneCounts->copyDtoHAsync(stream)) != RGY_ERR_NONE) return sts;
                sceneCutBlockThreshold = rgy_degrain_scale_scene_change_block_threshold(
                    static_cast<size_t>(analysis.layout.blocksX) * analysis.layout.blocksY,
                    m_motionDegrainParam->degrain.thscd2);
            }
        }
    }
    if (prm->filmGrain.denoiser == FGS_DENOISE_FFT3D && m_fft3d) {
        const float sigma8 = denoiseSigma / depthScale;
        if (m_fft3dSigma < 0.0f || std::abs(sigma8 - m_fft3dSigma) > std::max(0.3f, m_fft3dSigma * 0.10f)) {
            // A single-frame block Wiener filter with sigma matched 1:1 to the
            // actual noise std only removes ~65-70% of a flat region's noise
            // power (per-bin power is a high-variance estimate of a matched
            // threshold, so gain rarely reaches zero); measured directly by
            // probing denoise-fft3d on synthetic flat noise at multiple sigma.
            // FGS wants the base layer clean, so the programmed sigma is
            // calibrated above the measured noise level to drive removal
            // toward complete.
            constexpr float FFT3D_SIGMA_CALIBRATION = 2.0f;
            m_fft3dParam->fft3d.sigma = clamp(sigma8 * FFT3D_SIGMA_CALIBRATION, 1.0f, 100.0f);
            if ((sts = m_fft3d->init(m_fft3dParam, m_pLog)) != RGY_ERR_NONE) {
                AddMessage(RGY_LOG_ERROR, _T("Failed to update FFT3D sigma for film-grain: %s.\n"), get_err_mes(sts));
                return sts;
            }
            m_fft3dSigma = sigma8;
        }
        RGYFrameInfo *fft3dOut[1] = { output };
        int fft3dOutNum = 0;
        sts = m_fft3d->filter(const_cast<RGYFrameInfo *>(source), fft3dOut, &fft3dOutNum, stream);
        if (sts != RGY_ERR_NONE) return sts;
        if (fft3dOutNum != 1 || fft3dOut[0] != output) {
            AddMessage(RGY_LOG_ERROR, _T("FFT3D denoiser did not produce the expected 1-in-1-out frame.\n"));
            return RGY_ERR_UNKNOWN;
        }
        // FFT3D supplies the global luma clean base; the local pass corrects
        // brightness-dependent grain strength and handles the semi-planar
        // chroma that FFT3D cannot process here.  Its luma correction is faded
        // out in directionally coherent blocks so it does not erase structured
        // texture which the Wiener filter preserved.
        sts = copyFrameAsync(&m_denoiseWork->frame, output, stream);
        if (sts != RGY_ERR_NONE) return sts;
        sts = denoise_frame(output, &m_denoiseWork->frame, &m_denoiseWork->frame, prm->filmGrain.analyzeChroma, true,
            1, bitDepth, denoiseSigma,
            adaptiveSigma ? static_cast<const float *>(m_sigmaMap->ptrDevice) : nullptr,
            static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice),
            m_blocksX, m_blocksY, stream);
        if (sts != RGY_ERR_NONE) return sts;
    } else if (prm->filmGrain.denoiser == FGS_DENOISE_MOTION) {
        // Temporal averaging deliberately leaves some grain in a causal
        // three-frame window.  Finish the base with one local edge-aware pass:
        // it operates on the motion-cleaned luma instead of the original, and
        // also handles semi-planar chroma which the motion child leaves raw.
        sts = copyFrameAsync(&m_denoiseWork->frame, output, stream);
        if (sts != RGY_ERR_NONE) return sts;
        const bool finishLuma = m_motionFinishMode != MotionFinishMode::ChromaOnly;
        const auto detailMetrics = m_motionFinishMode == MotionFinishMode::DetailAware
            ? static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice)
            : nullptr;
        sts = denoise_frame(output, &m_denoiseWork->frame, &m_denoiseWork->frame,
            prm->filmGrain.analyzeChroma, finishLuma,
            1, bitDepth, denoiseSigma,
            adaptiveSigma ? static_cast<const float *>(m_sigmaMap->ptrDevice) : nullptr,
            detailMetrics,
            m_blocksX, m_blocksY, stream);
        if (sts != RGY_ERR_NONE) return sts;
    } else {
        sts = denoise_frame(output, &m_denoiseWork->frame, source, prm->filmGrain.analyzeChroma, true,
            prm->filmGrain.denoisePasses, bitDepth, denoiseSigma,
            adaptiveSigma ? static_cast<const float *>(m_sigmaMap->ptrDevice) : nullptr,
            nullptr,
            m_blocksX, m_blocksY, stream);
        if (sts != RGY_ERR_NONE) return sts;
    }

    const bool temporalLeakEnabled = prm->leakTargetQuality >= 0.0f
        && m_previousSource && m_previousBase;
    const auto flatMask = static_cast<const uint8_t *>(m_blockMask->ptrDevice);
    auto sourceLumaModelMask = flatMask;
    if (m_sourceTemporalMask) {
        auto temporalMask = static_cast<uint8_t *>(m_sigmaMap->ptrDevice);
        if (temporalLeakEnabled && m_temporalLeakValid) {
            sts = collect_temporal_static_mask(
                *source, m_previousSource->frame, m_blocksX, m_blocksY,
                flatMask, temporalMask,
                static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice),
                stream);
            if (sts != RGY_ERR_NONE) return sts;
        } else {
            cudaerr = cudaMemsetAsync(
                temporalMask, 0, static_cast<size_t>(m_blocksX) * m_blocksY, stream);
            if (cudaerr != cudaSuccess) return err_to_rgy(cudaerr);
        }
        sourceLumaModelMask = temporalMask;
    }

    cudaerr = cudaMemsetAsync(m_modelStats->ptrDevice, 0, m_modelStats->nSize, stream);
    if (cudaerr != cudaSuccess) return err_to_rgy(cudaerr);
    // Temporal stability materially improves source-luma AR fitting, but the
    // same luma-derived subset removes useful U/V observations and biases the
    // much smaller chroma fits. Keep chroma on the established spatial-flat
    // population until it has an independently validated temporal selector.
    sts = collect_model_stats(source, output, prm->filmGrain.analyzeChroma, m_blocksX, m_blocksY,
        bitDepth, sourceLumaModelMask, flatMask,
        static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice),
        static_cast<FilmGrainGpuStats *>(m_modelStats->ptrDevice),
        prm->filmGrain.modelFromSource, stream);
    if (sts != RGY_ERR_NONE) return sts;
    if (prm->filmGrain.modelFromSource) {
        // A source-derived model can be rejected after quantization when AV1's
        // finite AR template would need an unsafe strength correction. Keep a
        // residual fit over the exact same bilateral base as a conservative
        // fallback. This leaves the separator independent of model success;
        // restoring the original frame remains the last resort only when both
        // models are unsolvable.
        cudaerr = cudaMemsetAsync(
            m_fallbackModelStats->ptrDevice, 0, m_fallbackModelStats->nSize, stream);
        if (cudaerr != cudaSuccess) return err_to_rgy(cudaerr);
        sts = collect_model_stats(source, output, prm->filmGrain.analyzeChroma,
            m_blocksX, m_blocksY, bitDepth,
            flatMask, flatMask,
            static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice),
            static_cast<FilmGrainGpuStats *>(m_fallbackModelStats->ptrDevice),
            false, stream);
        if (sts != RGY_ERR_NONE) return sts;
    }
    if (temporalLeakEnabled && m_temporalLeakValid) {
        sts = collect_temporal_strength(*source, m_previousSource->frame, *output,
            m_previousBase->frame, m_blocksX, m_blocksY, bitDepth,
            flatMask,
            static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice),
            &static_cast<FilmGrainGpuStats *>(m_modelStats->ptrDevice)->plane[0], stream);
        if (sts != RGY_ERR_NONE) return sts;
        if (m_textureLeakClosure) {
            sts = collect_temporal_texture_stats(*source, m_previousSource->frame,
                *output, m_previousBase->frame, m_blocksX, m_blocksY,
                sourceLumaModelMask,
                &static_cast<FilmGrainGpuStats *>(m_modelStats->ptrDevice)->temporalLuma,
                stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
        if (m_chromaLeakMode != ChromaLeakMode::Off) {
            // Denoising has already consumed the adaptive sigma map. Reuse its
            // device storage as a one-byte-per-luma-block temporal-static mask
            // for the opt-in U/V measurement.
            sts = collect_temporal_chroma_strength(*source, m_previousSource->frame, *output,
                m_previousBase->frame, m_blocksX, m_blocksY, bitDepth,
                flatMask,
                static_cast<uint8_t *>(m_sigmaMap->ptrDevice),
                static_cast<const FilmGrainBlockMetric *>(m_blockMetrics->ptrDevice),
                static_cast<FilmGrainGpuStats *>(m_modelStats->ptrDevice), stream);
            if (sts != RGY_ERR_NONE) return sts;
        }
    }
    if (temporalLeakEnabled) {
        if ((sts = copyFrameAsync(&m_previousSource->frame, source, stream)) != RGY_ERR_NONE
            || (sts = copyFrameAsync(&m_previousBase->frame, output, stream)) != RGY_ERR_NONE) return sts;
    }
    if ((sts = m_modelStats->copyDtoHAsync(stream)) != RGY_ERR_NONE) return sts;
    if (prm->filmGrain.modelFromSource
        && (sts = m_fallbackModelStats->copyDtoHAsync(stream)) != RGY_ERR_NONE) return sts;
    cudaerr = cudaStreamSynchronize(stream);
    if (cudaerr != cudaSuccess) return err_to_rgy(cudaerr);
    if (temporalLeakEnabled) m_temporalLeakValid = true;

    bool sceneReset = false;
    bool motionSceneCut = false;
    if (sceneCutNearestDirection && sceneCutBlockThreshold > 0) {
        const auto counts = static_cast<const uint32_t *>(m_sceneCounts->ptrHost);
        motionSceneCut = counts[1] > sceneCutBlockThreshold;
    }
    bool spatialSceneCut = false;
    if (m_state->previousBlockMeans.size() == static_cast<size_t>(blockCount)) {
        double meanDelta8 = 0.0;
        int changedBlocks = 0;
        for (int i = 0; i < blockCount; ++i) {
            const float delta8 = std::abs(metrics[i].mean - m_state->previousBlockMeans[i]) / depthScale;
            meanDelta8 += delta8;
            changedBlocks += delta8 >= FGS_SCENE_BLOCK_DELTA_8BIT;
        }
        meanDelta8 /= std::max(1, blockCount);
        spatialSceneCut = meanDelta8 >= FGS_SCENE_MEAN_DELTA_8BIT
            && changedBlocks >= static_cast<int>(std::ceil(blockCount * FGS_SCENE_CHANGED_BLOCK_FRACTION));
    }
    if (!m_state->history.empty()) {
        const float ratio = measuredNoise / std::max(0.01f, m_state->stableNoise);
        if (motionSceneCut || spatialSceneCut || ratio < 0.55f || ratio > 1.80f
            || source->timestamp <= m_state->lastTimestamp) {
            m_state->clear();
            sceneReset = true;
        }
    }
    m_state->previousBlockMeans.resize(blockCount);
    for (int i = 0; i < blockCount; ++i) {
        m_state->previousBlockMeans[i] = metrics[i].mean;
    }
    FilmGrainHostStats current = {};
    std::memcpy(&current.gpu, m_modelStats->ptrHost, sizeof(current.gpu));
    if (prm->filmGrain.modelFromSource) {
        std::memcpy(&current.fallbackGpu,
            m_fallbackModelStats->ptrHost, sizeof(current.fallbackGpu));
    }
    if (sceneReset) {
        // The current frame becomes the reference for the new scene, but its
        // difference against the old scene must not enter the new model even
        // if a pathological cut happens to pass the static-ratio gate.
        for (auto& temporal : current.gpu.plane) {
            std::fill(std::begin(temporal.temporalSourceVarSum),
                std::end(temporal.temporalSourceVarSum), 0.0);
            std::fill(std::begin(temporal.temporalBaseVarSum),
                std::end(temporal.temporalBaseVarSum), 0.0);
            std::fill(std::begin(temporal.temporalBlockCount),
                std::end(temporal.temporalBlockCount), uint64_t{ 0 });
        }
        current.gpu.temporalLuma = {};
    }
    current.measuredNoise = measuredNoise;
    current.grainCorrelation = measuredGrainCorrelation;
    double detailRiskSum = 0.0;
    for (int i = 0; i < blockCount; ++i) {
        detailRiskSum += clamp(
            (metrics[i].coherence - FGS_DETAIL_COHERENCE_LOW)
                / (FGS_DETAIL_COHERENCE_HIGH - FGS_DETAIL_COHERENCE_LOW),
            0.0f, 1.0f);
    }
    current.detailRisk = static_cast<float>(detailRiskSum / std::max(1, blockCount));
    m_state->history.push_back(current);
    while (static_cast<int>(m_state->history.size()) > prm->filmGrain.modelWindow) m_state->history.pop_front();
    m_state->stableNoise = 0.0f;
    diagnostics.detailRisk = 0.0f;
    diagnostics.grainCorrelation = 0.0f;
    for (const auto& frame : m_state->history) {
        m_state->stableNoise += frame.measuredNoise;
        diagnostics.detailRisk += frame.detailRisk;
        diagnostics.grainCorrelation += frame.grainCorrelation;
    }
    m_state->stableNoise /= m_state->history.size();
    diagnostics.detailRisk /= m_state->history.size();
    diagnostics.grainCorrelation /= m_state->history.size();
    if (prm->filmGrain.residualRetain < 0.0f) {
        const float target = auto_retain_from_detail_risk(diagnostics.detailRisk);
        // The rolling model window removes frame noise; an additional two-step
        // deadband prevents a single quantization boundary from changing the
        // base/synthesis split on adjacent frames.  A fresh scene adopts its
        // target immediately.
        if (m_state->history.size() == 1
            || std::abs(target - m_state->autoRetain) >= FGS_AUTO_RETAIN_STEP * 2.0f - 1e-6f) {
            m_state->autoRetain = target;
        }
        diagnostics.residualRetain = m_state->autoRetain;
    } else {
        diagnostics.residualRetain = prm->filmGrain.residualRetain;
    }
    m_state->lastTimestamp = source->timestamp;
    diagnostics.modelFrames = static_cast<int>(m_state->history.size());
    diagnostics.sceneReset = sceneReset;

    FilmGrainGpuStats combined = {};
    FilmGrainGpuStats fallbackCombined = {};
    for (const auto& frame : m_state->history) {
        for (int plane = 0; plane < 3; ++plane) {
            add_plane_stats(combined.plane[plane], frame.gpu.plane[plane]);
            if (prm->filmGrain.modelFromSource) {
                add_plane_stats(
                    fallbackCombined.plane[plane], frame.fallbackGpu.plane[plane]);
            }
        }
        if (m_textureLeakClosure) {
            add_temporal_ar_stats(combined.temporalLuma, frame.gpu.temporalLuma);
        }
    }
    bool chromaLeakCompensated = false;
    if (prm->filmGrain.modelFromSource) {
        apply_luma_leak_closure(combined,
            temporalLeakEnabled ? prm->leakTargetQuality : -1.0,
            static_cast<uint64_t>(requiredBlocks), m_lumaLeakLocal, diagnostics);
        if (m_textureLeakClosure) {
            apply_luma_texture_leak_closure(combined,
                static_cast<uint64_t>(requiredBlocks) * 64ULL, diagnostics);
        }
        if (m_chromaLeakMode != ChromaLeakMode::Off) {
            chromaLeakCompensated = apply_chroma_leak_closure(combined,
                temporalLeakEnabled ? prm->leakTargetQuality : -1.0,
                static_cast<uint64_t>(requiredBlocks),
                m_chromaLeakMode == ChromaLeakMode::Local
                    || m_chromaLeakMode == ChromaLeakMode::Independent,
                m_chromaLeakMode == ChromaLeakMode::Independent);
        }
    }
    bool modelValid = false;
    if (diagnostics.modelFrames >= prm->filmGrain.minModelFrames) {
        modelValid = prm->filmGrain.modelFromSource
            ? build_source_film_grain_params_with_residual_fallback(
                combined, fallbackCombined, bitDepth,
                prm->filmGrain.analyzeChroma,
                prm->filmGrain.clipToRestrictedRange, params, diagnostics,
                std::min(0.98, static_cast<double>(diagnostics.grainCorrelation)
                    + FGS_SOURCE_CORRELATION_MARGIN))
            : build_film_grain_params(
                combined, bitDepth, prm->filmGrain.analyzeChroma,
                prm->filmGrain.clipToRestrictedRange, params, diagnostics, -1.0);
    }
    if (modelValid) {
        const double modelTolerance = prm->filmGrain.denoiser == FGS_DENOISE_MOTION ? 0.10 : 0.05;
        if (!m_state->lastParamsValid) {
            m_state->lastParams = params;
            m_state->lastParamsValid = true;
            m_state->lastParamsFallback = diagnostics.sourceModelFallback;
            m_state->pendingParamsValid = false;
            m_state->modelWindowSettled = diagnostics.modelFrames >= prm->filmGrain.modelWindow;
            m_state->pendingStreak = 0;
            m_state->framesSinceModelUpdate = 0;
        } else if (!m_state->modelWindowSettled
            && diagnostics.modelFrames >= prm->filmGrain.modelWindow) {
            // The first model is intentionally available after one frame so
            // synthesis never starts late, but it is a noisy estimate.  Once
            // the rolling window fills, adopt that statistically stronger fit
            // immediately instead of pinning the one-frame model for the
            // normal 24-frame anti-twinkle cadence.
            m_state->modelWindowSettled = true;
            m_state->pendingParamsValid = false;
            m_state->pendingStreak = 0;
            if (film_grain_params_close(
                params, m_state->lastParams, modelTolerance, modelTolerance)) {
                params = m_state->lastParams;
                diagnostics.sourceModelFallback = m_state->lastParamsFallback;
                diagnostics.modelHeld = true;
                m_state->advanceModelAge();
            } else {
                m_state->lastParams = params;
                m_state->lastParamsFallback = diagnostics.sourceModelFallback;
                m_state->framesSinceModelUpdate = 0;
            }
        } else if (film_grain_params_close(
            params, m_state->lastParams, modelTolerance, modelTolerance)) {
            // Hold the previously signalled model while the fresh fit only
            // jitters around it; requantizing every frame makes the grain
            // character twinkle.  NVENC still varies the grain seed per frame.
            params = m_state->lastParams;
            diagnostics.sourceModelFallback = m_state->lastParamsFallback;
            diagnostics.modelHeld = true;
            m_state->pendingParamsValid = false;
            m_state->pendingStreak = 0;
            m_state->advanceModelAge();
        } else {
            // A genuinely different fit must remain coherent for several
            // frames and respect a minimum update cadence.  This prevents a
            // noisy rolling fit from generating dozens of table intervals per
            // scene, while resetTemporalState()/scene cuts still accept the
            // first new model immediately.
            constexpr double candidateTolerance = 0.10;
            if (m_state->pendingParamsValid && film_grain_params_close(
                params, m_state->pendingParams, candidateTolerance, candidateTolerance)) {
                m_state->pendingParams = params;
                m_state->pendingParamsFallback = diagnostics.sourceModelFallback;
                ++m_state->pendingStreak;
            } else {
                m_state->pendingParams = params;
                m_state->pendingParamsValid = true;
                m_state->pendingParamsFallback = diagnostics.sourceModelFallback;
                m_state->pendingStreak = 1;
            }
            if (m_state->pendingStreak >= FGS_MODEL_CANDIDATE_FRAMES
                && m_state->framesSinceModelUpdate >= FGS_MODEL_MIN_UPDATE_FRAMES) {
                params = m_state->pendingParams;
                m_state->lastParams = params;
                m_state->lastParamsFallback = m_state->pendingParamsFallback;
                diagnostics.sourceModelFallback = m_state->lastParamsFallback;
                m_state->pendingParamsValid = false;
                m_state->pendingStreak = 0;
                m_state->framesSinceModelUpdate = 0;
            } else {
                params = m_state->lastParams;
                diagnostics.sourceModelFallback = m_state->lastParamsFallback;
                diagnostics.modelHeld = true;
                m_state->advanceModelAge();
            }
        }
        m_state->heldStreak = 0;
    } else if (m_state->lastParamsValid && m_state->heldStreak < prm->filmGrain.modelWindow) {
        // A transiently unsolvable frame keeps the last model rather than
        // dropping grain for a single frame; bounded so a persistent failure
        // cannot pin a stale model.
        params = m_state->lastParams;
        diagnostics.sourceModelFallback = m_state->lastParamsFallback;
        diagnostics.modelHeld = true;
        modelValid = true;
        m_state->pendingParamsValid = false;
        m_state->pendingStreak = 0;
        m_state->advanceModelAge();
        ++m_state->heldStreak;
    } else {
        std::memset(&params, 0, sizeof(params));
        diagnostics.sourceModelFallback = false;
        sts = copyFrameAsync(output, source, stream);
        if (sts != RGY_ERR_NONE) return sts;
    }
    diagnostics.reliable = modelValid;
    if (modelValid && params.applyGrain && diagnostics.residualRetain > 0.0f) {
        // Residual retention: keep retain * (source - clean) in the base luma
        // and shrink the signalled synthesis so total variance is preserved.
        // The scaling is applied to a local copy each frame; the hysteresis
        // state keeps comparing unscaled fits.  Applied before the table
        // recording and the level-compensation LUT so both describe what the
        // decoder actually synthesizes on top of the blended base.
        const float retain = diagnostics.residualRetain;
        const float synthScale = std::sqrt(std::max(0.0f, 1.0f - retain * retain));
        for (uint32_t i = 0; i < params.numYPoints; ++i) {
            params.pointYScaling[i] = static_cast<uint8_t>(clamp(
                static_cast<int>(std::lround(params.pointYScaling[i] * synthScale)), 0, 255));
        }
        const auto lumaOut = getPlane(output, RGY_PLANE_Y);
        const auto lumaSrc = getPlane(source, RGY_PLANE_Y);
        switch (output->csp) {
        case RGY_CSP_NV12:
        case RGY_CSP_YV12:
            sts = launch_residual_retain<uint8_t, 0>(lumaOut, lumaSrc, bitDepth, retain, stream);
            break;
        case RGY_CSP_YV12_10:
            sts = launch_residual_retain<uint16_t, 0>(lumaOut, lumaSrc, bitDepth, retain, stream);
            break;
        case RGY_CSP_P010:
            sts = launch_residual_retain<uint16_t, 6>(lumaOut, lumaSrc, bitDepth, retain, stream);
            break;
        default:
            sts = RGY_ERR_UNSUPPORTED;
            break;
        }
        if (sts != RGY_ERR_NONE) {
            AddMessage(RGY_LOG_ERROR, _T("Failed to apply film-grain residual retention: %s.\n"), get_err_mes(sts));
            return sts;
        }
    }
    if (modelValid && params.applyGrain && !m_tableOutPath.empty()) {
        recordTableEntry(source->timestamp, source->duration, params);
    }
    if (modelValid && params.applyGrain) {
        build_strength_lut(params, bitDepth, static_cast<float *>(m_strengthLut->ptrHost));
        if ((sts = m_strengthLut->copyHtoDAsync(stream)) != RGY_ERR_NONE) return sts;
        const int rangeMin = prm->filmGrain.clipToRestrictedRange ? (16 << (bitDepth - 8)) : 0;
        const int rangeMax = prm->filmGrain.clipToRestrictedRange ? (235 << (bitDepth - 8)) : ((1 << bitDepth) - 1);
        const auto lumaOut = getPlane(output, RGY_PLANE_Y);
        const auto lut = static_cast<const float *>(m_strengthLut->ptrDevice);
        switch (output->csp) {
        case RGY_CSP_NV12:
        case RGY_CSP_YV12:
            sts = launch_level_compensate<uint8_t, 0>(lumaOut, rangeMin, rangeMax, bitDepth, lut, stream);
            break;
        case RGY_CSP_YV12_10:
            sts = launch_level_compensate<uint16_t, 0>(lumaOut, rangeMin, rangeMax, bitDepth, lut, stream);
            break;
        case RGY_CSP_P010:
            sts = launch_level_compensate<uint16_t, 6>(lumaOut, rangeMin, rangeMax, bitDepth, lut, stream);
            break;
        default:
            sts = RGY_ERR_UNSUPPORTED;
            break;
        }
        if (sts != RGY_ERR_NONE) {
            AddMessage(RGY_LOG_ERROR, _T("Failed to apply film-grain level compensation: %s.\n"), get_err_mes(sts));
            return sts;
        }
    }
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
            _T("noise=%.2f/%.2f/%.2f risk=%.3f retain=%.2f grainCorr=%.3f modelCorr=%.3f arScale=%.3f strengthGain=%.3f regReject=%d fallback=%d ")
            _T("leak=%.3f>%.3f theta=%.3f temporal=%llu rectified=%llu leakClose=%d ")
            _T("texture=%llu:%.5f:%d:%d chromaLeak=%d:%d ")
            _T("scaleShift=%d arShift=%d corrCb=%d corrCr=%d ")
            _T("y=[%s] cb=[%s] cr=[%s]\n"),
            source->inputFrameId, static_cast<long long>(source->timestamp),
            modelValid ? 1 : 0, diagnostics.sceneReset ? 1 : 0, diagnostics.modelHeld ? 1 : 0,
            diagnostics.flatBlocks, diagnostics.totalBlocks, diagnostics.modelFrames,
            diagnostics.noiseStdDev[0], diagnostics.noiseStdDev[1], diagnostics.noiseStdDev[2],
            diagnostics.detailRisk, diagnostics.residualRetain, diagnostics.grainCorrelation,
            diagnostics.sourceModelCorrelation, diagnostics.sourceArScale,
            diagnostics.sourceStrengthGain, diagnostics.sourceRegularizationRejected ? 1 : 0,
            diagnostics.sourceModelFallback ? 1 : 0,
            diagnostics.preEncodeLeak, diagnostics.predictedPostEncodeLeak,
            diagnostics.leakDeadzone,
            static_cast<unsigned long long>(diagnostics.temporalLeakBlocks),
            static_cast<unsigned long long>(diagnostics.strengthRectifiedBlocks),
            diagnostics.leakCompensated ? 1 : 0,
            static_cast<unsigned long long>(diagnostics.temporalTextureObservations),
            diagnostics.textureCovarianceMinPivotRatio,
            diagnostics.textureLeakCompensated ? 1 : 0,
            diagnostics.textureLeakRejected ? 1 : 0,
            static_cast<int>(m_chromaLeakMode), chromaLeakCompensated ? 1 : 0,
            params.grainScalingMinus8 + 8, params.arCoeffShiftMinus6 + 6,
            static_cast<int>(params.arCoeffsCbPlus128[FGS_AR_COEFFS]) - 128,
            static_cast<int>(params.arCoeffsCrPlus128[FGS_AR_COEFFS]) - 128,
            pointsY.c_str(), pointsCb.c_str(), pointsCr.c_str());
    }
    attachResult();
    return RGY_ERR_NONE;
}

void NVEncFilterFilmGrain::close() {
    writeTableFile();
    m_motionDegrain.reset();
    m_motionDegrainParam.reset();
    m_fft3d.reset();
    m_fft3dParam.reset();
    m_fft3dSigma = -1.0f;
    m_previousSource.reset();
    m_previousBase.reset();
    m_temporalLeakValid = false;
    m_lumaLeakLocal = false;
    m_sourceTemporalMask = false;
    m_textureLeakClosure = false;
    m_frameBuf.clear();
    m_denoiseWork.reset();
    m_blockMetrics.reset();
    m_blockMask.reset();
    m_sigmaMap.reset();
    m_strengthLut.reset();
    m_sceneCounts.reset();
    m_modelStats.reset();
    m_fallbackModelStats.reset();
    if (m_state) m_state->clear();
    m_blocksX = 0;
    m_blocksY = 0;
    m_nFrameIdx = 0;
    m_param.reset();
}
