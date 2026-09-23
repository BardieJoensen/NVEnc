#include <cassert>
#include <iostream>
#include <vector>
#include "native_moments_json.h"
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
    for(unsigned depth:{8u,10u})for(unsigned side:{128u,192u}) {
        std::array<std::vector<uint16_t>,3> data;
        std::array<fgsmodel::FilmGrainNativePlane,3> planes{};
        std::array<std::array<uint64_t,3>,2> sums{},counts{};
        for(unsigned c=0;c<3;++c) {
            const unsigned size=c?side/2:side,stride=size+11,block=c?32:64;
            data[c].assign(size*stride,65535); // Padding must never count.
            for(unsigned y=0;y<size;++y)for(unsigned x=0;x<size;++x) {
                const unsigned f=(x/block+y/block)&1;
                const unsigned value=((x*13+y*7+c*11)%113+30+f*50)<<(depth-8);
                data[c][y*stride+x]=uint16_t(value);sums[f][c]+=value;++counts[f][c];
            }
            planes[c]={data[c].data(),data[c].size(),stride};
        }
        const auto moments=fgsmodel::film_grain_native_moments(planes,side,side,depth);
        assert(moments.valid);
        for(unsigned f=0;f<2;++f)for(unsigned c=0;c<3;++c) {
            assert(moments.folds[f].meanValid);
            assert(moments.folds[f].mean[c]==double(sums[f][c])/counts[f][c]/(1u<<(depth-8)));
        }
        for(unsigned c=0;c<3;++c)
            assert(moments.mean[c]==double(sums[0][c]+sums[1][c])/(counts[0][c]+counts[1][c])/(1u<<(depth-8)));
        auto json=fgsdiagnostic::moments(moments);
        const auto restored=fgsdiagnostic::moments(json);
        for(unsigned f=0;f<2;++f)
            assert(restored.folds[f].meanValid && restored.folds[f].mean==moments.folds[f].mean);
        for(auto& fold:json["folds"]) {fold.erase("mean_valid");fold.erase("mean");}
        const auto older=fgsdiagnostic::moments(json);
        assert(older.valid && !older.folds[0].meanValid && !older.folds[1].meanValid);
        json["folds"][0]["mean_valid"]=true;
        bool rejected=false;try {fgsdiagnostic::moments(json);}catch(const nlohmann::json::exception&){rejected=true;}
        assert(rejected); // Declaring measured data does not supply its values.
    }
    std::cout<<"All1250 displacement-integral moments match independent direct sums; nonstationary shifted supports stay distinct\n";
}
