// Source-restored colour must survive the final AV1 active-zero-curve clamp.
// This applies to the encoder's supported 4:2:0 colour planes, before lossy
// compression; it does not promise a lossless transcode.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <array>
#include <cstdint>
#include "NVEncFilmGrainSyntax.h"

namespace fgsmodel {
struct FilmGrainSourceRange {
    uint64_t samples = 0;
    unsigned minimum = 0xffffffffu, maximum = 0;
};
// Bits 0/1 identify copied Cb/Cr that cannot be proved safe. Missing or invalid
// complete-component evidence is a failure. Absent curves do not activate the
// decoder clamp; present curves containing only zeros still do.
inline unsigned film_grain_copied_chroma_range_mask(
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, unsigned bitDepth,
    uint64_t expectedSamples, const std::array<FilmGrainSourceRange,2>& range) {
    if (!params.applyGrain || params.chromaScalingFromLuma || !params.clipToRestrictedRange) return 0;
    if ((bitDepth != 8 && bitDepth != 10) || !expectedSamples
        || expectedSamples > uint64_t(8192)*8192/4
        || params.numCbPoints > 10 || params.numCrPoints > 10) return 3;
    unsigned mask = 0;
    const unsigned count[2]={params.numCbPoints,params.numCrPoints};
    const uint8_t* scaling[2]={params.pointCbScaling,params.pointCrScaling};
    for (unsigned c=0;c<2;++c) {
        if (!count[c]) continue;
        bool zero = true;
        for (unsigned i=0;i<count[c];++i) zero &= scaling[c][i]==0;
        if (!zero) continue; // This component is not restored as zero synthesis.
        const auto& r=range[c];
        if (r.samples!=expectedSamples || r.minimum>r.maximum
            || r.maximum>=(1u<<bitDepth) || r.minimum<(16u<<(bitDepth-8))
            || r.maximum>(240u<<(bitDepth-8))) mask |= 1u<<c;
    }
    return mask;
}
} // namespace fgsmodel
