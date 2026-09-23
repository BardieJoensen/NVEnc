// Native planar measurements for the reconstructed-base selection prototype.
// Tile-aligned development pictures only; no population/coverage admission.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

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
    if(width<64 || height<64 || width>4096 || height>2160 || width%64 || height%64 || (depth!=8 && depth!=10))return result;
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
    const unsigned columns=width/64,rows=height/64;
    std::array<double,4096> tile{};
    for(unsigned by=0;by<rows;++by)for(unsigned bx=0;bx<columns;++bx) {
        const unsigned fold=(by+bx)&1;++result.blocks[fold];
        for(unsigned field=0;field<4;++field) {
            const unsigned side=field?32:64,c=field<2?0:field-1;
            const double center=(side-1)*.5;double sum=0.,sumx=0.,sumy=0.,norm=0.;
            const auto& p=planes[c];
            for(unsigned y=0;y<side;++y)for(unsigned x=0;x<side;++x) {
                double value;
                if(field==1) {
                    const auto offset=size_t(by*64+y*2)*p.stride+bx*64+x*2;
                    value=(unsigned(p.data[offset])+p.data[offset+1]+p.data[offset+p.stride]+p.data[offset+p.stride+1])/(4.*scale);
                } else value=p.data[size_t(by*side+y)*p.stride+bx*side+x]/scale;
                const auto dx=x-center,dy=y-center;tile[y*side+x]=value;sum+=value;sumx+=value*dx;sumy+=value*dy;norm+=dx*dx;
            }
            const double mean=sum/(side*side),slopex=sumx/norm,slopey=sumy/norm;double squares=0.;
            for(unsigned y=3;y<side-3;++y)for(unsigned x=3;x<side-3;++x) {
                const double value=tile[y*side+x]-mean-slopex*(x-center)-slopey*(y-center);squares+=value*value;
            }
            result.variance[fold][field]+=squares;
        }
    }
    if(!result.blocks[0] || !result.blocks[1])return result;
    for(unsigned fold=0;fold<2;++fold)for(unsigned field=0;field<4;++field) {
        const unsigned side=field?26:58;auto& variance=result.variance[fold][field];variance/=result.blocks[fold]*side*side;
        if(!std::isfinite(variance) || variance<0.)return result;
    }
    result.valid=true;return result;
}
} // namespace fgsmodel
