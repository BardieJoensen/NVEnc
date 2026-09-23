// Necessary synthesis-coverage conditions under the frozen R1 population rule.
// This is a conservative preflight, not model, range or picture qualification.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainRetentionSelect.h"
#include "NVEncFilmGrainScaling.h"

namespace fgsmodel {
struct FilmGrainPopulationEnvelope {
    bool valid = false;
    unsigned bitDepth = 0, occupiedCodes = 0, possibleCodes = 0;
    uint64_t samples = 0, possibleSamples = 0, blockedSamples = 0;
    uint64_t eligibleSamplesAtBlockedCodes = 0;
    std::array<uint64_t, 1024> occupancy{}, eligible{};
    // A false entry forbids positive synthesis at an occupied native lookup.
    // Unoccupied codes still need interpolation and final-population checks.
    std::array<bool, 1024> possible{};
};

// Cells must be a complete census at the actual candidate base/model's native
// lookup, with source-only population and disjoint train/check counts. A change
// to Y retention or the chroma lookup equation requires a fresh census. Source
// brightness groups are not native lookup codes. Cell quality-check flags do
// not grant eligibility to quiet, rejected, border or undersupported populations.
inline FilmGrainPopulationEnvelope film_grain_population_envelope(
    const FilmGrainRetentionFrame& frame, unsigned component,
    const std::vector<FilmGrainRetentionPopulationCell>& cells) {
    FilmGrainPopulationEnvelope result;
    constexpr size_t maxCells = 20 * 6 * 4 * 1024;
    if (!frame.valid() || component > 2 || cells.empty() || cells.size() > maxCells) return result;
    const auto invalid = []() { return FilmGrainPopulationEnvelope{}; };
    const uint64_t expected = uint64_t(frame.width) * frame.height / (component ? 4 : 1);
    const unsigned codes = 1u << frame.bitDepth;
    for (const auto& cell : cells) {
        if (static_cast<unsigned>(cell.population) > 3 || cell.nativeLookup >= codes
            || !cell.samples || cell.samples > expected || result.samples > expected-cell.samples
            || cell.trainBlocks > 10000000 || cell.checkBlocks > 10000000) return invalid();
        result.samples += cell.samples;
        result.occupancy[cell.nativeLookup] += cell.samples;
        if (cell.population == FilmGrainRetentionPopulation::Grain
            && cell.trainBlocks >= 16 && cell.checkBlocks >= 16)
            result.eligible[cell.nativeLookup] += cell.samples;
    }
    if (result.samples != expected) return invalid();
    for (unsigned code = 0; code < codes; ++code) {
        const uint64_t count = result.occupancy[code];
        if (!count) continue;
        ++result.occupiedCodes;
        result.possible[code] = result.eligible[code] == count;
        if (result.possible[code]) {
            ++result.possibleCodes; result.possibleSamples += count;
        } else {
            result.blockedSamples += count;
            result.eligibleSamplesAtBlockedCodes += result.eligible[code];
        }
    }
    result.bitDepth = frame.bitDepth;
    result.valid = true;
    return result;
}

struct FilmGrainPopulationCurveCheck {
    bool valid = false;
    uint64_t nonzeroSamples = 0, blockedNonzeroSamples = 0;
};
// Use the exact native integer LUT, including endpoint extension and high-depth
// interpolation. A zero blocked count is only a necessary coverage condition;
// it does not prove source preservation, decoder-range safety or model fidelity.
inline FilmGrainPopulationCurveCheck film_grain_population_curve_check(
    const FilmGrainPopulationEnvelope& envelope, const FilmGrainScalingLut& lut) {
    FilmGrainPopulationCurveCheck result;
    if (!envelope.valid || (envelope.bitDepth != 8 && envelope.bitDepth != 10)
        || !envelope.samples || envelope.samples > uint64_t(8192)*8192
        || !lut.valid() || lut.bitDepth() != envelope.bitDepth) return result;
    uint64_t samples = 0;
    for (unsigned code = 0; code < (1u << envelope.bitDepth); ++code) {
        const auto count = envelope.occupancy[code];
        if (count > envelope.samples || samples > envelope.samples-count
            || envelope.eligible[code] > count
            || envelope.possible[code] != (count && count == envelope.eligible[code])) return {};
        samples += count;
        unsigned strength = 0;
        if (!lut.lookup(code, strength)) return {};
        if (strength) {
            result.nonzeroSamples += envelope.occupancy[code];
            if (!envelope.possible[code]) result.blockedNonzeroSamples += envelope.occupancy[code];
        }
    }
    if (samples != envelope.samples) return {};
    result.valid = true;
    return result;
}
} // namespace fgsmodel
