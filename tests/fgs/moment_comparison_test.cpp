#include <cassert>
#include <iostream>
#include "NVEncFilmGrainMomentComparison.h"
using namespace fgsmodel;
static FilmGrainNativeMoments fixture() {
    FilmGrainNativeMoments m;
    m.valid=true; m.width=m.height=128; m.depth=10; m.blocks={2,2}; m.mean={80,128,128};
    for (auto& f:m.folds) {
        f.meanValid=true; f.mean=m.mean;
        for (unsigned i=0;i<25;++i) f.y[i*25+i]=1.;
        for (auto& c:f.colour) for (unsigned i=0;i<26;++i) c[i*26+i]=1.;
        f.common[0]=f.common[4]=f.common[8]=1.;
    }
    return m;
}
int main() {
    const auto source=fixture();
    assert(film_grain_compare_moments(source,source).fullPass);
    unsigned invalid=0;
    for (unsigned kind=0;kind<12;++kind) {
        auto a=source,b=source;
        if (kind==0) a.valid=false;
        if (kind==1) b.depth=8;
        if (kind==2) a.blocks[0]=0;
        if (kind==3) a.width=96;
        if (kind==4) a.folds[0].y[0]=0.;
        if (kind==5) b.folds[1].common[4]=-1.;
        if (kind==6) a.folds[0].cross[48]=std::numeric_limits<double>::infinity();
        if (kind==7) b.folds[1].colour[1][27]=std::numeric_limits<double>::quiet_NaN();
        if (kind==8) a.mean[0]=std::numeric_limits<double>::infinity();
        if (kind==9) a.folds[0].y[0]=1e-12;
        if (kind==10) b.folds[1].common[1]=std::numeric_limits<double>::infinity();
        if (kind==11) a.height=64;
        const auto check=film_grain_compare_moments(a,b);
        assert(!check.valid && !check.fullPass); ++invalid;
    }
    auto shifted=source; shifted.mean[0]+=.125;
    assert(film_grain_compare_moments(source,shifted).fullPass);
    shifted.mean[0]+=.00001;
    const auto mean=film_grain_compare_moments(source,shifted);
    assert(mean.valid && !mean.fullPass && !mean.folds[0].framePass);
    for (unsigned k=0;k<3;++k) {
        auto bad=source;
        if (k==0) bad.folds[0].y[1]=bad.folds[0].y[25]=.1;
        if (k==1) bad.folds[1].colour[0][0]=1.09;
        if (k==2) bad.folds[0].common[8]=.91;
        const auto c=film_grain_compare_moments(source,bad);
        assert(c.valid && !c.fullPass && (!c.folds[0].framePass || !c.folds[1].framePass));
    }
    auto colourShape=source;
    colourShape.folds[0].colour[1][1]=colourShape.folds[0].colour[1][26]=.12;
    colourShape.folds[1].cross[17]=.12;
    const auto shape=film_grain_compare_moments(source,colourShape);
    assert(shape.valid && !shape.fullPass && shape.folds[0].framePass && shape.folds[1].framePass);

    const unsigned seeds[]={27109,35028,42947,50866}; unsigned calls=0;
    const auto selected=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        FilmGrainMomentCandidate c; c.calibrated=true; c.moments=source;
        if (calls++==0) c.moments.folds[0].y[0]=.5;
        return c;
    });
    assert(calls==2 && selected.selected==1 && selected.passesDiagnostic);
    calls=0;
    const auto heldout=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        FilmGrainMomentCandidate c; c.calibrated=true; c.moments=source;
        if (calls++==0) c.moments.folds[1].y[0]=.5;
        return c;
    });
    assert(calls==1 && heldout.selected==0 && !heldout.passesDiagnostic
        && heldout.reason==FilmGrainMomentSelectionReason::CheckFold);
    calls=0;
    const auto strict=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;
        if(calls++==0)c.moments.folds[0].colour[0][1]=.12;
        return c;
    },FilmGrainMomentSpatialPolicy::FullPicture);
    assert(calls==2 && strict.selected==1 && strict.passesDiagnostic);
    for(unsigned kind=0;kind<3;++kind) {
        calls=0;
        const auto veto=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
            FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;
            if(calls++==0) {
                if(kind==0)c.moments.folds[1].colour[0][1]=.12;
                if(kind==1)c.moments.folds[1].cross[7]=.12;
                if(kind==2)c.moments.mean[0]+=.2;
            }
            return c;
        },FilmGrainMomentSpatialPolicy::FullPicture);
        assert(calls==1 && veto.selected==0 && !veto.passesDiagnostic
            && veto.reason==FilmGrainMomentSelectionReason::CheckFold);
    }
    calls=0;
    const auto noSpatial=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        ++calls;FilmGrainMomentCandidate c;c.calibrated=true;c.moments=colourShape;return c;
    },FilmGrainMomentSpatialPolicy::FullPicture);
    assert(calls==4 && noSpatial.complete && noSpatial.selected==-1);
    calls=0;
    const auto trainedMean=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;
        if(calls++==0) {
            c.moments.folds[0].mean[2]+=.126;
            c.moments.folds[1].mean[2]-=.126; // Global cancellation must not pass.
        }
        return c;
    },FilmGrainMomentSpatialPolicy::FullPictureMeans);
    assert(calls==2 && trainedMean.selected==1 && trainedMean.passesDiagnostic);
    const auto boundaryMean=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;
        c.moments.mean[1]+=.125;for(auto& f:c.moments.folds)f.mean[1]+=.125;return c;
    },FilmGrainMomentSpatialPolicy::FullPictureMeans);
    assert(boundaryMean.selected==0 && boundaryMean.passesDiagnostic);
    for(unsigned kind=0;kind<5;++kind) {
        calls=0;
        const auto veto=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
            FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;++calls;
            if(kind==0)c.moments.folds[1].mean[1]+=.126;
            if(kind==1)c.moments.folds[1].meanValid=false;
            if(kind==2)c.moments.folds[1].mean[1]=std::numeric_limits<double>::infinity();
            if(kind==3)c.moments.mean[1]+=.126;
            if(kind==4)c.moments.folds[1].cross[3]=.09;
            return c;
        },FilmGrainMomentSpatialPolicy::FullPictureMeans);
        assert(calls==1 && veto.selected==0 && !veto.passesDiagnostic
            && veto.reason==FilmGrainMomentSelectionReason::CheckFold);
    }
    for(unsigned kind=0;kind<3;++kind) {
        calls=0;
        const auto absent=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
            FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;++calls;
            if(kind==0)c.moments.folds[0].meanValid=false;
            if(kind==1)c.moments.folds[0].mean[0]=std::numeric_limits<double>::quiet_NaN();
            if(kind==2)c.moments.folds[0].mean[0]+=.126;
            return c;
        },FilmGrainMomentSpatialPolicy::FullPictureMeans);
        assert(calls==4 && absent.complete && absent.selected==-1);
    }
    auto missingMean=source;missingMean.folds[1].meanValid=false;
    assert(!film_grain_select_moment_seed(missingMean,seeds,4,[&](unsigned) {
        assert(false);return FilmGrainMomentCandidate{};
    },FilmGrainMomentSpatialPolicy::FullPictureMeans).complete);
    // The new measurements do not silently change an older declared policy.
    const auto oldPolicy=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;
        c.moments.folds[0].mean[0]+=1.;c.moments.folds[1].mean[0]-=1.;return c;
    },FilmGrainMomentSpatialPolicy::FullPicture);
    assert(oldPolicy.selected==0 && oldPolicy.passesDiagnostic);
    calls=0;
    const auto windowMean=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;
        if(calls++==0) {
            c.moments.folds[0].mean[0]+=.126;c.moments.folds[1].mean[0]-=.126;
        }
        return c;
    },FilmGrainMomentSpatialPolicy::FrameWindowMeans);
    assert(calls==2 && windowMean.selected==1 && windowMean.passesDiagnostic);
    for(unsigned kind=0;kind<5;++kind) {
        calls=0;
        const auto veto=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
            FilmGrainMomentCandidate c;c.calibrated=true;c.moments=source;++calls;
            if(kind==0) {c.moments.folds[1].mean[0]+=.3;c.moments.mean[0]+=.15;}
            if(kind==1)c.moments.folds[1].meanValid=false;
            if(kind==2)c.moments.folds[1].y[1]=.1;
            if(kind==3)c.moments.folds[1].colour[0][0]=.5;
            if(kind==4)c.moments.mean[1]+=.126;
            return c;
        },FilmGrainMomentSpatialPolicy::FrameWindowMeans);
        assert(calls==1 && veto.selected==0 && !veto.passesDiagnostic
            && veto.reason==FilmGrainMomentSelectionReason::CheckFold);
    }
    // The calibrated temporal policy preserves its per-picture protection;
    // colour spatial failures stay explicit and must pass the pooled window.
    const auto windowShape=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        FilmGrainMomentCandidate c;c.calibrated=true;c.moments=colourShape;return c;
    },FilmGrainMomentSpatialPolicy::FrameWindowMeans);
    assert(windowShape.selected==0 && windowShape.passesDiagnostic
        && !windowShape.attempts[0].comparison.fullPass);
    assert(!film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        assert(false);return FilmGrainMomentCandidate{};
    },static_cast<FilmGrainMomentSpatialPolicy>(9)).complete);
    calls=0;
    const auto none=film_grain_select_moment_seed(source,seeds,4,[&](unsigned) {
        ++calls; return FilmGrainMomentCandidate{};
    });
    assert(calls==4 && none.complete && none.selected==-1 && !none.passesDiagnostic);
    for (unsigned seed:{0u,18904u,46372u,65536u}) {
        const auto bad=film_grain_select_moment_seed(source,&seed,1,[&](unsigned) {
            assert(false); return FilmGrainMomentCandidate{};
        });
        assert(!bad.complete && !bad.passesDiagnostic);
    }
    const unsigned duplicate[]={27109,27109};
    assert(!film_grain_select_moment_seed(source,duplicate,2,[&](unsigned) {
        assert(false); return FilmGrainMomentCandidate{};
    }).complete);
    FilmGrainMomentWindow window;
    for (unsigned i=0;i<16;++i) {
        assert(window.push(i,73,source,source));
        assert(window.releaseThrough()==(i<7?-1:int64_t(i-7)));
    }
    assert(window.windows()==9 && window.finish() && window.releaseThrough()==15);
    assert(!window.push(16,73,source,source));
    for (unsigned kind=0;kind<7;++kind) {
        FilmGrainMomentWindow bad;
        assert(bad.push(0,73,source,source));
        auto actual=source;
        if (kind==0) assert(!bad.push(2,73,source,source));
        if (kind==1) assert(!bad.push(1,74,source,source));
        if (kind==2) assert(!bad.finish());
        if (kind==3) { actual.depth=8; assert(!bad.push(1,73,actual,actual)); }
        if (kind==4) { actual.folds[0].common[8]=.5; assert(!bad.push(1,73,source,actual)); }
        if (kind==5) { actual.mean[2]+=.126; assert(!bad.push(1,73,source,actual)); }
        if (kind==6) {
            for (unsigned i=1;i<7;++i) assert(bad.push(i,73,source,colourShape));
            assert(!bad.push(7,73,source,colourShape));
            assert(bad.reason()==FilmGrainMomentWindowReason::Pooled);
        }
        assert(!bad.push(1,73,source,source)); // Failure cannot be erased by later good data.
    }
    // One isolated 50% loss passes pooled variance (6.25%) but must still fail
    // the per-picture guard. A pooled-only policy would miss this dropout.
    auto dropout=source; dropout.folds[0].common[8]=.5;
    std::array<const FilmGrainNativeMoments*,8> pool{}; pool.fill(&source); pool[3]=&dropout;
    assert(film_grain_compare_moments(source,film_grain_average_moments(pool.data(),8)).fullPass);
    assert(!film_grain_compare_moments(source,dropout).folds[0].framePass);
    pool[3]=nullptr; assert(!film_grain_average_moments(pool.data(),8).valid);
    assert(!film_grain_average_moments(nullptr,0).valid);
    assert(!film_grain_average_moments(pool.data(),9).valid);
    pool.fill(&source);pool[3]=&missingMean;
    const auto incompleteMean=film_grain_average_moments(pool.data(),8);
    assert(incompleteMean.valid && incompleteMean.folds[0].meanValid
        && !incompleteMean.folds[1].meanValid && incompleteMean.folds[1].mean[0]==0.);
    auto positiveMean=source;positiveMean.folds[0].mean[0]+=.125;
    pool[3]=&positiveMean;
    const auto pooledMean=film_grain_average_moments(pool.data(),8);
    assert(pooledMean.folds[0].meanValid && pooledMean.folds[0].mean[0]==80.+.125/8);
    std::cout<<"Moment policy: "<<invalid<<" invalid measurements, independent-fold selection, bounded search, window identities/tails and isolated dropout controls passed\n";
}
