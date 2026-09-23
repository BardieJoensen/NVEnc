#include <cassert>
#include <iostream>
#include "NVEncFilmGrainModelEvidence.h"
#include "joint_template_vectors.h"
using namespace fgsmodel;
using Json = nlohmann::json;
int main() {
    assert(film_grain_probe_template_seeds(Json::object()).empty());
    const auto seeds=film_grain_probe_template_seeds({{"template_seeds",{0,1,19437,65535}}});
    assert((seeds==std::vector<uint16_t>{0,1,19437,65535}));
    const std::vector<Json> invalid={Json::array(),{1,1},{-1},{65536},{1.5},{true},{"1"},
        Json(nullptr),Json(1),Json::array({0,18446744073709551615ULL}),std::vector<int>(33,1)};
    for(const auto& input:invalid) {
        bool failed=false;
        try {film_grain_probe_template_seeds({{"template_seeds",input}});}catch(const std::runtime_error&){failed=true;}
        assert(failed);
    }
    for(const auto& v:jointTemplateVectors) {
        NV_ENC_FILM_GRAIN_PARAMS_AV1 p{};
        p.applyGrain=1;p.arCoeffLag=v.lag;p.arCoeffShiftMinus6=v.arShift-6;p.grainScaleShift=v.grainShift;
        p.numYPoints=2;p.pointYValue[1]=255;p.pointYScaling[0]=p.pointYScaling[1]=40;
        p.numCbPoints=p.numCrPoints=2;p.pointCbValue[1]=p.pointCrValue[1]=255;
        p.pointCbScaling[0]=p.pointCbScaling[1]=10; // Cr is a PRESENT zero-strength curve.
        std::copy(v.y.begin(),v.y.end(),p.arCoeffsYPlus128);
        std::copy(v.cb.begin(),v.cb.end(),p.arCoeffsCbPlus128);
        std::copy(v.cr.begin(),v.cr.end(),p.arCoeffsCrPlus128);
        FilmGrainJointTemplateParameters t;
        assert(film_grain_model_template_parameters(p,v.depth,t));
        assert(t.valid() && t.cbActive && t.crActive && t.y==v.y && t.cb==v.cb && t.cr==v.cr);
        const auto record=film_grain_final_model_evidence(p,v.depth,{v.seed});
        assert(record.at("component_second_moment")[2]==v.moments[5]);
        assert(record.at("template_active")==Json::array({true,true,true}));
        assert(record.at("syntax").at("scaling_points").at("cr")==Json::array({{0,0},{255,0}}));
        assert(record.at("syntax").at("ar_coeffs").at("cb")[24]==int(v.cb[24])-128);
        assert(record.dump(2).size()<16384); // Covered by the probe's reserved JSON budget.
        p.numCrPoints=0;assert(!film_grain_model_template_parameters(p,v.depth,t));
        p.numCbPoints=0;assert(film_grain_model_template_parameters(p,v.depth,t) && !t.cbActive && !t.crActive);
        p.chromaScalingFromLuma=1;assert(film_grain_model_template_parameters(p,v.depth,t) && t.cbActive && t.crActive);
        p.numCbPoints=p.numCrPoints=1;assert(!film_grain_model_template_parameters(p,v.depth,t));
        p.chromaScalingFromLuma=0;p.numYPoints=0;assert(!film_grain_model_template_parameters(p,v.depth,t));
        p.numYPoints=2;p.pointYValue[1]=0;assert(!film_grain_model_template_parameters(p,v.depth,t));
        p.pointYValue[1]=255;p.cbOffset=512;assert(!film_grain_model_template_parameters(p,v.depth,t));
        p.cbOffset=0;p.numCbPoints=11;assert(!film_grain_model_template_parameters(p,v.depth,t));
        p.applyGrain=0; // Invalid/stale fields are ignored on grain-off frames.
        const auto off=film_grain_final_model_evidence(p,v.depth,seeds);
        assert(off.at("syntax")==Json({{"apply_grain",false}}));
        assert(off.at("component_second_moment")==Json::array({0.,0.,0.}));
        assert(!film_grain_model_template_parameters(p,9,t) && !t.valid());
    }
    std::cout<<"Final model evidence: seed bounds, legal 4:2:0 syntax, zero curves, grain-off reset and independent moments passed\n";
}
