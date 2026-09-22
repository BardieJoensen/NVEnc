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
    // Template RMS / nominal innovation sigma (32 * 2^(depth-8-grainScaleShift)).
    // Ordinary shift-zero fitting uses its qualified AR/correlation estimate.
    // Nonzero shifts require fresh finite gain evidence for the exact model.
    std::array<float, 3> templateGain;
    std::array<uint64_t, 3> observations;
    float detailRisk;
    float residualRetain;
    float grainCorrelation;
    std::array<float, 3> strengthFitError;
    bool sourceFidelityFallback;
    bool freshModel;
    bool strengthRefit; // recovered using occupied-bin amplitudes and measured intensities
    bool reliable;
    bool rejectedModel; // quantized AR feedback could not be certified stable
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
    // Actual luma coordinates of occupied strength observations. Intensity
    // counts distinguish measured black from older/analytical centre-only data.
    double binLumaSum[FGS_STRENGTH_BINS];
    uint64_t intensityBlocks;
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

// Fidelity of this encoder's luma-indexed strength curves in occupied bins.
// This measures amplitude fit, not decoded spatial texture or perceptual quality.
struct FilmGrainStrengthFidelity {
    std::array<double, 3> relativeRmsError = {};
    std::array<double, 3> rmsError8bit = {};
    std::array<uint64_t, 3> blocks = {};
    bool needsSource(double relativeLimit = 0.25, double absoluteLimit8bit = 0.5) const;
};
FilmGrainStrengthFidelity film_grain_strength_fidelity(const FilmGrainGpuStats& stats,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, int bitDepth,
    const std::array<float, 3>& templateGain);

// Source-flat observations: fine 16x16 patches and larger 32x32 correlated
// luma patches with independent temporal evidence. One-code brightness and
// separate strength populations retain differences a coarse fit can hide.
// Compare source variance with base + independently synthesized grain variance;
// removed-residual variance alone ignores grain already retained in the base.
constexpr int FGS_LOCAL_STRENGTH_BINS = 256;
constexpr int FGS_LOCAL_STRENGTH_GROUPS = 6; // sigma boundaries: 0.5, 2, 4, 8, 16 in 8-bit units
constexpr int FGS_LOCAL_STRENGTH_SLOTS = FGS_LOCAL_STRENGTH_BINS * (1 + FGS_LOCAL_STRENGTH_GROUPS);
constexpr int FGS_LOCAL_COVARIANCE_SAMPLES = 16 * 22;
constexpr int FGS_LOCAL_COVARIANCES = 46; // dy 0: dx 0..6; dy 1..3: dx -6..6
FGS_HOST_DEVICE constexpr int fgs_covariance_index(int dy, int dx) {
    if (dy < -3 || dy > 3 || dx < -6 || dx > 6) return -1;
    if (dy < 0 || (dy == 0 && dx < 0)) { dy = -dy; dx = -dx; }
    return dy == 0 ? (dx <= 6 ? dx : -1)
        : (dy <= 3 && dx >= -6 && dx <= 6 ? 7 + (dy - 1) * 13 + dx + 6 : -1);
}
struct FilmGrainLocalStrengthStats {
    double varianceSum[FGS_LOCAL_STRENGTH_SLOTS]; // source after removing a local plane
    double baseVarianceSum[FGS_LOCAL_STRENGTH_SLOTS]; // filtered base with the same detrending
    double covarianceSum[FGS_LOCAL_STRENGTH_SLOTS]; // source/base, before optional residual blending
    double intensitySum[FGS_LOCAL_STRENGTH_SLOTS];
    uint64_t blocks[FGS_LOCAL_STRENGTH_SLOTS];
    uint64_t correlatedBlocks[FGS_LOCAL_STRENGTH_BINS]; // larger patches with independent temporal evidence
    double sourceCovariance[FGS_LOCAL_COVARIANCES];
    double baseCovariance[FGS_LOCAL_COVARIANCES];
    double crossCovariance[FGS_LOCAL_COVARIANCES]; // source/base in both spatial directions
    uint64_t covarianceBlocks;
};
struct FilmGrainLocalStrengthFidelity {
    std::array<double, FGS_LOCAL_STRENGTH_SLOTS> observedSigma = {};
    std::array<double, FGS_LOCAL_STRENGTH_SLOTS> modeledSigma = {};
    std::array<uint64_t, FGS_LOCAL_STRENGTH_SLOTS> blocks = {};
    bool valid = true;
    bool needsSource(double relativeLimit = 0.25, double absoluteLimit8bit = 0.5) const;
};
FilmGrainLocalStrengthFidelity film_grain_local_strength_fidelity(const FilmGrainLocalStrengthStats& stats,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, int bitDepth, double templateGain, double residualRetain = 0.0, int plane = 0);
// Retry only luma strength with independent local source/base evidence,
// including quiet patches. AR coefficients, chroma curves and the global
// scaling shift are preserved. templateGain has the nominal convention below.
// If stats describe an already rounded retained base, pass residualRetain=0:
// applying its retention fraction again would double-count retained energy.
// Failure leaves the caller's model unchanged.
bool refit_local_strength(const FilmGrainLocalStrengthStats& stats, int bitDepth,
    double templateGain, double residualRetain, NV_ENC_FILM_GRAIN_PARAMS_AV1& params);

// Where independent correlated-grain evidence exists, the desired synthesis
// is source variance minus retained-base variance, not removed-residual energy.
// Keep AR normal equations and unobserved coarse bins unchanged.
FilmGrainGpuStats local_strength_targets(const FilmGrainGpuStats& coarse,
    const FilmGrainLocalStrengthStats& local, int bitDepth, double residualRetain);

// Fit the independent synthesis covariance as source minus retained base.
// Return false for sparse, invalid or nonpositive covariance evidence.
bool apply_local_covariance(FilmGrainGpuStats& stats,
    const FilmGrainLocalStrengthStats& local, double residualRetain, double *highpassFraction = nullptr);

// Linear DC amplification proxy in nominal 8-bit sigma units, including the
// grain innovation shift and later residual scaling. This is not a finite
// worst-seed/maximum-pixel bound: template rounding/clipping and mean still
// need independent checks. Instability/invalid inputs return infinity.
double film_grain_luma_dc_amplitude(const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, double residualRetain);
bool build_covariance_recovery_model(const FilmGrainGpuStats& stats, int bitDepth,
    bool analyzeChroma, bool limitedRange, double residualRetain, double highpassFraction,
    NV_ENC_FILM_GRAIN_PARAMS_AV1& params, NVEncFilmGrainDiagnostics& diagnostics);

// Stable debug reason codes; these describe the first failing eligibility
// condition, not an observed picture defect. 254/255 are reserved by the
// filter for inactive components and checks not reached, respectively.
enum class FilmGrainChromaRestoreReason : uint32_t {
    Eligible = 0, InvalidPlane = 1, ScalingFromLuma = 2, UnsupportedLag = 3,
    InvalidShift = 4, SignalledCoupling = 5, InsufficientObservations = 6,
    InvalidVariance = 7, MissingEnergy = 8, MissingPredictor = 9,
    SpatialCorrelation = 10, InvalidCorrelation = 11, MeasuredCoupling = 12
};
FilmGrainChromaRestoreReason chroma_restore_reason(const FilmGrainGpuStats& stats,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, int plane);

// Current reasons for whole-source output. Several checks can fail on one
// frame; RecoveryHold alone means the stricter re-entry has not settled.
enum FilmGrainSourceReason : uint32_t {
    FGS_SOURCE_NO_MODEL = 1u, FGS_SOURCE_FEEDBACK = 2u, FGS_SOURCE_NO_ADJACENT = 4u,
    FGS_SOURCE_STRENGTH = 8u, FGS_SOURCE_LOCAL = 16u, FGS_SOURCE_COLOUR = 32u,
    FGS_SOURCE_COVARIANCE = 64u, FGS_SOURCE_DC = 128u, FGS_SOURCE_RECOVERY_HOLD = 256u,
    FGS_SOURCE_INSUFFICIENT_FLAT = 512u, FGS_SOURCE_SUPPORT = 1024u,
    FGS_SOURCE_SYNTHESIS_RECOVERY = 2048u
};

// Independent colour-source restoration is permitted only with substantial
// current evidence and negligible measured/signalled luma coupling.
bool can_restore_chroma_component(const FilmGrainGpuStats& stats,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, int plane);

using StrengthPoint = std::pair<double, double>;

bool solve_linear_system(std::vector<double> matrix, std::vector<double> rhs, std::vector<double>& solution, int n);
FilmGrainSolvedPlane solve_plane(const FilmGrainGpuPlaneStats& stats, bool chroma, const FilmGrainSolvedPlane *lumaSolved);
// Auto fidelity mode fits at the centres of the actual GPU intensity
// intervals. The default preserves existing fixed-retention tables.
std::vector<StrengthPoint> fit_strength_points(const FilmGrainSolvedPlane& solved, int bitDepth, int maxPoints,
    bool useBinCenters = false);
void add_plane_stats(FilmGrainGpuPlaneStats& dst, const FilmGrainGpuPlaneStats& src);
bool build_film_grain_params(const FilmGrainGpuStats& stats, int bitDepth,
    bool analyzeChroma, bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics, bool useBinCenters = false);
// Retry an inaccurate amplitude model using only current-frame evidence. An
// occupied-bin fit can recover sharp curves lost to smoothing, using measured
// brightness coordinates where available. The full syntax/feedback guards
// still apply, followed by the stricter quantized per-plane recovery fit.
// Failure leaves caller outputs unchanged.
bool build_fidelity_recovery_model(const FilmGrainGpuStats& stats, int bitDepth,
    bool analyzeChroma, bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics);

double eval_scaling_curve(const uint8_t *values, const uint8_t *scalings, uint32_t count, double x);
bool film_grain_params_close(const NV_ENC_FILM_GRAIN_PARAMS_AV1& a, const NV_ENC_FILM_GRAIN_PARAMS_AV1& b,
    double relativeSigmaTolerance = 0.05, double coefficientTolerance = 0.05);

// Smooth grain sigma estimate in native code values, indexed by 8-bit intensity.
// templateGain is template RMS / (32 * 2^(bitDepth-8-grainScaleShift)), measured
// for this model, bit depth and shift. A finite-template power normalized by the
// *actual rounded* Gaussian moment needs conversion to that nominal convention.
// This is not the decoder's integer LUT or complete displayed-pixel synthesis:
// output rounding, overlap, picture clipping and means require separate checks.
// Used by ordinary mean-lift compensation and source-strength guards. Invalid
// arguments produce an infinite LUT, never an apparently quiet component.
constexpr int FGS_STRENGTH_LUT_SIZE = 256;
void build_strength_lut(const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, int bitDepth,
    float lut[FGS_STRENGTH_LUT_SIZE], int plane = 0, double templateGain = 1.0);

} // namespace fgsmodel

#endif // __NVENC_FILM_GRAIN_MODEL_H__
