// Selector/schedule mechanism controls. Complete evidence below is a unit
// fixture, not measured footage and not permission to admit a real source.
#include "NVEncFilmGrainRetentionSchedule.h"
#include <iostream>
using namespace fgsmodel;
static void require(bool b,const char* why){if(!b)throw std::runtime_error(why);}
template<class F> static void rejects(F f){bool caught=false;try{f();}catch(...){caught=true;}require(caught,"missing rejection");}
static std::vector<FilmGrainRetentionFrame> frames(unsigned count=16) {
    std::vector<FilmGrainRetentionFrame> v;
    for(unsigned i=0;i<count;++i)v.push_back({1024,512,10,int64_t(20+i),int64_t(800+40*i),1,99+i});
    return v;
}
static FilmGrainRetentionCandidate supported(const FilmGrainRetentionRequest& r) {
    FilmGrainRetentionCandidate c;c.request=r;c.modelId=100+r.component;
    c.checks={FGS_RETAIN_ALL_CHECKS,FGS_RETAIN_ALL_CHECKS};
    FilmGrainRetentionPopulationCell p;p.population=FilmGrainRetentionPopulation::Grain;
    p.nativeLookup=r.frame.bitDepth==8?128:513;p.scaling=32;p.samples=uint64_t(r.frame.width)*r.frame.height/(r.component?4:1);
    p.changedSamples=p.samples/2;p.trainBlocks=p.checkBlocks=16;
    p.checks={FGS_RETAIN_ALL_POPULATION_CHECKS,FGS_RETAIN_ALL_POPULATION_CHECKS};c.cells={p};return c;
}
static FilmGrainRetentionJointEvidence joint(const FilmGrainRetentionCombination& c) {
    return {c,{FGS_RETAIN_ALL_JOINT_CHECKS,FGS_RETAIN_ALL_JOINT_CHECKS}};
}
static FilmGrainConstantChroma measured(const FilmGrainRetentionFrame& f,unsigned mask,unsigned code,bool changed=false) {
    struct Plane {const uint16_t* data;size_t samples,stride;};
    const size_t w=f.width/2,h=f.height/2,stride=w+3;
    std::array<std::vector<uint16_t>,3> data;
    std::array<Plane,3> views{};
    for(unsigned c=1;c<3;++c)if(mask&(1u<<c)) {
        data[c].assign(stride*h,0xffff); // Padding must not certify or spoil a copy.
        for(size_t y=0;y<h;++y)for(size_t x=0;x<w;++x)data[c][y*stride+x]=uint16_t(code);
        if(changed)data[c][(h-1)*stride+w-1]++;
        views[c]={data[c].data(),data[c].size(),stride};
    }
    return film_grain_measure_constant_chroma(views,f.width,f.height,f.bitDepth,mask);
}
static void copiedSchedule() {
    unsigned positives=0,negativePlans=0;
    for(unsigned depth:{8u,10u})for(unsigned mask:{2u,4u,6u})for(unsigned code:{16u,128u,240u})for(unsigned count:{8u,16u}) {
        auto f=frames(count);for(auto& a:f){a.bitDepth=depth;a.width=130;a.height=126;}
        FilmGrainRetentionSchedule s(f,mask);
        for(const auto& a:f) {
            std::array<unsigned,3> calls{};unsigned jointCalls=0;
            s.push(a,.1f,[&](const auto& r){
                ++calls[r.component];auto c=supported(r);
                if(mask&(1u<<r.component))c.checks={};
                return c;
            },[&](const auto& combination){++jointCalls;return joint(combination);},measured(a,mask,code<<(depth-8)));
            require(calls==std::array<unsigned,3>{{1,mask&2?5u:1u,mask&4?5u:1u}} && jointCalls==1,
                "copied proof changed bounded candidate/joint search");
        }
        s.finish();for(const auto& row:s.rows()) {
            require(!row.source() && !row.reasons && row.selection.sourceMask==mask,"proved constant mixture lost");
            require(row.retain==std::array<float,3>{{.1f,mask&2?1.f:0.f,mask&4?1.f:0.f}},"copied proof changed selected fractions");
        }
        ++positives;
    }
    for(unsigned depth:{8u,10u})for(unsigned mask:{2u,4u,6u})for(unsigned variant=0;variant<11;++variant) {
        auto f=frames();for(auto& a:f)a.bitDepth=depth;
        FilmGrainRetentionSchedule s(f,mask);
        for(unsigned i=0;i<f.size();++i) {
            auto proof=measured(f[i],mask,128u<<(depth-8));
            if(variant==0)proof={};
            if(variant==1)proof=measured(f[i],mask,128u<<(depth-8),true);
            if(variant==2)proof=measured(f[i],mask,15u<<(depth-8));
            if(variant==3)proof=measured(f[i],mask,241u<<(depth-8));
            if(variant==4)proof.width+=2;
            if(variant==5)proof.depth=depth==8?10:8;
            if(variant==6 && i>=8)proof=measured(f[i],mask,129u<<(depth-8));
            if(variant==7 && i==8)proof=measured(f[i],mask,128u<<(depth-8),true);
            s.push(f[i],0,[&](const auto& r){
                auto c=supported(r);
                if((mask&(1u<<r.component)) && variant!=8)c.checks={};
                if(variant==10 && r.component==0)c.checks.passed&=~FGS_RETAIN_DETAIL;
                return c;
            },[&](const auto& combination){
                auto j=joint(combination);if(variant==9)j.checks.passed&=~FGS_RETAIN_Y_CB;return j;
            },proof);
        }
        s.finish();for(unsigned i=0;i<f.size();++i) {
            const auto& row=s.rows()[i];
            // A bad frame at ordinal 8 leaves only the earlier full 8-frame
            // segment usable. A valid but changed code has no source boundary,
            // so the entire interval is unsupported by the constant fitter.
            require(row.source()==!(variant==7 && i<8),"unproved constant plan installed");
            if(variant==6)require(row.reasons==FilmGrainRetentionSchedule::ChangedCopiedChroma,"constant change not explained");
            if(variant==8)require(row.reasons==FilmGrainRetentionSchedule::UnsupportedComponents,"option forced a source choice");
            if(variant>=9)require(row.reasons==FilmGrainRetentionSchedule::SelectedSource,"copy bypassed candidate or joint veto");
        }
        ++negativePlans;
    }
    for(unsigned sourceFirst:{0u,1u}) {
        auto f=frames();FilmGrainRetentionSchedule s(f,6);
        for(unsigned i=0;i<f.size();++i)s.push(f[i],((i<8)==bool(sourceFirst))?1.f:0.f,
            [](const auto& r){auto c=supported(r);if(r.component)c.checks={};return c;},joint,
            measured(f[i],6,(i<8?128:129)*4));
        s.finish();for(unsigned i=0;i<f.size();++i)
            require(s.rows()[i].source()==((i<8)==bool(sourceFirst)),"constant proof pooled across explicit source segment");
    }
    for(unsigned mask:{1u,3u,5u,7u,8u,UINT32_MAX})rejects([&]{FilmGrainRetentionSchedule s(frames(),mask);});
    std::cout<<"Copied-colour schedules: "<<positives<<" measured native controls, "<<negativePlans
        <<" preservation controls, both source boundaries and illegal masks passed\n";
}
int main() {try {
    const auto f=frames();unsigned partialRows=0;
    // Independent specification: a partial row survives iff it belongs to
    // at least one eight-picture window consisting entirely of partial rows.
    for(unsigned mask=0;mask<65536;++mask) {
        FilmGrainRetentionSchedule s(f);
        for(unsigned i=0;i<16;++i)s.push(f[i],(mask&(1u<<i))?1.f:0.f,supported,joint);
        rejects([&]{s.rows();});s.finish();const auto& rows=s.rows();const auto fractions=s.fractions();
        for(unsigned i=0;i<16;++i) {
            bool covered=false;
            for(unsigned start=0;start<=8;++start)
                if(start<=i && i<start+8 && !(mask&(255u<<start)))covered=true;
            require(rows[i].source()!=covered,"short interval crossed a source row");
            require(fractions[i]==rows[i].retain,"published schedule differs");
            require(rows[i].selection.sourceFrame==bool(mask&(1u<<i)),"original decision overwritten");
            require(rows[i].reasons==((mask&(1u<<i))?FilmGrainRetentionSchedule::SelectedSource:
                covered?0u:FilmGrainRetentionSchedule::ShortModelInterval),"preservation reason differs");
            partialRows+=covered;
        }
    }
    for(unsigned cb=0;cb<=5;++cb)for(unsigned cr=0;cr<=5;++cr) {
        FilmGrainRetentionSchedule s(f);
        for(const auto& frame:f) {
            unsigned calls[3]{};unsigned joints=0;
            s.push(frame,.1f,[&](const FilmGrainRetentionRequest& r){
                auto c=supported(r);const auto attempt=calls[r.component]++;
                if(r.component && attempt<(r.component==1?cb:cr))c.checks.passed&=~FGS_RETAIN_FINITE_SYNTHESIS;
                return c;
            },[&](const FilmGrainRetentionCombination& c){++joints;return joint(c);});
            require(calls[0]==1 && calls[1]==std::min(cb+1,5u) && calls[2]==std::min(cr+1,5u)
                && joints==1,"selector call bound changed");
        }
        s.finish();for(const auto& r:s.rows()) {
            require(r.source()==(cb==5 || cr==5),"unsupported mixture installed");
            require(r.reasons==((cb==5 || cr==5)?FilmGrainRetentionSchedule::UnsupportedComponents:0u),"mixture reason lost");
        }
    }
    for(unsigned boundary=1;boundary<16;++boundary) {
        auto split=f;for(unsigned i=boundary;i<16;++i)split[i].epoch=2;
        FilmGrainRetentionSchedule s(split);for(const auto& frame:split)s.push(frame,0,supported,joint);s.finish();
        require(s.rows()[boundary].reasons&FilmGrainRetentionSchedule::EpochBoundary,"epoch boundary retained history");
        for(unsigned i=0;i<16;++i) {
            const bool partial=i<boundary?boundary>=8:i>boundary && 15-boundary>=8;
            require(s.rows()[i].source()!=partial,"modeled interval crosses source epoch");
        }
    }
    for(unsigned failure=0;failure<12;++failure) {
        auto bad=f;
        if(failure==0)bad.resize(7);
        if(failure==1)bad=frames(17);
        if(failure==2)bad[8].frameId++;
        if(failure==3)bad[8].timestamp=bad[7].timestamp;
        if(failure==4)bad[8].width=1920;
        if(failure==5)bad[8].height=1080;
        if(failure==6)bad[8].bitDepth=8;
        if(failure==7)bad[8].sourcePopulationId=0;
        if(failure==8)for(auto& x:bad){x.width=64;x.height=64;}
        if(failure==9)bad[8].frameId=INT64_MAX;
        if(failure==10)bad[8].timestamp=INT64_MIN;
        if(failure==11)bad[8].width=1023;
        rejects([&]{FilmGrainRetentionSchedule s(bad);});
    }
    for(unsigned failure=0;failure<6;++failure) {
        FilmGrainRetentionSchedule s(f);auto bad=f[0];unsigned calls=0;
        if(failure==0)++bad.frameId;
        if(failure==1)++bad.timestamp;
        if(failure==2)++bad.epoch;
        if(failure==3)++bad.sourcePopulationId;
        if(failure==4)bad.width=1920;
        if(failure==5)bad.bitDepth=8;
        const auto e=[&](const FilmGrainRetentionRequest& r){++calls;return supported(r);};
        rejects([&]{s.push(bad,0,e,joint);});rejects([&]{s.push(f[0],0,e,joint);});
        rejects([&]{s.finish();});rejects([&]{s.fractions();});require(!calls,"closed/stale schedule evaluated candidate");
    }
    for(unsigned mode=0;mode<4;++mode) {
        FilmGrainRetentionSchedule s(f);
        for(const auto& frame:f)s.push(frame,0,[&](const FilmGrainRetentionRequest& r){
            auto c=supported(r);if(mode<2){c.checks.passed&=~FGS_RETAIN_DETAIL;if(mode==0)c.checks.measured&=~FGS_RETAIN_DETAIL;}return c;
        },[&](const FilmGrainRetentionCombination& c){auto j=joint(c);if(mode>=2){j.checks.passed&=~FGS_RETAIN_CB_CR;if(mode==2)j.checks.measured&=~FGS_RETAIN_CB_CR;}return j;});
        s.finish();for(const auto& r:s.rows())require(r.source() && r.reasons==FilmGrainRetentionSchedule::SelectedSource,"missing/failed evidence installed");
    }
    FilmGrainRetentionSchedule incomplete(f);incomplete.push(f[0],0,supported,joint);
    rejects([&]{incomplete.finish();});rejects([&]{incomplete.push(f[1],0,supported,joint);});rejects([&]{incomplete.rows();});
    FilmGrainRetentionSchedule broken(f);rejects([&]{broken.push(f[0],0,[](auto)->FilmGrainRetentionCandidate{throw std::runtime_error("measurement failure");},joint);});
    rejects([&]{broken.push(f[0],0,supported,joint);});
    copiedSchedule();
    std::cout<<"Retention schedule: 65536 binary plans ("<<partialRows<<" surviving partial rows), 36 component searches, 15 epochs and terminal evidence/identity failures passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
