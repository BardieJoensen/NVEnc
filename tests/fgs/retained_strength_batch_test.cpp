#include <cassert>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainRetainedStrengthBatch.h"
using namespace fgsmodel;
int main() {
    unsigned total=0;
    for(unsigned mode=0;mode<7;++mode)for(unsigned caseId=0;caseId<64;++caseId) {
        std::array<FilmGrainRetainedStrengthTarget,3> targets{};
        for(unsigned c=0;c<3;++c) {
            targets[c].channels=c?1:2;
            targets[c].source={1.+c,2.+c};
            for(unsigned k=0;k<targets[c].channels;++k)targets[c].missing[k]=targets[c].source[k]*(caseId+1)/65.;
        }
        if(mode==6)targets[1].missing[0]=-1.;
        auto measure=[&](unsigned c,unsigned strength) {
            FilmGrainRetainedStrengthMeasurement m;m.valid=true;
            for(unsigned k=0;k<targets[c].channels;++k) {
                const auto quantized=std::floor(double(strength)*strength*(c+k+1)/37.);
                m.variance[k]=quantized/1000.;
                if(mode==1)m.variance[k]=0.;
                if(mode==2)m.variance[k]+=10.;
                if(mode==3 && strength==127)m.variance[k]=100.;
                if(mode==4 && strength==255)m.valid=false;
                if(mode==5 && strength==0)m.variance[k]=std::numeric_limits<double>::quiet_NaN();
            }
            return m;
        };
        std::array<FilmGrainRetainedStrength,3> independent;
        for(unsigned c=0;c<3;++c)independent[c]=film_grain_calibrate_retained_strength(targets[c],[&](unsigned strength){return measure(c,strength);});
        unsigned calls=0;
        const auto batch=film_grain_calibrate_retained_strength_batch(targets,[&](const std::array<unsigned,3>& strengths) {
            ++calls;std::array<FilmGrainRetainedStrengthMeasurement,3> values;
            for(unsigned c=0;c<3;++c)values[c]=measure(c,strengths[c]);
            return values;
        });
        assert(batch.complete && calls<=10 && batch.samples.size()==calls);
        for(unsigned c=0;c<3;++c) {
            const auto& a=independent[c];const auto& b=batch.components[c];
            assert(a.valid==b.valid && a.strength==b.strength && a.error==b.error && a.samples.size()==b.samples.size());
            for(size_t i=0;i<a.samples.size();++i) {
                assert(a.samples[i].strength==b.samples[i].strength);
                assert(a.samples[i].measurement.valid==b.samples[i].measurement.valid);
            }
        }
        assert(batch.valid==std::all_of(independent.begin(),independent.end(),[](const auto& value){return value.valid;}));++total;
    }
    unsigned preserved=0;
    for(unsigned mask:{2u,4u,6u})for(double missing:{-.25,0.,.25}) {
        std::array<FilmGrainRetainedStrengthTarget,3> targets{};
        for(unsigned c=0;c<3;++c) {
            targets[c].channels=c?1:2;targets[c].source={1.,1.};targets[c].missing={.3,.3};
            if(mask&(1u<<c))targets[c].missing[0]=missing;
        }
        for(unsigned fault=0;fault<4;++fault) {
            auto measure=[&](const std::array<unsigned,3>& strengths) {
                std::array<FilmGrainRetainedStrengthMeasurement,3> values{};
                for(unsigned c=0;c<3;++c) {
                    values[c].valid=true;
                    if(mask&(1u<<c)) {
                        assert(strengths[c]==0);
                        if(fault==1)values[c].variance[0]=1e-9;
                        if(fault==2)values[c].valid=false;
                    } else values[c].variance={double(strengths[c])*strengths[c]/65536.,double(strengths[c])*strengths[c]/65536.};
                }
                return values;
            };
            auto input=targets;if(fault==3)input[(mask&2)?1:2].source[0]=0.;
            const auto batch=film_grain_calibrate_retained_strength_batch(input,measure,0,mask);
            assert(batch.valid==(fault==0));
            for(unsigned c=1;c<3;++c)if(mask&(1u<<c))assert(batch.components[c].strength==0);
            ++preserved;
        }
    }
    std::cout<<total<<" batched calibrations exactly match independent scalar searches; "<<preserved
        <<" preserved-texture calibration/zero-synthesis vetoes passed\n";
}
