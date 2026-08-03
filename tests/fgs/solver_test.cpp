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

void testStratifiedSampling() {
    bool sawLumaX[FGS_BLOCK_SIZE] = {};
    bool sawLumaY[FGS_BLOCK_SIZE] = {};
    bool sawChromaX[FGS_BLOCK_SIZE / 2] = {};
    for (int block = 0; block < 256; ++block) {
        for (int tid = 0; tid < 64; ++tid) {
            const int tx = tid & 7;
            const int ty = tid >> 3;
            const uint32_t hash = fgs_sample_hash(static_cast<uint32_t>(block * 64 + tid));
            const int lx = fgs_stratified_sample_offset(
                FGS_BLOCK_SIZE, FGS_AR_LAG, FGS_AR_LAG, tx, hash);
            const int ly = fgs_stratified_sample_offset(
                FGS_BLOCK_SIZE, FGS_AR_LAG, 0, ty, hash >> 8);
            const int cx = fgs_stratified_sample_offset(
                FGS_BLOCK_SIZE / 2, FGS_AR_LAG, FGS_AR_LAG, tx, hash);
            expect(lx >= FGS_AR_LAG && lx + FGS_AR_LAG < FGS_BLOCK_SIZE,
                "luma horizontal sample keeps AR margins");
            expect(ly >= FGS_AR_LAG && ly < FGS_BLOCK_SIZE,
                "luma vertical sample keeps AR margin");
            expect(cx >= FGS_AR_LAG && cx + FGS_AR_LAG < FGS_BLOCK_SIZE / 2,
                "chroma horizontal sample keeps AR margins");
            sawLumaX[lx] = true;
            sawLumaY[ly] = true;
            sawChromaX[cx] = true;
        }
    }
    for (int x = FGS_AR_LAG; x < FGS_BLOCK_SIZE - FGS_AR_LAG; ++x) {
        expect(sawLumaX[x], "staggered luma samples cover every safe column");
    }
    for (int y = FGS_AR_LAG; y < FGS_BLOCK_SIZE; ++y) {
        expect(sawLumaY[y], "staggered luma samples cover every safe row");
    }
    for (int x = FGS_AR_LAG; x < FGS_BLOCK_SIZE / 2 - FGS_AR_LAG; ++x) {
        expect(sawChromaX[x], "staggered chroma samples cover every safe column");
    }
}

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

void fillHorizontalPlane(FilmGrainGpuPlaneStats& plane, const double sigma,
    const double correlation) {
    fillWhitePlane(plane, sigma, false);
    // The final luma predictor is the immediately preceding sample on the
    // current row.  Diagonal normal equations make its solved coefficient
    // exactly `correlation` while keeping the fixture analytically simple.
    plane.atb[FGS_AR_COEFFS - 1] = static_cast<int64_t>(
        N_OBS * sigma * sigma * correlation);
}

void testSourceCorrelationRegularizer() {
    std::vector<double> horizontal(FGS_AR_COEFFS, 0.0);
    horizontal.back() = 0.60;
    expect(implied_luma_correlation(horizontal) > 0.25,
        "horizontal AR fixture has measurable lag-one correlation");
    expect(std::abs(implied_luma_correlation(std::vector<double>(
        FGS_AR_COEFFS, 0.0))) < 0.03, "white AR fixture stays near zero correlation");

    FilmGrainGpuStats stats = {};
    fillHorizontalPlane(stats.plane[0], 6.0, 0.60);
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diag;
    expect(build_film_grain_params(
        stats, 8, false, true, params, diag, 0.20),
        "moderate source correlation can be regularised");
    expect(diag.sourceArScale < 0.99f && diag.sourceArScale > 0.0f,
        "source regularizer scales the AR coefficients");
    expect(diag.sourceModelCorrelation <= 0.205f,
        "source regularizer respects the correlation ceiling");
    const double emittedScale = static_cast<double>(
        1 << (params.arCoeffShiftMinus6 + 6));
    std::vector<double> emittedCoefficients(FGS_AR_COEFFS, 0.0);
    for (int i = 0; i < FGS_AR_COEFFS; ++i) {
        emittedCoefficients[i] =
            (static_cast<int>(params.arCoeffsYPlus128[i]) - 128) / emittedScale;
    }
    expect(implied_luma_correlation(emittedCoefficients) <= 0.205,
        "quantized AV1 coefficients respect the correlation ceiling");
    expect(diag.sourceStrengthGain > 1.0f
        && diag.sourceStrengthGain <= FGS_SOURCE_MAX_STRENGTH_GAIN,
        "source regularizer recomputes bounded strength");
    expect(!diag.sourceRegularizationRejected,
        "moderate source regularization is accepted");

    FilmGrainGpuStats unstable = {};
    fillHorizontalPlane(unstable.plane[0], 6.0, 0.90);
    NVEncFilmGrainDiagnostics rejected;
    expect(!build_film_grain_params(
        unstable, 8, false, true, params, rejected, 0.20),
        "near-unstable source fit is rejected instead of amplified");
    expect(rejected.sourceRegularizationRejected,
        "rejected source fit is exposed in diagnostics");
}

void testSourceTemplateGain() {
    FilmGrainGpuStats stats = {};
    fillHorizontalPlane(stats.plane[0], 6.0, 0.55);
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diag;
    expect(build_film_grain_params(
        stats, 8, false, true, params, diag, 0.98),
        "unclamped source fit normalizes realized template gain");
    expectNear(diag.sourceArScale, 1.0, 1e-6,
        "template-gain normalization does not change in-bound correlation");
    expect(std::abs(diag.sourceStrengthGain - 1.0f) > 1e-4f,
        "source fit exposes quantized-template strength correction");
    expect(diag.sourceStrengthGain >= 1.0f / FGS_SOURCE_MAX_STRENGTH_GAIN
        && diag.sourceStrengthGain <= FGS_SOURCE_MAX_STRENGTH_GAIN,
        "source template-gain correction stays bounded");
    expectNear(diag.noiseStdDev[0], 6.0, 0.05,
        "source template-gain normalization preserves target sigma");
}

void testSourceModelResidualFallback() {
    FilmGrainGpuStats unstableSource = {};
    fillHorizontalPlane(unstableSource.plane[0], 6.0, 0.90);
    FilmGrainGpuStats stableResidual = {};
    fillHorizontalPlane(stableResidual.plane[0], 6.0, 0.15);
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diagnostics;
    expect(build_source_film_grain_params_with_residual_fallback(
        unstableSource, stableResidual, 8, false, true,
        params, diagnostics, 0.20),
        "residual model keeps synthesis available after source rejection");
    expect(diagnostics.sourceRegularizationRejected,
        "fallback preserves the source rejection diagnostic");
    expect(diagnostics.sourceModelFallback,
        "fallback selection is exposed in diagnostics");
    expect(params.applyGrain != 0,
        "residual fallback emits grain instead of a denoised-only base");

    FilmGrainGpuStats emptyResidual = {};
    NVEncFilmGrainDiagnostics failed;
    expect(!build_source_film_grain_params_with_residual_fallback(
        unstableSource, emptyResidual, 8, false, true,
        params, failed, 0.20),
        "source fallback still fails closed when neither model is solvable");
    expect(failed.sourceRegularizationRejected,
        "double failure preserves the source rejection diagnostic");
    expect(!failed.sourceModelFallback,
        "failed residual solve is not reported as a selected fallback");
}

void testTemporalLeakClosure() {
    FilmGrainGpuStats stats = {};
    auto& luma = stats.plane[0];
    constexpr double sourceVariance = 100.0;
    constexpr double preLeak = 0.40;
    for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
        luma.binVarSum[bin] = 10.0; // must be replaced, not multiplied in place
        luma.binBlockCount[bin] = 10;
        luma.temporalSourceVarSum[bin] = 10.0 * sourceVariance;
        luma.temporalBaseVarSum[bin] = 10.0 * sourceVariance * preLeak * preLeak;
        luma.temporalBlockCount[bin] = 10;
        luma.rectifiedBlockCount[bin] = 2;
    }
    NVEncFilmGrainDiagnostics diag;
    expect(apply_luma_leak_closure(stats, 29.0, 100, diag),
        "temporal leak closure accepts calibrated QVBR and coverage");
    const double theta = FGS_LEAK_THETA_INTERCEPT + FGS_LEAK_THETA_QVBR_SLOPE * 29.0;
    const double postLeak = preLeak - theta;
    const double expectedVariance = sourceVariance * (1.0 - postLeak * postLeak);
    expectNear(stats.plane[0].binVarSum[0] / stats.plane[0].binBlockCount[0],
        expectedVariance, 1e-9, "temporal closure writes post-encode target variance");
    expectNear(diag.preEncodeLeak, preLeak, 1e-6, "temporal closure reports pre-encode leak");
    expectNear(diag.predictedPostEncodeLeak, postLeak, 1e-6,
        "temporal closure reports predicted post-encode leak");
    expectNear(diag.leakDeadzone, theta, 1e-6, "temporal closure reports deadzone");
    expect(diag.temporalLeakBlocks == 200, "temporal closure reports coverage");
    expect(diag.strengthRectifiedBlocks == 40, "temporal closure reports rectification");
    expect(diag.leakCompensated, "temporal closure reports application");

    FilmGrainGpuStats outOfRange = {};
    outOfRange.plane[0] = luma;
    NVEncFilmGrainDiagnostics gated;
    expect(!apply_luma_leak_closure(outOfRange, 20.0, 100, gated),
        "temporal closure does not extrapolate outside calibrated QVBR");
    expect(!gated.leakCompensated, "gated temporal closure stays diagnostic-only");
}

void testChromaTemporalLeakClosure() {
    constexpr double sourceVariance = 100.0;
    constexpr double qvbr = 29.0;
    const double theta = FGS_LEAK_THETA_INTERCEPT + FGS_LEAK_THETA_QVBR_SLOPE * qvbr;

    FilmGrainGpuStats global = {};
    for (int plane = 1; plane <= 2; ++plane) {
        const double preLeak = plane == 1 ? 0.40 : 0.60;
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            auto& chroma = global.plane[plane];
            chroma.binVarSum[bin] = 10.0;
            chroma.binBlockCount[bin] = 10;
            chroma.temporalSourceVarSum[bin] = 10.0 * sourceVariance;
            chroma.temporalBaseVarSum[bin] =
                10.0 * sourceVariance * preLeak * preLeak;
            chroma.temporalBlockCount[bin] = 10;
        }
    }
    expect(apply_chroma_leak_closure(global, qvbr, 100, false),
        "global chroma closure accepts paired plane coverage");
    for (int plane = 1; plane <= 2; ++plane) {
        const double preLeak = plane == 1 ? 0.40 : 0.60;
        const double postLeak = preLeak - theta;
        const double expected = sourceVariance * (1.0 - postLeak * postLeak);
        expectNear(global.plane[plane].binVarSum[3]
            / global.plane[plane].binBlockCount[3], expected, 1e-9,
            "global chroma closure uses each plane's aggregate leak");
    }

    FilmGrainGpuStats local = {};
    for (int plane = 1; plane <= 2; ++plane) {
        for (int bin = 0; bin < FGS_STRENGTH_BINS; ++bin) {
            const double preLeak = bin & 1 ? 0.60 : 0.20;
            auto& chroma = local.plane[plane];
            chroma.temporalSourceVarSum[bin] = 10.0 * sourceVariance;
            chroma.temporalBaseVarSum[bin] =
                10.0 * sourceVariance * preLeak * preLeak;
            chroma.temporalBlockCount[bin] = 10;
        }
    }
    expect(apply_chroma_leak_closure(local, qvbr, 100, true),
        "local chroma closure accepts paired plane coverage");
    for (int bin = 0; bin < 2; ++bin) {
        const double preLeak = bin ? 0.60 : 0.20;
        const double postLeak = std::max(0.0, preLeak - theta);
        const double expected = sourceVariance * (1.0 - postLeak * postLeak);
        expectNear(local.plane[1].binVarSum[bin]
            / local.plane[1].binBlockCount[bin], expected, 1e-9,
            "local chroma closure follows per-bin leak");
    }

    FilmGrainGpuStats missingPlane = global;
    missingPlane.plane[2] = {};
    expect(!apply_chroma_leak_closure(missingPlane, qvbr, 100, false),
        "chroma closure requires both 4:2:0 planes");
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

void testAsymmetricChromaFallsBackToLumaOnly() {
    FilmGrainGpuStats stats = {};
    fillWhitePlane(stats.plane[0], 6.0, false);
    // A 4:2:0 AV1 stream must apply grain to both chroma planes or neither.
    // Reproduce the production failure where Cb was unsolvable but Cr was
    // valid: emitting numCbPoints=0 with numCrPoints>0 makes a non-conformant
    // frame header which dav1d rejects.
    fillWhitePlane(stats.plane[2], 2.0, true);
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diag;
    expect(build_film_grain_params(stats, 8, true, true, params, diag),
        "asymmetric chroma keeps luma model");
    expect(params.numYPoints == 14, "asymmetric chroma keeps luma points");
    expect(params.numCbPoints == 0 && params.numCrPoints == 0,
        "asymmetric chroma is disabled as a pair");
    expect(params.cbMult == 0 && params.crMult == 0,
        "asymmetric chroma index mults stay disabled");
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

void testStrengthLut() {
    FilmGrainGpuStats stats = {};
    fillWhitePlane(stats.plane[0], 6.0, false);
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
    NVEncFilmGrainDiagnostics diag;
    expect(build_film_grain_params(stats, 8, false, true, params, diag), "lut base solves");
    float lut[FGS_STRENGTH_LUT_SIZE];
    build_strength_lut(params, 8, lut);
    expectNear(lut[32], 6.0, 0.4, "lut recovers flat sigma (mid)");
    expectNear(lut[200], 6.0, 0.4, "lut recovers flat sigma (high)");
    // 10-bit: the same 8-bit-domain curve scales to native code values
    build_strength_lut(params, 10, lut);
    expectNear(lut[128], 24.0, 1.6, "lut scales to 10-bit code values");
    NV_ENC_FILM_GRAIN_PARAMS_AV1 off = {};
    build_strength_lut(off, 10, lut);
    expect(lut[64] == 0.0f, "lut is zero with grain disabled");
}

} // namespace

int main() {
    testStratifiedSampling();
    testSourceCorrelationRegularizer();
    testSourceTemplateGain();
    testSourceModelResidualFallback();
    testTemporalLeakClosure();
    testChromaTemporalLeakClosure();
    testWhiteLuma();
    testRampLuma();
    testChromaCorrelationClamp();
    testSingularChromaFallsBackToLumaOnly();
    testAsymmetricChromaFallsBackToLumaOnly();
    testParamsClose();
    testEvalScalingCurve();
    testStrengthLut();
    if (failures) {
        std::cerr << failures << " solver test(s) failed\n";
        return 1;
    }
    std::cout << "all film grain solver tests passed\n";
    return 0;
}
