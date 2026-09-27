#include <cassert>
#include <iostream>
#include "NVEncFilmGrainNativePair.h"
#include "NVEncFilmGrainRetainedStrengthBatch.h"
#include "NVEncFilmGrainSourceFrame.h"
#include "native_moments_json.h"
using namespace fgsmodel;
using namespace fgsdiagnostic;
struct Picture {
    unsigned width,height,depth;
    std::array<std::vector<uint16_t>,3> data;
    std::array<FilmGrainNativePlane,3> view() const {
        std::array<FilmGrainNativePlane,3> p{};
        for(unsigned c=0;c<3;++c)p[c]={data[c].data(),data[c].size(),(c?width/2:width)+5};
        return p;
    }
    Picture(unsigned w,unsigned h,unsigned d,unsigned mask,unsigned code):width(w),height(h),depth(d) {
        uint32_t state=927680;
        for(unsigned c=0;c<3;++c) {
            const unsigned cw=c?w/2:w,ch=c?h/2:h,stride=cw+5;
            data[c].assign(size_t(stride)*ch,65535); // Invalid padding must not be counted.
            for(unsigned y=0;y<ch;++y)for(unsigned x=0;x<cw;++x) {
                state=1664525*state+1013904223;
                data[c][y*stride+x]=(mask&(1u<<c))?code:uint16_t(((c?120:80)+int(state>>27))*(1u<<(d-8)));
            }
        }
    }
    FilmGrainNativeMoments moments() const {return film_grain_native_moments(view(),width,height,depth);}
};
template<class F> void rejects(F f){bool no=false;try{f();}catch(...){no=true;}assert(no);}
int main() {
    unsigned positive=0,negative=0;
    for(unsigned depth:{8u,10u})for(unsigned mask:{2u,4u,6u})
        for(auto geometry:{std::array<unsigned,2>{128,128},{130,126},{256,128}})
            for(unsigned code8:{16u,128u,240u}) {
        Picture p(geometry[0],geometry[1],depth,mask,code8<<(depth-8));
        const auto a=p.moments();const auto constant=film_grain_measure_constant_chroma(p.view(),p.width,p.height,depth,mask);
        assert(a.valid && constant.mask==mask && constant.code==a.constants.code);
        assert(film_grain_same_constant_chroma(a.constants,constant,mask,p.width,p.height,depth));
        assert(!film_grain_compare_moments(a,a).valid); // Still rejected without explicit opt-in.
        assert(film_grain_compare_moments(a,a,mask).fullPass);
        const auto roundtrip=fgsdiagnostic::moments(fgsdiagnostic::moments(a));
        assert(film_grain_compare_moments(a,roundtrip,mask).fullPass);
        auto missing=fgsdiagnostic::moments(a);missing.erase("constants");
        assert(!film_grain_compare_moments(a,fgsdiagnostic::moments(missing),mask).valid);++negative;
        FilmGrainMomentWindow window(mask);
        for(unsigned i=0;i<8;++i)assert(window.push(i,1,a,a));
        assert(window.finish() && window.releaseThrough()==7);++positive;
        for(unsigned c=1;c<3;++c)if(mask&(1u<<c)) {
            auto changed=p;const size_t last=(p.height/2-1)*(p.width/2+5)+p.width/2-1;
            changed.data[c][last]+=code8==240?-1:1;
            const auto b=changed.moments();
            assert(!film_grain_compare_moments(a,b,mask).valid);
            assert(!film_grain_measure_constant_chroma(changed.view(),p.width,p.height,depth,mask).covers(mask,p.width,p.height,depth));
            ++negative;
        }
        for(unsigned kind=0;kind<12;++kind) {
            auto b=a;const unsigned c=(mask&2)?1:2;
            if(kind==0)b.constants.mask=0;
            if(kind==1)++b.constants.code[c-1];
            if(kind==2)b.constants.depth=12;
            if(kind==3)++b.constants.width;
            if(kind==4)b.mean[c]+=.00001;
            if(kind==5)b.folds[1].mean[c]+=.00001;
            if(kind==6)b.folds[0].colour[c-1][0]=1e-20;
            if(kind==7)b.folds[1].colour[c-1][24*26]=1e-20;
            if(kind==8)b.folds[0].common[c*3]=1e-20;
            if(kind==9)b.folds[1].cross[48]=1e-20;
            if(kind==10)b.folds[1].meanValid=false;
            if(kind==11)b.constants.mask|=1;
            assert(!film_grain_compare_moments(a,b,mask).valid);++negative;
        }
        auto activeBad=a;activeBad.folds[1].y[0]*=1.09;
        assert(!film_grain_compare_moments(a,activeBad,mask).fullPass);++negative;
        for(unsigned badMask:{1u,3u,5u,7u,8u})assert(!film_grain_compare_moments(a,a,badMask).valid);
        const unsigned seeds[]={27109,35028};unsigned calls=0;
        const auto chosen=film_grain_select_moment_seed(a,seeds,2,[&](unsigned) {
            ++calls;FilmGrainMomentCandidate c;c.calibrated=true;c.moments=a;
            if(calls==1)c.moments.folds[1].y[0]*=1.09;
            return c;
        },FilmGrainMomentSpatialPolicy::FrameWindowMeans,mask);
        assert(calls==1 && chosen.selected==0 && !chosen.passesDiagnostic);++negative;
        const auto strength=film_grain_select_moment_seed(a,seeds,2,[&](unsigned) {
            FilmGrainMomentCandidate c;c.calibrated=true;c.moments=a;c.strengths[(mask&2)?1:2]=1;return c;
        },FilmGrainMomentSpatialPolicy::FrameWindowMeans,mask);
        assert(strength.complete && strength.selected==-1);++negative;
    }
    for(unsigned depth:{8u,10u})for(unsigned code:{0u,15u,241u,255u}) {
        Picture p(128,128,depth,6,code<<(depth-8));const auto a=p.moments();
        assert(a.valid && !film_grain_compare_moments(a,a,6).valid);++negative;
    }
    // Fixed codes within a modeled interval; a changing constant cannot be
    // pooled into an apparent zero-variance result.
    Picture p(128,128,10,6,512),q(128,128,10,6,513);
    const auto a=p.moments(),b=q.moments();
    FilmGrainMomentWindow window(6);assert(window.push(0,0,a,a));assert(!window.push(1,0,b,b));
    const FilmGrainNativeMoments* pair[]={&a,&b};
    const auto pooled=film_grain_average_moments(pair,2);
    assert(pooled.valid && !film_grain_compare_moments(pooled,pooled,6).valid);
    // Calibration exercises the active search unchanged and never asks for a
    // nonzero copied-component strength. The callback must still witness zero.
    for(unsigned mask:{2u,4u,6u}) {
        std::array<FilmGrainRetainedStrengthTarget,3> targets;
        for(unsigned c=0;c<3;++c)targets[c]={1,{{(mask&(1u<<c))?0.:4.,0}},{{(mask&(1u<<c))?0.:10.,0}}};
        unsigned calls=0;
        const auto fit=film_grain_calibrate_retained_strength_batch(targets,[&](auto strengths) {
            ++calls;std::array<FilmGrainRetainedStrengthMeasurement,3> m{};
            for(unsigned c=0;c<3;++c) {
                if(mask&(1u<<c))assert(strengths[c]==0);
                m[c]={true,{{double(strengths[c])/10.,0}}};
            }
            return m;
        },mask);
        assert(fit.valid && fit.complete && calls<=10);
        for(unsigned c=0;c<3;++c)assert(fit.components[c].strength==((mask&(1u<<c))?0:40));
        const auto bad=film_grain_calibrate_retained_strength_batch(targets,[&](auto) {
            std::array<FilmGrainRetainedStrengthMeasurement,3> m{};for(auto& c:m)c={true,{{1e-20,0}}};return m;
        },mask);assert(!bad.valid);
        assert(!film_grain_calibrate_retained_strength_batch(targets,[&](auto) {assert(false);return std::array<FilmGrainRetainedStrengthMeasurement,3>{};},1).valid);
    }
    // Plan and preservation association: ordinary override reasons never pass.
    for(unsigned mask:{2u,4u,6u}) {
        std::array<float,3> f{.1f,.25f,.25f};for(unsigned c=1;c<3;++c)if(mask&(1u<<c))f[c]=1;
        Json j={{"pre_encode_retention",f},{"pre_encode_copied_chroma",mask}};
        const auto plan=PreEncodeRetentionPlan::parse(j,8);
        assert(plan.copiedChroma()==mask && plan.modelSegments().size()==1 && plan.evidence()==j);
        rejects([&]{plan.requireAllPartial();});
        for(unsigned active:{7u,7u^mask}) {
            const auto d=preEncodeRetentionDecision(f,true,true,false,0,false,active);
            requirePartialRetentionModel(d,f,mask);
            rejects([&]{requirePartialRetentionModel(d,f);});
        }
        for(unsigned kind=0;kind<5;++kind) {
            const auto d=preEncodeRetentionDecision(f,kind!=0,kind!=1,kind==2,kind==3,kind==4,7);
            rejects([&]{requirePartialRetentionModel(d,f,mask);});
        }
        j["pre_encode_retention"][0]=1;rejects([&]{PreEncodeRetentionPlan::parse(j,8).modelSegments();});
        j["pre_encode_source_segments"]=true;j["pre_encode_retention"]={1,1,1};
        assert(PreEncodeRetentionPlan::parse(j,8).modelSegments()[0].source);
    }
    for(const Json bad:{Json(-1),Json(1),Json(3),Json(7),Json(4294967296ull),Json(2.0),Json(true),Json("2")})
        rejects([&]{PreEncodeRetentionPlan::parse({{"pre_encode_retention",{.1,1,.25}},{"pre_encode_copied_chroma",bad}},8);});
    // The capture proof is required as well as a source constant; changing one
    // original pixel after capture also invalidates that association.
    auto memory=std::make_shared<SourceMemory>(1024*1024);
    NativeSourceFrame source(memory,0,0,0,1,24,128,128,10);
    for(auto& plane:source.planes)std::fill(plane.begin(),plane.end(),512);
    rejects([&]{source.requireCopiedChroma(6);});
    source.copiedChroma={128,128,10,6,{512,512}};source.requireCopiedChroma(6);
    ++source.planes[2].back();rejects([&]{source.requireCopiedChroma(6);});
    std::cout<<"Constant chroma: "<<positive<<" native positive and "<<negative
        <<" pixel/moment vetoes, fixed-code windows, calibration, plans and capture association passed\n";
}
