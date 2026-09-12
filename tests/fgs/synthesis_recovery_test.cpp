#include <cstdlib>
#include <iostream>
#include "NVEncFilmGrainRecovery.h"

static void require(bool value, const char *message) {
    if (!value) { std::cerr << message << '\n'; std::exit(1); }
}

int main() {
    using fgsmodel::FilmGrainSynthesisRecovery;
    FilmGrainSynthesisRecovery recovery;
    // Undisturbed grain retains immediate startup and ordinary model holding.
    require(recovery.allow(true, true, false), "startup changed");
    require(recovery.allow(true, false, true), "ordinary bounded hold changed");
    require(!recovery.allow(false, false, true), "rejected model emitted");

    // The reported E10 fit pattern: 42 rejected, one accepted, one rejected,
    // 11 accepted, two rejected, five accepted, one rejected. No grain flash.
    for (int run : {-42, 1, -1, 11, -2, 5, -1, 4, -1, 11, -7, 2, -9, 3,
                    -1, 9, -1, 2, -1, 1, -1, 22, -50, 6, -1, 4, -1, 1, -1}) {
        for (int i = 0; i < std::abs(run); ++i)
            require(!recovery.allow(run > 0, run > 0, true), "E10 flash returned");
    }
    // Two-on/two-off E11 alternation must never accumulate recovery credit.
    for (int i = 0; i < 200; ++i) {
        const bool good = i % 4 < 2;
        require(!recovery.allow(good, good, true), "two-frame alternation emitted");
    }
    // Losing flat blocks (E9) clears fit history, not the source-preservation
    // decision. New one-frame fits and cached fits cannot bypass probation.
    recovery.preserveSource();
    for (int i = 0; i < 100; ++i)
        require(!recovery.allow(true, true, false), "unsettled window recovered");
    for (int i = 0; i < 100; ++i)
        require(!recovery.allow(true, false, true), "stale model recovered");
    for (int i = 0; i < FilmGrainSynthesisRecovery::recoveryFrames - 1; ++i)
        require(!recovery.allow(true, true, true), "recovered before stable evidence");
    require(recovery.allow(true, true, true), "stable grain never recovered");
    require(!recovery.active() && recovery.frames() == 0, "recovery state leaked");
    // An explicit discontinuity starts independent evidence; repeated model
    // history resets are not calls to this reset operation.
    recovery.preserveSource();
    recovery.reset();
    require(recovery.allow(true, true, false), "explicit reset retained old fallback");
    for (int i = 0; i < 1000000; ++i)
        require(recovery.allow(true, true, true), "long stable run changed");
    std::cout << "synthesis recovery tests passed\n";
}
