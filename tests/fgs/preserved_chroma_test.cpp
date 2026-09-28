#include <cassert>
#include <iostream>
#include <vector>
#include "NVEncFilmGrainPreservedChroma.h"
using namespace fgsmodel;
struct Plane {const uint16_t* data;size_t samples,stride;};
int main() {
    unsigned positive=0,negative=0;
    for(unsigned depth:{8u,10u})for(unsigned mask:{2u,4u,6u})
    for(auto size:{std::array<unsigned,2>{64,64},{130,126},{1920,1080},{3840,2160}})
    for(unsigned padding:{0u,7u}) {
        const auto w=size[0],h=size[1],cw=w/2,ch=h/2,scale=1u<<(depth-8);
        std::array<std::vector<uint16_t>,3> a,b;std::array<Plane,3> av{},bv{};
        for(unsigned c=1;c<3;++c) {
            a[c].assign(size_t(cw+padding)*ch,65535);b[c].assign(size_t(cw+padding+3)*ch,65535);
            for(unsigned y=0;y<ch;++y)for(unsigned x=0;x<cw;++x) {
                // Includes both legal endpoints; padding is deliberately invalid.
                const auto value=uint16_t((16+(x+7*y+13*c)%225)*scale);
                a[c][size_t(y)*(cw+padding)+x]=value;b[c][size_t(y)*(cw+padding+3)+x]=value;
            }
            av[c]={a[c].data(),(ch-1)*size_t(cw+padding)+cw,cw+padding};
            bv[c]={b[c].data(),(ch-1)*size_t(cw+padding+3)+cw,cw+padding+3};
        }
        assert(film_grain_preserved_chroma_equal(av,bv,w,h,depth,mask));++positive;
        const auto proof=film_grain_measure_preserved_chroma(av,w,h,depth,mask);
        assert(proof.covers(mask,w,h,depth));
        for(unsigned c=1;c<3;++c)if(mask&(1u<<c)) {
            assert(proof.minimum[c-1]==16*scale && proof.maximum[c-1]==240*scale);
            assert(proof.samples[c-1]==uint64_t(cw)*ch);
        }
        for(unsigned bad=0;bad<9;++bad) {
            auto changed=proof;const auto c=mask&2?0:1;
            if(bad==0)changed.width+=2;
            if(bad==1)changed.height+=2;
            if(bad==2)changed.depth=depth==8?10:8;
            if(bad==3)changed.mask^=2u<<c;
            if(bad==4)--changed.samples[c];
            if(bad==5)++changed.samples[c];
            if(bad==6)changed.minimum[c]=16*scale-1;
            if(bad==7)changed.maximum[c]=240*scale+1;
            if(bad==8)changed.minimum[c]=changed.maximum[c]+1;
            assert(!changed.covers(mask,w,h,depth));++negative;
        }
        for(unsigned c=1;c<3;++c)if(mask&(1u<<c)) {
            const auto at=(ch-1)*size_t(cw+padding)+cw-1;const auto original=a[c][at];
            for(unsigned bad:{16*scale-1,240*scale+1,1u<<depth}) {
                a[c][at]=uint16_t(bad);assert(!film_grain_preserved_chroma_range(av,w,h,depth,mask));++negative;
                const auto changed=film_grain_measure_preserved_chroma(av,w,h,depth,mask);
                assert(!changed.covers(mask,w,h,depth));
                assert(changed.minimum[c-1]==bad || changed.maximum[c-1]==bad);
            }
            a[c][at]=original;
            const auto bt=(ch-1)*size_t(cw+padding+3)+cw-1;const auto before=b[c][bt];
            b[c][bt]=uint16_t(before==16*scale?before+1:before-1);
            assert(!film_grain_preserved_chroma_equal(av,bv,w,h,depth,mask));++negative;b[c][bt]=before;
            for(unsigned kind=0;kind<4;++kind) {
                auto bad=av;
                if(kind==0)--bad[c].samples;
                if(kind==1)bad[c].stride=cw-1;
                if(kind==2)bad[c].stride=65537;
                if(kind==3)bad[c].data=nullptr;
                assert(!film_grain_preserved_chroma_range(bad,w,h,depth,mask));++negative;
                assert(!film_grain_measure_preserved_chroma(bad,w,h,depth,mask).covers(mask,w,h,depth));
            }
        }
        for(unsigned m:{0u,1u,3u,5u,7u,8u}) {
            assert(!film_grain_preserved_chroma_range(av,w,h,depth,m));++negative;
            assert(!film_grain_measure_preserved_chroma(av,w,h,depth,m).covers(m,w,h,depth));
        }
        assert(!film_grain_preserved_chroma_range(av,w+1,h,depth,mask));
        assert(!film_grain_preserved_chroma_range(av,w,h,12,mask));negative+=2;
    }
    std::cout<<positive<<" preserved native range/equality controls and "<<negative
        <<" border, layout, code and mask vetoes passed\n";
}
