#include <cassert>
#include <iostream>
#include "NVEncFilmGrainNativePair.h"
using namespace fgsmodel;
static FilmGrainNativePairMoments fixture() {
    FilmGrainNativePairMoments p;
    p.valid=true; p.width=p.height=512; p.depth=10;
    for (unsigned f=0;f<2;++f) {
        auto& y=p.luma[f]; y.blocks=32; y.observations=32*58*58;
        for (unsigned i=0;i<25;++i) y.source[i*25+i]=y.observations;
        y.source[23*25+24]=y.source[24*25+23]=.125*y.observations;
        for (auto& component:p.colour) {
            auto& c=component[f]; c.blocks=32; c.observations=32*26*26;
            for (unsigned i=0;i<26;++i) c.source[i*26+i]=c.observations;
            c.source[23*26+25]=c.source[25*26+23]=.125*c.observations;
            c.source[24*26+25]=c.source[25*26+24]=.1*c.observations;
        }
    }
    return p;
}
int main() {
    unsigned exact=0;
    for (const auto size:{std::array<unsigned,2>{32,32},{64,64},{62,46},{17,16}}) {
        const auto width=size[0],height=size[1];
        std::array<double,4096> source{},base{};
        for (unsigned y=0;y<height;++y) for (unsigned x=0;x<width;++x) {
            source[y*width+x]=(x+3)*(x+3)+(y+2)*(y+2)+(x*y)%7;
            base[y*width+x]=(2*x+1)*(y+7)+(x*y)%13;
        }
        std::array<std::pair<int,int>,25> offset{};unsigned at=0;
        for (int y=-3;y<0;++y) for (int x=-3;x<=3;++x) offset[at++]={y,x};
        for (int x=-3;x<0;++x) offset[at++]={0,x};
        offset[24]={0,0};
        std::array<double,625> cross{},reverse{};
        native_pair_detail::spatial(source.data(),base.data(),width,height,cross);
        native_pair_detail::spatial(base.data(),source.data(),width,height,reverse);
        for (unsigned i=0;i<25;++i) for (unsigned j=0;j<25;++j) {
            double expected=0.;
            for (unsigned y=3;y<height-3;++y) for (unsigned x=3;x<width-3;++x)
                expected+=source[unsigned(int(y)+offset[i].first)*width+unsigned(int(x)+offset[i].second)]
                    *base[unsigned(int(y)+offset[j].first)*width+unsigned(int(x)+offset[j].second)];
            assert(cross[i*25+j]==expected && reverse[j*25+i]==expected); ++exact;
        }
        assert(cross[1]!=cross[25]); // Symmetrization or reversal loses evidence.
    }
    const auto p=fixture(); const uint16_t seeds[]={1031,2062,3093,4124};
    auto ragged=p;ragged.width=130;ragged.height=126;
    for(unsigned f=0;f<2;++f) {
        auto& y=ragged.luma[f];const uint64_t n=f?6420:6348;
        for(auto& v:y.source)v=v/y.observations*n;
        y.blocks=3;y.observations=n;
        for(auto& c:ragged.colour) {
            auto& m=c[f];const uint64_t cn=f?1206:1191;
            for(auto& v:m.source)v=v/m.observations*cn;
            m.blocks=3;m.observations=cn;
        }
    }
    FilmGrainNativeShapeTraining unequal;
    for(unsigned i=0;i<8;++i)assert(unequal.push(i,17,ragged));
    assert(unequal.luma().observations==8*6348);
    assert(unequal.colour()[0].observations==8*1191);
    assert(unequal.fit(6,0,seeds,4).valid());
    for(unsigned c=0;c<3;++c) {
        auto bad=ragged;
        if(c==0)bad.luma[0].observations=3*58*58;
        else bad.colour[c-1][0].observations=3*26*26;
        FilmGrainNativeShapeTraining oldGeometry;
        assert(!oldGeometry.push(0,17,bad));
    }
    FilmGrainNativeShapeTraining train,heldout;
    auto changed=p;
    changed.luma[1].source.fill(1e10);
    for (auto& c:changed.colour) { c[1].source.fill(1e10); c[1].sourceBase.fill(-1e10); }
    for (unsigned i=0;i<8;++i) {
        assert(train.push(i,17,p) && heldout.push(i,17,changed));
        if (i<7) assert(!train.fit(6,0,seeds,4).valid());
    }
    const auto fitted=train.fit(6,0,seeds,4),independent=heldout.fit(6,0,seeds,4);
    assert(fitted.valid() && independent.valid());
    assert(fitted.luma.luma.parameters().y==independent.luma.luma.parameters().y);
    assert(fitted.luma.luma.parameters().y[23]==136);
    for (unsigned c=0;c<2;++c) assert(fitted.colour[c].coefficients==independent.colour[c].coefficients);
    assert(!train.push(8,17,p) && !train.fit(6,0,seeds,4).valid());
    for (unsigned kind=0;kind<8;++kind) {
        FilmGrainNativeShapeTraining bad; assert(bad.push(0,17,p)); auto broken=p;
        if (kind==0) broken.valid=false;
        if (kind==1) broken.depth=8;
        if (kind==2) broken.colour[1][0].observations=1;
        if (kind==3) broken.luma[0].sourceBase[0]=std::numeric_limits<double>::infinity();
        if (kind==4) broken.width=576;
        if (kind==5) broken.luma[0].blocks=1;
        assert(!bad.push(kind==6?2:1,kind==7?18:17,broken));
        assert(!bad.push(1,17,p));
    }
    for (unsigned kind=0;kind<4;++kind) {
        FilmGrainNativeShapeTraining bad; auto broken=p;
        if (kind==0) broken.luma[0].sourceBase[0]=1e20;
        if (kind==1) broken.colour[0][0].sourceBase[0]=1e20;
        if (kind==2) for (auto& c:broken.colour) for (auto& f:c) { f.base=f.source; f.sourceBase=f.source; }
        if (kind==3) { broken.luma[0].source[23*25+24]=broken.luma[0].observations*.99; broken.luma[0].source[24*25+23]=broken.luma[0].source[23*25+24]; }
        for (unsigned i=0;i<8;++i) assert(bad.push(i,17,broken));
        assert(!bad.fit(6,0,seeds,4).valid());
    }
    std::cout<<"Native pair: "<<exact<<" exact oriented sums/transposes, frozen training-half fit, invalid pooling/PSD/stability and untouched check-half controls passed\n";
}
