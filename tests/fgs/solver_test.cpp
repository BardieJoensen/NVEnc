// CPU known-answer tests for the film grain model solver (NVEncFilmGrainModel).
// No GPU required.  Build and run via tests/fgs/run_cpu_tests.sh, or:
//   g++ -std=c++17 -O2 -I NVEncCore -I NVEncSDK/Common/inc
//       tests/fgs/solver_test.cpp NVEncCore/NVEncFilmGrainModel.cpp -o solver_test
//
// Statistics are constructed analytically: for white noise of variance v the
// AR normal equations have ata = N*v on the diagonal and atb = 0, and each
// strength bin observes the per-block variance directly.  Expected quantized
// parameters follow from the AV1 scaling-shift/coeff-shift derivations.

#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>

#include "NVEncFilmGrainModel.h"

using namespace fgsmodel;

namespace {

int failures = 0;

void expect(const bool ok, const char *what) {
    if (!ok) {
        std::cerr << "FAIL: " << what << "\n";
        ++failures;
    }
}

void expectNear(const double got, const double want, const double tol, const char *what) {
    if (std::abs(got - want) > tol) {
        std::cerr << "FAIL: " << what << ": got " << got << ", want " << want << " +-" << tol << "\n";
        ++failures;
    }
}

constexpr uint64_t N_OBS = 100000;

// White noise of std `sigma` on every strength bin: diagonal normal equations,
// zero correlation with the predictors.
void fillWhitePlane(FilmGrainGpuPlaneStats& plane, const double sigma, const bool chroma) {
    const int n = chroma ? FGS_AR_COEFFS_CHROMA : FGS_AR_COEFFS;
    for (int i = 0; i < n; ++i) {
        plane.ata[tri_index(n, i, i)] = static_cast<int64_t>(N_OBS * sigma * sigma);
    }
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        plane.binBlockCount[bin] = 100;
        plane.binVarSum[bin] = 100.0 * sigma * sigma;
    }
    plane.observations = N_OBS;
}

void testWhiteLuma() {
    FilmGrainGpuStats stats = {};
    fillWhitePlane(stats.plane[0], 6.0, false);
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diag;
    expect(build_film_grain_params(stats, 8, false, true, params, diag), "white luma solves");
    expect(params.applyGrain == 1, "applyGrain set");
    expect(params.arCoeffLag == FGS_AR_LAG, "arCoeffLag");
    expect(params.clipToRestrictedRange == 1, "clipToRestrictedRange");
    expect(params.numYPoints == 14, "14 luma points");
    expect(params.numCbPoints == 0 && params.numCrPoints == 0, "no chroma points");
    // maxScaling 6 -> scalingShift 10, factor 32 -> scaling ~192 flat.
    expect(params.grainScalingMinus8 == 2, "scaling shift 10");
    for (uint32_t i = 0; i < params.numYPoints; ++i) {
        expectNear(params.pointYScaling[i], 192.0, 2.0, "flat luma scaling ~sigma*32");
    }
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        expect(params.arCoeffsYPlus128[i] == 128, "white noise AR coeffs are zero");
    }
    expectNear(diag.noiseStdDev[0], 6.0, 0.05, "diag luma sigma");
}

void testRampLuma() {
    FilmGrainGpuStats stats = {};
    auto& plane = stats.plane[0];
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        plane.ata[tri_index(FGS_AR_COEFFS, i, i)] = static_cast<int64_t>(N_OBS * 36.0);
    }
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        const double sigma = 2.0 + 8.0 * bin / (FGS_STRENGTH_BINS - 1);
        plane.binBlockCount[bin] = 100;
        plane.binVarSum[bin] = 100.0 * sigma * sigma;
    }
    plane.observations = N_OBS;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diag;
    expect(build_film_grain_params(stats, 8, false, true, params, diag), "ramp luma solves");
    // maxScaling 10 -> factor 16; the first/last bins are never dropped by the
    // point fitter and are not touched by the 121 smoothing.
    expect(params.pointYValue[0] == 0 && params.pointYValue[params.numYPoints - 1] == 255, "endpoints kept");
    expectNear(params.pointYScaling[0], 2.0 * 16.0, 2.0, "ramp start ~2*16");
    expectNear(params.pointYScaling[params.numYPoints - 1], 10.0 * 16.0, 2.0, "ramp end ~10*16");
    for (uint32_t i = 1; i < params.numYPoints; ++i) {
        expect(params.pointYScaling[i] + 1 >= params.pointYScaling[i - 1], "ramp monotonic");
    }
}

// Chroma noise T^2 = (corr*sigmaPred)^2 + u^2 with the luma-correlation
// coefficient fitted through the averaged-luma predictor.  With corr=0.8,
// sigmaPred=3 (white luma sigma 6), u=1: corrIdeal = 4.8 which must clamp to
// 1.9, and the scaling curve must keep total chroma energy sqrt(6.76) = 2.6.
void testChromaCorrelationClamp() {
    FilmGrainGpuStats stats = {};
    fillWhitePlane(stats.plane[0], 6.0, false);
    const double corr = 0.8;
    const double sigmaPred = 3.0;
    const double uncorr = 1.0;
    const double totalVar = corr * corr * sigmaPred * sigmaPred + uncorr * uncorr;
    for (int c = 1; c < 3; ++c) {
        auto& plane = stats.plane[c];
        const int n = FGS_AR_COEFFS_CHROMA;
        for (int i = 0; i + 1 < n; ++i) {
            plane.ata[tri_index(n, i, i)] = static_cast<int64_t>(N_OBS * totalVar);
        }
        plane.ata[tri_index(n, n - 1, n - 1)] = static_cast<int64_t>(N_OBS * sigmaPred * sigmaPred);
        plane.atb[n - 1] = static_cast<int64_t>(N_OBS * corr * sigmaPred * sigmaPred);
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            plane.binBlockCount[bin] = 100;
            plane.binVarSum[bin] = 100.0 * totalVar;
        }
        plane.lumaPredVarSum = 100.0 * sigmaPred * sigmaPred;
        plane.lumaPredBlocks = 100;
        plane.observations = N_OBS;
    }
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diag;
    expect(build_film_grain_params(stats, 8, true, true, params, diag), "correlated chroma solves");
    expect(params.numCbPoints == 10 && params.numCrPoints == 10, "chroma points present");
    // coeff range includes the clamped 1.9 -> arShift 6, scale 64 -> 1.9*64 ~ 122.
    expect(params.arCoeffShiftMinus6 == 0, "arShift 6 for clamped corr");
    expectNear(params.arCoeffsCbPlus128[FGS_AR_COEFFS], 128 + 122, 2.0, "clamped Cb correlation");
    expectNear(params.arCoeffsCrPlus128[FGS_AR_COEFFS], 128 + 122, 2.0, "clamped Cr correlation");
    // templateVariance = 1 + (1.9 * sigmaPred/sigmaLuma)^2 = 1.9025 ->
    // strength = sqrt(6.76/1.9025) ~ 1.885, scaling factor 32 (max is luma 6).
    expectNear(params.pointCbScaling[0], 1.885 * 32.0, 3.0, "chroma scaling keeps total energy");
    expectNear(diag.noiseStdDev[1], std::sqrt(totalVar), 0.1, "diag chroma sigma = total");
    expect(params.cbMult == 128 && params.cbLumaMult == 192 && params.cbOffset == 256, "cb scaling index setup");
}

void testSingularChromaFallsBackToLumaOnly() {
    FilmGrainGpuStats stats = {};
    fillWhitePlane(stats.plane[0], 6.0, false);
    // chroma planes left all-zero: unsolvable, must not invalidate the model
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diag;
    expect(build_film_grain_params(stats, 8, true, true, params, diag), "luma-only fallback solves");
    expect(params.numYPoints == 14, "luma points survive");
    expect(params.numCbPoints == 0 && params.numCrPoints == 0, "no chroma points");
    expect(params.arCoeffsCbPlus128[FGS_AR_COEFFS] == 128, "no Cb correlation");
    expect(params.cbMult == 0 && params.crMult == 0, "chroma index mults untouched");
}

void testParamsClose() {
    NV_ENC_FILM_GRAIN_PARAMS_AV1 a, b, c;
    NVEncFilmGrainDiagnostics diag;
    FilmGrainGpuStats stats = {};
    fillWhitePlane(stats.plane[0], 6.0, false);
    expect(build_film_grain_params(stats, 8, false, true, a, diag), "params_close base solves");
    b = a;
    expect(film_grain_params_close(a, b), "identical params are close");
    FilmGrainGpuStats stats2 = {};
    fillWhitePlane(stats2.plane[0], 7.0, false);
    expect(build_film_grain_params(stats2, 8, false, true, c, diag), "params_close variant solves");
    expect(!film_grain_params_close(a, c), "17% stronger grain is not close");
    FilmGrainGpuStats stats3 = {};
    fillWhitePlane(stats3.plane[0], 6.05, false);
    NV_ENC_FILM_GRAIN_PARAMS_AV1 d;
    expect(build_film_grain_params(stats3, 8, false, true, d, diag), "params_close jitter solves");
    expect(film_grain_params_close(a, d), "1% jitter is close");
}

void testEvalScalingCurve() {
    const uint8_t values[2] = { 0, 100 };
    const uint8_t scalings[2] = { 10, 20 };
    expectNear(eval_scaling_curve(values, scalings, 2, 0.0), 10.0, 1e-9, "curve at first knot");
    expectNear(eval_scaling_curve(values, scalings, 2, 50.0), 15.0, 1e-9, "curve interpolates");
    expectNear(eval_scaling_curve(values, scalings, 2, 200.0), 20.0, 1e-9, "curve clamps right");
    expectNear(eval_scaling_curve(values, scalings, 0, 128.0), 0.0, 1e-9, "empty curve is zero");
}

} // namespace

int main() {
    testWhiteLuma();
    testRampLuma();
    testChromaCorrelationClamp();
    testSingularChromaFallsBackToLumaOnly();
    testParamsClose();
    testEvalScalingCurve();
    if (failures) {
        std::cerr << failures << " solver test(s) failed\n";
        return 1;
    }
    std::cout << "all film grain solver tests passed\n";
    return 0;
}
