#include "NVEncFilmGrainQuietEvidence.h"
#include <cassert>
#include <iostream>
#include <vector>
using namespace fgsmodel;
struct Picture {
    unsigned w,h;std::array<std::vector<uint16_t>,3> values;
    Picture(unsigned width=128,unsigned height=128,unsigned level=128):w(width),h(height) {
        for(unsigned c=0;c<3;++c)values[c].assign(size_t(w)*h/(c?4:1),uint16_t(level));
    }
    std::array<FilmGrainNativePlane,3> view()const {
        std::array<FilmGrainNativePlane,3> p{};
        for(unsigned c=0;c<3;++c)p[c]={values[c].data(),values[c].size(),c?w/2:w};
        return p;
    }
};
static FilmGrainQuietEvidence measure(const Picture& s,const Picture& b,const Picture& r,const Picture& d,
    unsigned depth,FilmGrainQuietModel model={}) {
    return film_grain_quiet_evidence(s.view(),b.view(),r.view(),d.view(),s.w,s.h,depth,model);
}
int main() {
    for(unsigned depth:{8u,10u}) {
        const unsigned scale=1u<<(depth-8);Picture source(130,66,128*scale);
        auto result=measure(source,source,source,source,depth);assert(result.valid);
        for(unsigned c=0;c<3;++c) {
            const auto n=source.values[c].size();const auto& r=result.components[c];
            assert(r.fine.samples==n && r.coarse.samples==n && r.range.samples==n);
            assert(r.fine.quietSamples==n && r.coarse.quietSamples==n);
            assert(r.quietPass() && r.range.pass());
            auto changed=source;changed.values[c].back()+=1;
            auto q=measure(source,changed,source,source,depth);assert(q.valid);
            assert(q.components[c].fine.changedQuiet==1 && !q.components[c].quietPass());
            FilmGrainQuietModel grain;grain.strength[c]=1;
            q=measure(source,source,source,source,depth,grain);assert(q.valid && !q.components[c].quietPass());
        }
        Picture low(128,128,0),clamped=low;
        for(auto& plane:clamped.values)for(auto& v:plane)v=16*scale;
        auto q=measure(low,low,low,clamped,depth);assert(q.valid);
        for(const auto& c:q.components)assert(c.range.measured() && !c.range.pass() && !c.quietPass());
        FilmGrainQuietModel off;off.apply=false;
        q=measure(low,low,low,low,depth,off);for(const auto& c:q.components)assert(c.range.pass() && c.quietPass());
        FilmGrainQuietModel full;full.restricted=false;
        q=measure(low,low,low,low,depth,full);for(const auto& c:q.components)assert(c.range.pass());
        full.strength={1,1,1};q=measure(low,low,low,low,depth,full);
        for(const auto& c:q.components)assert(!c.range.measured() && c.range.ambiguous==c.range.samples);
        Picture endpoint(128,128,16*scale);
        q=measure(endpoint,endpoint,endpoint,endpoint,depth);for(const auto& c:q.components)assert(c.range.pass());
        FilmGrainQuietModel nonzero;nonzero.strength={1,1,1};
        q=measure(endpoint,endpoint,endpoint,endpoint,depth,nonzero);
        for(const auto& c:q.components)assert(!c.range.measured() && !c.range.pass());
    }
    // Native alternating luma rows must never become a flat source through a
    // 2x2 average. Quiet evidence remains separate from a detail approval.
    Picture rows;for(unsigned y=0;y<128;++y)for(unsigned x=0;x<128;++x)rows.values[0][y*128+x]=uint16_t(128+(y&1?4:-4));
    auto q=measure(rows,rows,rows,rows,8);assert(q.valid && !q.components[0].fine.quietSamples && !q.components[0].coarse.quietSamples);
    // The quiet island is smaller than the statistical model tile.
    Picture island=rows;for(unsigned y=8;y<16;++y)for(unsigned x=8;x<16;++x)island.values[0][y*128+x]=128;
    FilmGrainQuietModel grain;grain.strength[0]=32;
    q=measure(island,island,island,island,8,grain);assert(q.valid && q.components[0].fine.quietSamples==64 && !q.components[0].quietPass());
    // A clean plane has large raw variance but no detrended grain.
    Picture ramp;for(unsigned y=0;y<128;++y)for(unsigned x=0;x<128;++x)ramp.values[0][y*128+x]=uint16_t(48+x);
    q=measure(ramp,ramp,ramp,ramp,8,grain);assert(q.valid && !q.components[0].fine.quietSamples && q.components[0].coarse.quietSamples==128*128 && !q.components[0].quietPass());
    Picture invalid;invalid.values[2].back()=256;
    assert(!measure(rows,rows,rows,invalid,8).valid);
    auto shortPlane=rows.view();--shortPlane[0].samples;
    assert(!film_grain_quiet_evidence(shortPlane,rows.view(),rows.view(),rows.view(),128,128,8,{}).valid);
    for(unsigned depth:{0u,9u,12u})assert(!measure(rows,rows,rows,rows,depth).valid);
    FilmGrainQuietModel bad;bad.matrix=0;assert(!measure(rows,rows,rows,rows,8,bad).valid);
    bad={};bad.strength[0]=256;assert(!measure(rows,rows,rows,rows,8,bad).valid);
    bad={};bad.apply=false;bad.strength[0]=1;assert(!measure(rows,rows,rows,rows,8,bad).valid);
    std::cout<<"Native quiet/range evidence: small islands, gradients, borders, native Y, zero curves and endpoint ambiguity passed\n";
}
