// Direct native source/base-to-shape adapter. Never grants population approval.
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include "NVEncFilmGrainNativePair.h"
#include "json.hpp"
using Json=nlohmann::json;
using namespace fgsmodel;
template<class M> static Json moments(const M& m) {
    return {{"blocks",m.blocks},{"observations",m.observations},{"source",m.source},
        {"base",m.base},{"sourceBase",m.sourceBase}};
}
static void require(bool b,const char* why) { if(!b)throw std::runtime_error(why); }
int main() {
    try {
        Json j;std::cin>>j;const unsigned w=j.at("width"),h=j.at("height"),depth=j.at("depth");
        require(w>=64 && h>=64 && w<=4096 && h<=2160 && w%64==0 && h%64==0 && (depth==8 || depth==10),"unsupported native layout");
        const auto& frames=j.at("frames");const bool fit=j.value("fit",false);
        require(frames.is_array() && !frames.empty() && frames.size()<=16 && (!fit || frames.size()>=8),"frame budget");
        const auto start=std::chrono::steady_clock::now();Json rows=Json::array();FilmGrainNativeShapeTraining training;
        for(size_t index=0;index<frames.size();++index) {
            const auto& frame=frames[index];std::array<std::array<std::vector<uint16_t>,3>,2> data;
            std::array<std::array<FilmGrainNativePlane,3>,2> planes{};
            for(unsigned kind=0;kind<2;++kind)for(unsigned c=0;c<3;++c) {
                const unsigned width=c?w/2:w,height=c?h/2:h;const size_t count=size_t(width)*height;
                const auto path=std::filesystem::u8path(frame.at(kind?"base":"source").at(c).get<std::string>());
                require(std::filesystem::file_size(path)==count*2,"native plane byte count differs");
                auto& a=data[kind][c];a.resize(count);std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(a.data()),count*2);require(bool(file),"native plane read failed");planes[kind][c]={a.data(),count,width};
            }
            const auto pair=film_grain_native_pair(planes[0],planes[1],w,h,depth);require(pair.valid,"invalid native pair");
            Json luma=Json::array(),colour=Json::array();
            for(const auto& m:pair.luma)luma.push_back(moments(m));
            for(const auto& c:pair.colour) { Json folds=Json::array();for(const auto& m:c)folds.push_back(moments(m));colour.push_back(folds); }
            rows.push_back({{"luma",luma},{"colour",colour}});
            if(fit && index<8)require(training.push(frame.at("ordinal"),frame.at("segment"),pair),"invalid training sequence");
        }
        Json model=nullptr;
        if(fit) {
            const auto rawSeeds=j.at("seeds").get<std::vector<unsigned>>();require(!rawSeeds.empty() && rawSeeds.size()<=32,"seed budget");std::vector<uint16_t> seeds;
            for(auto seed:rawSeeds) { require(seed<=65535,"seed range");seeds.push_back(uint16_t(seed)); }
            const unsigned shift=j.at("shift"),grainShift=j.at("grain_shift");const auto shape=training.fit(shift,grainShift,seeds.data(),seeds.size());
            std::array<int,24> y{};std::array<std::array<int,25>,2> cc{};
            for(unsigned i=0;i<24;++i)y[i]=int(shape.luma.luma.parameters().y[i])-128;
            for(unsigned c=0;c<2;++c)for(unsigned i=0;i<25;++i)cc[c][i]=int(shape.colour[c].coefficients[i])-128;
            Json pooledColour=Json::array();for(const auto& c:training.colour())pooledColour.push_back(moments(c));
            model={{"valid",shape.valid()},{"reasons",shape.reasons},{"luma_coefficients",y},{"colour_coefficients",cc},
                {"luma_driver_power",shape.luma.luma.power().roundedAverageLumaPower},{"luma_gain",shape.luma.luma.power().nominalLumaGain},
                {"pooled_luma",moments(training.luma())},{"pooled_colour",pooledColour}};
        }
        std::cout<<Json({{"complete",true},{"rows",rows},{"model",model},{"seconds",std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()}}).dump()<<'\n';return 0;
    }catch(const std::exception& e) { std::cerr<<e.what()<<'\n';return 1; }
}
