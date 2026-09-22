// Native AV1 lookup: integer rounding is part of the candidate being tested.
#include <array>
#include <cassert>
#include <iostream>
#include "NVEncFilmGrainScaling.h"
#include "native_scaling_vectors.h"

int main() {
    using fgsmodel::FilmGrainScalingLut;
    FilmGrainScalingLut lut;
    unsigned value = 999;
    assert(!lut.lookup(0, value) && value == 0);
    for (const auto& vector : nativeScalingVectors) {
        assert(lut.build(vector.values.data(), vector.strengths.data(), vector.count, vector.depth));
        uint64_t hash = 14695981039346656037ULL;
        for (unsigned code = 0; code < (1U << vector.depth); ++code) {
            assert(lut.lookup(code, value)); hash ^= value; hash *= 1099511628211ULL;
        }
        assert(hash == vector.hash);
    }
    const uint8_t x[] = {0, 8, 16, 255}, y[] = {0, 1, 0, 0};
    for (unsigned depth : {8U, 10U, 12U}) {
        assert(lut.build(x, y, 4, depth) && lut.valid() && lut.bitDepth() == depth);
        const unsigned scale = 1U << (depth - 8);
        assert(lut.lookup(3 * scale, value) && value == 0);
        assert(lut.lookup(4 * scale, value) && value == 1); // Positive half rounds up.
        assert(lut.lookup(12 * scale, value) && value == 1); // Negative half rounds toward +infinity.
        assert(lut.lookup(13 * scale, value) && value == 0);
        assert(!lut.lookup(1U << depth, value) && value == 0);
        if (depth != 8) {
            // First stage has 0 at code 3 and 1 at code 4. The native second
            // stage changes at 3.5, not at the unrounded segment's code 4.
            assert(lut.lookup(3 * scale + scale / 2, value) && value == 1);
            assert(lut.lookup(3 * scale + scale / 2 - 1, value) && value == 0);
        }
        const uint8_t endpointX[] = {2, 254}, endpointY[] = {37, 129};
        assert(lut.build(endpointX, endpointY, 2, depth));
        assert(lut.lookup(0, value) && value == 37);
        assert(lut.lookup((1U << depth) - 1, value) && value == 129);
        assert(lut.build(nullptr, nullptr, 0, depth));
        for (unsigned code = 0; code < (1U << depth); ++code)
            assert(lut.lookup(code, value) && value == 0);
        assert(lut.build(endpointX, endpointY, 1, depth));
        for (unsigned code = 0; code < (1U << depth); ++code)
            assert(lut.lookup(code, value) && value == 37);
    }
    const uint8_t duplicate[] = {3, 3}, decreasing[] = {4, 3};
    for (const uint8_t* bad : {duplicate, decreasing}) {
        assert(!lut.build(bad, y, 2, 10) && !lut.valid());
        value = 999; assert(!lut.lookup(12, value) && value == 0);
    }
    assert(!lut.build(x, y, 15, 10));
    assert(!lut.build(nullptr, y, 4, 10));
    assert(!lut.build(x, nullptr, 4, 10));
    for (unsigned depth : {0U, 7U, 9U, 11U, 13U, 32U})
        assert(!lut.build(x, y, 4, depth) && !lut.valid());
    std::cout << "Native scaling: both integer interpolation stages, endpoints, weak curves and invalidation passed\n";
}
