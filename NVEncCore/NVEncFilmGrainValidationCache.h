// Bounded, exact-key memoization of the quantized synthesis policy.
// Copyright (c) 2026 NVEnc contributors. MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainStability.h"

namespace fgsmodel {

class FilmGrainValidationCache {
    struct Entry {
        std::array<uint8_t, 24> coefficients{};
        unsigned lag = 0, shift = 0;
        bool occupied = false, safe = false;
    };
    std::array<Entry, 128> entries_{};
    uint64_t hits_ = 0, misses_ = 0;
public:
    bool check(const uint8_t *coefficients, unsigned lag, unsigned shift) {
        if (!coefficients || lag > 3 || shift < 6 || shift > 9) return false;
        const unsigned count = 2 * lag * (lag + 1);
        uint32_t hash = (2166136261U ^ lag) * 16777619U;
        hash = (hash ^ shift) * 16777619U;
        for (unsigned i = 0; i < count; ++i) hash = (hash ^ coefficients[i]) * 16777619U;
        auto& entry = entries_[hash % entries_.size()];
        // A hash collision can only cause recomputation, never acceptance.
        if (entry.occupied && entry.lag == lag && entry.shift == shift
            && std::equal(coefficients, coefficients + count, entry.coefficients.begin())) {
            ++hits_;
            return entry.safe;
        }
        ++misses_;
        const bool safe = film_grain_ar_synthesis_safe(coefficients, lag, shift);
        std::copy(coefficients, coefficients + count, entry.coefficients.begin());
        entry.lag = lag; entry.shift = shift; entry.safe = safe; entry.occupied = true;
        return safe;
    }
    uint64_t hits() const { return hits_; }
    uint64_t misses() const { return misses_; }
};

inline bool film_grain_ar_synthesis_safe_cached(const uint8_t *coefficients, unsigned lag, unsigned shift) {
    // Encoder instances/threads never share mutable cache state. No allocation,
    // media-dependent growth, or skipped analysis of a newly quantized model.
    static thread_local FilmGrainValidationCache cache;
    return cache.check(coefficients, lag, shift);
}
} // namespace fgsmodel
