// Exact native constant-colour evidence for the finite diagnostic fitter.
// This is not grain/source admission and never makes a zero variance measurable.
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include "NVEncFilmGrainNativeGrid.h"

namespace fgsmodel {
inline bool film_grain_copied_chroma_mask(unsigned mask) { return (mask & ~6u) == 0; }

struct FilmGrainConstantChroma {
    unsigned width=0,height=0,depth=0,mask=0;
    std::array<unsigned,2> code{};
    bool covers(unsigned requested,unsigned w,unsigned h,unsigned d) const {
        if(!requested || !film_grain_copied_chroma_mask(requested)
            || !film_grain_copied_chroma_mask(mask) || (mask&requested)!=requested
            || width!=w || height!=h || depth!=d || (d!=8 && d!=10))return false;
        const unsigned scale=1u<<(d-8);
        for(unsigned c=0;c<2;++c)if((requested&(2u<<c)) && (code[c]<16*scale || code[c]>240*scale))return false;
        return true;
    }
};

// Accept plane views with native uint16 data, samples and sample stride.
// Scan visible samples only, including every edge; padding is not evidence.
template<class Plane>
inline FilmGrainConstantChroma film_grain_measure_constant_chroma(const std::array<Plane,3>& planes,
    unsigned width,unsigned height,unsigned depth,unsigned requested=6) {
    FilmGrainConstantChroma result;
    const auto grid=film_grain_native_grid(width,height);
    if(!grid.valid || !requested || !film_grain_copied_chroma_mask(requested) || (depth!=8 && depth!=10))return result;
    result.width=width;result.height=height;result.depth=depth;
    const size_t w=width/2,h=height/2;
    for(unsigned c=1;c<3;++c)if(requested&(1u<<c)) {
        const auto& p=planes[c];
        if(!p.data || p.stride<w || p.stride>65536 || p.samples<(h-1)*p.stride+w)return {};
        const unsigned code=p.data[0];bool constant=true;
        for(size_t y=0;y<h;++y)for(size_t x=0;x<w;++x) {
            const auto value=p.data[y*p.stride+x];if(value>=(1u<<depth))return {};
            constant&=value==code;
        }
        if(constant){result.mask|=1u<<c;result.code[c-1]=code;}
    }
    return result;
}

inline bool film_grain_same_constant_chroma(const FilmGrainConstantChroma& a,
    const FilmGrainConstantChroma& b,unsigned mask,unsigned width,unsigned height,unsigned depth) {
    if(!a.covers(mask,width,height,depth) || !b.covers(mask,width,height,depth))return false;
    for(unsigned c=0;c<2;++c)if((mask&(2u<<c)) && a.code[c]!=b.code[c])return false;
    return true;
}

// Retain only constants witnessed at the same native code in every input.
// A changed constant over time remains unsupported by this narrow diagnostic.
inline void film_grain_intersect_constant_chroma(FilmGrainConstantChroma& a,const FilmGrainConstantChroma& b) {
    if(a.width!=b.width || a.height!=b.height || a.depth!=b.depth){a={};return;}
    a.mask&=b.mask;
    for(unsigned c=0;c<2;++c)if(a.code[c]!=b.code[c])a.mask&=~(2u<<c);
}
} // namespace fgsmodel
