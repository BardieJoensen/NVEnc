#include <cassert>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainPreEncodeRetention.h"
using namespace fgsdiagnostic;
int main() {
    unsigned cases=0;
    for(unsigned mask=0;mask<8;++mask)for(unsigned guards=0;guards<32;++guards) {
        const std::array<float,3> r{{0,.25f,.75f}};
        const auto d=preEncodeRetentionDecision(r,!(guards&1),!(guards&2),guards&4,guards&8,guards&16,mask);
        for(unsigned c=0;c<3;++c) {
            const bool preserve=guards || !(mask&(1u<<c));
            assert(d.effective[c]==(preserve?1:r[c]));
            assert(bool(d.preservedComponents&(1u<<c))==preserve);
        }
        assert(d.wholeSource()==bool(guards || !mask));++cases;
    }
    for(unsigned c=0;c<3;++c)for(float value:{-0.01f,1.01f,std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()}) {
        std::array<float,3> r{{0,0,0}};r[c]=value;bool rejected=false;
        try{preEncodeRetentionDecision(r,false,false,true,1,true,0);}catch(...){rejected=true;}
        assert(rejected);++cases; // Invalid candidates cannot hide behind fallback.
    }
    const auto source=preEncodeRetentionDecision({{1,1,1}},true,true,false,0,false,7);
    assert(source.wholeSource() && source.preservedComponents==7);
    requireSourceRetentionModel(source,{{1,1,1}});
    for(unsigned guard=0;guard<8;++guard) {
        const auto d=preEncodeRetentionDecision({{1,1,1}},!(guard&1),!(guard&2),false,0,guard&4,7);
        requireSourceRetentionModel(d,{{1,1,1}});
    }
    for(unsigned kind=0;kind<7;++kind) {
        auto d=source;auto expected=d.requested;
        if(kind==0)d.requested[0]=0;
        if(kind==1)d.effective[1]=0;
        if(kind==2)d.preservedComponents=3;
        if(kind==3)d.reasonMask=0;
        if(kind==4)d.reasonMask=32;
        if(kind==5)expected[2]=.75;
        if(kind==6)d.requested[1]=std::numeric_limits<float>::quiet_NaN();
        bool rejected=false;try{requireSourceRetentionModel(d,expected);}catch(...){rejected=true;}assert(rejected);
    }
    assert(preEncodeRetentionEvidence(source).at("grain_model")=="off; candidate measurement only");
    const std::array<float,3> requested{{.1f,.25f,.75f}};
    auto valid=preEncodeRetentionDecision(requested,true,true,false,0,false,7);
    requirePartialRetentionModel(valid,requested);
    for(unsigned mutation=0;mutation<6;++mutation) {
        auto d=valid;auto expected=requested;bool rejected=false;
        if(mutation==0)d.effective[1]=1;
        if(mutation==1)d.reasonMask=1;
        if(mutation==2)d.preservedComponents=2;
        if(mutation==3)d.requested[1]=.5;
        if(mutation==4)expected[1]=.5;
        if(mutation==5)d.effective=d.requested=expected={{1,1,1}};
        try{requirePartialRetentionModel(d,expected);}catch(...){rejected=true;}
        assert(rejected);++cases;
    }
    using Json=nlohmann::json;
    const auto disabled=PreEncodeRetentionPlan::parse(Json::object(),16);
    assert(!disabled.enabled() && disabled.evidence().empty());
    bool outside=false;try {disabled.at(0);}catch(...){outside=true;}assert(outside);
    const Json fixed={{"pre_encode_retention",{0,.1,.75}}};
    for(const auto flag:{Json(1),Json("true"),Json(nullptr)}) {
        auto j=fixed;j["pre_encode_source_segments"]=flag;
        bool rejected=false;try{PreEncodeRetentionPlan::parse(j,16);}catch(...){rejected=true;}assert(rejected);
    }
    for(unsigned kind=0;kind<3;++kind) {
        Json j={{"pre_encode_source_segments",true}};
        if(kind==1)j["pre_encode_retention"]={0,1,0};
        if(kind==2)j["pre_encode_retention_frames"]={{0,0,0},{1,1,1}};
        bool rejected=false;
        try{PreEncodeRetentionPlan::parse(j,kind==2?2:16).modelSegments();}catch(...){rejected=true;}assert(rejected);
    }
    for(unsigned count:{1u,16u}) {
        const auto plan=PreEncodeRetentionPlan::parse(fixed,count);
        assert(plan.enabled() && plan.size()==count && plan.at(count-1)==plan.at(0));
        assert(plan.at(0)[1]==.1f && plan.evidence().contains("pre_encode_retention"));
        plan.requireAllPartial();outside=false;try{plan.at(count);}catch(...){outside=true;}assert(outside);
    }
    const Json varying={{"pre_encode_retention_frames",{{0,.1,.75},{.1,.25,.5},{1,1,1}}}};
    const auto plan=PreEncodeRetentionPlan::parse(varying,3);
    assert(plan.size()==3 && plan.at(0)[1]==.1f && plan.at(1)[1]==.25f && plan.at(2)[1]==1.f);
    assert(plan.evidence().contains("pre_encode_retention_frames") && !plan.evidence().contains("pre_encode_retention"));
    outside=false;try{plan.requireAllPartial();}catch(...){outside=true;}assert(outside);
    for(unsigned ordinal=0;ordinal<3;++ordinal) {
        const auto d=preEncodeRetentionDecision(plan.at(ordinal),true,true,false,0,false,7);
        assert(d.requested==plan.at(ordinal) && d.effective==plan.at(ordinal));
        if(ordinal<2)requirePartialRetentionModel(d,plan.at(ordinal));
        outside=false;try{requirePartialRetentionModel(d,plan.at((ordinal+1)%3));}catch(...){outside=true;}assert(outside);
    }
    for(unsigned kind=0;kind<17;++kind) {
        auto j=varying;size_t count=3;
        if(kind==0)j["pre_encode_retention"]={0,0,0};
        if(kind==1)count=0;
        if(kind==2)count=17;
        if(kind==3)count=2;
        if(kind==4)count=4;
        if(kind==5)j["pre_encode_retention_frames"]=Json::array();
        if(kind==6)j["pre_encode_retention_frames"]=true;
        if(kind==7)j["pre_encode_retention_frames"][1]={0,.25};
        if(kind==8)j["pre_encode_retention_frames"][1]={0,.25,.5,.75};
        if(kind==9)j["pre_encode_retention_frames"][1][0]=true;
        if(kind==10)j["pre_encode_retention_frames"][1][0]=-.01;
        if(kind==11)j["pre_encode_retention_frames"][1][0]=1.01;
        if(kind==12)j["pre_encode_retention_frames"][1][0]=std::numeric_limits<double>::infinity();
        if(kind==13)j["pre_encode_retention_frames"][1][0]=nullptr;
        if(kind==14)j["pre_encode_retention_frames"][1]="0,.25,.5";
        if(kind==15)j=nullptr;
        if(kind==16)j["pre_encode_retention_frames"][1][0]=std::numeric_limits<double>::quiet_NaN();
        bool rejected=false;try{PreEncodeRetentionPlan::parse(j,count);}catch(...){rejected=true;}assert(rejected);++cases;
    }
    std::cout<<cases+1<<" pre-encode preservation, guard and invalid-candidate controls passed\n";
}
