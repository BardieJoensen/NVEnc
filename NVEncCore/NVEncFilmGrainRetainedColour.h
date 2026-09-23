// Joint compatibility when one colour component is copied exactly from source.
// Experimental pre-compression model evidence; no encoder output call sites.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainColourFidelity.h"
#include "NVEncFilmGrainSourcePreservation.h"

namespace fgsmodel {
// group is the selected-colour source cohort collected by R2 (not an arbitrary
// pixel aggregate). Its existing 26x26 moments include the other colour even
// where that colour failed grain gates. Caller identities bind those moments
// to the current model/base, coordinates, frame and full preservation scan.
inline bool film_grain_retained_colour_source_base(const FilmGrainCollectGroup& group,
    uint64_t cohortId, unsigned selectedColour, const FilmGrainSourceComponentCounts& exactOther,
    const FilmGrainRetentionFrame& frame, uint64_t modelId,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, bool matrixIdentity,
    FilmGrainColourMoments& source, FilmGrainColourMoments& base) {
    source = {}; base = {};
    if (!cohortId || (selectedColour != 1 && selectedColour != 2)
        || !film_grain_component_source_preserved(exactOther, frame, modelId, 3 - selectedColour, params, matrixIdentity)
        || group.blocks < 16 || group.blocks > 10000000 || group.observations != group.blocks * 676
        || group.observations > 1000000000 || group.otherColourSupportedBlocks > group.blocks) return false;
    constexpr unsigned colour = 3 * FGS_COLLECT_MATRIX, lag = colour + 3 * 9;
    std::copy_n(group.moments + colour, 9, source.covariance.begin());
    std::copy_n(group.moments + colour + 9, 9, base.covariance.begin());
    std::copy_n(group.moments + lag, 49, source.cbCrLag.begin());
    std::copy_n(group.moments + lag + 49, 49, base.cbCrLag.begin());
    source.blocks = base.blocks = group.blocks; source.observations = base.observations = group.observations;
    source.jointlySupportedBlocks = base.jointlySupportedBlocks = group.otherColourSupportedBlocks;
    source.cohortId = base.cohortId = cohortId;
    return true;
}

// The source-only cohort must pass BOTH Y and selected-colour source gates.
// The other colour may be quiet/textured: its WHOLE component is proven exact,
// rather than incorrectly classifying its pixels as synthesizable grain.
// This consumes the ordinary cohort's actual moments and original divisor.
// It does not divide by the smaller other-colour-support count or infer a
// missing covariance. Every Y/Cb, Y/Cr and spatial Cb/Cr check still applies.
inline FilmGrainColourFidelity film_grain_retained_colour_fidelity(
    const FilmGrainColourMoments& source, const FilmGrainColourMoments& reconstructed,
    unsigned selectedColour, const FilmGrainSourceComponentCounts& exactOther,
    const FilmGrainRetentionFrame& frame, uint64_t modelId,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, bool matrixIdentity) {
    if ((selectedColour != 1 && selectedColour != 2)
        || !film_grain_component_source_preserved(exactOther, frame, modelId, 3 - selectedColour, params, matrixIdentity)
        || source.jointlySupportedBlocks > source.blocks
        || reconstructed.jointlySupportedBlocks != source.jointlySupportedBlocks) return {};
    // The exact-other component's detrended variance must agree too. An
    // inconsistent aggregate is not repaired by an unrelated global counter.
    const unsigned diagonal = (3 - selectedColour) * 4;
    const double a = source.covariance[diagonal], b = reconstructed.covariance[diagonal];
    if (!std::isfinite(a) || !std::isfinite(b) || std::abs(a - b) > std::max(1e-12, std::abs(a) * 1e-9)) return {};
    auto s = source, r = reconstructed;
    // These local copies express eligibility of all three components by the
    // appropriate evidence. Preserve the original source support counts.
    s.jointlySupportedBlocks = s.blocks; r.jointlySupportedBlocks = r.blocks;
    return film_grain_colour_fidelity(s, r);
}
} // namespace fgsmodel
