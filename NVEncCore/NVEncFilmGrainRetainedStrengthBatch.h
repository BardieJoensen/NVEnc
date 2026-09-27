// Cooperative bounded calibration: one synthesized picture measures all three
// independent output component strengths. No source/quality admission follows.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainRetainedStrength.h"
#include "NVEncFilmGrainConstantChroma.h"

namespace fgsmodel {
struct FilmGrainRetainedStrengthBatchSample {
    std::array<unsigned,3> strengths{};
    std::array<FilmGrainRetainedStrengthMeasurement,3> measurements{};
};
struct FilmGrainRetainedStrengthBatch {
    bool complete=false,valid=false;
    unsigned copiedConstantMask=0,preservedMask=0;
    std::array<FilmGrainRetainedStrength,3> components;
    std::vector<FilmGrainRetainedStrengthBatchSample> samples;
};

// Contract: a component's measured variances depend only on that component's
// strength; base, seed, curves' presence, quantized shape and selected pixels
// stay fixed. AV1 luma-driver grain is upstream of scaling, but changing active
// point counts or using a coupled callback violates this contract. Callers must
// qualify independence with their actual synthesizer; this is not inferred.
//
// Reuse the existing single-component search, replaying at most ten cached
// measurements per component. A missing callback yields its next request to
// the batch. This retains the original numerical/monotonicity rules without
// three child processes or a second copy of the search algorithm.
template<class Measure>
FilmGrainRetainedStrengthBatch film_grain_calibrate_retained_strength_batch(
    const std::array<FilmGrainRetainedStrengthTarget,3>& targets,Measure measure,
    unsigned copiedConstantMask=0,unsigned preservedMask=0) {
    struct Requested {unsigned strength;};
    FilmGrainRetainedStrengthBatch out;
    std::array<std::vector<FilmGrainRetainedStrengthSample>,3> cache;
    std::array<bool,3> done{};
    std::array<unsigned,3> strengths{};
    if(!film_grain_copied_chroma_mask(copiedConstantMask) || !film_grain_copied_chroma_mask(preservedMask)
        || (copiedConstantMask && preservedMask))return out;
    out.copiedConstantMask=copiedConstantMask;out.preservedMask=preservedMask;
    // This explicit mechanism requires a separate complete native constant
    // proof at the caller. Zero variance by itself never selects this path.
    for(unsigned c=1;c<3;++c)if(copiedConstantMask&(1u<<c)) {
        if(targets[c].channels!=1 || targets[c].source[0]!=0. || targets[c].missing[0]!=0.)return out;
        done[c]=true;out.components[c].valid=true;
    }
    // Preserved texture has positive variance, but we deliberately add no
    // colour grain. Missing/negative variance is not a request to synthesize
    // over copied pixels. Complete source/output moments still have to pass
    // at the caller; none of these rows is excluded from those comparisons.
    for(unsigned c=1;c<3;++c)if(preservedMask&(1u<<c)) {
        if(targets[c].channels!=1 || !std::isfinite(targets[c].source[0]) || targets[c].source[0]<=1e-12
            || !std::isfinite(targets[c].missing[0]))return out;
        done[c]=true;out.components[c].valid=true;
    }
    for(unsigned round=0;round<=10;++round) {
        std::array<bool,3> pending{};
        for(unsigned c=0;c<3;++c) {
            if(done[c])continue;
            try {
                out.components[c]=film_grain_calibrate_retained_strength(targets[c],[&](unsigned strength) {
                    const auto found=std::find_if(cache[c].begin(),cache[c].end(),[&](const auto& sample){return sample.strength==strength;});
                    if(found==cache[c].end())throw Requested{strength};
                    return found->measurement;
                });
                done[c]=true;
                if(out.components[c].valid)strengths[c]=out.components[c].strength;
            }catch(const Requested& request){pending[c]=true;strengths[c]=request.strength;}
        }
        if(std::all_of(done.begin(),done.end(),[](bool x){return x;})) {
            out.complete=true;out.valid=std::all_of(out.components.begin(),out.components.end(),[](const auto& c){return c.valid;});return out;
        }
        if(round==10)return out; // No unbounded retry or invented measurement.
        FilmGrainRetainedStrengthBatchSample sample;
        sample.strengths=strengths;sample.measurements=measure(strengths);
        out.samples.push_back(sample);
        for(unsigned c=1;c<3;++c)if(((copiedConstantMask|preservedMask)&(1u<<c))
            && (!sample.measurements[c].valid || sample.measurements[c].variance[0]!=0.))return out;
        for(unsigned c=0;c<3;++c)if(pending[c]) {
            FilmGrainRetainedStrengthSample value;
            value.strength=strengths[c];value.measurement=sample.measurements[c];cache[c].push_back(value);
        }
    }
    return out;
}
} // namespace fgsmodel
