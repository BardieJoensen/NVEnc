#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainPersistentDetail.h"
using namespace fgsmodel;
static FilmGrainPersistentMoments scene(double detailBase, double retainedNoise) {
    // Independent latent persistent picture P(var64), current N(var4),
    // older mean A(var4/3) and other mean H(var1).
    const double weights[4][4] = {{1,1,0,0},{detailBase,retainedNoise,0,0},{1,0,1,0},{1,0,0,1}};
    const double variance[] = {64,4,4./3,1};
    FilmGrainPersistentMoments m; m.mean.fill(128);m.samples=1024;
    for(unsigned i=0;i<4;++i)for(unsigned j=0;j<4;++j)
        for(unsigned k=0;k<4;++k)m.covariance[i*4+j]+=weights[i][k]*weights[j][k]*variance[k];
    return m;
}
int main() {
    const FilmGrainPersistentLimits limits{.02,.125,.125,.5,.8};
    for(double noise : {0.,.1,.25,.5,.75,1.}) {
        auto out=film_grain_persistent_detail(scene(1,noise),limits);
        assert(out.valid && out.anchorsSupported && out.withinLimits);
        assert(out.contrastLoss[0]==0 && out.contrastLoss[1]==0);
        assert(std::abs(out.sourceBaseRms-2*(1-noise))<1e-12);
    }
    for(double detail : {.9,1.1}) {
        auto out=film_grain_persistent_detail(scene(detail,.25),limits);
        assert(out.valid && out.anchorsSupported && !out.withinLimits);
        assert(std::abs(out.contrastLoss[0]-(1-detail))<1e-12);
    }
    // Retaining source reduces persistent loss too; the actual rounded native
    // base must be measured by the caller rather than assumed to be this line.
    for(double r : {0.,.1,.25,.5,.75,1.}) {
        auto out=film_grain_persistent_detail(scene(.95+.05*r,r),limits);
        assert(out.valid && out.withinLimits==(r>=.75));
    }
    auto m=scene(1,.25);m.mean[1]+=.5;
    auto out=film_grain_persistent_detail(m,limits);assert(out.valid && !out.withinLimits);
    // Equal source/base power is insufficient: remove picture, replace by noise.
    m=scene(0,std::sqrt(17.));out=film_grain_persistent_detail(m,limits);
    assert(out.valid && out.anchorsSupported && !out.withinLimits);
    assert(std::abs(out.contrastLoss[0]-1)<1e-12);
    // Quiet/uncorrelated history does not become evidence of preserved detail.
    m={};m.samples=1024;m.mean.fill(128);
    out=film_grain_persistent_detail(m,limits);assert(out.valid && !out.anchorsSupported && !out.withinLimits);
    for(int defect=0;defect<5;++defect) {
        m=scene(1,.25);
        if(defect==0)m.samples=0;
        if(defect==1)m.covariance[0]=-1;
        if(defect==2)m.covariance[1]+=.1;
        if(defect==3)m.mean[0]=std::numeric_limits<double>::quiet_NaN();
        if(defect==4)m.covariance[0]=std::numeric_limits<double>::infinity();
        out=film_grain_persistent_detail(m,limits);assert(!out.valid && !out.withinLimits);
    }
    auto invalid=limits;invalid.sourceHistoryCorrelation=0;
    assert(!film_grain_persistent_detail(scene(1,.25),invalid).valid);
    std::cout<<"Persistent source projections: exact detail, lost detail, sharpening, unknown and invalid evidence passed\n";
}
