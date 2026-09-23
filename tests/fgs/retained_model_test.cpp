// Analytic construction controls. A fit is not a picture-quality clearance.
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainRetainedModel.h"
using namespace fgsmodel;
constexpr size_t N = FGS_JOINT_VARIABLES;
static FilmGrainJointMoments moments(double spatial, double correlation,
    double chromaScale=1., double lumaScale=1.) {
    FilmGrainJointMoments m; m.blocks=16; m.observations=16*676;
    for (unsigned i=0;i<N;++i)
        m.source[i*N+i]=m.observations*(i==24 ? lumaScale*lumaScale : chromaScale*chromaScale);
    m.source[23*N+25]=m.source[25*N+23]=spatial*chromaScale*chromaScale*m.observations;
    m.source[24*N+25]=m.source[25*N+24]=correlation*lumaScale*chromaScale*m.observations;
    return m;
}
static void near(double a,double b,double tol=1e-9) {
    assert(std::isfinite(a) && std::abs(a-b)<=tol*std::max(1.,std::abs(b)));
}
int main() {
    const std::array<uint16_t,4> seeds{{1031,2062,3093,4124}};
    FilmGrainJointTemplateParameters p;
    p.bitDepth=10; p.lag=3; p.arShift=7; p.grainShift=1;
    p.lumaActive=p.cbActive=p.crActive=true;
    p.y.fill(128); p.cb.fill(128); p.cr.fill(128);
    const auto luma=film_grain_retained_luma(p,seeds.data(),seeds.size());
    assert(luma.valid() && luma.parameters()==p);
    assert(!FilmGrainRetainedLuma{}.valid() && !FilmGrainRetainedChroma{}.valid());
    assert(!film_grain_retained_luma(p,nullptr,4).valid());
    assert(!film_grain_retained_luma(p,seeds.data(),513).valid());
    for (unsigned defect=0;defect<5;++defect) {
        auto bad=p;
        if (defect==0) bad.lag=2;
        if (defect==1) bad.lumaActive=false;
        if (defect==2) bad.arShift=5;
        if (defect==3) bad.grainShift=4;
        if (defect==4) bad.y[23]=255; // 127/128 horizontal pole fails 0.95 bound.
        assert(!film_grain_retained_luma(bad,seeds.data(),4).valid());
    }
    const auto single=film_grain_fit_retained_chroma({moments(.1,.2)},luma);
    assert(single.valid());
    assert(single.coefficients[23]==141); // nearest signed 0.1*128
    const double innovation=1.-.1*.1-.2*.2;
    const double expected=.2/std::sqrt(luma.power().roundedAverageLumaPower*innovation);
    assert(int(single.coefficients[24])-128==std::lround(expected*128));
    const double rawDriver=std::ldexp(double(int(single.coefficients[24])-128),-7)
        *std::sqrt(innovation*luma.power().roundedAverageLumaPower);
    near(single.groupPredictors[0][24],rawDriver);
    const double loss=std::pow(13./128.-.1,2)+std::pow(rawDriver-.2,2);
    near(single.quantizedTrainingExcess[0],loss/innovation);
    const auto rescaled=film_grain_fit_retained_chroma({moments(.1,.2,3.,.5)},luma);
    assert(rescaled.valid() && rescaled.coefficients==single.coefficients);
    near(rescaled.groupPredictors[0][24],rawDriver*6.);
    const auto balanced=film_grain_fit_retained_chroma({moments(.1,.1),moments(.3,.1)},luma);
    assert(balanced.valid() && balanced.groupPredictors.size()==2);
    // Strong coupling is representable at shared shift six but not seven.
    const auto clipped=film_grain_fit_retained_chroma({moments(0.,.6)},luma);
    assert(!clipped.valid() && clipped.reasons==FGS_RETAIN_MODEL_QUANTIZATION);
    auto coarse=p; coarse.arShift=6;
    const auto coarseLuma=film_grain_retained_luma(coarse,seeds.data(),4);
    assert(film_grain_fit_retained_chroma({moments(0.,.6)},coarseLuma).valid());
    assert(!film_grain_fit_retained_chroma({},luma).valid());
    assert(!film_grain_fit_retained_chroma(std::vector<FilmGrainJointMoments>(21,moments(0.,0.)),luma).valid());
    assert(film_grain_fit_retained_chroma({moments(0.,0.)},{}).reasons==FGS_RETAIN_MODEL_LUMA);
    for (unsigned defect=0;defect<5;++defect) {
        auto bad=moments(.1,.2);
        if (defect==0) bad.blocks=15;
        if (defect==1) bad.sourceBase[0]=1e10; // Invalid complete S/B evidence.
        if (defect==2) bad.source[0]=std::numeric_limits<double>::quiet_NaN();
        if (defect==3) { bad.base=bad.source; bad.sourceBase=bad.source; }
        if (defect==4) for (size_t i=0;i<N*N;++i) { bad.base[i]=4*bad.source[i]; bad.sourceBase[i]=2*bad.source[i]; }
        assert(!film_grain_fit_retained_chroma({bad},luma).valid());
    }
    // Native luma embedding must give the independently known scalar optimum,
    // with no coupling to the unmeasured algebraic dummy predictor.
    FilmGrainRetainedLumaMoments native;
    constexpr size_t L=FGS_RETAINED_LUMA_VARIABLES;
    native.blocks=16; native.observations=16*58*58;
    for (size_t i=0;i<L;++i) native.source[i*L+i]=native.observations;
    native.source[23*L+24]=native.source[24*L+23]=.2*native.observations;
    const auto yf=film_grain_fit_retained_luma({native},10,7,1,seeds.data(),4);
    assert(yf.valid() && yf.balanced.predictors[24]==0.);
    near(yf.balanced.predictors[23],.2);
    assert(yf.luma.parameters().y[23]==154);
    for (size_t i=0;i<23;++i) assert(yf.luma.parameters().y[i]==128);
    auto exact=native; exact.base=exact.source; exact.sourceBase=exact.source;
    assert(!film_grain_fit_retained_luma({exact},10,7,1,seeds.data(),4).valid());
    auto impossible=native; impossible.sourceBase[0]=1e12;
    assert(film_grain_fit_retained_luma({impossible},10,7,1,seeds.data(),4).reasons==FGS_RETAIN_MODEL_TARGET);
    assert(!film_grain_fit_retained_luma({native},12,7,1,seeds.data(),4).valid());
    assert(!film_grain_fit_retained_luma({native},10,7,1,nullptr,4).valid());
    // Source Y is copied; a colour-only model must neither synthesize it nor
    // invent a luma driver to explain a finite empirical source correlation.
    auto colour=moments(.1,.02);
    colour.base[24*N+24]=colour.source[24*N+24];
    for (size_t i=0;i<N;++i) colour.sourceBase[i*N+24]=colour.source[i*N+24];
    const auto marginal=film_grain_fit_retained_colour_without_luma({colour},7);
    assert(marginal.valid() && marginal.coefficients[23]==141);
    assert(marginal.balanced.predictors[24]==0.);
    // The full missing covariance remains indefinite, and is NOT repaired.
    assert(!film_grain_joint_target(colour,{}).valid);
    const auto coupledSource=moments(.1,.6);
    colour.source=coupledSource.source;
    for (size_t i=0;i<N;++i) colour.sourceBase[i*N+24]=colour.source[i*N+24];
    const auto stronglyCoupled=film_grain_fit_retained_colour_without_luma({colour},7);
    assert(stronglyCoupled.valid()); // Still only a marginal fit; joint output must veto lost coupling.
    for (unsigned defect=0;defect<4;++defect) {
        auto bad=colour;
        if (defect==0) bad.base[24*N+24]*=.9;
        if (defect==1) bad.sourceBase[25*N+24]=0.;
        if (defect==2) bad.sourceBase[0]=1e12;
        if (defect==3) bad.blocks=15;
        assert(!film_grain_fit_retained_colour_without_luma({bad},7).valid());
    }
    std::cout<<"Retained model: native luma, analytic quantization, exact model binding, shared shift and invalid evidence passed\n";
}
