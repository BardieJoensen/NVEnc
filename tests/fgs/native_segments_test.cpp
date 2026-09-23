#include <cassert>
#include <iostream>
#include "NVEncFilmGrainNativeSegments.h"
using namespace fgsdiagnostic;
using Json=nlohmann::json;
struct FakeEngine {
    static inline unsigned opened=0,pushed=0;
    Json config;size_t received=0;bool failed=false,finished=false;
    FakeEngine(const std::filesystem::path&,const Json& j):config(j) {++opened;}
    void push(uint64_t ordinal,int64_t pts,const FgsNativePlane* p) {pushPair(ordinal,pts,p,p);}
    void pushPair(uint64_t ordinal,int64_t pts,const FgsNativePlane*,const FgsNativePlane*) {
        if(config.value("fail",false) && ordinal==3) {failed=true;throw std::runtime_error("controlled model failure");}
        assert(ordinal==received && config.at("sources").at(ordinal).at("pts")==pts);
        ++received;++pushed;if(received==config.at("frame_count"))finished=true;
    }
    fgsmodel::FilmGrainModelDecision model(uint64_t ordinal) {
        if(failed)throw std::runtime_error("failed mock");
        if(received<8 || ordinal>=received)return {};
        return {fgsmodel::FilmGrainModelReadiness::Replace,{{"apply",true},{"seed",ordinal+101}}};
    }
    void finish() {if(failed || received!=config.at("frame_count"))throw std::runtime_error("incomplete mock");finished=true;}
    Json report() const {
        Json models=Json::array(),ready=Json::array(),rows=Json::array();
        for(size_t i=0;i<config.at("frame_count").get<size_t>();++i)ready.push_back(received>=8 && i<received?int64_t(std::max<size_t>(7,i)):-1);
        if(received>=8)for(size_t i=0;i<received;++i) {
            models.push_back({{"apply",true},{"seed",i+101}});rows.push_back({{"ordinal",i}});
        }
        return {{"complete",finished},{"failed",failed},{"received",received},{"selected",models.size()},
            {"models",models},{"ready_at",ready},{"rows",rows},{"spatial_policy",config.at("spatial_policy")}};
    }
};
static Json config() {
    Json j={{"schema",1},{"width",128},{"height",64},{"depth",10},{"frame_count",16},
        {"source_mode","memory"},{"spatial_policy","frame_window_means"},{"sources",Json::array()}};
    for(unsigned i=0;i<16;++i)j["sources"].push_back({{"ordinal",i},{"pts",int64_t(i)*50000}});
    return j;
}
static PreEncodeRetentionPlan plan(unsigned mask) {
    Json j={{"pre_encode_source_segments",true},{"pre_encode_retention_frames",Json::array()}};
    for(unsigned i=0;i<16;++i)j["pre_encode_retention_frames"].push_back(mask&(1u<<i)?Json{1,1,1}:Json{0,.25,.5});
    return PreEncodeRetentionPlan::parse(j,16);
}
template<class F> static void rejects(F&& f) {bool bad=false;try{f();}catch(...){bad=true;}assert(bad);}
int main() {
    unsigned accepted=0;
    for(unsigned mask=0;mask<65536;++mask) {
        bool expected=true;unsigned run=0;
        for(unsigned i=0;i<=16;++i) {
            if(i<16 && !(mask&(1u<<i)))++run;
            else {if(run && run<8)expected=false;run=0;}
        }
        bool valid=true;try {
            const auto segments=plan(mask).modelSegments();size_t covered=0;
            for(const auto& s:segments) {assert(s.begin==covered && s.count>0);covered+=s.count;}
            assert(covered==16);
        }catch(...){valid=false;}
        assert(valid==expected);accepted+=valid;
    }
    std::array<std::vector<uint16_t>,3> data;
    std::array<FgsNativePlane,3> planes{};
    for(unsigned c=0;c<3;++c) {
        const unsigned w=c?64:128,h=c?32:64;data[c].assign(w*h,512);planes[c]={data[c].data(),data[c].size(),w};
    }
    using Sequence=NativeModelSegments<FakeEngine>;
    for(unsigned mask:{0u,65535u,255u,65280u,1u,32768u}) {
        const auto p=plan(mask);const auto prior=FakeEngine::pushed,opened=FakeEngine::opened;
        Sequence s("unused",config(),p);assert(FakeEngine::opened-opened==(mask==65535?0:1));
        for(unsigned i=0;i<16;++i) {
            assert(s.model(i).state==fgsmodel::FilmGrainModelReadiness::Pending);
            s.pushPair(i,i*50000,planes.data(),planes.data());
            if(mask&(1u<<i)) {
                const auto m=s.model(i);assert(m.state==fgsmodel::FilmGrainModelReadiness::Replace && m.model==Json({{"apply",false}}));
            }
        }
        s.finish();const auto report=s.report();assert(report["complete"]==true && report["failed"]==false && report["selected"]==16);
        unsigned source=0;for(unsigned i=0;i<16;++i)source+=bool(mask&(1u<<i));
        assert(report["source_preserved"]==source && FakeEngine::pushed-prior==16-source);
        unsigned local=0;
        for(unsigned i=0;i<16;++i) {
            const auto m=s.model(i);assert(m.state==fgsmodel::FilmGrainModelReadiness::Replace);
            if(mask&(1u<<i)) {assert(m.model["apply"]==false);local=0;}
            else {assert(m.model["seed"]==local+101);++local;}
            assert(report["models"][i]==m.model && report["rows"][i]["ordinal"]==i);
        }
        if(mask==255)for(unsigned i=8;i<16;++i)assert(report["ready_at"][i]==15);
    }
    // Full-source identity/range validation remains meaningful without a fitter.
    for(unsigned kind=0;kind<8;++kind) {
        Sequence s("unused",config(),plan(65535));auto broken=planes;
        if(kind==0)broken[1].data=nullptr;
        if(kind==1)broken[1].samples=1;
        if(kind==2)broken[2].stride=1;
        if(kind==3)broken[0].stride=65537;
        if(kind==4)data[0][0]=1024;
        rejects([&]{s.pushPair(kind==5?1:0,kind==6?1:0,kind==7?nullptr:broken.data(),planes.data());});
        data[0][0]=512;rejects([&]{s.pushPair(0,0,planes.data(),planes.data());});assert(s.report()["failed"]==true);
    }
    {
        Sequence s("unused",config(),plan(255));s.pushPair(0,0,planes.data(),planes.data());
        rejects([&]{s.finish();});rejects([&]{s.model(0);});assert(s.report()["failed"]==true);
    }
    {
        auto j=config();j["fail"]=true;Sequence s("unused",j,plan(65280));
        for(unsigned i=0;i<3;++i)s.pushPair(i,i*50000,planes.data(),planes.data());
        rejects([&]{s.pushPair(3,150000,planes.data(),planes.data());});
        rejects([&]{s.pushPair(8,400000,planes.data(),planes.data());});rejects([&]{s.model(8);});assert(s.report()["failed"]==true);
    }
    for(unsigned kind=0;kind<6;++kind) {
        auto j=config();
        if(kind==0)j["sources"][8]["ordinal"]=7;
        if(kind==1)j["sources"][8]["pts"]=0;
        if(kind==2)j["sources"][0]["planes"]=Json::array();
        if(kind==3)j["source_mode"]="files";
        if(kind==4)j["width"]=127;
        if(kind==5)j["frame_count"]=15;
        rejects([&]{Sequence s("unused",j,plan(255));});
    }
    // Source-only intervals bypass the fitter but keep its strict native and
    // clock types. Numeric truncation/wrap is not a valid identity match.
    for(const auto key:{"schema","width","height","depth","frame_count"}) {
        auto j=config();j[key]=double(j.at(key).get<unsigned>());
        rejects([&]{Sequence s("unused",j,plan(65535));});
    }
    for(unsigned kind=0;kind<7;++kind) {
        auto j=config();
        if(kind==0)j["width"]=uint64_t(0x100000080ull);
        if(kind==1)j["depth"]=uint64_t(0x10000000aull);
        if(kind==2)j["sources"][1]["pts"]=50000.0;
        if(kind==3)j["sources"][1]["pts"]=uint64_t(INT64_MAX)+1;
        if(kind==4)j["sources"][0]["pts"]=INT64_MIN;
        if(kind==5)j["sources"][0]["ordinal"]=0.0;
        if(kind==6)j["schema"]=true;
        rejects([&]{Sequence s("unused",j,plan(65535));});
    }
    std::cout<<"65536 source/model schedules checked ("<<accepted<<" valid); isolated fitter ordinals, whole-source zero models, exact readiness and terminal failures passed\n";
}
