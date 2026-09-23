#pragma once
#include <cstdint>

// AV1 v1.0.0 Errata 1, Annex A.3. A mapped level is not necessarily defined:
// index 23 maps to 7.3, but has no defined constraints in that revision.
// Index 31 means maximum parameters. This is a compatibility policy, not
// proof that a stream satisfies the constraints of its declared level.
struct Av1SequenceLevels {
    uint32_t seen = 0, undefined = 0;
    uint64_t fields = 0;
    bool invalid = false;
    static bool defined(int value) {
        return value == 0 || value == 1 || value == 4 || value == 5
            || value == 8 || value == 9 || (value >= 12 && value <= 19)
            || value == 31;
    }
    void observe(int operatingPoint, int value) {
        if (operatingPoint < 0 || operatingPoint > 31 || value < 0 || value > 31) {
            invalid = true;
            return;
        }
        ++fields;
        seen |= uint32_t(1) << value;
        if (!defined(value)) undefined |= uint32_t(1) << value;
    }
    bool accepted() const { return fields && !invalid && !undefined; }
};
