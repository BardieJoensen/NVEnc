#include <cassert>
#include <iostream>
#include <vector>
#include "NVEncFilmGrainNativeVariance.h"
using namespace fgsmodel;
int main() {
    constexpr unsigned width=128,height=128;
    for(unsigned depth:{8u,10u})for(unsigned padding:{0u,7u}) {
        std::array<std::vector<uint16_t>,3> data;std::array<FilmGrainNativePlane,3> planes;
        const unsigned scale=1u<<(depth-8);
        for(unsigned c=0;c<3;++c) {
            const unsigned w=c?width/2:width,h=c?height/2:height,stride=w+padding;
            data[c].assign(size_t(stride)*h,65535);planes[c]={data[c].data(),data[c].size(),stride};
            for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
                const int amplitude=c==0?1:c==1?2:3;
                data[c][size_t(y)*stride+x]=uint16_t((128+((x+y)&1?amplitude:-amplitude))*scale);
            }
        }
        const auto noise=film_grain_native_variance(planes,width,height,depth);assert(noise.valid);
        assert((noise.blocks==std::array<uint64_t,2>{2,2}));
        for(auto mean:noise.mean)assert(mean==128.);
        for(const auto& fold:noise.variance)assert((fold==std::array<double,4>{1.,0.,4.,9.}));
        for(unsigned c=0;c<3;++c) {
            const unsigned w=c?width/2:width,h=c?height/2:height;
            for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
                const unsigned value=c==0?16+x%64+y%64:c==1?48+2*(x%32)+y%32:80+x%32+2*(y%32);
                data[c][size_t(y)*planes[c].stride+x]=uint16_t(value*scale);
            }
        }
        const auto plane=film_grain_native_variance(planes,width,height,depth);assert(plane.valid);
        assert((plane.mean==std::array<double,3>{79.,94.5,126.5}));
        for(const auto& fold:plane.variance)for(double value:fold)assert(value<1e-25);
        for(unsigned bad=0;bad<8;++bad) {
            auto invalid=planes;unsigned w=width,h=height,d=depth;
            if(bad==0)invalid[0].data=nullptr;
            if(bad==1)invalid[1].samples=1;
            if(bad==2)invalid[2].stride=1;
            if(bad==3)invalid[0].stride=65537;
            if(bad==4)w=96;
            if(bad==5)d=12;
            if(bad==6)w=h=64;
            if(bad==7)data[0][0]=uint16_t(1u<<depth);
            assert(!film_grain_native_variance(invalid,w,h,d).valid);
        }
    }
    std::cout<<"Native variance: exact checkerboard/plane controls at8/10bit, padded planes and invalid span/layout/range controls passed\n";
}
