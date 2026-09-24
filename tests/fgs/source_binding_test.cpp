#include "NVEncFilmGrainReconConfig.h"
#include <iostream>
using namespace fgsdiagnostic;using Json=nlohmann::json;
static void require(bool b,const char* why){if(!b)throw std::runtime_error(why);}
template<class F> static void rejects(F f){bool caught=false;try{f();}catch(...){caught=true;}require(caught,"missing rejection");}
static Json manifest() {
    Json j={{"schema",1},{"frames",Json::array()},{"capture_source",true},{"pre_encode_retention",{1,1,1}},
        {"max_output_bytes",uint64_t(536870912)},{"output_directory","/tmp/source-binding-test"}};
    Json b={{"schema",1},{"width",128},{"height",64},{"depth",10},{"timebase",{1,24}},{"frames",Json::array()}};
    for(unsigned i=0;i<8;++i){j["frames"].push_back(i);b["frames"].push_back({{"ordinal",i},{"source_id",20+i},{"pts",-80+int(i)*40},
        {"plane_sha256",{std::string(64,'a'),std::string(64,'b'),std::string(64,'c')}}});}
    j["pre_encode_source_binding"]=b;return j;
}
int main(){try {
    const auto j=manifest();const auto b=NVEncFilmGrainReconConfig::parse(j).sourceBinding;
    require(b.enabled(),"binding not enabled");auto memory=std::make_shared<SourceMemory>(1048576);
    for(unsigned i=0;i<8;++i){NativeSourceFrame f(memory,i,20+i,-80+int(i)*40,2,48,128,64,10);unsigned c=0;
        b.require(f,[&](const auto&,unsigned depth){require(depth==10,"depth differs");return std::string(64,char('a'+c++));});require(c==3,"not all planes checked");}
    for(unsigned failure=0;failure<27;++failure) {
        auto bad=j;auto& x=bad["pre_encode_source_binding"];auto& row=x["frames"][3];
        if(failure==0)x["schema"]=1.0;
        if(failure==1)x["width"]=128.0;
        if(failure==2)x["height"]=65;
        if(failure==3)x["depth"]=9;
        if(failure==4)x["timebase"][0]=0;
        if(failure==5)x["timebase"][1]=uint64_t(INT_MAX)+1;
        if(failure==6)x["timebase"][1]=24.0;
        if(failure==7)x["frames"].erase(7);
        if(failure==8)row["ordinal"]=2;
        if(failure==9)row["ordinal"]=3.0;
        if(failure==10)row["source_id"]=23.0;
        if(failure==11)row["source_id"]=22;
        if(failure==12)row["source_id"]=uint64_t(INT_MAX)+1;
        if(failure==13)row["pts"]=40.0;
        if(failure==14)row["pts"]=int64_t(INT64_MIN);
        if(failure==15)row["pts"]=uint64_t(INT64_MAX)+1;
        if(failure==16)row["pts"]=0;
        if(failure==17)row["plane_sha256"][1]=std::string(64,'A');
        if(failure==18)row["plane_sha256"][1]=std::string(63,'a');
        if(failure==19)row["plane_sha256"][1]=4;
        if(failure==20)row["plane_sha256"].erase(2);
        if(failure==21)bad.erase("pre_encode_retention");
        if(failure==22)bad["capture_source"]=false;
        if(failure==23)bad["frames"].erase(7);
        if(failure==24)x["timebase"]={1,24,24};
        if(failure==25)x["width"]=true;
        if(failure==26)x=nullptr;
        rejects([&]{NVEncFilmGrainReconConfig::parse(bad);});
    }
    for(unsigned failure=0;failure<11;++failure) {
        NativeSourceFrame f(memory,failure==0?8:0,failure==1?21:20,failure==2?-79:-80,1,failure==3?25:24,
            failure==4?130:128,failure==5?66:64,failure==6?8:10);
        if(failure==7)f.planes[2].pop_back();
        unsigned c=0;
        rejects([&]{b.require(f,[&](const auto&,unsigned){const auto index=c++;return std::string(64,(failure>=8 && index==failure-8)?'d':char('a'+index));});});
        if(failure<8)require(c==0,"identity failure hashed content");
    }
    auto disabled=j;disabled.erase("pre_encode_source_binding");const auto off=NVEncFilmGrainReconConfig::parse(disabled).sourceBinding;
    NativeSourceFrame f(memory,0,0,0,1,24,128,64,10);
    off.require(f,[](const auto&,unsigned)->std::string{throw std::runtime_error("off path hashed");});
    std::cout<<"Source binding: exact identities/all planes, 27 typed/config failures, 11 content/identity failures and off-path passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
