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
    std::cout<<total<<" batched calibrations exactly match independent scalar searches; monotonicity, invalid targets and failed measurements retained\n";
}
