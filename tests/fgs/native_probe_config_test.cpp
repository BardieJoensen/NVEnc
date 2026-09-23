#include <cassert>
#include <iostream>
#include "NVEncFilmGrainNativeProbe.h"
int main() {
    using Json=nlohmann::json;
    Json j={{"schema",1},{"library","/tmp/model.so"},{"engine_library","/tmp/native.so"},
        {"packets",Json::array()},{"engine",{{"frame_count",8},{"width",1024},{"height",512},{"depth",10},{"sources",Json::array()}}}};
    std::set<uint32_t> captured;
    for(unsigned i=0;i<8;++i) {captured.insert(i);j["packets"].push_back({{"pts",i},{"sha256",{std::string(64,'a')}}});j["engine"]["sources"].push_back({{"ordinal",i},{"pts",i}});}
    auto c=NVEncFilmGrainNativeConfig::parse(j,captured);c.requireLayout(1024,512,10);
    for(unsigned bad=0;bad<12;++bad) {
        auto copy=j;auto frames=captured;bool rejected=false;
        if(bad==0)copy["models"]=Json::array();
        if(bad==1)copy["ready_after"]=7;
        if(bad==2)copy["engine_library"]="native.so";
        if(bad==3)copy["engine"]["frame_count"]=7;
        if(bad==4)copy["engine"]["sources"].erase(0);
        if(bad==5)copy["engine"]["sources"][1]["pts"]=9;
        if(bad==6)copy["engine"]["sources"][1]["ordinal"]=0;
        if(bad==7)copy["engine"]["width"]=1025;
        if(bad==8)copy["engine"]["height"]=480;
        if(bad==9)copy["engine"]["depth"]=8;
        if(bad==10) {frames.erase(7);copy["packets"].erase(7);}
        if(bad==11)copy["packets"][1]["sha256"]={std::string(63,'a')};
        try {auto invalid=NVEncFilmGrainNativeConfig::parse(copy,frames);invalid.requireLayout(1024,512,10);}
        catch(const std::exception&){rejected=true;}
        assert(rejected);
    }
    std::cout<<"Native model config: complete8frame identity and12 invalid/mixed-layout/source/model settings passed\n";
}
