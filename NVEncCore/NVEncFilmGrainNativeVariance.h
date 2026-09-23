// Native planar measurements for the reconstructed-base selection prototype.
// Complete disjoint native partitions; no population/coverage admission.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include "NVEncFilmGrainNativeGrid.h"

namespace fgsmodel {
struct FilmGrainNativePlane {
    const uint16_t* data=nullptr;
    size_t samples=0,stride=0;
};
struct FilmGrainNativeVariance {
    bool valid=false;
    std::array<double,3> mean{};
    // Native Y, 2x2-averaged Y, Cb, Cr; independent checkerboard halves.
    std::array<std::array<double,4>,2> variance{};
    std::array<uint64_t,2> blocks{};
};

inline FilmGrainNativeVariance film_grain_native_variance(
    const std::array<FilmGrainNativePlane,3>& planes,unsigned width,unsigned height,unsigned depth) {
    FilmGrainNativeVariance result;
    const auto grid=film_grain_native_grid(width,height);
    if(!grid.valid || !grid.blocks[0] || !grid.blocks[1] || (depth!=8 && depth!=10))return result;
    const double scale=double(1u<<(depth-8));
    for(unsigned c=0;c<3;++c) {
        const unsigned w=c?width/2:width,h=c?height/2:height;const auto& p=planes[c];
        if(!p.data || p.stride<w || p.stride>65536 || p.samples<p.stride*(h-1)+w)return result;
        uint64_t sum=0;
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
            const auto value=p.data[size_t(y)*p.stride+x];if(value>=(1u<<depth))return result;sum+=value;
        }
        result.mean[c]=double(sum)/(uint64_t(w)*h)/scale;
    }
    result.blocks=grid.blocks;
    std::array<double,4096> tile{};
    for(unsigned by=0;by<grid.rows;++by)for(unsigned bx=0;bx<grid.columns;++bx) {
        const unsigned fold=(by+bx)&1;const auto bounds=grid.tile(bx,by);
        for(unsigned field=0;field<4;++field) {
            const unsigned tw=field?bounds.width/2:bounds.width,th=field?bounds.height/2:bounds.height,c=field<2?0:field-1;
            const double centerx=(tw-1)*.5,centery=(th-1)*.5;double sum=0.,sumx=0.,sumy=0.,normx=0.,normy=0.;
            const auto& p=planes[c];
            for(unsigned y=0;y<th;++y)for(unsigned x=0;x<tw;++x) {
                double value;
                if(field==1) {
                    const auto offset=size_t(bounds.y+y*2)*p.stride+bounds.x+x*2;
                    value=(unsigned(p.data[offset])+p.data[offset+1]+p.data[offset+p.stride]+p.data[offset+p.stride+1])/(4.*scale);
                } else value=p.data[size_t(bounds.y/(c?2:1)+y)*p.stride+bounds.x/(c?2:1)+x]/scale;
                const auto dx=x-centerx,dy=y-centery;tile[y*tw+x]=value;sum+=value;sumx+=value*dx;sumy+=value*dy;normx+=dx*dx;normy+=dy*dy;
            }
            const double mean=sum/(tw*th),slopex=sumx/normx,slopey=sumy/normy;double squares=0.;
            for(unsigned y=3;y<th-3;++y)for(unsigned x=3;x<tw-3;++x) {
                const double value=tile[y*tw+x]-mean-slopex*(x-centerx)-slopey*(y-centery);squares+=value*value;
            }
            result.variance[fold][field]+=squares;
        }
    }
    if(!result.blocks[0] || !result.blocks[1])return result;
    for(unsigned fold=0;fold<2;++fold)for(unsigned field=0;field<4;++field) {
        auto& variance=result.variance[fold][field];variance/=(field?grid.colourObservations[fold]:grid.lumaObservations[fold]);
        if(!std::isfinite(variance) || variance<0.)return result;
    }
    result.valid=true;return result;
}
} // namespace fgsmodel
