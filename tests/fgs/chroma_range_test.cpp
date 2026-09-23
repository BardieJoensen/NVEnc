#include "NVEncFilmGrainChromaRange.h"
#include <cassert>
#include <iostream>
using namespace fgsmodel;
int main(){
    NV_ENC_FILM_GRAIN_PARAMS_AV1 p{};p.applyGrain=1;p.clipToRestrictedRange=1;
    p.numCbPoints=p.numCrPoints=2;p.pointCbValue[1]=p.pointCrValue[1]=255;
    for(unsigned depth:{8u,10u}){
        const unsigned lo=16u<<(depth-8),hi=240u<<(depth-8);
        std::array<FilmGrainSourceRange,2> ranges{{{16384,lo,hi},{16384,lo,hi}}};
        const auto check=[&](){return film_grain_copied_chroma_range_mask(p,depth,16384,ranges);};
        assert(check()==0);
        ranges[1].maximum=hi+1;assert(check()==2);
        ranges[0].minimum=lo-1;assert(check()==3);
        p.pointCrScaling[0]=1;assert(check()==1);p.pointCrScaling[0]=0;
        p.numCrPoints=0;assert(check()==1);p.numCrPoints=2;
        ranges[0]={16383,lo,hi};ranges[1]={16384,lo,hi};assert(check()==1);
        ranges[0]={16384,hi,lo};assert(check()==1);
        ranges[0]={16384,lo,1u<<depth};assert(check()==1);
        p.clipToRestrictedRange=0;assert(check()==0);p.clipToRestrictedRange=1;
        p.applyGrain=0;assert(check()==0);p.applyGrain=1;
        p.chromaScalingFromLuma=1;assert(check()==0);p.chromaScalingFromLuma=0;
    }
    std::array<FilmGrainSourceRange,2> ranges{};
    assert(film_grain_copied_chroma_range_mask(p,12,16384,ranges)==3);
    assert(film_grain_copied_chroma_range_mask(p,10,0,ranges)==3);
    p.numCbPoints=11;assert(film_grain_copied_chroma_range_mask(p,10,16384,ranges)==3);
    std::cout<<"copied chroma: active zero, absent, full range, boundaries and incomplete evidence pass\n";
}
