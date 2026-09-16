#include <cstdlib>
#include <iostream>
#include <limits>
#include <random>
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

    // Total source variance is separate evidence. A thin near-white light
    // with roughly one code of source noise must not inherit fourteen codes
    // of synthesis from a neighboring textured wall. Clipped luma never
    // supplies a chroma-noise estimate to the quiet guard above.
    fgsmodel::FilmGrainSourceVarianceGuard variance;
    require(variance.observe(234.0, 0.977, 13.865, 8, 8) < 0.15,
        "thin bright source region received excessive synthesis");
    require(variance.observe(128.0, 2.0, 12.0, 8, 8) < 0.3,
        "non-flat source variance did not bound gross synthesis");
    const auto conflicts = variance.conflictingBlocks;
    for (double sigma : {0.0, 0.3, 1.0, 3.0, 8.0, 20.0}) {
        require(variance.observe(128.0, sigma, sigma, 8, 8) == 1.0,
            "matching genuine grain was capped");
        require(variance.observe(128.0, sigma, 1.5*sigma + 0.5, 8, 8) == 1.0,
            "small-region sampling uncertainty was capped");
    }
    require(variance.observe(234.0, 0, 20, 7, 8) == 1.0
        && variance.observe(234.0, 0, 20, 8, 7) == 1.0,
        "undersized edge region constrained the model");
    require(variance.conflictingBlocks == conflicts,
        "non-conflicting source observations changed diagnostics");
    fgsmodel::FilmGrainSourceVarianceGuard invalidVariance;
    invalidVariance.observe(100, std::numeric_limits<double>::quiet_NaN(), 5, 8, 8);
    require(invalidVariance.invalid, "non-finite source variance was accepted");

    // A textured region may straddle a steep grain-strength peak while its
    // average lies on the low shoulder. Its actual pixels still receive the
    // peak, including a small reconstruction margin outside source values.
    float strengths[256] = {};
    const uint8_t peakValues[] = {0, 100, 104, 108, 255};
    for (int x = 100; x <= 108; ++x)
        strengths[x] = static_cast<float>(12 - 3 * std::abs(x - 104));
    const double hiddenPeak = fgsmodel::film_grain_range_peak(strengths, peakValues, 5, 98, 106);
    require(hiddenPeak == 12 && strengths[102] == 6,
        "enclosed strength peak was reduced to the region mean");
    require(variance.observe(102, 3, hiddenPeak, 8, 8) < 0.5
        && variance.observe(102, 3, strengths[102], 8, 8) == 1,
        "range peak did not expose the mean-only source-support gap");
    require(fgsmodel::film_grain_range_peak(strengths, peakValues, 5, 101, 102) == 6,
        "range endpoint interpolation was omitted");
    require(fgsmodel::film_grain_range_peak(strengths, peakValues, 5, 20, 30) == 0,
        "unrelated grain strength escaped its interval");

    for (double bad : {-1.0, std::numeric_limits<double>::infinity(),
                       std::numeric_limits<double>::quiet_NaN()}) {
        FilmGrainQuietSourceGuard invalid;
        invalid.observe(2, 100, 0, bad);
        require(invalid.needsSource(), "invalid prediction cleared source");
    }
    fgsmodel::FilmGrainSourceCaps caps;
    const uint8_t values[] = {0, 64, 128, 192, 255};
    uint8_t scales[] = {64, 64, 64, 64, 64};
    caps.preserveCurveInterval(0, values, 5, 90, 100);
    require(caps.lowerCurve(0, values, scales, 5), "source interval not protected");
    require(scales[0] == 64 && scales[1] == 0 && scales[2] == 0
        && scales[3] == 64 && scales[4] == 64, "protection escaped its bracketing knots");
    require(caps.gain(1, 90) == 1, "luma protection disabled unrelated chroma");
    for (int i = 0; i < 100; ++i) caps.advance(false);
    require(caps.gain(0, 90) == 0, "stale fits released source protection");
    for (int i = 0; i < caps.holdFrames; ++i) caps.advance(true);
    require(caps.gain(0, 90) == 0, "source hold ended early");
    caps.advance(true);
    require(caps.gain(0, 90) == 1.0/caps.rampFrames, "source release flashed to full strength");
    caps.preserveCurveInterval(0, values, 5, 90, 100);
    require(caps.gain(0, 90) == 0, "new conflict did not stop release");
    for (int i = 0; i < caps.holdFrames + caps.rampFrames + 100; ++i) caps.advance(true);
    require(caps.gain(0, 90) == 1, "source protection never released");
    caps.preserveCurveInterval(2, values, 5, 0, 0);
    require(caps.gain(2, 0) == 0 && caps.gain(2, 192) == 1, "endpoint protection escaped its range");
    caps.reset();
    require(caps.gain(2, 0) == 1, "explicit reset retained source constraints");

    // A narrow clean foreground must not erase a broad noisy background just
    // because the old fit had no knot near that foreground's brightness.
    uint8_t localValues[14] = {0, 64, 128, 192, 255};
    uint8_t localScales[14] = {64, 64, 64, 64, 64};
    caps.preserveRange(0, 96, 100);
    bool changed = false;
    const auto localCount = caps.refitCurve(0, localValues, localScales, 5, 14, changed);
    require(changed && localCount <= 14, "local envelope did not fit syntax limits");
    for (int x = 96; x <= 100; ++x)
        require(caps.lookup(localValues, localScales, localCount, x) == 0, "local protection overshot");
    require(caps.lookup(localValues, localScales, localCount, 80) == 64
        && caps.lookup(localValues, localScales, localCount, 120) == 64,
        "narrow source protection erased unrelated brightness levels");
    caps.preserveRange(1, 90, 110, .3);
    for (int i = 0; i < 100; ++i) caps.advance(true);
    require(caps.gain(1, 100) == 1, "fractional source cap overshot full recovery");

    // Random, disjoint protected regions exercise constrained refitting at
    // both syntax capacities. Compare every normative LUT entry, not merely
    // the output knots, including one-code intervals and negative slopes.
    std::mt19937 rng(20260912);
    for (int trial = 0; trial < 600; ++trial) {
        caps.reset();
        const int capacity = trial % 2 ? 10 : 14;
        uint8_t xv[14], yv[14], originalX[14], originalY[14];
        for (int i = 0; i < capacity; ++i) {
            xv[i] = originalX[i] = static_cast<uint8_t>(255 * i / (capacity - 1));
            yv[i] = originalY[i] = static_cast<uint8_t>(rng() % 256);
        }
        for (int j = 0; j < 1 + trial % 10; ++j) {
            const int left = rng() % 256;
            caps.preserveRange(0, left, std::min(255, left + static_cast<int>(rng() % 20)), (rng() % 5) / 5.0);
        }
        changed = false;
        const auto count = caps.refitCurve(0, xv, yv, capacity, capacity, changed);
        require(count >= 2 && count <= static_cast<uint32_t>(capacity), "invalid refit point count");
        for (uint32_t i = 1; i < count; ++i) require(xv[i] > xv[i-1], "unordered output knots");
        for (int x = 0; x < 256; ++x) {
            const int ceiling = static_cast<int>(std::floor(caps.lookup(originalX, originalY, capacity, x) * caps.gain(0, x)));
            const int actual = caps.lookup(xv, yv, count, x);
            require(actual >= 0 && actual <= ceiling, "normative scaling lookup exceeded source envelope");
        }
    }
    std::cout << "quiet source guard and curve protection tests passed\n";
}
