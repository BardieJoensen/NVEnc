// Shared validation of the NVENC 4:2:0 film-grain parameter view.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "../NVEncSDK/Common/inc/nvEncodeAPI.h"
namespace fgsmodel {
inline bool film_grain_params_420_valid(const NV_ENC_FILM_GRAIN_PARAMS_AV1& p, unsigned depth) {
    if (depth != 8 && depth != 10 && depth != 12) return false;
    if (!p.applyGrain) return true; // Unsignalled/stale fields are ignored.
    if (p.numYPoints > 14 || p.numCbPoints > 10 || p.numCrPoints > 10
        || (p.chromaScalingFromLuma && (p.numCbPoints || p.numCrPoints))
        || (!p.numYPoints && (p.numCbPoints || p.numCrPoints))
        || ((p.numCbPoints == 0) != (p.numCrPoints == 0))
        || (p.numCbPoints && p.cbOffset > 511) || (p.numCrPoints && p.crOffset > 511)) return false;
    const unsigned count[3] = {p.numYPoints, p.numCbPoints, p.numCrPoints};
    const uint8_t* values[3] = {p.pointYValue, p.pointCbValue, p.pointCrValue};
    for (unsigned plane = 0; plane < 3; ++plane)
        for (unsigned i = 1; i < count[plane]; ++i)
            if (values[plane][i] <= values[plane][i - 1]) return false;
    return true;
}
} // namespace fgsmodel
