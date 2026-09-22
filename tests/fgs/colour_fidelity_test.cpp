#include "NVEncFilmGrainColourFidelity.h"
#include <iostream>
#include <stdexcept>
using namespace fgsmodel;
static void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
static FilmGrainColourMoments reference() {
    FilmGrainColourMoments r;
    r.blocks = r.jointlySupportedBlocks = 20; r.observations = 20*676; r.cohortId = 123;
    r.covariance = {{4, .2, -.3, .2, 2, .4, -.3, .4, 1}};
    for (unsigned i = 0; i < 49; ++i) r.cbCrLag[i] = i == 24 ? .4 : .02;
    for (auto& value : r.covariance) value *= r.observations;
    for (auto& value : r.cbCrLag) value *= r.observations;
    return r;
}
int main() {
    try {
        const auto source = reference();
        require(!film_grain_colour_fidelity(source, source).needsSource(), "identical total reconstruction rejected");
        auto actual = source;
        actual.covariance[5] = actual.covariance[7] = -.4*source.observations;
        actual.cbCrLag[24] = actual.covariance[5];
        auto r = film_grain_colour_fidelity(source, actual);
        require(r.valid && r.maximumVarianceError == 0 && r.pairError[0] == 0 && r.pairError[1] == 0
            && r.needsSource(), "matched per-plane/Y-C statistics hid wrong Cb/Cr coupling");
        actual = source; actual.cbCrLag[0] = .5*source.observations;
        r = film_grain_colour_fidelity(source, actual);
        require(r.valid && r.maximumVarianceError == 0 && r.maximumCovarianceError == 0 && r.needsSource(),
            "zero-lag checks hid spatial colour cross-correlation");
        for (unsigned p = 0; p < 3; ++p) {
            actual = source; actual.covariance[p*3+p] *= 1.081;
            require(film_grain_colour_fidelity(source, actual).needsSource(), "component excess hidden by average");
        }
        actual = source; actual.cohortId++;
        require(!film_grain_colour_fidelity(source, actual).valid, "different source coordinates accepted");
        actual = source; --actual.jointlySupportedBlocks;
        require(!film_grain_colour_fidelity(source, actual).valid, "unsupported other colour admitted");
        actual = source; actual.cbCrLag[24] = 0;
        require(!film_grain_colour_fidelity(source, actual).valid, "inconsistent centre lag accepted");
        actual = source; actual.covariance[1] = std::numeric_limits<double>::quiet_NaN();
        require(!film_grain_colour_fidelity(source, actual).valid, "nonfinite moments accepted");
        actual = source; actual.cbCrLag[48] = std::numeric_limits<double>::infinity();
        require(!film_grain_colour_fidelity(source, actual).valid, "nonfinite lag accepted");
        actual = source; actual.covariance[1] = actual.covariance[3] = 100*source.observations;
        require(!film_grain_colour_fidelity(source, actual).valid, "non-PSD observation accepted");
        auto quiet = source;
        for (unsigned p = 0; p < 3; ++p) quiet.covariance[p*3+2] = quiet.covariance[2*3+p] = 0;
        quiet.cbCrLag.fill(0);
        require(!film_grain_colour_fidelity(quiet, quiet).needsSource(), "exact quiet reconstruction rejected");
        actual = quiet; actual.covariance[8] = 1e-10;
        require(film_grain_colour_fidelity(quiet, actual).needsSource(), "energy added to zero source passed");
        actual = quiet; actual.cbCrLag[0] = 1e-10;
        require(film_grain_colour_fidelity(quiet, actual).needsSource(), "new cross-correlation with zero source passed");
        quiet.cbCrLag[0] = 1e-13;
        require(!film_grain_colour_fidelity(quiet, quiet).valid, "impossible quiet reference accepted");
        actual = source; actual.cbCrLag[0] = 1e200;
        require(!film_grain_colour_fidelity(actual, actual).valid, "impossible moment range accepted");
        require(film_grain_colour_fidelity(source, source).needsSource(std::numeric_limits<double>::quiet_NaN()),
            "invalid quality threshold bypassed rejection");
        // An aggregate with 19/20 common tiles cannot be repaired by dividing
        // all 20 tiles' moments by 19. Recollect the actual intersection.
        FilmGrainCollectGroup group{};
        group.blocks = 20; group.observations = 20*676; group.otherColourSupportedBlocks = 19;
        constexpr unsigned colour = 3*FGS_COLLECT_MATRIX, lag = colour+3*9;
        std::copy(source.covariance.begin(), source.covariance.end(), group.moments+colour);
        std::copy(source.cbCrLag.begin(), source.cbCrLag.end(), group.moments+lag);
        FilmGrainColourMoments s, b;
        require(!film_grain_colour_source_base(group, 123, s, b) && s.cohortId == 0, "mixed-cohort aggregate accepted");
        group.otherColourSupportedBlocks = 20;
        require(film_grain_colour_source_base(group, 123, s, b), "common cohort rejected");
        require(s.covariance == source.covariance && s.cbCrLag == source.cbCrLag && b.covariance == std::array<double, 9>{},
            "collector source/base/lag offsets incorrect");
        group.observations--;
        require(!film_grain_colour_source_base(group, 123, s, b), "partial observation cohort accepted");
        std::cout << "colour reconstruction: pair, spatial, support, quiet and invalid-evidence checks passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
