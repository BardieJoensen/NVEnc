#include <cassert>
#include <iostream>
#include "NVEncFilmGrainRetainedColour.h"
using namespace fgsmodel;
static NV_ENC_FILM_GRAIN_PARAMS_AV1 model() {
    NV_ENC_FILM_GRAIN_PARAMS_AV1 p{};p.applyGrain=1;p.numYPoints=p.numCbPoints=p.numCrPoints=2;
    p.pointYValue[1]=p.pointCbValue[1]=p.pointCrValue[1]=255;
    p.pointYScaling[0]=p.pointYScaling[1]=60;p.pointCbScaling[0]=p.pointCbScaling[1]=40;
    return p;
}
int main() {
    for(unsigned depth:{8U,10U}) for(unsigned component=0;component<3;++component) {
        FilmGrainRetentionFrame f{66,70,depth,17,680,3,999};const size_t n=size_t(f.width)*f.height/(component?4:1);
        const unsigned scale=1u<<(depth-8);std::vector<uint16_t> source(n,128*scale),base=source;
        auto p=model();auto* curve=component==0?p.pointYScaling:component==1?p.pointCbScaling:p.pointCrScaling;
        curve[0]=curve[1]=0;
        auto counts=film_grain_source_component_counts(f,123,component,source.data(),base.data(),n);
        assert(film_grain_component_source_preserved(counts,f,123,component,p,false));
        FilmGrainNativeComponentCounts native{counts.samples,counts.changedSamples,counts.invalidSamples,counts.minimum,counts.maximum};
        auto completed=film_grain_source_component_counts_from_native(f,123,component,native);
        assert(film_grain_component_source_preserved(completed,f,123,component,p,false));
        native.samples--;assert(!film_grain_source_component_counts_from_native(f,123,component,native).complete);
        native.samples++;native.invalidSamples=n+1;assert(!film_grain_source_component_counts_from_native(f,123,component,native).complete);
        native.invalidSamples=0;native.changedSamples=n+1;assert(!film_grain_source_component_counts_from_native(f,123,component,native).complete);
        native.changedSamples=0;native.minimum=native.maximum+1;assert(!film_grain_source_component_counts_from_native(f,123,component,native).complete);
        base.back()++;auto bad=film_grain_source_component_counts(f,123,component,source.data(),base.data(),n);
        assert(bad.changedSamples==1 && !film_grain_component_source_preserved(bad,f,123,component,p,false));base=source;
        assert(!film_grain_source_component_counts(f,123,component,source.data(),base.data(),n-1).complete);
        assert(!film_grain_source_component_counts(f,123,component,nullptr,base.data(),n).complete);
        source.back()=base.back()=1u<<depth;bad=film_grain_source_component_counts(f,123,component,source.data(),base.data(),n);
        assert(bad.invalidSamples==1 && !film_grain_component_source_preserved(bad,f,123,component,p,false));source.back()=base.back()=128*scale;
        auto stale=f;stale.epoch++;assert(!film_grain_component_source_preserved(counts,stale,123,component,p,false));
        stale=f;stale.sourcePopulationId++;assert(!film_grain_component_source_preserved(counts,stale,123,component,p,false));
        assert(!film_grain_component_source_preserved(counts,f,124,component,p,false));
        curve[1]=1;assert(!film_grain_component_source_preserved(counts,f,123,component,p,false));curve[1]=0;
        p.clipToRestrictedRange=1;assert(film_grain_component_source_preserved(counts,f,123,component,p,false));
        source.back()=base.back()=0;counts=film_grain_source_component_counts(f,123,component,source.data(),base.data(),n);
        assert(!film_grain_component_source_preserved(counts,f,123,component,p,false));
        p.applyGrain=0;assert(film_grain_component_source_preserved(counts,f,123,component,p,false));p.applyGrain=1;
        source.back()=base.back()=238*scale;counts=film_grain_source_component_counts(f,123,component,source.data(),base.data(),n);
        assert(film_grain_component_source_preserved(counts,f,123,component,p,false)==(component!=0));
        assert(!film_grain_component_source_preserved(counts,f,123,component,p,true));
        if(component) {
            p.numCbPoints=p.numCrPoints=0;assert(film_grain_component_source_preserved(counts,f,123,component,p,true));
            p.chromaScalingFromLuma=1;assert(!film_grain_component_source_preserved(counts,f,123,component,p,false));
            p.pointYScaling[0]=p.pointYScaling[1]=0;p.clipToRestrictedRange=0;
            assert(film_grain_component_source_preserved(counts,f,123,component,p,false));
        }
    }
    FilmGrainRetentionFrame f{64,64,10,7,280,1,444};std::vector<uint16_t> plane(1024,512);auto p=model();
    const auto exact=film_grain_source_component_counts(f,77,2,plane.data(),plane.data(),plane.size());
    FilmGrainCollectGroup group{};group.blocks=20;group.observations=20*676;group.otherColourSupportedBlocks=3;
    constexpr unsigned C=3*FGS_COLLECT_MATRIX,L=C+27;
    const std::array<double,9> covariance{{4,.2,-.3,.2,2,.4,-.3,.4,1}};
    for(unsigned i=0;i<9;++i)group.moments[C+i]=group.moments[C+9+i]=covariance[i]*group.observations;
    group.moments[L+24]=group.moments[L+49+24]=.4*group.observations;
    FilmGrainColourMoments s,b;
    assert(!film_grain_colour_source_base(group,987,s,b));
    assert(film_grain_retained_colour_source_base(group,987,1,exact,f,77,p,false,s,b));
    assert(s.jointlySupportedBlocks==3 && s.blocks==20 && s.observations==20*676); // No subset/divisor trick.
    assert(!film_grain_colour_fidelity(s,b).valid);
    assert(!film_grain_retained_colour_fidelity(s,b,1,exact,f,77,p,false).needsSource());
    auto wrong=b;wrong.covariance[5]=wrong.covariance[7]=-.4*group.observations;wrong.cbCrLag[24]=wrong.covariance[5];
    assert(film_grain_retained_colour_fidelity(s,wrong,1,exact,f,77,p,false).needsSource());
    wrong=b;wrong.cbCrLag[0]=.5*group.observations;
    assert(film_grain_retained_colour_fidelity(s,wrong,1,exact,f,77,p,false).needsSource());
    wrong=b;wrong.covariance[8]*=.99;assert(!film_grain_retained_colour_fidelity(s,wrong,1,exact,f,77,p,false).valid);
    wrong=b;wrong.cohortId++;assert(!film_grain_retained_colour_fidelity(s,wrong,1,exact,f,77,p,false).valid);
    wrong=b;wrong.jointlySupportedBlocks=4;assert(!film_grain_retained_colour_fidelity(s,wrong,1,exact,f,77,p,false).valid);
    assert(!film_grain_retained_colour_fidelity(s,b,2,exact,f,77,p,false).valid);
    auto failed=exact;failed.changedSamples=1;assert(!film_grain_retained_colour_fidelity(s,b,1,failed,f,77,p,false).valid);
    p.pointCrScaling[1]=1;assert(!film_grain_retained_colour_fidelity(s,b,1,exact,f,77,p,false).valid);
    std::cout<<"Exact component preservation: native borders, syntax, range, identity and retained-colour covariance controls passed\n";
}
