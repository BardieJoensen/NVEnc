// Joint source-minus-base targets: cross-plane retention and coupled fits.
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainJointModel.h"
using namespace fgsmodel;
constexpr size_t N=FGS_JOINT_VARIABLES;

static void near(double a,double b) { assert(std::isfinite(a)&&std::abs(a-b)<1e-8*std::max(1.0,std::abs(b))); }
static FilmGrainJointMoments identity_moments() {
    FilmGrainJointMoments m;m.blocks=256;m.observations=16384;
    for(size_t i=0;i<N;++i)m.source[i*N+i]=m.observations;
    return m;
}
int main() {
    std::array<double,N> retain{};
    auto m=identity_moments();
    auto target=film_grain_joint_target(m,retain);
    assert(target.valid);
    for(size_t i=0;i<N;++i)near(target.covariance[i*N+i],1.0);
    // A known scalar base checks the one-component variance identity, while
    // unequal retention checks the mixed terms on cross-component moments.
    for(const double r:{0.,.1,.5,1.}) {
        m=identity_moments();retain.fill(r);
        for(size_t i=0;i<N;++i) {
            m.base[i*N+i]=.25*m.observations;
            m.sourceBase[i*N+i]=.5*m.observations;
        }
        target=film_grain_joint_target(m,retain);assert(target.valid);
        for(size_t i=0;i<N;++i)near(target.covariance[i*N+i],1.-(.5+.5*r)*(.5+.5*r));
    }
    // Native 10-bit example: source is 512 +/- 2, base is 512 +/- 1.
    // A quarter of the residual gives 512 +/- 1.25 before rounding, but the
    // actual retained pixels round back to 512 +/- 1. The missing variance
    // is 3, not 2.4375. Measure the rounded base and request ZERO further
    // retention; a pre-rounding covariance identity cannot certify it.
    m=identity_moments();retain.fill(.25);
    for(size_t i=0;i<N;++i) {
        m.source[i*N+i]=4*m.observations;
        m.base[i*N+i]=m.observations;
        m.sourceBase[i*N+i]=2*m.observations;
    }
    auto beforeRounding=film_grain_joint_target(m,retain);assert(beforeRounding.valid);
    near(beforeRounding.covariance[0],2.4375);
    retain.fill(0.);
    auto measuredRounded=film_grain_joint_target(m,retain);assert(measuredRounded.valid);
    near(measuredRounded.covariance[0],3.0);
    assert(measuredRounded.covariance[0]/beforeRounding.covariance[0]-1.0>.23);
    // base = B*source, B[0,1]=.1: Cov(source_i,base_j) is asymmetric.
    m=identity_moments();retain.fill(0.);retain[1]=.5;
    for(size_t i=0;i<N;++i) {
        m.base[i*N+i]=.04*m.observations;
        m.sourceBase[i*N+i]=.2*m.observations;
    }
    m.base[0]=.05*m.observations;
    m.base[1]=m.base[N]=.02*m.observations;
    m.sourceBase[N]=.1*m.observations;
    target=film_grain_joint_target(m,retain);assert(target.valid);
    near(target.covariance[1],-.06);near(target.covariance[N],-.06);
    near(target.covariance[0],.95);near(target.covariance[N+1],.64);
    // Merely symmetrizing source/base cross-moments gives the wrong answer.
    auto symmetrized=m;symmetrized.sourceBase[1]=symmetrized.sourceBase[N]=.05*m.observations;
    assert(!film_grain_joint_target(symmetrized,retain).valid); // Impossible joint evidence.
    for(int defect=0;defect<9;++defect) {
        auto bad=m;auto r=retain;
        if(defect==0)bad.blocks=15;
        if(defect==1)bad.observations=1;
        if(defect==2)bad.source[0]=-1;
        if(defect==3)bad.source[1]=1234;
        if(defect==4)bad.sourceBase[0]=100*m.observations;
        if(defect==5)bad.base[0]=std::numeric_limits<double>::quiet_NaN();
        if(defect==6)r[0]=-.1;
        if(defect==7)r[0]=1.1;
        if(defect==8)r[0]=std::numeric_limits<double>::infinity();
        assert(!film_grain_joint_target(bad,r).valid);
    }
    // Physically valid source/base evidence can still require subtraction
    // in one direction. Independent added grain cannot realize that target.
    m=identity_moments();retain.fill(0.);
    m.base[0]=4*m.observations;m.sourceBase[0]=2*m.observations;
    assert(!film_grain_joint_target(m,retain).valid);
    // Joint least-squares control: C = .3*C_left + .4*avgY + epsilon.
    // The averaged Y variance is 4, C_left variance 9 and epsilon variance 4.
    m=identity_moments();
    for(size_t i=0;i<24;++i)m.source[i*N+i]=9*m.observations;
    m.source[24*N+24]=4*m.observations;
    m.source[23*N+25]=m.source[25*N+23]=.3*9*m.observations;
    m.source[24*N+25]=m.source[25*N+24]=.4*4*m.observations;
    m.source[25*N+25]=(.3*.3*9+.4*.4*4+4)*m.observations;
    target=film_grain_joint_target(m,retain);assert(target.valid);
    auto fit=film_grain_fit_joint_chroma(target,.5);assert(fit.valid);
    near(fit.spatial[23],.3);near(fit.rawLumaCoefficient,.4);
    near(fit.innovationVariance,4.);near(fit.lumaInnovationVariance,8.);
    near(fit.templateLumaCoefficient,.4*std::sqrt(2.));
    for(size_t i=0;i<23;++i)near(fit.spatial[i],0.);
    // Bit-depth scaling changes innovation energies, not normalized AV1 coefficients.
    for(auto& v:target.covariance)v*=16;
    auto ten=film_grain_fit_joint_chroma(target,.5);assert(ten.valid);
    near(ten.templateLumaCoefficient,fit.templateLumaCoefficient);
    near(ten.innovationVariance,16*fit.innovationVariance);
    for(double bad:{0.,-1.,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()})
        assert(!film_grain_fit_joint_chroma(target,bad).valid);
    target.valid=false;assert(!film_grain_fit_joint_chroma(target,.5).valid);
    target.valid=true;target.covariance[0]=-1;assert(!film_grain_fit_joint_chroma(target,.5).valid);
    std::cout<<"Joint source/base covariance, asymmetric retention, representability and coupled fitting passed\n";
}
