#include <cassert>
#include <iostream>
#include "NVEncFilmGrainSourceLumaSelect.h"
using namespace fgsmodel;
static FilmGrainRetentionCandidate candidate(const FilmGrainRetentionRequest& request) {
    FilmGrainRetentionCandidate c;
    c.request=request; c.modelId=100+request.component;
    c.checks={FGS_RETAIN_ALL_CHECKS,FGS_RETAIN_ALL_CHECKS};
    FilmGrainRetentionPopulationCell cell;
    cell.population=FilmGrainRetentionPopulation::Grain;
    cell.nativeLookup=128;cell.scaling=64;cell.samples=uint64_t(request.frame.width)*request.frame.height/4;
    cell.changedSamples=cell.samples;cell.trainBlocks=cell.checkBlocks=16;
    cell.checks={FGS_RETAIN_ALL_POPULATION_CHECKS,FGS_RETAIN_ALL_POPULATION_CHECKS};
    c.cells.push_back(cell);return c;
}
static FilmGrainSourceLumaJointEvidence joint(const FilmGrainRetentionCombination& combination) {
    FilmGrainSourceLumaJointEvidence e;
    e.colour.combination=combination;e.colour.checks={FGS_RETAIN_ALL_JOINT_CHECKS,FGS_RETAIN_ALL_JOINT_CHECKS};
    e.modelId=777;e.parameters.applyGrain=1;
    e.parameters.numYPoints=e.parameters.numCbPoints=e.parameters.numCrPoints=2;
    e.parameters.pointYValue[1]=e.parameters.pointCbValue[1]=e.parameters.pointCrValue[1]=255;
    e.parameters.pointCbScaling[0]=e.parameters.pointCbScaling[1]=combination.retain[1]<1.f?64:0;
    e.parameters.pointCrScaling[0]=e.parameters.pointCrScaling[1]=combination.retain[2]<1.f?64:0;
    e.parameters.clipToRestrictedRange=1;
    const unsigned level=80u<<(combination.frame.bitDepth-8);
    for (unsigned c=0;c<3;++c)
        e.sourceComponents[c]=film_grain_source_component_counts_from_native(combination.frame,e.modelId,c,
            {uint64_t(combination.frame.width)*combination.frame.height/(c?4:1),0,0,level,level});
    return e;
}
int main() {
    for (unsigned depth : {8u,10u}) {
        FilmGrainRetentionFrame frame{512,256,depth,7,280,1,999};
        unsigned calls=0;
        auto evaluate=[&](const FilmGrainRetentionRequest& r) {
            ++calls;assert(r.component && r.lumaRetain==1.f);
            auto c=candidate(r);
            if (r.retain<(r.component==1?.75f:.5f)) c.checks.passed&=~FGS_RETAIN_FINITE_SYNTHESIS;
            return c;
        };
        auto r=film_grain_select_with_source_luma(frame,evaluate,joint);
        assert(!r.selection.sourceFrame && r.sourceLumaProven && calls==9);
        assert((r.selection.selected.retain==std::array<float,3>{{1.f,.75f,.5f}}));
        assert(r.selection.sourceMask==1 && r.selection.evaluations[0]==0 && r.selection.jointEvaluations==1);
        for (unsigned defect=0;defect<9;++defect) {
            auto wrong=[&](const auto& combination) {
                auto e=joint(combination);
                if (defect==0) e.sourceComponents[0].changedSamples=1;
                if (defect==1) e.sourceComponents[0].minimum=0; // Active zero curve clips.
                if (defect==2) e.sourceComponents[0].modelId++;
                if (defect==3) e.sourceComponents[0].frame.epoch++;
                if (defect==4) e.parameters.pointYScaling[1]=1;
                if (defect==5) e.colour.checks.passed&=~FGS_RETAIN_CB_CR;
                if (defect==6) e.colour.checks.measured=e.colour.checks.passed=0;
                if (defect==7) e.colour.combination.retain[1]=.1f;
                if (defect==8) e.sourceComponents[0].samples--;
                return e;
            };
            r=film_grain_select_with_source_luma(frame,evaluate,wrong);
            assert(r.selection.sourceFrame && r.selection.sourceMask==7 && r.selection.jointEvaluations==1);
            assert(r.selection.jointReasons & FGS_RETAIN_JOINT_UNPROVEN);
            assert((r.selection.selected.retain==std::array<float,3>{{1.f,1.f,1.f}}));
            assert((r.selection.selected.modelId==std::array<uint64_t,3>{}));
        }
        calls=0;
        auto stale=[&](const auto& request) {++calls;auto c=candidate(request);c.request.lumaRetain=.5f;return c;};
        r=film_grain_select_with_source_luma(frame,stale,joint);
        assert(r.selection.sourceFrame && calls==10 && r.selection.jointEvaluations==0);
        assert(r.selection.rejectionReasons[1] & FGS_RETAIN_STALE_EVIDENCE);
        for (unsigned copied : {1u,2u}) {
            auto mixed=[&](const auto& request) {
                auto c=candidate(request);
                if (request.component==copied) c.checks.passed=0;
                return c;
            };
            r=film_grain_select_with_source_luma(frame,mixed,joint);
            assert(!r.selection.sourceFrame && r.selection.sourceMask==(1u|(1u<<copied)));
            assert(r.sourcePreservedMask==r.selection.sourceMask);
            for (unsigned defect=0;defect<7;++defect) {
                auto badCopy=[&](const auto& combination) {
                    auto e=joint(combination);auto& proof=e.sourceComponents[copied];
                    if (defect==0) proof.changedSamples=1;
                    if (defect==1) proof.minimum=0;
                    if (defect==2) proof.modelId++;
                    if (defect==3) proof.complete=false;
                    if (defect==4) proof.component=3-copied;
                    if (defect==5) {
                        auto* curve=copied==1?e.parameters.pointCbScaling:e.parameters.pointCrScaling;
                        curve[1]=1;
                    }
                    if (defect==6) {e.matrixIdentity=true;proof.maximum=236u<<(depth-8);}
                    return e;
                };
                r=film_grain_select_with_source_luma(frame,mixed,badCopy);
                assert(r.selection.sourceFrame && r.selection.jointReasons&FGS_RETAIN_JOINT_UNPROVEN);
                assert(!(r.sourcePreservedMask&(1u<<copied)));
            }
        }
        // The existing R1 full-source Y decision stays terminal and unchanged.
        calls=0;
        const auto ordinary=film_grain_select_retention(frame,1.f,stale,[](const auto& c) {return joint(c).colour;});
        assert(ordinary.sourceFrame && calls==0 && ordinary.jointEvaluations==0);
    }
    std::cout<<"Source-luma selector: bounded colour search, exact Y/range proof, stale evidence and unchanged R1 policy passed\n";
}
