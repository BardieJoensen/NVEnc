#include <cassert>
#include <iostream>
#include "NVEncFilmGrainModelProbe.h"
using Json=nlohmann::json;
int main() {
    const auto base=Json::parse(R"({"schema":1,"library":"/tmp/libfgsmodel.so","packets":[{"pts":0,"sha256":["0000000000000000000000000000000000000000000000000000000000000000"]},{"pts":1,"sha256":["1111111111111111111111111111111111111111111111111111111111111111"]}],"models":[null,{"apply":false}],"ready_after":1})");
    const std::set<uint32_t> captures{0,1};const auto c=NVEncFilmGrainModelConfig::parse(base,captures);
    assert(c.packets.size()==2 && c.models.size()==2 && c.readyAfter==1 && c.models[0].is_null());
    for(unsigned failure=0;failure<24;++failure) {
        auto j=base;auto frames=captures;
        if(failure==0)j["schema"]=2;
        if(failure==1)j["schema"]=1.0;
        if(failure==2)j["library"]="relative.so";
        if(failure==3)j["packets"]=Json::array();
        if(failure==4)j["models"]=Json::array();
        if(failure==5)j["models"][0]=false;
        if(failure==6)j["packets"][0]["pts"]=true;
        if(failure==7)j["packets"][0]["pts"]=INT64_MIN;
        if(failure==8)j["packets"][0]["pts"]=UINT64_MAX;
        if(failure==9)j["packets"][1]["pts"]=0;
        if(failure==10)j["packets"][1]["sha256"]=Json::array();
        if(failure==11)j["packets"][1]["sha256"]=std::vector<std::string>(3,std::string(64,'0'));
        if(failure==12)j["packets"][1]["sha256"]=std::vector<std::string>(2,std::string(64,'0'));
        if(failure==13)j["packets"][1]["sha256"]={std::string(64,'A')};
        if(failure==14)j["packets"][1]["sha256"]={std::string(63,'0')};
        if(failure==15)j["ready_after"]=2;
        if(failure==16)j["ready_after"]=-1;
        if(failure==17)j["max_pending_packets"]=0;
        if(failure==18)j["max_pending_packets"]=65;
        if(failure==19)j["max_pending_bytes"]=-1;
        if(failure==20)j["max_pending_bytes"]=268435457;
        if(failure==21)frames={0};
        if(failure==22)frames={0,2};
        if(failure==23){j["packets"]=std::vector<Json>(17,base["packets"][0]);j["models"]=std::vector<Json>(17,nullptr);}
        bool threw=false;try{NVEncFilmGrainModelConfig::parse(j,frames);}catch(const std::exception&){threw=true;}
        assert(threw);
    }
    auto signedClock=base;signedClock["packets"][0]["pts"]=-2;signedClock["packets"][1]["pts"]=-1;
    assert(NVEncFilmGrainModelConfig::parse(signedClock,captures).packets[0].pts==-2);
    auto twoHashes=base;twoHashes["packets"][0]["sha256"].push_back(std::string(64,'f'));
    assert(NVEncFilmGrainModelConfig::parse(twoHashes,captures).packets[0].hashes.size()==2);
    std::cout<<"Finite model output: complete picture/packet binding, signed clocks, exact hashes and bounded readiness passed\n";
}
