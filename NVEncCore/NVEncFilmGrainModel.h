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
// The statistical model and parameter quantization are derived from the
// Alliance for Open Media libaom noise model (aom_dsp/noise_model.c), which is
// distributed under the BSD 2-Clause License and AOM Patent License 1.0:
// https://aomedia.googlesource.com/aom/+/refs/heads/main/aom_dsp/noise_model.c
// ------------------------------------------------------------------------------------------

// CPU-only half of the AV1 film grain analyzer: accumulator layout shared with
// the CUDA kernels, the AR/strength solver and the quantization to
// NV_ENC_FILM_GRAIN_PARAMS_AV1.  Deliberately free of GPU and rgy_* includes so
// it can be exercised by host-only unit tests (tests/fgs/solver_test.cpp).

#pragma once
#ifndef __NVENC_FILM_GRAIN_MODEL_H__
#define __NVENC_FILM_GRAIN_MODEL_H__

#include <array>
#include <cstdint>
#include <utility>
#include <vector>

#pragma warning (push)
#pragma warning (disable: 4819)
#include "nvEncodeAPI.h"
#pragma warning (pop)

struct NVEncFilmGrainDiagnostics {
    int flatBlocks;
    int totalBlocks;
    int modelFrames;
    std::array<float, 3> noiseStdDev;
    std::array<uint64_t, 3> observations;
    float detailRisk;
    float residualRetain;
    float grainCorrelation;
    float sourceModelCorrelation;
    float sourceArScale;
    float sourceStrengthGain;
    float preEncodeLeak;
    float predictedPostEncodeLeak;
    float leakDeadzone;
    uint64_t temporalLeakBlocks;
    uint64_t strengthRectifiedBlocks;
    bool sourceRegularizationRejected;
    bool sourceModelFallback;
    bool leakCompensated;
    bool reliable;
    bool sceneReset;
    bool modelHeld;

    NVEncFilmGrainDiagnostics();
};

namespace fgsmodel {

constexpr int FGS_BLOCK_SIZE = 32;
constexpr int FGS_AR_LAG = 3;
constexpr int FGS_AR_COEFFS = 24;
constexpr int FGS_AR_COEFFS_CHROMA = 25;
constexpr int FGS_STRENGTH_BINS = 20;
constexpr int FGS_TRI_Y = FGS_AR_COEFFS * (FGS_AR_COEFFS + 1) / 2;
constexpr int FGS_TRI_C = FGS_AR_COEFFS_CHROMA * (FGS_AR_COEFFS_CHROMA + 1) / 2;
// grain_scale_shift is a 2-bit field, so 3 is the format maximum.
constexpr int FGS_MAX_GRAIN_SCALE_SHIFT = 3;
// How far out the decoder's grain template clip must sit, in template standard
// deviations, before the saturation loss is negligible.  The clip lands at
// 4 * 2^grain_scale_shift / arGain sigma, so this chooses the shift.  At 3.5
// the measured amplitude loss on coarse_luma falls from 30% to nothing, while
// white grain (arGain ~1) still selects shift 0 and is untouched.
constexpr double FGS_TEMPLATE_CLIP_SIGMA = 3.5;
// A source-derived lag-3 fit can absorb picture structure that survives the
// per-block plane.  Keep it near the independent one-pixel source statistic,
// while leaving a deliberately conservative margin until more film is gated.
constexpr double FGS_SOURCE_CORRELATION_MARGIN = 0.05;
// Near-unstable fits can require several times more scaling strength after
// their coefficients are regularised.  Reject/hold those models rather than
// trading a texture error for an amplitude spike.
constexpr double FGS_SOURCE_MAX_STRENGTH_GAIN = 1.25;
// Six-film QVBR 25/29/34/39 closure fit.  The clean base's temporal grain
// residue follows post=max(0, pre-theta), with theta linear in requested QVBR.
// Keep this deliberately inside the measured rate range until a wider corpus
// establishes whether extrapolation is safe.
constexpr double FGS_LEAK_THETA_INTERCEPT = 0.01579030304339795;
constexpr double FGS_LEAK_THETA_QVBR_SLOPE = 0.004870139420489915;
// Test-only plane-specific transfer fitted on six retained films at QVBR
// 25/29/34/39. U and V do not share luma's post-encode deadzone. Keep these
// behind NVENC_FGS_TEST_CHROMA_LEAK=independent until a bilateral hardware
// corpus confirms the offline leave-one-title-out result.
constexpr double FGS_CHROMA_U_LEAK_THETA_INTERCEPT = -0.07637246049661427;
constexpr double FGS_CHROMA_U_LEAK_THETA_QVBR_SLOPE = 0.013076297968397295;
constexpr double FGS_CHROMA_V_LEAK_THETA_INTERCEPT = 0.29641760722347593;
constexpr double FGS_CHROMA_V_LEAK_THETA_QVBR_SLOPE = 0.0035356659142212277;
constexpr double FGS_LEAK_QVBR_MIN = 25.0;
constexpr double FGS_LEAK_QVBR_MAX = 39.0;
constexpr uint64_t FGS_MIN_TEMPORAL_BIN_BLOCKS = 4;

#ifdef __CUDACC__
#define FGS_HOST_DEVICE __host__ __device__
#else
#define FGS_HOST_DEVICE
#endif

FGS_HOST_DEVICE constexpr int tri_index(const int n, const int i, const int j) {
    return i * n - i * (i + 1) / 2 + j;
}

// Mix the block/sample index so the sparse AR observations do not repeatedly
// hit the same pixel phase in every model block.  A fixed 8x8 lattice can
// alias spatially correlated film grain and substantially overestimate the AR
// synthesis gain.
FGS_HOST_DEVICE constexpr uint32_t fgs_sample_hash(uint32_t value) {
    value ^= value >> 16;
    value *= 0x7feb352dU;
    value ^= value >> 15;
    value *= 0x846ca68bU;
    value ^= value >> 16;
    return value;
}

// Pick one deterministic, staggered sample from each of eight strata.  Margins
// keep every AR predictor inside the frame/model block. Partial edge blocks
// may have fewer pixels than strata, in which case adjacent strata safely
// reuse the same coordinate.
FGS_HOST_DEVICE constexpr int fgs_stratified_sample_offset(const int extent,
    const int leadingMargin, const int trailingMargin, const int stratum,
    const uint32_t random) {
    const int usable = extent - leadingMargin - trailingMargin;
    if (usable <= 0) return leadingMargin;
    const int begin = leadingMargin + usable * stratum / 8;
    const int end = leadingMargin + usable * (stratum + 1) / 8;
    const int span = end - begin;
    return begin + (span > 0 ? static_cast<int>(random % static_cast<uint32_t>(span)) : 0);
}

// Accumulators filled by the CUDA statistics kernels and merged on the host
// over the rolling model window; layout must stay memcpy/memset-compatible.
struct FilmGrainGpuPlaneStats {
    int64_t ata[FGS_TRI_C];
    int64_t atb[FGS_AR_COEFFS_CHROMA];
    double binVarSum[FGS_STRENGTH_BINS];
    uint64_t binBlockCount[FGS_STRENGTH_BINS];
    double temporalSourceVarSum[FGS_STRENGTH_BINS];
    double temporalBaseVarSum[FGS_STRENGTH_BINS];
    uint64_t temporalBlockCount[FGS_STRENGTH_BINS];
    uint64_t rectifiedBlockCount[FGS_STRENGTH_BINS];
    double lumaPredVarSum;
    uint64_t lumaPredBlocks;
    uint64_t observations;
};

struct FilmGrainGpuStats {
    FilmGrainGpuPlaneStats plane[3];
};

static_assert(sizeof(FilmGrainGpuStats) < 16 * 1024, "FGS readback must stay compact");

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

using StrengthPoint = std::pair<double, double>;

bool solve_linear_system(std::vector<double> matrix, std::vector<double> rhs, std::vector<double>& solution, int n);
FilmGrainSolvedPlane solve_plane(const FilmGrainGpuPlaneStats& stats, bool chroma, const FilmGrainSolvedPlane *lumaSolved);
std::vector<StrengthPoint> fit_strength_points(const FilmGrainSolvedPlane& solved, int bitDepth, int maxPoints);
void add_plane_stats(FilmGrainGpuPlaneStats& dst, const FilmGrainGpuPlaneStats& src);
bool apply_luma_leak_closure(FilmGrainGpuStats& stats, double qvbr,
    uint64_t minTemporalBlocks, bool perBin,
    NVEncFilmGrainDiagnostics& diagnostics);
bool apply_chroma_leak_closure(FilmGrainGpuStats& stats, double qvbr,
    uint64_t minTemporalBlocks, bool perBin, bool planeSpecific);
bool build_film_grain_params(const FilmGrainGpuStats& stats, int bitDepth,
    bool analyzeChroma, bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics, double maxLumaCorrelation = -1.0);
bool build_source_film_grain_params_with_residual_fallback(
    const FilmGrainGpuStats& sourceStats, const FilmGrainGpuStats& residualStats,
    int bitDepth, bool analyzeChroma, bool limitedRange,
    NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics, double maxLumaCorrelation);
double implied_luma_correlation(const std::vector<double>& coeffs, double scale = 1.0);
double eval_scaling_curve(const uint8_t *values, const uint8_t *scalings, uint32_t count, double x);
bool film_grain_params_close(const NV_ENC_FILM_GRAIN_PARAMS_AV1& a, const NV_ENC_FILM_GRAIN_PARAMS_AV1& b,
    double relativeSigmaTolerance = 0.05, double coefficientTolerance = 0.05);

// Luma grain std in native code values, indexed by 8-bit intensity, decoded
// from the quantized scaling curve.  Used to pre-compensate the mean lift the
// decoder's grain-plus-clip synthesis introduces near the legal range floor
// and ceiling.
constexpr int FGS_STRENGTH_LUT_SIZE = 256;
void build_strength_lut(const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, int bitDepth, float lut[FGS_STRENGTH_LUT_SIZE]);

} // namespace fgsmodel

#endif // __NVENC_FILM_GRAIN_MODEL_H__
