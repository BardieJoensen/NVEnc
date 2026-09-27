// Full native-plane evidence for zero synthesized colour grain. This proves
// range and sample identity only; it is not grain/population admission.
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include "NVEncFilmGrainConstantChroma.h"

namespace fgsmodel {
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
