// Compression recovery cannot turn a fallback into synthesis permission.
#include <cassert>
#include <iostream>
#include "NVEncFilmGrainReconConfig.h"
using namespace fgsdiagnostic;
using Json=nlohmann::json;
template<class F> void rejects(F f) {bool caught=false;try{f();}catch(...){caught=true;}assert(caught);}
int main() {
    Json request={{"pre_encode_retention",{1,1,1}},{"pre_encode_modeled_source",true}};
    for(unsigned n:{8u,16u}) {
        auto p=PreEncodeRetentionPlan::parse(request,n);
        assert(p.modeledSource() && !p.sourceSegments() && p.sourceChroma()==0);
        const auto ranges=p.modelSegments();assert(ranges.size()==1 && ranges[0].count==n && !ranges[0].source);
        assert(p.evidence()==request);rejects([&]{p.requireAllPartial();});
        auto rows=request;rows.erase("pre_encode_retention");rows["pre_encode_retention_frames"]=Json::array();
        for(unsigned i=0;i<n;++i)rows["pre_encode_retention_frames"].push_back({1,1,1});
        assert(PreEncodeRetentionPlan::parse(rows,n).modelSegments().size()==1);
        rows["pre_encode_retention_frames"][n-1][2]=.75;
        rejects([&]{PreEncodeRetentionPlan::parse(rows,n);});
    }
    for(unsigned failure=0;failure<10;++failure) {
        auto bad=request;unsigned count=8;
        if(failure==0)bad.erase("pre_encode_retention");
        if(failure==1)count=7;
        if(failure==2)count=17;
        if(failure==3)bad["pre_encode_source_segments"]=true;
        if(failure==4)bad["pre_encode_copied_chroma"]=2;
        if(failure==5)bad["pre_encode_preserved_chroma"]=6;
        if(failure==6)bad["pre_encode_modeled_source"]=1;
        if(failure==7)bad["pre_encode_modeled_source"]=nullptr;
        if(failure==8)bad["pre_encode_retention"][0]=.5;
        if(failure==9)bad["pre_encode_retention"][1]=std::numeric_limits<double>::quiet_NaN();
        rejects([&]{PreEncodeRetentionPlan::parse(bad,count);});
    }
    assert(PreEncodeRetentionPlan::parse({{"pre_encode_modeled_source",false}},8).evidence().empty());
    auto legacy=request;legacy.erase("pre_encode_modeled_source");
    rejects([&]{PreEncodeRetentionPlan::parse(legacy,8).modelSegments();});
    legacy["pre_encode_source_segments"]=true;assert(PreEncodeRetentionPlan::parse(legacy,8).modelSegments()[0].source);
    unsigned accepted=0;
    for(unsigned active=0;active<8;++active)for(unsigned guard=0;guard<32;++guard) {
        const auto d=preEncodeRetentionDecision({{1,1,1}},!(guard&1),!(guard&2),guard&4,guard&8,guard&16,active);
        if(active==7 && !guard) {requireModeledSourceRetention(d);++accepted;}
        else rejects([&]{requireModeledSourceRetention(d);});
        requireSourceRetentionModel(d,{{1,1,1}}); // Existing grain-off fallback remains usable.
    }
    assert(accepted==1);
    auto decision=preEncodeRetentionDecision({{1,1,1}},true,true,false,0,false,7);
    auto memory=std::make_shared<SourceMemory>(1048576);
    for(unsigned failure=0;failure<8;++failure) {
        auto d=decision;
        if(failure==3)d.effective[0]=.5;
        if(failure==4)d.requested[2]=.75;
        if(failure==5)d.reasonMask|=32;
        if(failure==6)d.preservedComponents=3;
        if(failure==7)d.reasonMask=0;
        NativeSourceFrame source(memory,0,0,0,1,24,128,64,10,d);
        source.modeledSourceCopied=failure!=0;
        if(failure==1)source.copiedChroma.mask=2;
        if(failure==2)source.preservedChroma=4;
        rejects([&]{source.requireModeledSource();});
    }
    assert(memory->live==0);
    {NativeSourceFrame source(memory,0,0,0,1,24,128,64,10,decision);
     source.modeledSourceCopied=true;source.requireModeledSource();}
    auto manifest=request;manifest.update({{"schema",1},{"frames",Json::array()},{"capture_source",true},
        {"output_directory","/tmp/modeled-source-test"},{"max_output_bytes",uint64_t(536870912)},
        {"native_model_output",{{"engine",{{"source_mode","memory"},{"spatial_policy","full_picture_means"},{"pre_encode_modeled_source",true}}}}}});
    Json binding={{"schema",1},{"width",128},{"height",64},{"depth",10},{"timebase",{1,24}},{"frames",Json::array()}};
    for(unsigned i=0;i<8;++i) {
        manifest["frames"].push_back(i);binding["frames"].push_back({{"ordinal",i},{"source_id",i},{"pts",i},
            {"plane_sha256",{std::string(64,'a'),std::string(64,'b'),std::string(64,'c')}}});
    }
    manifest["pre_encode_source_binding"]=binding;
    assert(NVEncFilmGrainReconConfig::parse(manifest).retention.modeledSource());
    for(unsigned failure=0;failure<9;++failure) {
        auto bad=manifest;
        if(failure==0)bad.erase("pre_encode_source_binding");
        if(failure==1)bad.erase("native_model_output");
        if(failure==2)bad["native_model_output"]["engine"].erase("pre_encode_modeled_source");
        if(failure==3)bad["native_model_output"]["engine"]["pre_encode_modeled_source"]=false;
        if(failure==4)bad["native_model_output"]["engine"]["pre_encode_modeled_source"]=1;
        if(failure==5)bad["native_model_output"]["engine"]["spatial_policy"]="frame_window_means";
        if(failure==6)bad["native_model_output"]["engine"]["source_mode"]="files";
        if(failure==7)bad["capture_source"]=false;
        if(failure==8)bad["model_output"]=nullptr;
        rejects([&]{NVEncFilmGrainReconConfig::parse(bad);});
    }
    std::cout<<"Modeled source: finite configuration, exact copy proof, 256 ordinary decisions and unchanged source fallback passed\n";
}
