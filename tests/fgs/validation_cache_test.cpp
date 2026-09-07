#include <array>
#include <cstdint>
#include <iostream>
#include "NVEncFilmGrainValidationCache.h"

int main() {
    fgsmodel::FilmGrainValidationCache cache;
    std::array<uint8_t, 24> coefficients{};
    coefficients.fill(128);
    if (!cache.check(coefficients.data(), 3, 7)) return 1;
    if (!cache.check(coefficients.data(), 3, 7) || cache.hits() != 1) return 2;
    // Two flips of bit 6 cancel in FNV modulo 128: this unsafe
    // unit-pole model and the white-grain model occupy the SAME cache slot.
    // Different full keys must still produce their different answers.
    coefficients[0] = coefficients[23] = 192;
    if (cache.check(coefficients.data(), 3, 7)) return 7;
    coefficients[0] = coefficients[23] = 128;
    if (!cache.check(coefficients.data(), 3, 7)) return 8;
    // Alter one quantized tap after a cached acceptance: the new rejection must
    // not inherit the old result. Changing shift changes the physical model.
    coefficients[23] = 192;
    if (cache.check(coefficients.data(), 3, 6)) return 3;
    if (!cache.check(coefficients.data(), 3, 8)) return 4;
    if (cache.check(nullptr, 3, 7) || cache.check(coefficients.data(), 4, 7)
        || cache.check(coefficients.data(), 3, 5)) return 5;
    // Exercise eviction/collisions and all lag/shift keys against the uncached
    // mathematical policy. Include strong coefficients and their perturbations.
    uint32_t random = 0x4214b813;
    for (unsigned n = 0; n < 1600; ++n) {
        for (auto& c : coefficients) {
            random ^= random << 13; random ^= random >> 17; random ^= random << 5;
            c = static_cast<uint8_t>(128 + int(random % 61) - 30);
        }
        const unsigned lag = n % 4, shift = 6 + (n / 4) % 4;
        const bool expected = fgsmodel::film_grain_ar_synthesis_safe(coefficients.data(), lag, shift);
        if (cache.check(coefficients.data(), lag, shift) != expected
            || cache.check(coefficients.data(), lag, shift) != expected) return 6;
    }
    std::cout << "Exact-key grain validation cache passed: " << cache.hits()
              << " hits, " << cache.misses() << " misses\n";
}
