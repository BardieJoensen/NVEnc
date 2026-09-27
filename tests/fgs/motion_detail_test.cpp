#include "NVEncFilmGrainMotionDetail.h"
#include <cassert>
#include <iostream>
using namespace fgsmodel;
int main() {
    for(unsigned depth:{8u,10u}) {
        const unsigned w=128,h=96,stride=w+5,scale=1u<<(depth-8);
        std::array<std::vector<uint16_t>,8> raw;std::array<FilmGrainNativePlane,8> source;
        std::array<int64_t,8> ids{},pts{};std::vector<uint16_t> clean(w*h);
        uint32_t rng=23949;
        for(auto& value:clean){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;value=uint16_t(112+rng%33);}
        for(unsigned f=0;f<8;++f) {
            raw[f].assign(stride*h,65535);
            for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x)
                raw[f][size_t(y)*stride+x]=uint16_t(clean[size_t(y)*w+(x+w-f*7)%w]*scale);
            source[f]={raw[f].data(),raw[f].size(),stride};ids[f]=f;pts[f]=f*41;
        }
        auto base=raw[7];auto view=[&](){return FilmGrainNativePlane{base.data(),base.size(),stride};};
        auto run=[&](){return film_grain_motion_detail(source,view(),w,h,depth,32,16,4,ids,pts);};
        auto out=run();assert(out.valid && out.tiles.size()==12);
        const auto& t=out.tiles[5];assert(t.x==32 && t.y==32 && t.dx==-7 && t.dy==0);
        assert(t.motionSupported && t.anchorSupported && !t.conflict && t.projectedSamples==1024);
        assert(t.correlation==1. && t.contrastChange==0. && t.removedProjectionRms==0.);
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x)base[size_t(y)*stride+x]=128*scale;
        out=run();assert(out.tiles[5].conflict && out.tiles[5].contrastChange==1.);
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x)
            base[size_t(y)*stride+x]=uint16_t(128*scale+2*(int(raw[7][size_t(y)*stride+x])-int(128*scale)));
        out=run();assert(out.tiles[5].conflict && out.tiles[5].contrastChange==-1.);
        for(unsigned f=4;f<8;++f)for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x)
            raw[f][size_t(y)*stride+x]=uint16_t(clean[size_t(y)*w+(x+f*7)%w]*scale);
        out=run();assert(out.tiles[5].dx==-7 && out.tiles[5].dy==0 && !out.tiles[5].motionSupported);
        ids[7]=9;assert(!run().valid);ids[7]=7;pts[7]=pts[6];assert(!run().valid);pts[7]=7*41;
        raw[6][0]=uint16_t(1u<<depth);assert(!run().valid);raw[6][0]=128*scale;
        --source[0].samples; // Padding is irrelevant if all active samples fit.
        assert(run().valid);source[0].samples=(h-1)*stride+w-1;assert(!run().valid);
    }
    std::array<std::vector<uint16_t>,8> raw;std::array<FilmGrainNativePlane,8> source;
    std::array<int64_t,8> ids{},pts{};
    for(unsigned f=0;f<8;++f){raw[f].assign(130*66,128);source[f]={raw[f].data(),raw[f].size(),130};ids[f]=pts[f]=f;}
    auto base=raw[7];base.back()=129;
    auto r=film_grain_motion_detail(source,{base.data(),base.size(),130},130,66,8,64,32,4,ids,pts);
    assert(r.valid && r.tiles.size()==6 && r.tiles.back().samples==4 && r.tiles.back().changedSamples==1);
    assert(!r.tiles.back().motionSupported && !r.tiles.back().anchorSupported && !r.tiles.back().conflict);
    // Native matching must retain the nullspace of the smoothed matcher.
    for(unsigned f=0;f<8;++f) {
        raw[f].resize(128*128);
        for(unsigned y=0;y<128;++y)for(unsigned x=0;x<128;++x)raw[f][y*128+x]=uint16_t(128+((y+f)%2?16:-16));
        source[f]={raw[f].data(),raw[f].size(),128};
    }
    base.assign(128*128,128);
    auto smoothed=film_grain_motion_detail(source,{base.data(),base.size(),128},128,128,8,64,32,4,ids,pts);
    auto native=film_grain_motion_detail(source,{base.data(),base.size(),128},128,128,8,64,32,4,ids,pts,true);
    assert(smoothed.valid && native.valid);
    for(unsigned i=0;i<4;++i){assert(!smoothed.tiles[i].motionSupported);assert(native.tiles[i].conflict);}
    const auto combined=film_grain_motion_detail_veto(source,{base.data(),base.size(),128},128,128,8,64,32,4,ids,pts);
    assert(combined.valid && combined.conflicts.size()==4);
    for(bool conflict:combined.conflicts)assert(conflict);
    pts[7]=pts[6];assert(!film_grain_motion_detail_veto(source,{base.data(),base.size(),128},128,128,8,64,32,4,ids,pts).valid);
    std::cout<<"Native motion/detail: fast translation, preservation/loss/sharpening, disjoint validation, padding, borders and native alias control passed\n";
}
