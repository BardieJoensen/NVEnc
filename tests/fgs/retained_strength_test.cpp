#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainRetainedStrength.h"
using namespace fgsmodel;
int main() {
    // Deliberately nonlinear integer variance: floor-rounded weak-noise steps.
    const auto measure=[](unsigned s) {
        FilmGrainRetainedStrengthMeasurement m; m.valid=true;
        m.variance={{double((s*s)/97)/128., double((s*s)/71)/256.}}; return m;
    };
    for (unsigned channels : {1u,2u}) for (double desired : {.001,.1,.8,2.,3.9}) {
        FilmGrainRetainedStrengthTarget t{channels,{{desired,desired*.55}},{{5.,3.}}};
        const auto r=film_grain_calibrate_retained_strength(t,measure);
        assert(r.valid && r.samples.size()<=10);
        double minimum=1e10;
        for (unsigned s=0;s<256;++s) {
            const auto m=measure(s); double error=0.;
            for (unsigned c=0;c<channels;++c)
                error=std::max(error,std::abs((m.variance[c]-t.missing[c])/t.source[c]));
            minimum=std::min(minimum,error);
        }
        assert(std::abs(r.error-minimum)<1e-12);
    }
    FilmGrainRetainedStrengthTarget t{1,{{1.,0.}},{{2.,0.}}};
    auto r=film_grain_calibrate_retained_strength(t,[](unsigned s) {
        return FilmGrainRetainedStrengthMeasurement{true,{{s/1024.,0.}}}; });
    assert(r.valid && r.strength==255 && r.error>.3); // No fictitious quality pass.
    assert(r.samples.size()==2);
    for (unsigned defect=0;defect<5;++defect) {
        auto broken=t;
        if (defect==0) broken.channels=0;
        if (defect==1) broken.missing[0]=-1.;
        if (defect==2) broken.missing[0]=3.;
        if (defect==3) broken.source[0]=std::numeric_limits<double>::infinity();
        if (defect==4) broken.missing[0]=0.;
        unsigned calls=0;
        r=film_grain_calibrate_retained_strength(broken,[&](unsigned s) {++calls;return measure(s);});
        assert(!r.valid && !calls);
    }
    for (unsigned defect=0;defect<4;++defect) {
        r=film_grain_calibrate_retained_strength(t,[&](unsigned s) {
            auto m=measure(s);
            if (s==127) {
                if (defect==0) m.valid=false;
                if (defect==1) m.variance[0]=-1.;
                if (defect==2) m.variance[0]=std::numeric_limits<double>::quiet_NaN();
                if (defect==3) m.variance[0]=1e6;
            }
            return m;
        });
        assert(!r.valid && r.samples.size()==3);
    }
    std::cout<<"Retained strength: nonlinear integer oracle, joint luma minimax, finite budget and rejected measurements passed\n";
}
