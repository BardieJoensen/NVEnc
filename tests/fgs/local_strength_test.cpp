// Independent fine-grid amplitude evidence must catch omissions in a coarse fit.
#include <cassert>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainModel.h"

using namespace fgsmodel;

static NV_ENC_FILM_GRAIN_PARAMS_AV1 constant_model() {
    NV_ENC_FILM_GRAIN_PARAMS_AV1 p = {};
    p.applyGrain = 1;
    p.numYPoints = 2;
    p.pointYValue[0] = 0;
    p.pointYValue[1] = 255;
    p.pointYScaling[0] = p.pointYScaling[1] = 48; // sigma 6 at scaling shift 8
    return p;
}

int main() {
    for (const int bits : {8, 10}) {
        const double ds = 1 << (bits - 8);
        auto p = constant_model();
        FilmGrainLocalStrengthStats local = {};
        local.blocks[48] = 8;
        local.varianceSum[48] = 8 * 36 * ds * ds;
        local.intensitySum[48] = 8 * 48.25 * ds;
        assert(!film_grain_local_strength_fidelity(local, p, bits, 1).needsSource());

        // A local filter can retain more source grain than the model's flat
        // patches. Compare the total predicted energy, not just the removed
        // residual; the latter falsely rejected valid sharp grain curves.
        auto retained = local;
        retained.varianceSum[48] = 8 * 100 * ds * ds;
        retained.baseVarianceSum[48] = 8 * 64 * ds * ds;
        assert(!film_grain_local_strength_fidelity(retained, p, bits, 1).needsSource(.10, .25));
        retained.covarianceSum[48] = 8 * 80 * ds * ds;
        const auto blended = film_grain_local_strength_fidelity(retained, p, bits, 1, .5);
        assert(blended.valid && std::abs(blended.modeledSigma[48] - std::sqrt(108.0)) < 1e-6);
        assert(!blended.needsSource(.10, .25));
        assert(!film_grain_local_strength_fidelity(retained, p, bits, 1, 1).needsSource(.01, .01));
        assert(film_grain_local_strength_fidelity(retained, p, bits, 1, -1).needsSource());
        assert(film_grain_local_strength_fidelity(retained, p, bits, 1, 1.1).needsSource());
        auto invalidCovariance = retained;
        invalidCovariance.covarianceSum[48] = 8 * 1000 * ds * ds;
        assert(film_grain_local_strength_fidelity(invalidCovariance, p, bits, 1).needsSource());
        retained.baseVarianceSum[48] = 8 * 150 * ds * ds;
        assert(film_grain_local_strength_fidelity(retained, p, bits, 1).needsSource());
        retained.baseVarianceSum[48] = -1;
        assert(film_grain_local_strength_fidelity(retained, p, bits, 1).needsSource());

        // Correlated filtering leaves source grain in the base. The removed
        // residual variance (9) understates independent synthesis needed (27).
        FilmGrainGpuStats residualModel = {};
        residualModel.plane[0].binBlockCount[10] = 8;
        residualModel.plane[0].binVarSum[10] = 8 * 9 * ds * ds;
        residualModel.plane[0].binLumaSum[10] = 8 * 128 * ds;
        residualModel.plane[0].intensityBlocks = 8;
        FilmGrainLocalStrengthStats total = {};
        total.blocks[128] = total.correlatedBlocks[128] = 8;
        total.varianceSum[128] = 8 * 36 * ds * ds;
        total.baseVarianceSum[128] = 8 * 9 * ds * ds;
        total.covarianceSum[128] = 8 * 18 * ds * ds;
        total.intensitySum[128] = 8 * 128 * ds;
        const auto target = local_strength_targets(residualModel, total, bits, 0);
        assert(std::abs(target.plane[0].binVarSum[10] - 8 * 27 * ds * ds) < 1e-8);
        // Four independent coarse observations remain sufficient when
        // their measured means straddle two adjacent fine brightness bins.
        auto spread = total;
        for (const int x : {128, 129}) {
            spread.blocks[x] = spread.correlatedBlocks[x] = 2;
            spread.varianceSum[x] = 2 * 36 * ds * ds;
            spread.baseVarianceSum[x] = 2 * 9 * ds * ds;
            spread.covarianceSum[x] = 2 * 18 * ds * ds;
            spread.intensitySum[x] = 2 * x * ds;
        }
        const auto pooled = local_strength_targets(residualModel, spread, bits, 0);
        assert(pooled.plane[0].binBlockCount[10] == 4);
        assert(std::abs(pooled.plane[0].binVarSum[10] - 4 * 27 * ds * ds) < 1e-8);
        total.correlatedBlocks[128] = 0;
        const auto oldTarget = local_strength_targets(residualModel, total, bits, 0);
        assert(std::memcmp(&oldTarget, &residualModel, sizeof(oldTarget)) == 0);
        assert(film_grain_strength_fidelity(local_strength_targets(residualModel, total, bits, 1), p, bits, {1, 1, 1}).needsSource());

        // A coarse model can fit every sampled block while entirely missing
        // weaker grain at a nearby brightness, even within the same old bin.
        FilmGrainGpuStats coarse = {};
        const int bin = 3;
        coarse.plane[0].binBlockCount[bin] = 8;
        coarse.plane[0].binVarSum[bin] = 8 * 36 * ds * ds;
        coarse.plane[0].binLumaSum[bin] = 8 * 48.25 * ds;
        coarse.plane[0].intensityBlocks = 8;
        assert(!film_grain_strength_fidelity(coarse, p, bits, {1, 1, 1}).needsSource());
        local.blocks[50] = 8;
        local.varianceSum[50] = 8 * 4 * ds * ds;
        local.intensitySum[50] = 8 * 50 * ds;
        assert(film_grain_local_strength_fidelity(local, p, bits, 1).needsSource());
        auto quiet = local;
        quiet.varianceSum[50] = 0;
        assert(film_grain_local_strength_fidelity(quiet, p, bits, 1).needsSource());

        // Independent observations can repair a representable noisy/quiet
        // curve without discarding the complete source picture. AR and
        // chroma parameters remain byte-identical after a luma-only refit.
        auto recovered = p;
        assert(refit_local_strength(quiet, bits, 1, 0, recovered));
        assert(!film_grain_local_strength_fidelity(quiet, recovered, bits, 1).needsSource(.10, .25));
        auto unchanged = recovered;
        unchanged.numYPoints = p.numYPoints;
        std::memcpy(unchanged.pointYValue, p.pointYValue, sizeof(p.pointYValue));
        std::memcpy(unchanged.pointYScaling, p.pointYScaling, sizeof(p.pointYScaling));
        assert(std::memcmp(&unchanged, &p, sizeof(p)) == 0);

        // A single quiet intensity constrains only its small plateau. Keep
        // unobserved intensities intact, including a fractional HDR mean.
        for (const double x : {16.0, 49.5}) {
            FilmGrainLocalStrengthStats one = {};
            const int bin = static_cast<int>(std::round(x));
            one.blocks[bin] = 8;
            one.intensitySum[bin] = 8 * x * ds;
            auto candidate = p;
            assert(refit_local_strength(one, bits, 1, 0, candidate));
            assert(!film_grain_local_strength_fidelity(one, candidate, bits, 1).needsSource(.10, .25));
            for (const double outside : {0.0, 15.0, 51.0, 128.0, 255.0})
                assert(std::abs(eval_scaling_curve(candidate.pointYValue, candidate.pointYScaling, candidate.numYPoints, outside) - 48.0) < 1e-8);
        }
        // Per-component lookup must use its own curve, not the luma curve.
        auto colour = p;
        colour.numCbPoints = colour.numCrPoints = 2;
        colour.pointCbValue[1] = colour.pointCrValue[1] = 255;
        colour.pointCbScaling[0] = colour.pointCbScaling[1] = 16;
        auto coloured = local;
        coloured.blocks[50] = 0;
        coloured.varianceSum[48] = 8 * 4 * ds * ds;
        assert(!film_grain_local_strength_fidelity(coloured, colour, bits, 1, 0, 1).needsSource());
        assert(film_grain_local_strength_fidelity(coloured, colour, bits, 1).needsSource());
        assert(film_grain_local_strength_fidelity(coloured, colour, bits, 1, 0, 3).needsSource());
        colour.arCoeffLag = FGS_AR_LAG;
        colour.arCoeffShiftMinus6 = 3;
        colour.arCoeffsCbPlus128[FGS_AR_COEFFS] = 128;
        FilmGrainGpuStats independent = {};
        auto& c = independent.plane[1];
        c.observations = 2048;
        c.binBlockCount[8] = 32;
        c.binVarSum[8] = 32 * 9 * ds * ds;
        c.ata[tri_index(FGS_AR_COEFFS_CHROMA, FGS_AR_COEFFS, FGS_AR_COEFFS)] = 2048 * 9 * ds * ds;
        assert(can_restore_chroma_component(independent, colour, 1));
        c.atb[0] = 2048 * 9 * ds * ds / 2;
        assert(!can_restore_chroma_component(independent, colour, 1));
        c.atb[0] = 0;
        c.atb[FGS_AR_COEFFS] = 2048 * 9 * ds * ds / 2;
        assert(!can_restore_chroma_component(independent, colour, 1));
        c.atb[FGS_AR_COEFFS] = 0;
        colour.arCoeffsCbPlus128[FGS_AR_COEFFS] = 200;
        assert(!can_restore_chroma_component(independent, colour, 1));
        colour.arCoeffsCbPlus128[FGS_AR_COEFFS] = 128;
        c.observations = 128;
        assert(!can_restore_chroma_component(independent, colour, 1));

        // Twenty alternating strengths cannot fit this point budget. A
        // failed retry must leave the accepted model untouched.
        FilmGrainLocalStrengthStats overBudget = {};
        for (int i = 0; i < 20; ++i) {
            const int x = 20 + 11 * i;
            overBudget.blocks[x] = 8;
            overBudget.varianceSum[x] = (i % 2 ? 0 : 36) * 8 * ds * ds;
            overBudget.intensitySum[x] = x * 8 * ds;
        }
        recovered = p;
        assert(!refit_local_strength(overBudget, bits, 1, 0, recovered));
        assert(std::memcmp(&recovered, &p, sizeof(p)) == 0);

        // Most pixels may have normal grain while a small quiet area shares
        // the same brightness. The average fits; its quiet population does
        // not. One global curve cannot synthesize both at that brightness.
        FilmGrainLocalStrengthStats populations = {};
        populations.blocks[128] = 44;
        populations.varianceSum[128] = 40 * 36 * ds * ds;
        populations.intensitySum[128] = 44 * 128 * ds;
        populations.blocks[200] = 8;
        populations.varianceSum[200] = 8 * 36 * ds * ds;
        populations.intensitySum[200] = 8 * 200 * ds;
        assert(!film_grain_local_strength_fidelity(populations, p, bits, 1).needsSource());
        const int quietSlot = FGS_LOCAL_STRENGTH_BINS + 128;
        populations.blocks[quietSlot] = 4;
        populations.intensitySum[quietSlot] = 4 * 128 * ds;
        assert(film_grain_local_strength_fidelity(populations, p, bits, 1).needsSource());
        assert(!refit_local_strength(populations, bits, 1, 0, recovered));
        assert(std::memcmp(&recovered, &p, sizeof(p)) == 0);
        assert(!refit_local_strength(quiet, bits, 1, 1, recovered));
        auto invalidQuiet = quiet;
        invalidQuiet.baseVarianceSum[50] = -1;
        assert(!refit_local_strength(invalidQuiet, bits, 1, 0, recovered));
        assert(std::memcmp(&recovered, &p, sizeof(p)) == 0);

        // A representable sharp curve passes using measured coordinates.
        p.numYPoints = 4;
        p.pointYValue[0] = 0; p.pointYValue[1] = 49;
        p.pointYValue[2] = 50; p.pointYValue[3] = 255;
        p.pointYScaling[0] = p.pointYScaling[1] = 48;
        p.pointYScaling[2] = p.pointYScaling[3] = 16;
        assert(!film_grain_local_strength_fidelity(local, p, bits, 1).needsSource(.10, .25));
        p.applyGrain = 0;
        assert(film_grain_local_strength_fidelity(local, p, bits, 1).needsSource());

        // Evidence must be valid before it can participate in acceptance.
        p = constant_model();
        auto invalid = local;
        invalid.varianceSum[48] = -1;
        assert(!film_grain_local_strength_fidelity(invalid, p, bits, 1).valid);
        invalid = local;
        invalid.intensitySum[48] = std::numeric_limits<double>::quiet_NaN();
        assert(film_grain_local_strength_fidelity(invalid, p, bits, 1).needsSource());
        invalid = local;
        invalid.intensitySum[48] = 8 * 80 * ds;
        assert(!film_grain_local_strength_fidelity(invalid, p, bits, 1).valid);
        assert(film_grain_local_strength_fidelity(local, p, bits, 0).needsSource());
        assert(film_grain_local_strength_fidelity(local, p, bits,
            std::numeric_limits<double>::infinity()).needsSource());

        // Unsupported sparse evidence stays explicitly below the threshold.
        local.blocks[50] = 3;
        local.varianceSum[50] = 3 * 4 * ds * ds;
        local.intensitySum[50] = 3 * 50 * ds;
        assert(!film_grain_local_strength_fidelity(local, p, bits, 1).needsSource());
        for (int i = 0; i < 2; ++i) p.pointYScaling[i] = 24;
        assert(!film_grain_local_strength_fidelity(local, p, bits, 2).needsSource());
    }
    auto p = constant_model();
    FilmGrainLocalStrengthStats endpoint = {};
    endpoint.blocks[255] = 4;
    endpoint.varianceSum[255] = 4 * 36 * 16;
    endpoint.intensitySum[255] = 4 * 1023;
    assert(!film_grain_local_strength_fidelity(endpoint, p, 10, 1).needsSource());
    assert(film_grain_local_strength_fidelity(endpoint, p, 16, 1).needsSource());
    std::cout << "Local strength fidelity checks passed\n";
}
