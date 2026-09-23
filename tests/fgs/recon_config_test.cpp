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
    auto retention=source;retention["frames"]={0,1,2};retention["pre_encode_retention"]={0,.25,1};
    const auto candidate=NVEncFilmGrainReconConfig::parse(retention);assert(candidate.preEncodeRetention() && candidate.retention.at(2)[1]==.25f);
    auto native=retention;native["pre_encode_retention"]={0,.25,.75};native["native_model_output"]={{"engine",{{"source_mode","memory"}}}};
    assert(NVEncFilmGrainReconConfig::parse(native).preEncodeRetention());
    auto varying=native;varying.erase("pre_encode_retention");
    varying["pre_encode_retention_frames"]={{0,.25,.75},{.1,.25,.5},{0,0,0}};
    const auto scheduled=NVEncFilmGrainReconConfig::parse(varying);
    assert(scheduled.preEncodeRetention() && scheduled.retention.size()==3
        && scheduled.retention.at(1)[0]==.1f && scheduled.retention.at(2)[1]==0.f);
    for(unsigned failure=0;failure<8;++failure) {
        auto bad=varying;bool rejected=false;
        if(failure==0)bad["pre_encode_retention"]={0,0,0};
        if(failure==1)bad["pre_encode_retention_frames"][2][2]=1;
        if(failure==2)bad["frames"]={0,2,3};
        if(failure==3)bad["capture_source"]=false;
        if(failure==4)bad["pre_encode_retention_frames"].erase(2);
        if(failure==5)bad["native_model_output"]["engine"]["source_mode"]="files";
        if(failure==6)bad["model_output"]=nullptr;
        if(failure==7)bad["pre_encode_retention_frames"][0][0]=.99999999999;
        try{NVEncFilmGrainReconConfig::parse(bad);}catch(...){rejected=true;}assert(rejected);
    }
    for(unsigned failure=0;failure<3;++failure) {
        auto bad=native;bool rejected=false;
        if(failure==0)bad["native_model_output"]["engine"]["source_mode"]="files";
        if(failure==1)bad["pre_encode_retention"][1]=1;
        if(failure==2)bad["pre_encode_retention"][0]=true;
        try{NVEncFilmGrainReconConfig::parse(bad);}catch(...){rejected=true;}assert(rejected);
    }
    for(unsigned failure=0;failure<11;++failure) {
        auto bad=retention;bool rejected=false;
        if(failure==0)bad["capture_source"]=false;
        if(failure==1)bad["frames"]={1,2,3};
        if(failure==2)bad["frames"]={0,2};
        if(failure==3)bad["pre_encode_retention"]={0,1};
        if(failure==4)bad["pre_encode_retention"]={0,true,1};
        if(failure==5)bad["pre_encode_retention"]={0,-.1,1};
        if(failure==6)bad["pre_encode_retention"]={0,1.001,1};
        if(failure==7)bad["pre_encode_retention"]={0,std::numeric_limits<double>::infinity(),1};
        if(failure==8)bad["model_output"]=nullptr;
        if(failure==9)bad["native_model_output"]=nullptr;
        if(failure==10)bad["pre_encode_retention"]="0,.25,1";
        try{NVEncFilmGrainReconConfig::parse(bad);}catch(...){rejected=true;}assert(rejected);
    }
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
