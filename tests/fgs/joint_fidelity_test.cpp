// Analytic controls for a regression fit that passes while synthesis fails.
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainJointFidelity.h"
using namespace fgsmodel;
constexpr size_t N = FGS_JOINT_VARIABLES;
static FilmGrainJointTarget identity() {
    FilmGrainJointTarget c;c.valid = true;
    for (size_t i = 0; i < N; ++i) c.covariance[i*N+i] = 1.0;
    return c;
}
static void near(double a, double b) { assert(std::abs(a-b) < 1e-10); }
int main() {
    auto white = identity();
    auto exact = film_grain_joint_synthesis_fidelity(white, white);
    assert(exact.valid && !exact.needsSource());
    // A white predictor has only 4.17% excess error on this correlated target,
    // so an 8% regression bound accepts it. Actual white synthesis loses its
    // 0.2 correlation and must fail the separate decoded covariance check.
    auto target = white;
    target.covariance[23*N+25] = target.covariance[25*N+23] = .2;
    const auto optimum = film_grain_fit_joint_chroma(target, .25);
    assert(optimum.valid && 1.0 / optimum.innovationVariance - 1.0 < .08);
    auto wrongShape = film_grain_joint_synthesis_fidelity(target, white);
    assert(wrongShape.valid && wrongShape.needsSource());
    near(wrongShape.maximumVarianceError, 0.0);
    near(wrongShape.maximumCovarianceError, .2);
    // Equal marginal power cannot hide an incorrect sign of colour coupling.
    target = white;
    target.covariance[24*N+25] = target.covariance[25*N+24] = .45;
    auto opposite = target;
    opposite.covariance[24*N+25] = opposite.covariance[25*N+24] = -.45;
    auto wrongSign = film_grain_joint_synthesis_fidelity(target, opposite);
    assert(wrongSign.valid && wrongSign.needsSource());
    near(wrongSign.lumaChromaCovarianceError, -.9);
    // Coordinate/bit-depth units do not change normalized fidelity.
    for (size_t i = 0; i < N; ++i) for (size_t j = 0; j < N; ++j) {
        const double scale = (i == 24 ? 3.0 : 16.0) * (j == 24 ? 3.0 : 16.0);
        target.covariance[i*N+j] *= scale;
        opposite.covariance[i*N+j] *= scale;
    }
    auto scaled = film_grain_joint_synthesis_fidelity(target, opposite);
    assert(scaled.valid && scaled.needsSource());
    near(scaled.maximumCovarianceError, wrongSign.maximumCovarianceError);
    // Test every diagonal, including a neighbour that is not current C/Y.
    auto wrongPower = white;wrongPower.covariance[0] = 1.2;
    auto energy = film_grain_joint_synthesis_fidelity(white, wrongPower);
    assert(energy.valid && energy.needsSource());
    near(energy.maximumVarianceError, .2);near(energy.chromaVarianceError, 0.0);
    auto small = white;small.covariance[25*N+25] = 1.04;
    small.covariance[24*N+25] = small.covariance[25*N+24] = -.03;
    assert(!film_grain_joint_synthesis_fidelity(white, small).needsSource());
    for (int defect = 0; defect < 6; ++defect) {
        auto bad = white;
        if (defect == 0) bad.valid = false;
        if (defect == 1) bad.covariance[0] = -1.;
        if (defect == 2) bad.covariance[0] = std::numeric_limits<double>::infinity();
        if (defect == 3) bad.covariance[1] = .1;
        if (defect == 4) bad.covariance[1] = bad.covariance[N] = 2.;
        if (defect == 5) bad.covariance[0] = std::numeric_limits<double>::quiet_NaN();
        auto invalid = film_grain_joint_synthesis_fidelity(white, bad);
        assert(!invalid.valid && invalid.needsSource());
    }
    auto quiet = white;quiet.covariance[0] = 0.0;
    assert(!film_grain_joint_synthesis_fidelity(quiet, quiet).valid);
    for (double bad : {-.01, 1.01, std::numeric_limits<double>::quiet_NaN()}) {
        assert(exact.needsSource(bad, .08));assert(exact.needsSource(.08, bad));
    }
    std::cout << "Joint synthesis: wrong shape/sign, hidden neighbour power, units and invalid evidence passed\n";
}
