// Bounded finite-template seed ranking for manual model research. A ranking
// never grants source, spatial, temporal or decoded-output qualification.
// MIT license, as NVEncFilmGrainJointTemplate.h.
#include <chrono>
#include <iostream>
#include <set>
#include "NVEncFilmGrainJointTemplate.h"
#include "json.hpp"
using Json=nlohmann::json;
using namespace fgsmodel;
int main() {
    try {
        Json j;std::cin>>j;FilmGrainJointTemplateParameters p;
        p.bitDepth=j.at("depth");p.lag=3;p.arShift=j.at("ar_shift");p.grainShift=j.at("grain_shift");
        p.lumaActive=p.cbActive=p.crActive=true;
        for(unsigned c=0;c<3;++c) {
            const auto& a=j.at("coefficients").at(c);
            if(!a.is_array() || a.size()!=(c?25:24))return 2;
            for(size_t i=0;i<a.size();++i) {
                if(!a[i].is_number_integer())return 2;
                const auto v=a[i].get<int64_t>();if(v < -128 || v >127)return 2;
                (c==0?p.y.data():(c==1?p.cb.data():p.cr.data()))[i]=uint8_t(v+128);
            }
        }
        const auto seeds=j.at("seeds").get<std::vector<unsigned>>();
        if(seeds.empty() || seeds.size()>8192 || !p.valid() || (p.bitDepth!=8 && p.bitDepth!=10))return 2;
        std::set<unsigned> unique;
        for(auto seed:seeds)if(seed>65535 || !unique.insert(seed).second)return 2;
        const auto source=j.at("source_variance").get<std::array<double,3>>();
        const auto missing=j.at("missing_variance").get<std::array<double,3>>();
        const auto bias=j.at("base_mean_error").get<std::array<double,3>>();
        const auto sourceCross=j.at("source_cross").get<std::array<double,49>>();
        const auto baseCross=j.at("base_cross").get<std::array<double,49>>();
        for(unsigned i=0;i<3;++i)if(!std::isfinite(source[i]) || source[i]<=0 || !std::isfinite(missing[i]) || missing[i]<=0 || missing[i]>source[i] || !std::isfinite(bias[i]))return 2;
        for(unsigned i=0;i<49;++i)if(!std::isfinite(sourceCross[i]) || !std::isfinite(baseCross[i]))return 2;
        const auto started=std::chrono::steady_clock::now();std::vector<Json> candidates;unsigned skipped=0;
        for(const unsigned seed:seeds) {
            if(seed==0 || seed==46372 || seed==18904){++skipped;continue;}
            FilmGrainJointTemplate grain;
            if(!film_grain_joint_template(p,uint16_t(seed),grain))return 2;
            const uint16_t nativeSeed=uint16_t(seed);
            const auto moments=film_grain_joint_template_moments(p,&nativeSeed,1);
            if(!moments.valid)return 2;
            double score=0.;std::array<double,3> mean{};
            for(unsigned c=0;c<3;++c) {
                const double variance=moments.componentSecondMoment[c]-moments.mean[c]*moments.mean[c];
                if(!(variance>0.))return 2;
                mean[c]=bias[c]+moments.mean[c]*std::sqrt(missing[c]/variance);
                score=std::max(score,std::abs(mean[c])/.125);
            }
            std::array<double,49> cross{};unsigned k=0;
            // A fixed interior template proxy; it does not model block overlap,
            // native display rounding or correlation with the actual base.
            // Final AOM/source checks remain mandatory for every selected seed.
            for(int dy=-3;dy<=3;++dy)for(int dx=-3;dx<=3;++dx) {
                double a=0.,b=0.,aa=0.,bb=0.,ab=0.;constexpr double count=26.*26.;
                for(int y=6;y<32;++y)for(int x=6;x<32;++x) {
                    const double va=grain.cb.samples[y*grain.cb.width+x];
                    const double vb=grain.cr.samples[(y+dy)*grain.cr.width+x+dx];
                    a+=va;b+=vb;aa+=va*va;bb+=vb*vb;ab+=va*vb;
                }
                const double va=aa-a*a/count,vb=bb-b*b/count;
                if(!(va>0. && vb>0.))return 2;
                const double correlation=(ab-a*b/count)/std::sqrt(va*vb);
                cross[k]=(baseCross[k]+correlation*std::sqrt(missing[1]*missing[2])-sourceCross[k])/std::sqrt(source[1]*source[2]);
                score=std::max(score,std::abs(cross[k])/.08);++k;
            }
            candidates.push_back({{"seed",seed},{"score",score},{"mean_proxy",mean},{"cross_proxy",cross}});
        }
        std::sort(candidates.begin(),candidates.end(),[](const Json& a,const Json& b){return a["score"]==b["score"]?a["seed"]<b["seed"]:a["score"]<b["score"];});
        if(candidates.size()>64)candidates.resize(64);
        std::cout<<Json({{"complete",true},{"examined",seeds.size()},{"degenerate_skipped",skipped},{"candidates",candidates},{"seconds",std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count()},{"admission",false}}).dump()<<'\n';return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 2;}
}
