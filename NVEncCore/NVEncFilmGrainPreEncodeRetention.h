// Finite candidate experiment. This is not source eligibility or model approval.
#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include "../json/json.hpp"

namespace fgsdiagnostic {
struct PreEncodeRetentionDecision {
    std::array<float,3> requested{}, effective{{1,1,1}};
    uint32_t reasonMask=0, preservedComponents=7;
    enum Reason : uint32_t {
        MissingBase=1, OrdinaryFallback=2, LimitedSupport=4, InactiveComponent=8,
        RequestedSource=16
    };
    bool wholeSource() const {return effective==std::array<float,3>{{1,1,1}};}
};

// An ordinary fallback always wins. Unsupported components keep the exact
// original, including when a candidate requested zero retention for them.
inline PreEncodeRetentionDecision preEncodeRetentionDecision(const std::array<float,3>& requested,
    bool haveBase,bool reliable,bool sourceFallback,uint32_t sourceReasons,
    bool limitedSupport,unsigned activeComponents) {
    PreEncodeRetentionDecision d;d.requested=requested;
    for(float f:requested)if(!std::isfinite(f)||f<0||f>1)
        throw std::runtime_error("pre-encode retention requires finite fractions in [0,1]");
    if(activeComponents>7)throw std::runtime_error("invalid pre-encode component mask");
    if(!haveBase)d.reasonMask|=d.MissingBase;
    if(!reliable||sourceFallback||sourceReasons)d.reasonMask|=d.OrdinaryFallback;
    if(limitedSupport)d.reasonMask|=d.LimitedSupport;
    if(d.reasonMask)return d;
    d.preservedComponents=0;
    for(unsigned c=0;c<3;++c) {
        if(!(activeComponents&(1u<<c)))d.reasonMask|=d.InactiveComponent;
        else d.effective[c]=requested[c];
        if(requested[c]==1)d.reasonMask|=d.RequestedSource;
        if(d.effective[c]==1)d.preservedComponents|=1u<<c;
    }
    return d;
}
inline nlohmann::json preEncodeRetentionEvidence(const PreEncodeRetentionDecision& d) {
    return {{"requested",d.requested},{"effective",d.effective},{"reason_mask",d.reasonMask},
        {"preserved_components",d.preservedComponents},{"whole_source",d.wholeSource()},
        {"grain_model","off; candidate measurement only"}};
}
}
