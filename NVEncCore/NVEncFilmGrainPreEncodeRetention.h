// Finite candidate experiment. This is not source eligibility or model approval.
#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>
#include "../json/json.hpp"

namespace fgsdiagnostic {
// Immutable finite input-ordinal schedule. It carries an experimental request,
// not source admission, and never changes in response to output/check evidence.
class PreEncodeRetentionPlan {
    std::vector<std::array<float,3>> frames_;
    bool varying_=false;
    static std::array<float,3> fractions(const nlohmann::json& values) {
        if(!values.is_array() || values.size()!=3)
            throw std::runtime_error("pre-encode retention requires three fractions");
        std::array<float,3> result{};
        for(unsigned c=0;c<3;++c) {
            if(!values[c].is_number())throw std::runtime_error("retention fractions must be numeric");
            const double f=values[c].get<double>();
            if(!std::isfinite(f)||f<0||f>1)
                throw std::runtime_error("retention fractions must be finite and in [0,1]");
            result[c]=float(f);
        }
        return result;
    }
public:
    static PreEncodeRetentionPlan parse(const nlohmann::json& j,size_t count) {
        PreEncodeRetentionPlan plan;
        if(!j.is_object())throw std::runtime_error("retention plan requires an object");
        const bool constant=j.contains("pre_encode_retention"),varying=j.contains("pre_encode_retention_frames");
        if(!constant && !varying)return plan;
        if(constant && varying)throw std::runtime_error("retention requires one constant or per-picture request, not both");
        if(!count || count>16)throw std::runtime_error("retention plan requires 1..16 pictures");
        plan.varying_=varying;
        if(constant)plan.frames_.assign(count,fractions(j.at("pre_encode_retention")));
        else {
            const auto& rows=j.at("pre_encode_retention_frames");
            if(!rows.is_array() || rows.size()!=count)
                throw std::runtime_error("retention plan requires exactly one row per input picture");
            for(const auto& row:rows)plan.frames_.push_back(fractions(row));
        }
        return plan;
    }
    bool enabled() const {return !frames_.empty();}
    size_t size() const {return frames_.size();}
    const std::array<float,3>& at(uint64_t ordinal) const {
        if(ordinal>=frames_.size())throw std::runtime_error("retention input ordinal is outside finite plan");
        return frames_[size_t(ordinal)];
    }
    void requireAllPartial() const {
        for(const auto& row:frames_)for(float f:row)if(f>=1)
            throw std::runtime_error("pre-encode model fitting requires all-partial fractions");
    }
    nlohmann::json evidence() const {
        if(!enabled())return nlohmann::json::object();
        if(varying_)return {{"pre_encode_retention_frames",frames_}};
        return {{"pre_encode_retention",frames_[0]}};
    }
};

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
// This finite fitter currently supports all-partial candidates only. A model
// failure cannot retroactively restore source pixels that NVENC has encoded.
// Reject before fitting if ordinary guards preserved any component; the manual
// controller must encode a new whole-source output or keep the original file.
inline void requirePartialRetentionModel(const PreEncodeRetentionDecision& d,
    const std::array<float,3>& expected) {
    if(d.requested!=expected || d.effective!=expected || d.reasonMask || d.preservedComponents)
        throw std::runtime_error("native candidate model cannot override source preservation");
    for(float f:expected)if(!std::isfinite(f)||f<0||f>=1)
        throw std::runtime_error("native candidate model requires all-partial fractions");
}
}
