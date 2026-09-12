#include <cstdlib>
#include <iostream>
#include <algorithm>
// NVEnc common headers define this legacy macro after standard headers.
#define clamp(x, lo, hi) (((x) <= (hi)) ? (((x) >= (lo)) ? (x) : (lo)) : (hi))
#include "NVEncFilmGrainRecovery.h"
#undef clamp

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
    require(recovery.gain() == 1.0 / FilmGrainSynthesisRecovery::rampFrames,
        "first post-recovery frame resumed at full strength");
    // Lost Tapes 01x05 at 90.257: precisely enough accepted evidence to exit
    // recovery, then another rejection. Its first frame must remain weak.
    require(!recovery.allow(false, false, false) && recovery.gain() == 0.0,
        "new rejection retained an old ramp");
    for (int i = 0; i < FilmGrainSynthesisRecovery::recoveryFrames - 1; ++i)
        require(!recovery.allow(true, true, true), "second recovery skipped evidence");
    require(recovery.allow(true, true, true), "second recovery never started");
    const double firstGain = recovery.gain();
    require(recovery.allow(true, false, true) && recovery.gain() == firstGain,
        "stale fit increased recovery strength");
    for (int i = 2; i <= FilmGrainSynthesisRecovery::rampFrames; ++i) {
        require(recovery.allow(true, true, true), "settled recovery interrupted");
        require(recovery.gain() == static_cast<double>(i) / FilmGrainSynthesisRecovery::rampFrames,
            "recovery ramp skipped a step");
    }
    // Luma may already retain source residual; chroma uses retained=0.
    // Verify the coupled base/synthesis variance rather than a curve alone.
    for (double retained : {0.0, 0.3, 0.8, 0.999, 1.0}) {
        for (int i = 0; i <= FilmGrainSynthesisRecovery::rampFrames; ++i) {
            const double gain = static_cast<double>(i) / FilmGrainSynthesisRecovery::rampFrames;
            const double q = fgsmodel::film_grain_recovery_source_blend(gain, retained);
            const double combined = retained + q * (1.0 - retained);
            require(q >= 0.0 && q <= 1.0, "invalid recovery blend");
            require(std::abs(combined * combined + gain * gain * (1.0 - retained * retained) - 1.0) < 1e-12,
                "recovery blend changed modeled residual variance");
        }
    }
    // An explicit discontinuity starts independent evidence; repeated model
    // history resets are not calls to this reset operation.
    recovery.preserveSource();
    recovery.reset();
    require(recovery.allow(true, true, false), "explicit reset retained old fallback");
    require(recovery.gain() == 1.0, "explicit reset retained an old ramp");
    for (int i = 0; i < 1000000; ++i)
        require(recovery.allow(true, true, true), "long stable run changed");
    std::cout << "synthesis recovery tests passed\n";
}
