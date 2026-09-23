#include <cassert>
#include <iostream>
#include "NVEncFilmGrainNativeMoments.h"
int main() {
    for(unsigned side:{32u,64u}) {
        std::array<double,4096> tile{};
        for(unsigned y=0;y<side;++y)for(unsigned x=0;x<side;++x)tile[y*side+x]=(x+3)*(x+3)+(y+2)*(y+2)+(x*y)%7;
        std::array<std::pair<int,int>,25> offsets{};unsigned k=0;
        for(int y=-3;y<0;++y)for(int x=-3;x<=3;++x)offsets[k++]={y,x};
        for(int x=-3;x<0;++x)offsets[k++]={0,x};
        offsets[24]={0,0};
        std::array<double,625> optimized{};fgsmodel::native_moments_detail::spatial(tile.data(),side,optimized);
        for(unsigned i=0;i<25;++i)for(unsigned j=0;j<25;++j) {
            double direct=0.;
            for(unsigned y=3;y<side-3;++y)for(unsigned x=3;x<side-3;++x)
                direct+=tile[size_t(int(y)+offsets[i].first)*side+size_t(int(x)+offsets[i].second)]*tile[size_t(int(y)+offsets[j].first)*side+size_t(int(x)+offsets[j].second)];
            assert(optimized[i*25+j]==direct);
        }
        // Equal displacement does not imply equal support in a nonstationary
        // tile. Central autocorrelation cannot replace these shifted moments.
        assert(optimized[0]!=optimized[24*25+24]);
        assert(optimized[1]!=optimized[24*25+23]);
    }
    std::cout<<"All1250 displacement-integral moments match independent direct sums; nonstationary shifted supports stay distinct\n";
}
