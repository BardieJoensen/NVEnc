// Native plane adapter for independent energy measurements; no admission.
#include <filesystem>
#include <fstream>
#include <iostream>
#include <vector>
#include "json.hpp"
#include "NVEncFilmGrainSourceOutputEnergy.h"
using Json=nlohmann::json;
static unsigned integer(const Json& j,const char* key,unsigned low,unsigned high) {
    const auto& v=j.at(key);
    if(!v.is_number_integer() || v<low || v>high)throw std::runtime_error("invalid native integer");
    return v.get<unsigned>();
}
int main() {try {
    Json j;std::cin>>j;
    const unsigned w=integer(j,"width",64,4096),h=integer(j,"height",64,2160),depth=integer(j,"depth",8,10);
    const auto grid=fgsmodel::film_grain_native_grid(w,h);
    if(!grid.valid || !grid.blocks[1] || (depth!=8 && depth!=10))throw std::runtime_error("invalid native layout");
    std::array<std::array<std::vector<uint16_t>,3>,2> data;
    std::array<std::array<fgsmodel::FilmGrainNativePlane,3>,2> views{};
    for(unsigned k=0;k<2;++k) {
        const auto& names=j.at(k?"actual":"source");
        if(!names.is_array() || names.size()!=3)throw std::runtime_error("three native planes required");
        for(unsigned c=0;c<3;++c) {
            const auto path=std::filesystem::u8path(names.at(c).get<std::string>());
            const unsigned width=c?w/2:w,height=c?h/2:h;const size_t count=size_t(width)*height;
            if(!path.is_absolute() || std::filesystem::file_size(path)!=count*2)throw std::runtime_error("native plane span differs");
            std::vector<uint8_t> raw(count*2);std::ifstream file(path,std::ios::binary);
            file.read(reinterpret_cast<char*>(raw.data()),raw.size());if(!file)throw std::runtime_error("native plane read failed");
            auto& values=data[k][c];values.resize(count);
            for(size_t i=0;i<count;++i)values[i]=uint16_t(unsigned(raw[2*i])|(unsigned(raw[2*i+1])<<8));
            views[k][c]={values.data(),count,width};
        }
    }
    const auto e=fgsmodel::film_grain_source_output_energy(views[0],views[1],w,h,depth);
    std::cout<<Json({{"valid",e.valid},{"pass",e.pass},{"source_admission",false},
        {"source_variance",e.source.variance},{"actual_variance",e.actual.variance},
        {"mean_error",e.meanError},{"fold_mean_error",e.foldMeanError},
        {"constant_source",e.constantSource},{"actual_matches_source",e.actualMatchesSource},
        {"local_mean_error",e.localMeanError},{"local_slope_error",e.localSlopeError},
        {"local_worst_tile",e.localWorstTile},{"local_plane_pass",e.localPlanePass},
        {"relative_variance_error",e.relativeVarianceError},{"quiet",e.quiet},{"variance_pass",e.variancePass}}).dump()<<'\n';
    return e.valid?0:1;
}catch(const std::exception& e){std::cout<<Json({{"valid",false},{"error",e.what()}}).dump()<<'\n';return 2;}}
