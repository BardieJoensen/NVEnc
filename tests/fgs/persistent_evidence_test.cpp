#include "NVEncFilmGrainPersistentEvidence.h"
#include <cassert>
#include <iostream>
using namespace fgsmodel;
static FilmGrainPersistentEvidence evidence(const FilmGrainRetentionCandidate& candidate, double gain) {
    FilmGrainPersistentEvidence out{candidate.request,candidate.modelId,{}};
    const auto& r=candidate.request;
    const unsigned side=r.component ? 32 : 64, w=r.frame.width/(r.component ? 2 : 1), h=r.frame.height/(r.component ? 2 : 1);
    for(unsigned y=0;y<h;y+=side)for(unsigned x=0;x<w;x+=side) {
        FilmGrainPersistentEvidenceTile tile;tile.tile={x,y,r.component};
        auto& m=tile.measurement;m.samples=std::min(side,w-x)*std::min(side,h-y);
        m.changedSamples=gain==1 ? 0 : m.samples;
        for(auto& value:m.mean)value=128;
        const double a[4]={1,gain,1,1};
        for(unsigned i=0;i<4;++i)for(unsigned j=0;j<4;++j)m.covariance[i*4+j]=(m.samples>1 ? 64 : 0)*a[i]*a[j];
        out.tiles.push_back(tile);
    }
    return out;
}
int main() {
    const FilmGrainPersistentLimits limits{.02,.125,.125,.5,.8};
    FilmGrainRetentionFrame frame{194,130,10,90,3750,4,901};
    FilmGrainRetentionCandidate candidate;candidate.request={frame,1,.25f,.25f};candidate.modelId=88;
    candidate.checks={FGS_RETAIN_ALL_CHECKS,FGS_RETAIN_ALL_CHECKS};
    auto good=evidence(candidate,1);
    auto result=film_grain_apply_persistent_veto(candidate,good,limits);
    assert(!result.reasons && result.samples==uint64_t(97)*65 && result.changedSamples==0);
    assert(candidate.checks.complete(FGS_RETAIN_ALL_CHECKS));
    auto lost=evidence(candidate,.9);result=film_grain_apply_persistent_veto(candidate,lost,limits);
    assert(result.reasons & FGS_RETAIN_FAILED_CHECK);
    assert(candidate.checks.measured & FGS_RETAIN_DETAIL);
    assert(!(candidate.checks.passed & FGS_RETAIN_DETAIL));
    // A subsequent necessary-pass cannot repair an independently failed check.
    film_grain_apply_persistent_veto(candidate,good,limits);
    assert(!(candidate.checks.passed & FGS_RETAIN_DETAIL));
    for(unsigned kind=0;kind<8;++kind) {
        auto bad=good;
        if(kind==0)bad.request.frame.frameId++;
        if(kind==1)bad.request.frame.timestamp++;
        if(kind==2)bad.request.frame.epoch++;
        if(kind==3)bad.request.frame.sourcePopulationId++;
        if(kind==4)bad.request.retain=.5f;
        if(kind==5)bad.request.lumaRetain=.5f;
        if(kind==6)bad.request.component=2;
        if(kind==7)bad.modelId++;
        assert(film_grain_assess_persistent_evidence(candidate,bad,limits).reasons==FGS_RETAIN_STALE_EVIDENCE);
    }
    auto bad=good;bad.tiles.pop_back();
    assert(film_grain_assess_persistent_evidence(candidate,bad,limits).reasons & FGS_RETAIN_INCOMPLETE_PICTURE);
    bad=good;bad.tiles.back()=bad.tiles.front();
    assert(film_grain_assess_persistent_evidence(candidate,bad,limits).reasons & FGS_RETAIN_INCOMPLETE_PICTURE);
    bad=good;bad.tiles.back().measurement.samples++;
    assert(film_grain_assess_persistent_evidence(candidate,bad,limits).reasons & FGS_RETAIN_INVALID);
    bad=good;for(auto& tile:bad.tiles) {
        for(auto& v:tile.measurement.covariance)v=0;
        tile.measurement.covariance[0]=tile.measurement.covariance[5]=tile.measurement.samples>1 ? 1 : 0;
        tile.measurement.changedSamples=tile.measurement.samples>1 ? tile.measurement.samples : 0;
    }
    candidate.checks={FGS_RETAIN_ALL_CHECKS,FGS_RETAIN_ALL_CHECKS};
    result=film_grain_apply_persistent_veto(candidate,bad,limits);
    assert(result.unknownSamples==uint64_t(97)*65-1 && result.reasons==FGS_RETAIN_UNMEASURED);
    assert(!(candidate.checks.measured & FGS_RETAIN_DETAIL) && !(candidate.checks.passed & FGS_RETAIN_DETAIL));
    // Independent flat grain has no historical picture direction. A complete
    // separate proof can remain in force; the projection cannot create one.
    constexpr auto independent=FilmGrainPersistentUnknownPolicy::UseIndependentCandidateChecks;
    FilmGrainRetentionPopulationCell support;
    support.population=FilmGrainRetentionPopulation::Grain;support.scaling=16;
    support.samples=uint64_t(97)*65;support.changedSamples=support.samples-1;
    support.trainBlocks=support.checkBlocks=16;
    support.checks={FGS_RETAIN_ALL_POPULATION_CHECKS,FGS_RETAIN_ALL_POPULATION_CHECKS};
    candidate.cells={support};candidate.checks={FGS_RETAIN_ALL_CHECKS,FGS_RETAIN_ALL_CHECKS};
    result=film_grain_apply_persistent_veto(candidate,bad,limits,independent);
    assert(!result.reasons && result.independentCandidateEvidenceUsed && result.unknownSamples==support.changedSamples);
    assert(candidate.checks.complete(FGS_RETAIN_ALL_CHECKS));
    for(unsigned missing=0;missing<8;++missing) {
        auto incomplete=candidate;incomplete.checks.measured&=~(1u<<missing);incomplete.checks.passed&=~(1u<<missing);
        result=film_grain_apply_persistent_veto(incomplete,bad,limits,independent);
        assert(result.reasons && !result.independentCandidateEvidenceUsed);
        assert(!(incomplete.checks.passed&FGS_RETAIN_DETAIL));
        auto failed=candidate;failed.checks.passed&=~(1u<<missing);
        result=film_grain_apply_persistent_veto(failed,bad,limits,independent);
        assert(result.reasons && !result.independentCandidateEvidenceUsed);
        assert(!(failed.checks.passed&(1u<<missing)));
    }
    auto undersupported=candidate;undersupported.cells[0].checkBlocks=15;
    result=film_grain_apply_persistent_veto(undersupported,bad,limits,independent);
    assert(result.reasons && !result.independentCandidateEvidenceUsed);
    auto noRange=candidate;noRange.cells[0].checks.passed&=~uint32_t(FGS_RETAIN_NATIVE_RANGE);
    result=film_grain_apply_persistent_veto(noRange,bad,limits,independent);
    assert(result.reasons && !result.independentCandidateEvidenceUsed);
    auto inconsistent=candidate;inconsistent.cells[0].changedSamples--;
    result=film_grain_apply_persistent_veto(inconsistent,bad,limits,independent);
    assert((result.reasons&FGS_RETAIN_INVALID) && !result.independentCandidateEvidenceUsed);
    for(auto population:{FilmGrainRetentionPopulation::Quiet,FilmGrainRetentionPopulation::Rejected,FilmGrainRetentionPopulation::Border}) {
        auto unsupported=candidate;unsupported.cells[0].population=population;
        result=film_grain_apply_persistent_veto(unsupported,bad,limits,independent);
        assert(result.reasons && !result.independentCandidateEvidenceUsed);
    }
    auto damaged=candidate;
    result=film_grain_apply_persistent_veto(damaged,lost,limits,independent);
    assert((result.reasons&FGS_RETAIN_FAILED_CHECK) && !result.independentCandidateEvidenceUsed);
    auto stale=bad;stale.request.frame.epoch++;
    result=film_grain_apply_persistent_veto(candidate,stale,limits,independent);
    assert((result.reasons&FGS_RETAIN_STALE_EVIDENCE) && !result.independentCandidateEvidenceUsed);
    // Selector control: the native detail veto forces a higher colour fraction.
    // Other evidence below is a policy fixture, not a claim of model fidelity.
    frame.width=192;frame.height=132; // Separate partial-border control with usable anchors.
    const auto evaluate=[&](const FilmGrainRetentionRequest& request) {
        FilmGrainRetentionCandidate c;c.request=request;c.modelId=11+request.component;
        c.checks={FGS_RETAIN_ALL_CHECKS,FGS_RETAIN_ALL_CHECKS};
        FilmGrainRetentionPopulationCell cell;cell.population=FilmGrainRetentionPopulation::Grain;
        cell.samples=uint64_t(frame.width)*frame.height/(request.component ? 4 : 1);
        cell.changedSamples=cell.samples;cell.scaling=16;cell.trainBlocks=cell.checkBlocks=16;
        cell.checks={FGS_RETAIN_ALL_POPULATION_CHECKS,FGS_RETAIN_ALL_POPULATION_CHECKS};c.cells.push_back(cell);
        auto measured=evidence(c,request.component ? 1-.05*(1-request.retain) : 1);
        film_grain_apply_persistent_veto(c,measured,limits);return c;
    };
    const auto joint=[](const FilmGrainRetentionCombination& c) {
        return FilmGrainRetentionJointEvidence{c,{FGS_RETAIN_ALL_JOINT_CHECKS,FGS_RETAIN_ALL_JOINT_CHECKS}};
    };
    const auto decision=film_grain_select_retention(frame,.25f,evaluate,joint);
    assert(!decision.sourceFrame && decision.selected.retain[1]==.75f && decision.selected.retain[2]==.75f);
    assert(decision.evaluations[1]==5 && decision.evaluations[2]==5);
    std::cout<<"Persistent evidence binds every native tile to the current candidate and only removes clearance\n";
}
