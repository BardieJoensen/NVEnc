#include <cassert>
#include <cmath>
#include <iostream>
#include <algorithm>
// The real CUDA filter includes the legacy function-like clamp macro first.
#define clamp(value, low, high) legacy_clamp_must_not_expand_here(value, low, high)
#include "NVEncFilmGrainJointTemplate.h"
#undef clamp
#include "joint_template_vectors.h"
using namespace fgsmodel;
template<size_t N>static uint64_t hash(const std::array<int16_t,N>& a) {
    uint64_t h=14695981039346656037ULL;
    for(int16_t value:a)for(unsigned shift:{0U,8U}){h^=(uint16_t(value)>>shift)&255;h*=1099511628211ULL;}
    return h;
}
int main() {
    for(const auto& v:jointTemplateVectors) {
        FilmGrainJointTemplateParameters p{v.depth,v.lag,v.arShift,v.grainShift,true,true,true,v.y,v.cb,v.cr};
        FilmGrainJointTemplate out;
        assert(film_grain_joint_template(p,v.seed,out) && out.valid && out.parameters==p && out.seed==v.seed);
        assert(hash(out.y.samples)==v.hash[0] && hash(out.cb.samples)==v.hash[1] && hash(out.cr.samples)==v.hash[2]);
        const auto m=film_grain_joint_template_moments(p,&v.seed,1);
        assert(m.valid && m.parameters==p && m.seeds==1);
        for(unsigned i=0;i<3;++i) {
            assert(m.mean[i]==v.moments[i] && m.componentSecondMoment[i]==v.moments[3+i]);
            const double expected=std::sqrt(v.moments[3+i])/std::ldexp(32.0,int(v.depth)-8-int(v.grainShift));
            assert(std::abs(m.nominalGain[i]-expected)<1e-12);
        }
        for(unsigned i=0;i<9;++i)assert(m.jointSecondMoment[i]==v.moments[6+i]);
        assert(m.driverMean==v.moments[15] && m.driverSecondMoment==v.moments[16]);
        assert(m.driverColourSecondMoment[0]==v.moments[17] && m.driverColourSecondMoment[1]==v.moments[18]);
        p.crActive=false;
        assert(film_grain_joint_template(p,v.seed,out) && out.cr.samples==FilmGrainChromaTemplate{}.samples);
        const auto quiet=film_grain_joint_template_moments(p,&v.seed,1);
        assert(quiet.valid && quiet.nominalGain[2]==0 && quiet.componentSecondMoment[2]==0 && quiet.mean[2]==0);
        for(unsigned i=0;i<3;++i)assert(quiet.jointSecondMoment[i*3+2]==0 && quiet.jointSecondMoment[6+i]==0);
        p.lumaActive=false;
        assert(film_grain_joint_template(p,v.seed,out));const auto absent=out.cb.samples;
        p.cb[24]=0;assert(film_grain_joint_template(p,v.seed,out) && out.cb.samples==absent);
        assert(out.y.samples==FilmGrainLumaTemplate{}.samples);
        p.bitDepth=9;assert(!film_grain_joint_template(p,v.seed,out) && !out.valid);
        assert(out.cb.samples==FilmGrainChromaTemplate{}.samples);
    }
    FilmGrainJointTemplateParameters p{10,3,7,0,true,true,true};p.y.fill(128);p.cb.fill(128);p.cr.fill(128);
    p.y[23]+=116;p.cb[23]+=96;p.cb[24]+=110;p.cr[23]+=96;p.cr[24]-=110;
    std::array<uint16_t,32> seeds{};for(unsigned i=0;i<seeds.size();++i)seeds[i]=(i+1)*1031;
    const auto zero=film_grain_joint_template_moments(p,seeds.data(),seeds.size());p.grainShift=1;
    const auto one=film_grain_joint_template_moments(p,seeds.data(),seeds.size());
    assert(zero.valid && one.valid && zero.clippedFraction[1]>.001 && one.clippedFraction[1]<zero.clippedFraction[1]);
    assert(std::abs(one.nominalGain[1]/zero.nominalGain[1]-1)>.05);
    assert(one.jointSecondMoment[1]>0 && one.jointSecondMoment[2]<0 && one.jointSecondMoment[5]<0);
    assert(!film_grain_joint_template_moments(p,nullptr,1).valid);
    assert(!film_grain_joint_template_moments(p,seeds.data(),0).valid);
    assert(!film_grain_joint_template_moments(p,seeds.data(),65537).valid);
    FilmGrainJointTemplate out;
    for(unsigned invalid:{0U,5U,10U,32U}){p.arShift=invalid;assert(!film_grain_joint_template(p,1,out));}
    p.arShift=7;p.lag=4;assert(!film_grain_joint_template(p,1,out));
    p.lag=3;p.grainShift=4;assert(!film_grain_joint_template(p,1,out));
    std::cout<<"Joint template: 12 independent AOM vectors, all-plane moments, quiet/absent components and scale-dependent clipping passed\n";
}
