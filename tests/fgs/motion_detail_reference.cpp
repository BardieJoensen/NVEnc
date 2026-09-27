// Manual native source-motion/detail diagnostic. No positive admission output.
#include "NVEncFilmGrainMotionDetail.h"
#include "../../json/json.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
using namespace fgsmodel;using Json=nlohmann::json;
static int64_t integer(const Json& j,int64_t low,int64_t high) {
    if(!j.is_number_integer() || j<low || j>high)throw std::runtime_error("invalid integer");
    return j.get<int64_t>();
}
int main(){try {
    Json j;std::cin>>j;
    const auto width=unsigned(integer(j.at("width"),32,4096)),height=unsigned(integer(j.at("height"),32,2160));
    const auto depth=unsigned(integer(j.at("depth"),8,10)),side=unsigned(integer(j.at("side"),32,64));
    const auto radius=unsigned(integer(j.at("radius"),1,32)),step=unsigned(integer(j.at("step"),2,4));
    if(j.contains("native_match") && !j.at("native_match").is_boolean())throw std::runtime_error("native matching flag must be boolean");
    const bool nativeMatch=j.value("native_match",false);
    if(!j.at("source").is_array() || j.at("source").size()!=8 || !j.at("ids").is_array() || j.at("ids").size()!=8
        || !j.at("pts").is_array() || j.at("pts").size()!=8)throw std::runtime_error("eight adjacent source frames required");
    std::array<std::vector<uint16_t>,9> storage;std::array<FilmGrainNativePlane,8> history;
    std::array<int64_t,8> ids{},pts{};
    for(unsigned f=0;f<9;++f) {
        const auto path=std::filesystem::u8path((f<8?j.at("source")[f]:j.at("base")).get<std::string>());
        const auto count=size_t(width)*height;
        if(!path.is_absolute() || std::filesystem::file_size(path)!=count*2)throw std::runtime_error("native plane span/path");
        std::ifstream file(path,std::ios::binary);std::vector<unsigned char> raw(count*2);
        file.read(reinterpret_cast<char*>(raw.data()),raw.size());if(!file)throw std::runtime_error("read failed");
        storage[f].resize(count);
        for(size_t i=0;i<count;++i)storage[f][i]=uint16_t(unsigned(raw[2*i])|(unsigned(raw[2*i+1])<<8));
        if(f<8) {
            history[f]={storage[f].data(),count,width};
            ids[f]=integer(j.at("ids")[f],0,INT32_MAX);pts[f]=integer(j.at("pts")[f],INT64_MIN+1,INT64_MAX);
        }
    }
    const auto evidence=film_grain_motion_detail(history,{storage[8].data(),storage[8].size(),width},width,height,depth,side,radius,step,ids,pts,nativeMatch);
    if(!evidence.valid)throw std::runtime_error("invalid native history/geometry/code scope");
    Json tiles=Json::array();
    for(const auto& t:evidence.tiles)tiles.push_back({{"x",t.x},{"y",t.y},{"width",t.width},{"height",t.height},
        {"fit_samples",t.fitSamples},{"dx",t.dx},{"dy",t.dy},{"training_mse",t.trainingMse},
        {"zero_mse",t.zeroMse},{"shifted_mse",t.shiftedMse},{"improvement",t.improvement},{"relative_defined",t.relativeDefined},
        {"motion_supported",t.motionSupported},{"anchor_supported",t.anchorSupported},{"conflict",t.conflict},
        {"samples",t.samples},{"changed_samples",t.changedSamples},{"projected_samples",t.projectedSamples},
        {"correlation",t.correlation},{"contrast_change",t.contrastChange},{"removed_projection_rms",t.removedProjectionRms},{"mean_error",t.meanError}});
    std::cout<<Json({{"valid",true},{"source_admission",false},{"detail_admission",false},{"tiles",tiles}}).dump(2)<<'\n';
}catch(const std::exception& e){std::cout<<Json({{"valid",false},{"error",e.what()}}).dump()<<'\n';return 1;}}
