// Necessary syntax/feedback facts for the current native fitter's model scope.
// A valid model is not source/population/detail or output-quality approval.
#include "NVEncFilmGrainStability.h"
#include "NVEncFilmGrainJointModel.h"
#include "../../json/json.hpp"
#include <iostream>
#include <stdexcept>
using Json=nlohmann::json;
static int integer(const Json& j,int lo,int hi) {
    if(!j.is_number_integer() || j<lo || j>hi)throw std::runtime_error("native model integer outside scope");
    return j.get<int>();
}
static bool flag(const Json& j) {
    if(j.is_boolean())return j.get<bool>();
    return integer(j,0,1)!=0;
}
static Json targetChecks(const Json& pairs) {
    Json result=Json::array();
    for(unsigned c=0;c<3;++c) {
        const auto& rows=c ? pairs.at("colour").at(c-1) : pairs.at("luma");
        if(!rows.is_array() || rows.size()!=2)throw std::runtime_error("two target folds required");
        Json folds=Json::array();const unsigned n=c?26:25;
        for(const auto& row:rows) {
            fgsmodel::FilmGrainJointMoments m;
            m.blocks=integer(row.at("blocks"),0,10000000);
            m.observations=integer(row.at("observations"),0,1000000000);
            const char* names[]={"source","base","sourceBase"};
            fgsmodel::FilmGrainJointMatrix* matrices[]={&m.source,&m.base,&m.sourceBase};
            for(unsigned k=0;k<3;++k) {
                const auto& data=row.at(names[k]);
                if(!data.is_array() || data.size()!=n*n)throw std::runtime_error("target matrix shape differs");
                for(unsigned y=0;y<n;++y)for(unsigned x=0;x<n;++x) {
                    const auto& j=data[y*n+x];
                    if(!j.is_number() || !std::isfinite(j.get<double>()))throw std::runtime_error("nonfinite target moment");
                    const unsigned yy=(!c && y==24)?25:y,xx=(!c && x==24)?25:x;
                    (*matrices[k])[yy*26+xx]=j.get<double>();
                }
            }
            // The native Y target has no chroma-driver variable at index 24.
            // Embed an independent unit source variable, as the actual fitter
            // does. The independent NumPy comparison keeps all 25 Y variables.
            if(!c)m.source[24*26+24]=double(m.observations);
            folds.push_back(fgsmodel::film_grain_joint_target(m,{}).valid);
        }
        result.push_back(folds);
    }
    return result;
}
int main(){try {
    Json input;std::cin>>input;const auto& m=input.at("model");
    if(!m.is_object() || !flag(m.at("apply")))throw std::runtime_error("active native model required");
    integer(input.at("depth"),8,10);if(input.at("depth")==9)throw std::runtime_error("native bit depth outside scope");
    const auto shift=integer(m.at("ar_shift"),6,9);integer(m.at("grain_shift"),0,3);integer(m.at("seed"),0,65535);
    if(integer(m.at("scaling_shift"),8,11)!=11 || !flag(m.at("overlap")) || !flag(m.at("restricted")))
        throw std::runtime_error("native fixed scaling/overlap/range scope differs");
    const auto& coefficients=m.at("coefficients");const auto& curves=m.at("curves");
    if(!coefficients.is_array() || coefficients.size()!=3 || !curves.is_array() || curves.size()!=3)
        throw std::runtime_error("native model components differ");
    Json checks=Json::array();
    for(unsigned c=0;c<3;++c) {
        const auto& values=coefficients[c];const auto& curve=curves[c];
        if(!values.is_array() || values.size()!=(c?25:24) || !curve.is_array() || curve.size()!=2
            || !curve[0].is_array() || curve[0].size()!=2 || !curve[1].is_array() || curve[1].size()!=2)
            throw std::runtime_error("native lag-three/constant-curve scope differs");
        integer(curve[0][0],0,0);integer(curve[1][0],255,255);
        const auto strength=integer(curve[0][1],0,255);
        if(integer(curve[1][1],0,255)!=strength)throw std::runtime_error("native constant-curve scope differs");
        std::array<uint8_t,25> q{};
        for(unsigned i=0;i<values.size();++i)q[i]=uint8_t(integer(values[i],-128,127)+128);
        const bool stable=fgsmodel::film_grain_ar_synthesis_safe(q.data(),3,unsigned(shift));
        checks.push_back({{"component",c},{"quantized_syntax_within_scope",true},
            {"causal_spectral_pass",stable},{"strength",strength}});
    }
    Json result={{"complete",true},{"source_admission",false},{"components",checks}};
    if(input.contains("pairs"))result["targets"]=targetChecks(input.at("pairs"));
    std::cout<<result.dump()<<'\n';
}catch(const std::exception& e){std::cout<<Json({{"complete",false},{"error",e.what()}}).dump()<<'\n';return 1;}}
