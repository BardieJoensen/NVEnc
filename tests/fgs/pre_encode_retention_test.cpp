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
    assert(preEncodeRetentionEvidence(source).at("grain_model")=="off; candidate measurement only");
    std::cout<<cases+1<<" pre-encode preservation, guard and invalid-candidate controls passed\n";
}
