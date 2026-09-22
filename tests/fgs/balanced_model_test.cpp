// Independent analytic minimax controls; no GPU or private media dependency.
#include <array>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainBalancedModel.h"
using namespace fgsmodel;
constexpr size_t N=FGS_JOINT_VARIABLES;
static FilmGrainJointTarget target(double spatial, double luma=0., double cs=1., double ys=1.) {
    FilmGrainJointTarget t;t.valid=true;
    for(size_t i=0;i<N;++i)t.covariance[i*N+i]=(i==24?ys*ys:cs*cs);
    t.covariance[23*N+25]=t.covariance[25*N+23]=spatial*cs*cs;
    t.covariance[24*N+25]=t.covariance[25*N+24]=luma*ys*cs;
    return t;
}
static void near(double a,double b,double tol=1e-7) {assert(std::isfinite(a)&&std::abs(a-b)<=tol*std::max(1.,std::abs(b)));}
int main() {
    const auto a=target(.1),b=target(.8);
    const double sa=std::sqrt(1.-.1*.1),sb=std::sqrt(1.-.8*.8);
    const double optimum=(.1*sb+.8*sa)/(sa+sb);
    const double loss=std::pow((optimum-.1)/sa,2);
    const auto fit=film_grain_fit_balanced_chroma({a,b});assert(fit.valid);
    near(fit.predictors[23],optimum);near(fit.predictors[24],0.);
    near(fit.maximumRelativeExcess,loss);near(fit.lowerBound,loss);
    assert(fit.dualityGap<=1e-7 && fit.maximumRelativeExcess>.08); // Valid optimization can still fail quality.
    // Dense scalar search is independent of the simplex-dual algorithm.
    double grid=1e9;
    for(int i=0;i<=100000;++i){double x=i/100000.;grid=std::min(grid,std::max(std::pow((x-.1)/sa,2),std::pow((x-.8)/sb,2)));}
    assert(fit.lowerBound<=grid+1e-10 && grid-fit.lowerBound<1e-5);
    const auto scaled=film_grain_fit_balanced_chroma({target(.1,0.,2.,3.),target(.8,0.,17.,.5)});assert(scaled.valid);
    near(scaled.predictors[23],optimum);near(scaled.maximumRelativeExcess,loss);
    near(scaled.chromaScale[0],2.);near(scaled.lumaScale[1],.5);
    const auto reordered=film_grain_fit_balanced_chroma({b,target(optimum),a});assert(reordered.valid);
    near(reordered.predictors[23],optimum);near(reordered.maximumRelativeExcess,loss);
    assert(reordered.weights[1]<1e-8); // Interior group cannot dilute the worst groups.
    const auto duplicate=film_grain_fit_balanced_chroma({b,a,b});assert(duplicate.valid);
    near(duplicate.predictors[23],optimum);near(duplicate.maximumRelativeExcess,loss);
    // Two-dimensional coupled predictors have the same analytic line solution.
    const double s0=std::sqrt(1.-.2*.2-.3*.3),s1=std::sqrt(1.-.4*.4-.5*.5);
    const auto coupled=film_grain_fit_balanced_chroma({target(.2,.3),target(-.4,.5)});assert(coupled.valid);
    near(coupled.predictors[23],(.2*s1-.4*s0)/(s0+s1));
    near(coupled.predictors[24],(.3*s1+.5*s0)/(s0+s1));
    const auto same=film_grain_fit_balanced_chroma({a,a});assert(same.valid);
    near(same.predictors[23],.1);near(same.maximumRelativeExcess,0.);
    assert(!film_grain_fit_balanced_chroma({}).valid);
    assert(!film_grain_fit_balanced_chroma(std::vector<FilmGrainJointTarget>(21,a)).valid);
    assert(!film_grain_fit_balanced_chroma({a},0).valid);
    assert(!film_grain_fit_balanced_chroma({a},4097).valid);
    for(double tol:{0.,-.1,.01,std::numeric_limits<double>::quiet_NaN()})assert(!film_grain_fit_balanced_chroma({a},256,tol).valid);
    for(int defect=0;defect<4;++defect){auto bad=a;if(defect==0)bad.valid=false;if(defect==1)bad.covariance[24*N+24]=0.;if(defect==2)bad.covariance[0]=-1.;if(defect==3)bad.covariance[25*N+25]=std::numeric_limits<double>::infinity();assert(!film_grain_fit_balanced_chroma({bad}).valid);}
    const auto unfinished=film_grain_fit_balanced_chroma({target(0.,0.),target(.6,0.),target(0.,.4)},1);
    assert(!unfinished.valid && unfinished.dualityGap>1e-7);
    std::cout<<"Balanced chroma: analytic/grid optimum, scaling, coupling, bounds and bounded convergence passed\n";
}
