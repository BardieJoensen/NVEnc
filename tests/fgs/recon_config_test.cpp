#include <cassert>
#include <iostream>
#include "NVEncFilmGrainReconConfig.h"
using nlohmann::json;
int main() {
    const auto base=json::parse(R"({"schema":1,"frames":[0,7,15],"max_output_bytes":536870912,"output_directory":"/tmp/fgs-recon-test"})");
    const auto c=NVEncFilmGrainReconConfig::parse(base);
    assert(c.requireLayout(3840,2160,10)==24883200);
    assert(c.requireLayout(1024,512,8)==786432);
    auto source=base;source["capture_source"]=true;source["max_source_bytes"]=uint64_t(536870912);
    const auto s=NVEncFilmGrainReconConfig::parse(source);assert(s.captureSource);s.requireLayout(3840,2160,10);
    for(unsigned failure=0;failure<7;++failure) {
        auto bad=source;bool rejected=false;
        if(failure==0)bad["capture_source"]=1;
        if(failure==1)bad["max_source_bytes"]=-1;
        if(failure==2)bad["max_source_bytes"]=uint64_t(0);
        if(failure==3)bad["max_source_bytes"]=uint64_t(536870913);
        if(failure==4)bad["capture_source"]=false;
        if(failure==5)bad["max_source_bytes"]=uint64_t(1);
        if(failure==6)bad["max_output_bytes"]=uint64_t(3*24883200+65536);
        try{NVEncFilmGrainReconConfig::parse(bad).requireLayout(3840,2160,10);}catch(...){rejected=true;}assert(rejected);
    }
    for (unsigned failure=0;failure<14;++failure) {
        auto j=base;
        if(failure==0)j["frames"]=json::array();
        if(failure==1)j["frames"]={1,1};
        if(failure==2)j["frames"]={-1};
        if(failure==3)j["frames"]={10000001};
        if(failure==4)j["frames"]={1.5};
        if(failure==5)j["frames"]={true};
        if(failure==6)j["max_output_bytes"]=-1;
        if(failure==7)j["max_output_bytes"]=uint64_t(536870913);
        if(failure==8)j["output_directory"]="relative";
        if(failure==9)j["schema"]=2;
        if(failure==10)j["frames"]=std::vector<int>(17,1);
        if(failure==11)j["max_device_bytes"]=-1;
        if(failure==12)j["max_device_bytes"]=uint64_t(2147483649);
        if(failure==13)j["max_device_bytes"]=uint64_t(0);
        bool threw=false;try{NVEncFilmGrainReconConfig::parse(j);}catch(...){threw=true;}assert(threw);
    }
    for (unsigned failure=0;failure<5;++failure) {
        auto bad=c;bool threw=false;
        if(failure==4)bad.maxBytes=100;
        try{bad.requireLayout(failure==0?8192:failure==1?1023:1024,failure==2?63:512,failure==3?12:10);}
        catch(...){threw=true;}assert(threw);
    }
    std::cout<<"Reconstruction manifest: bounded explicit identities, native layout and complete byte budget passed\n";
}
