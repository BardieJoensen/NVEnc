// Independent fine-grid amplitude evidence must catch omissions in a coarse fit.
#include <cassert>
#include <cmath>
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
