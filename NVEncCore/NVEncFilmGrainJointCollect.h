// Experimental native source/base measurements; MIT license, as NVEncFilmGrainModel.h.
// Collection is not eligibility or output-quality clearance. No production call sites.
#pragma once
#include <cstddef>
#include <cstdint>
#include <limits>

namespace fgsmodel {
constexpr unsigned FGS_COLLECT_SIDE = 32;
constexpr unsigned FGS_COLLECT_VARIABLES = 26;
constexpr unsigned FGS_COLLECT_MATRIX = 26 * 26;
constexpr unsigned FGS_COLLECT_MAX_TILES = 512;
constexpr unsigned FGS_COLLECT_LOOKUP_CODES = 1024;
constexpr unsigned FGS_COLLECT_GROUPS = 2 * 2 * 20; // component, check fold, brightness
constexpr unsigned FGS_COLLECT_MOMENTS = 3 * FGS_COLLECT_MATRIX + 3 * 9 + 4 * 49;

struct FilmGrainCollectPlane {
    const void *data = nullptr; // points at this component, including UV offset
    size_t pitchBytes = 0;
    unsigned pixelStride = 1; // samples, not bytes; two for interleaved UV
};
struct FilmGrainCollectFrame {
    FilmGrainCollectPlane plane[3]{};
    unsigned width = 0, height = 0;
    unsigned bitDepth = 10, storageShift = 0; // 8-bit bytes, native 10-bit or P010
    int64_t frameId = -1;
    int64_t timestamp = std::numeric_limits<int64_t>::min();
    uint64_t epoch = 0; // changes on reset/cut; caller owns history lifetime
    bool complete = false; // all three planes have been copied on the input stream
};
struct FilmGrainCollectTile { unsigned x = 0, y = 0, component = 1; }; // chroma coordinates
struct FilmGrainCollectRetention { float y = 0.0f, cb = 0.0f, cr = 0.0f; };
enum FilmGrainCollectReason : uint32_t {
    FGS_COLLECT_OK = 0,
    FGS_COLLECT_HISTORY = 1u << 0,
    FGS_COLLECT_COORDINATES = 1u << 1,
    FGS_COLLECT_LUMA_ENERGY = 1u << 2,
    FGS_COLLECT_CHROMA_ENERGY = 1u << 3,
    FGS_COLLECT_LUMA_LEVEL = 1u << 4,
    FGS_COLLECT_CHROMA_LEVEL = 1u << 5,
    FGS_COLLECT_LUMA_PERSISTENT = 1u << 6,
    FGS_COLLECT_CHROMA_PERSISTENT = 1u << 7,
    FGS_COLLECT_LUMA_DIRECTIONAL = 1u << 8,
    FGS_COLLECT_CHROMA_DIRECTIONAL = 1u << 9,
    FGS_COLLECT_CODES = 1u << 10
};
struct FilmGrainCollectResult {
    uint32_t reasons = 0, brightnessGroup = 0, checkFold = 0, observations = 0;
    uint32_t otherColourReasons = 0;
    // Source Y/C, rounded base Y/C, previous Y/C, then other-colour source/base/previous.
    double mean[9]{}, variance[9]{};
    double temporalCorrelation[3]{}, coherence[3]{}; // Y, selected C, other C
    // SUMS over 26x26 observations in 8-bit code units, including at 10 bit.
    // sourceBase[i,j] = source_i * base_j; its transpose is different.
    double source[FGS_COLLECT_MATRIX]{};
    double base[FGS_COLLECT_MATRIX]{};
    double sourceBase[FGS_COLLECT_MATRIX]{};
    // Common coordinates, fixed order Y/Cb/Cr regardless of the selected component.
    double colourSource[9]{}, colourBase[9]{}, colourSourceBase[9]{};
    // Cb(x,y) against Cr(x+dx,y+dy), dy/dx=-3..3 row-major. Mixed terms
    // retain both source-Cb/base-Cr and base-Cb/source-Cr orientations.
    double colourLagSource[49]{}, colourLagBase[49]{};
    double colourLagSourceBase[49]{}, colourLagBaseSource[49]{};
};
struct FilmGrainCollectLookup {
    // Full-picture counts for the current model's Y-referred chroma curves:
    // cb/cr_mult=128, cb/cr_luma_mult=192, cb/cr_offset=256. Not arbitrary curves.
    unsigned long long luma[FGS_COLLECT_LOOKUP_CODES]{};
    unsigned long long chroma[FGS_COLLECT_LOOKUP_CODES]{}; // count per colour plane
    unsigned long long invalidSamples = 0; // any nonzero value rejects the histogram
};
struct FilmGrainCollectGroup {
    uint64_t blocks=0, observations=0, otherColourSupportedBlocks=0;
    // Flattened in the Result declaration's matrix order, excluding scalar statistics.
    double moments[FGS_COLLECT_MOMENTS]{};
};

inline bool film_grain_collect_layout_valid(const FilmGrainCollectFrame& f) {
    if (!f.complete || f.width < 64 || f.height < 64 || f.width > 8192 || f.height > 8192
        || (f.width & 1) || (f.height & 1)
        || (f.bitDepth != 8 && f.bitDepth != 10)
        || (f.storageShift != 0 && !(f.bitDepth == 10 && f.storageShift == 6))) return false;
    const unsigned bytes = f.bitDepth == 8 ? 1 : 2;
    for (unsigned p = 0; p < 3; ++p) {
        const auto& v = f.plane[p];
        const unsigned w = p == 0 ? f.width : f.width / 2;
        if (!v.data || (v.pixelStride != 1 && !(p && v.pixelStride == 2))
            || v.pitchBytes < size_t(w) * v.pixelStride * bytes
            || v.pitchBytes % bytes || reinterpret_cast<uintptr_t>(v.data) % bytes) return false;
    }
    return true;
}
inline bool film_grain_collect_same_geometry(const FilmGrainCollectFrame& a,
    const FilmGrainCollectFrame& b) {
    return a.width == b.width && a.height == b.height && a.bitDepth == b.bitDepth
        && a.storageShift == b.storageShift;
}
inline bool film_grain_collect_history_valid(const FilmGrainCollectFrame& a,
    const FilmGrainCollectFrame& previous) {
    return film_grain_collect_layout_valid(a) && film_grain_collect_layout_valid(previous)
        && film_grain_collect_same_geometry(a, previous) && a.epoch == previous.epoch
        && a.frameId > 0 && previous.frameId == a.frameId - 1
        && previous.timestamp != std::numeric_limits<int64_t>::min()
        && a.timestamp > previous.timestamp;
}
inline bool film_grain_collect_base_valid(const FilmGrainCollectFrame& source,
    const FilmGrainCollectFrame& base) {
    return film_grain_collect_layout_valid(source) && film_grain_collect_layout_valid(base)
        && film_grain_collect_same_geometry(source, base) && source.frameId >= 0
        && source.frameId == base.frameId && source.epoch == base.epoch
        && source.timestamp != std::numeric_limits<int64_t>::min()
        && source.timestamp == base.timestamp;
}
} // namespace fgsmodel
