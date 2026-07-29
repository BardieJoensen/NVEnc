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

#ifdef __CUDACC__
#define FGS_HOST_DEVICE __host__ __device__
#else
#define FGS_HOST_DEVICE
#endif

FGS_HOST_DEVICE constexpr int tri_index(const int n, const int i, const int j) {
    return i * n - i * (i + 1) / 2 + j;
}

// Accumulators filled by the CUDA statistics kernels and merged on the host
// over the rolling model window; layout must stay memcpy/memset-compatible.
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
bool build_film_grain_params(const FilmGrainGpuStats& stats, int bitDepth,
    bool analyzeChroma, bool limitedRange, NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
    NVEncFilmGrainDiagnostics& diagnostics);
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
