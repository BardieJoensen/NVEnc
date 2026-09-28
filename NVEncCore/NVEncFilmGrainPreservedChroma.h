// Full native-plane evidence for zero synthesized colour grain. This proves
// range and sample identity only; it is not grain/population admission.
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include "NVEncFilmGrainConstantChroma.h"

namespace fgsmodel {
// Source-only planning evidence. It neither proves candidate equality nor
// grants permission to synthesize grain; both require separate measurements.
struct FilmGrainPreservedChroma {
    unsigned width=0,height=0,depth=0,mask=0;
    std::array<unsigned,2> minimum{},maximum{};
    std::array<uint64_t,2> samples{};
    bool covers(unsigned requested,unsigned w,unsigned h,unsigned d) const {
        if(!requested || !film_grain_copied_chroma_mask(requested)
            || !film_grain_copied_chroma_mask(mask) || (mask&requested)!=requested
            || width!=w || height!=h || depth!=d || (d!=8 && d!=10)
            || !film_grain_native_grid(w,h).valid)return false;
        const unsigned scale=1u<<(d-8);
        for(unsigned c=0;c<2;++c)if(requested&(2u<<c)) {
            if(samples[c]!=uint64_t(w/2)*(h/2) || minimum[c]>maximum[c]
                || minimum[c]<16*scale || maximum[c]>240*scale)return false;
        }
        return true;
    }
};

template<class Plane>
inline FilmGrainPreservedChroma film_grain_measure_preserved_chroma(const std::array<Plane,3>& planes,
    unsigned width,unsigned height,unsigned depth,unsigned requested) {
    FilmGrainPreservedChroma result;
    if(!requested || !film_grain_copied_chroma_mask(requested)
        || !film_grain_native_grid(width,height).valid || (depth!=8 && depth!=10))return result;
    result.width=width;result.height=height;result.depth=depth;
    const size_t w=width/2,h=height/2;
    for(unsigned c=1;c<3;++c)if(requested&(1u<<c)) {
        const auto& p=planes[c];
        if(!p.data || p.stride<w || p.stride>65536 || p.samples<(h-1)*p.stride+w)return {};
        unsigned low=UINT32_MAX,high=0;
        for(size_t y=0;y<h;++y)for(size_t x=0;x<w;++x) {
            const unsigned value=p.data[y*p.stride+x];
            if(value<low)low=value;
            if(value>high)high=value;
        }
        result.minimum[c-1]=low;result.maximum[c-1]=high;
        result.samples[c-1]=uint64_t(w)*h;result.mask|=1u<<c;
    }
    // Retain measured out-of-range extrema for an explainable preservation
    // decision. covers() rejects them; a mask alone is never proof of safety.
    return result;
}

template<class Plane>
inline bool film_grain_preserved_chroma_range(const std::array<Plane,3>& planes,
    unsigned width,unsigned height,unsigned depth,unsigned mask) {
    if(!mask || !film_grain_copied_chroma_mask(mask)
        || !film_grain_native_grid(width,height).valid || (depth!=8 && depth!=10))return false;
    const size_t w=width/2,h=height/2;
    const unsigned low=16u<<(depth-8),high=240u<<(depth-8);
    for(unsigned c=1;c<3;++c)if(mask&(1u<<c)) {
        const auto& p=planes[c];
        if(!p.data || p.stride<w || p.stride>65536 || p.samples<(h-1)*p.stride+w)return false;
        for(size_t y=0;y<h;++y)for(size_t x=0;x<w;++x) {
            const auto v=p.data[y*p.stride+x];if(v<low || v>high)return false;
        }
    }
    return true;
}

template<class Plane>
inline bool film_grain_preserved_chroma_equal(const std::array<Plane,3>& a,
    const std::array<Plane,3>& b,unsigned width,unsigned height,unsigned depth,unsigned mask) {
    if(!film_grain_preserved_chroma_range(a,width,height,depth,mask)
        || !film_grain_preserved_chroma_range(b,width,height,depth,mask))return false;
    for(unsigned c=1;c<3;++c)if(mask&(1u<<c))
        for(size_t y=0;y<height/2;++y)for(size_t x=0;x<width/2;++x)
            if(a[c].data[y*a[c].stride+x]!=b[c].data[y*b[c].stride+x])return false;
    return true;
}
} // namespace fgsmodel
