// CPU measurement adapter; complete emitted-model validation is separate.
#include "NVEncFilmGrainQuietEvidence.h"
#include "../../json/json.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
using Json=nlohmann::json;
static unsigned integer(const Json& j,unsigned low,unsigned high) {
    if(!j.is_number_integer() || j<low || j>high)throw std::runtime_error("native quiet integer outside scope");
    return j.get<unsigned>();
}
static bool flag(const Json& j) {
    if(!j.is_boolean())throw std::runtime_error("native quiet flag must be boolean");
    return j.get<bool>();
}
static Json regions(const fgsmodel::FilmGrainQuietRegions& r) {
    return {{"regions",r.regions},{"samples",r.samples},{"quiet_regions",r.quietRegions},
        {"quiet_samples",r.quietSamples},{"changed_quiet",r.changedQuiet},{"nonzero_quiet",r.nonzeroQuiet},
        {"output_changed_quiet",r.outputChangedQuiet},{"pass",r.pass()}};
}
int main(){try {
    Json input;std::cin>>input;const auto w=integer(input.at("width"),64,4096),h=integer(input.at("height"),64,2160),depth=integer(input.at("depth"),8,10);
    if((w&1) || (h&1) || depth==9)throw std::runtime_error("native quiet geometry/depth outside scope");
    const auto& m=input.at("model");fgsmodel::FilmGrainQuietModel model;
    model.apply=flag(m.at("apply"));model.restricted=flag(m.at("restricted"));model.matrix=integer(m.at("matrix"),1,9);
    if(!m.at("strength").is_array() || m.at("strength").size()!=3)throw std::runtime_error("three constant strengths required");
    for(unsigned c=0;c<3;++c)model.strength[c]=integer(m.at("strength")[c],0,255);
    std::array<std::array<std::vector<uint16_t>,3>,4> data;
    std::array<std::array<fgsmodel::FilmGrainNativePlane,3>,4> views{};
    const char* names[]={"source","rounded","reconstructed","decoded"};
    for(unsigned k=0;k<4;++k) {
        const auto& planes=input.at(names[k]);
        if(!planes.is_array() || planes.size()!=3)throw std::runtime_error("three complete native planes required");
        for(unsigned c=0;c<3;++c) {
            const auto path=std::filesystem::u8path(planes[c].get<std::string>());
            const size_t count=size_t(w)*h/(c?4:1);
            if(!path.is_absolute() || std::filesystem::file_size(path)!=count*2)throw std::runtime_error("native quiet plane byte span differs");
            std::vector<uint8_t> bytes(count*2);std::ifstream file(path,std::ios::binary);
            file.read(reinterpret_cast<char*>(bytes.data()),bytes.size());
            if(!file)throw std::runtime_error("native quiet plane read failed");
            auto& p=data[k][c];p.resize(count);
            for(size_t i=0;i<count;++i)p[i]=uint16_t(unsigned(bytes[2*i])|(unsigned(bytes[2*i+1])<<8));
            views[k][c]={p.data(),p.size(),c?w/2:w};
        }
    }
    const auto result=fgsmodel::film_grain_quiet_evidence(views[0],views[1],views[2],views[3],w,h,depth,model);
    if(!result.valid)throw std::runtime_error("invalid native quiet evidence");
    Json components=Json::array();
    for(const auto& c:result.components)components.push_back({{"fine",regions(c.fine)},{"coarse",regions(c.coarse)},
        {"quiet_pass",c.quietPass()},{"range",{{"samples",c.range.samples},{"safe",c.range.safe},
            {"ambiguous",c.range.ambiguous},{"failed",c.range.failed},{"measured",c.range.measured()},{"pass",c.range.pass()}}}});
    std::cout<<Json({{"complete",true},{"source_admission",false},{"components",components}}).dump()<<'\n';
}catch(const std::exception& e){std::cout<<Json({{"complete",false},{"error",e.what()}}).dump()<<'\n';return 1;}}
