#include <cstdlib>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainSourceGuard.h"

static void require(bool value, const char *message) {
    if (!value) { std::cerr << message << '\n'; std::exit(1); }
}

int main() {
    using fgsmodel::FilmGrainQuietSourceGuard;
    FilmGrainQuietSourceGuard ordinary;
    for (double noise : {0.0, 0.1, 0.3, 0.5, 2.0, 8.0})
        for (int plane = 0; plane < 3; ++plane)
            ordinary.observe(plane, 128.0, noise, noise);
    require(!ordinary.needsSource(), "matching source grain rejected");
    ordinary.observe(0, 128, 0, 0.25);
    require(!ordinary.needsSource(), "quarter-code uncertainty rejected");

    // Same-brightness smooth artwork must contradict a model trained only on
    // the textured background, even if thousands of other blocks fit it.
    FilmGrainQuietSourceGuard mixed;
    for (int i = 0; i < 2000; ++i) mixed.observe(0, 100, 3, 3);
    mixed.observe(0, 100, 0.1, 2.4);
    require(mixed.needsSource() && mixed.conflictingBlocks[0] == 1,
        "smooth foreground was diluted by textured background");

    // Chroma-only invented texture also matters, with no luma mismatch.
    FilmGrainQuietSourceGuard chroma;
    chroma.observe(0, 90, 2.0, 2.0);
    chroma.observe(1, 128, 0.0, 0.8);
    require(chroma.needsSource() && chroma.conflictingBlocks[1] == 1,
        "chroma-only source mismatch escaped");

    FilmGrainQuietSourceGuard clipped;
    clipped.observe(0, 16, 0, 5);
    clipped.observe(0, 235, 0, 5);
    require(!clipped.needsSource() && clipped.quietBlocks[0] == 0,
        "clipped endpoints treated as source noise evidence");

    for (double bad : {-1.0, std::numeric_limits<double>::infinity(),
                       std::numeric_limits<double>::quiet_NaN()}) {
        FilmGrainQuietSourceGuard invalid;
        invalid.observe(2, 100, 0, bad);
        require(invalid.needsSource(), "invalid prediction cleared source");
    }
    std::cout << "quiet source guard tests passed\n";
}
