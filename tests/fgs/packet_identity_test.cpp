#include <cassert>
#include "NVEncFilmGrainPacketIdentity.h"
using namespace fgsmodel;
static FilmGrainPacketHeader h(uint64_t code,unsigned hint,unsigned refresh=1,
    bool show=true,bool existing=false) {return {code,hint,7,refresh,existing,show,!show};}
int main() {
    FilmGrainPacketIdentity state;
    auto a=state.observe(0,125,100,{h(0,0,255)});assert(a.valid && a.readyPackets==std::vector<uint64_t>{0});
    a=state.observe(1,167,90,{h(1,3,1,false),h(2,1,2)});assert(a.valid && a.readyPackets.empty() && a.latestInput==3);
    a=state.observe(2,208,40,{h(3,2,4)});assert(a.valid && a.readyPackets.empty());
    a=state.observe(3,250,20,{h(1,3,0,false,true)});assert(a.valid && a.readyPackets==std::vector<uint64_t>({1,2,3}) && a.peakBytes==150 && a.peakPackets==3);
    assert(state.finish() && state.finish());assert(!state.observe(4,292,1,{h(4,4)}).valid && !state.finish());
    FilmGrainPacketIdentity wrap;
    for(unsigned i=0;i<260;++i){a=wrap.observe(i,int64_t(i)*100+1,5,{h(i,i%128,1u<<(i%8))});assert(a.valid && a.pictures[0].inputOrdinal==i && a.readyPackets==std::vector<uint64_t>{i});}
    assert(wrap.finish());
    FilmGrainPacketIdentity reset;
    for(unsigned i=0;i<20;++i){a=reset.observe(i,i+1,1,{h(i,i%10,i%10==0?255:1)});assert(a.valid && a.pictures[0].inputOrdinal==i);}
    assert(reset.finish());
    const auto fail=[](std::vector<FilmGrainPacketHeader> v,FilmGrainPacketIdentityReason why){FilmGrainPacketIdentity s;auto r=s.observe(0,1,10,v);assert(!r.valid && r.reason==why && !s.finish());assert(!s.observe(0,1,10,{h(0,0)}).valid);};
    fail({},FilmGrainPacketIdentityReason::Input);
    fail({h(0,0,1,false)},FilmGrainPacketIdentityReason::Display);
    fail({h(0,0),h(1,1)},FilmGrainPacketIdentityReason::Display);
    fail({h(1,0)},FilmGrainPacketIdentityReason::CodedOrder);
    fail({h(0,0,0,false,true)},FilmGrainPacketIdentityReason::Reference);
    fail({h(0,1,0,false),h(1,0)},FilmGrainPacketIdentityReason::Reference);
    fail({h(0,64,1,false),h(1,0)},FilmGrainPacketIdentityReason::AmbiguousPicture);
    fail({h(0,33,1,false),h(1,0)},FilmGrainPacketIdentityReason::Future);
    fail({h(0,127,1,false),h(1,0)},FilmGrainPacketIdentityReason::Future);
    fail({h(0,0,256)},FilmGrainPacketIdentityReason::Hint);
    auto bad=h(0,0);bad.hintBits=0;fail({bad},FilmGrainPacketIdentityReason::Hint);
    bad=h(0,0);bad.hintBits=6;fail({bad},FilmGrainPacketIdentityReason::Hint);
    FilmGrainPacketIdentity replay;assert(replay.observe(0,1,1,{h(0,0,255)}).valid);
    a=replay.observe(1,2,1,{h(0,0,0,false,true)});assert(!a.valid && a.reason==FilmGrainPacketIdentityReason::AmbiguousPicture);
    FilmGrainPacketIdentity duplicate;assert(duplicate.observe(0,1,1,{h(0,1,1,false),h(1,0,2)}).valid);
    a=duplicate.observe(1,2,1,{h(2,1)});assert(!a.valid && a.reason==FilmGrainPacketIdentityReason::AmbiguousPicture);
    FilmGrainPacketIdentity absent;assert(absent.observe(0,1,1,{h(0,1,1,false),h(1,0,2)}).valid);assert(!absent.finish());
    FilmGrainPacketIdentity clock;assert(clock.observe(0,10,1,{h(0,0)}).valid);assert(clock.observe(1,10,1,{h(1,1)}).reason==FilmGrainPacketIdentityReason::Clock);
    FilmGrainPacketIdentity gap;assert(gap.observe(1,1,1,{h(0,1)}).reason==FilmGrainPacketIdentityReason::Input);
    FilmGrainPacketIdentity budget(32,1,100);assert(budget.observe(0,1,80,{h(0,1,1,false),h(1,0,2)}).valid);assert(budget.observe(1,2,30,{h(0,1,0,false,true)}).reason==FilmGrainPacketIdentityReason::Buffer);
    FilmGrainPacketIdentity bytes(32,64,10);assert(bytes.observe(0,1,11,{h(0,0)}).reason==FilmGrainPacketIdentityReason::Buffer);
    FilmGrainPacketIdentity invalid(64);assert(!invalid.observe(0,1,1,{h(0,0)}).valid);
}
