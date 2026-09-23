// Native-resolution persistent-detail measurements. No population admission.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainJointCollect.h"
#include "NVEncFilmGrainPersistentDetail.h"

namespace fgsmodel {
// Oldest first; current source is passed separately. All planes must be owned
// by the caller until the input stream completes. Cuts change the epoch.
struct FilmGrainPersistentHistory { FilmGrainCollectFrame source[7]{}; };
// Native component coordinates, unlike the chroma-grid joint collector.
struct FilmGrainPersistentTile { unsigned x = 0, y = 0, component = 0; };
struct FilmGrainPersistentResult {
    uint32_t reasons = 0, samples = 0, changedSamples = 0;
    double mean[4]{}, covariance[16]{};
};
inline bool film_grain_persistent_history_valid(const FilmGrainCollectFrame& current,
    const FilmGrainPersistentHistory& history) {
    const auto *next = &current;
    for (int i = 6; i >= 0; --i) {
        if (!film_grain_collect_history_valid(*next, history.source[i])) return false;
        next = &history.source[i];
    }
    return true;
}
inline FilmGrainPersistentDetail film_grain_persistent_result_detail(
    const FilmGrainPersistentResult& result, const FilmGrainPersistentLimits& limits) {
    if (result.reasons || result.changedSamples > result.samples) return {};
    FilmGrainPersistentMoments m;
    m.samples = result.samples;
    for (unsigned i = 0; i < 4; ++i) m.mean[i] = result.mean[i];
    for (unsigned i = 0; i < 16; ++i) m.covariance[i] = result.covariance[i];
    return film_grain_persistent_detail(m, limits);
}
} // namespace fgsmodel
