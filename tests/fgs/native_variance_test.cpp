#include <cassert>
#include <iostream>
#include <vector>
#include "NVEncFilmGrainNativeVariance.h"
using namespace fgsmodel;
int main() {
    // Visit every permitted horizontal size against edge, ragged and UHD
    // vertical sizes. Contiguous even rectangles must cover every sample once.
    for(unsigned w=64;w<=4096;w+=2)for(unsigned h:{64u,66u,126u,1080u,2160u}) {
        const auto g=film_grain_native_grid(w,h);assert(g.valid);
        std::array<uint64_t,2> area{},yn{},cn{},blocks{};
        unsigned bottom=0;
        for(unsigned by=0;by<g.rows;++by) {
            unsigned right=0;
            for(unsigned bx=0;bx<g.columns;++bx) {
                const auto t=g.tile(bx,by);const auto f=(bx+by)&1;
                assert(t.x==right && t.y==bottom && !(t.x&1) && !(t.y&1));
                assert(!(t.width&1) && !(t.height&1));
                assert(t.width>=32 && t.width<=64 && t.height>=32 && t.height<=64);
                if(w%64==0)assert(t.width==64);
                if(h%64==0)assert(t.height==64);
                right+=t.width;++blocks[f];area[f]+=t.width*t.height;
                yn[f]+=(t.width-6)*(t.height-6);cn[f]+=(t.width/2-6)*(t.height/2-6);
            }
            assert(right==w);bottom+=g.tile(0,by).height;
        }
        assert(bottom==h && area[0]+area[1]==uint64_t(w)*h);
        assert(g.pixels==area && g.blocks==blocks && g.lumaObservations==yn && g.colourObservations==cn);
        assert(g.tile(g.columns,0).width==0 && g.tile(0,g.rows).height==0);
    }
    const auto ragged=film_grain_native_grid(130,126);
    assert((ragged.pixels==std::array<uint64_t,2>{8148,8232}));
    assert((ragged.lumaObservations==std::array<uint64_t,2>{6348,6420}));
    assert((ragged.colourObservations==std::array<uint64_t,2>{1191,1206}));
    for(const auto dims:{std::array<unsigned,2>{0,64},{62,64},{65,64},{64,65},{4098,64},{64,2162},{UINT32_MAX,128}})
        assert(!film_grain_native_grid(dims[0],dims[1]).valid);
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
            if(bad==4)w=95;
            if(bad==5)d=12;
            if(bad==6)w=h=64;
            if(bad==7)data[0][0]=uint16_t(1u<<depth);
            assert(!film_grain_native_variance(invalid,w,h,d).valid);
        }
    }
    std::cout<<"Native variance: complete even geometry, exact checkerboard/plane controls at8/10bit, padded planes and invalid span/layout/range controls passed\n";
}
