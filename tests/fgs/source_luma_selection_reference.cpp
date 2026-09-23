// Manual replay of measured native candidate evidence; no media installation.
#include <fstream>
#include <iostream>
#include "NVEncFilmGrainSourceLumaSelect.h"
#include "NVEncFilmGrainPersistentEvidence.h"
#include "json.hpp"
using namespace fgsmodel;
using nlohmann::json;
static std::vector<uint16_t> plane(const std::string& path, size_t samples) {
    std::vector<uint16_t> v(samples);
    std::ifstream file(path,std::ios::binary);
    if (!file || !file.read(reinterpret_cast<char*>(v.data()),samples*2)) throw std::runtime_error("short native plane");
    char extra; if (file.get(extra)) throw std::runtime_error("long native plane");
    return v;
}
int main(int argc,char** argv) {
    if (argc!=3) return 2;
    json input; std::ifstream(argv[1])>>input;
    json report={{"complete",false},{"cases",json::array()}};
    for (const auto& item : input.at("cases")) {
        const auto f=item.at("frame");
        FilmGrainRetentionFrame frame{f.at("width"),f.at("height"),f.at("depth"),
            f.at("frame_id"),f.at("pts"),f.at("epoch"),f.at("population_id")};
        json evaluations=json::array();
        const auto evaluate=[&](const FilmGrainRetentionRequest& request) {
            FilmGrainRetentionCandidate c; c.request=request;
            const json* found=nullptr;
            for (const auto& candidate : item.at("candidates"))
                if (candidate.at("component").get<unsigned>()==request.component
                    && candidate.at("retain").get<float>()==request.retain) {found=&candidate;break;}
            if (!found) throw std::runtime_error("missing bounded candidate");
            const auto& candidate=*found;
            c.modelId=candidate.at("model_id");
            c.checks={candidate.at("measured"),candidate.at("passed")};
            for (const auto& row : candidate.at("cells")) {
                FilmGrainRetentionPopulationCell cell;
                cell.population=static_cast<FilmGrainRetentionPopulation>(row.at("population").get<unsigned>());
                cell.nativeLookup=row.at("native_lookup");cell.scaling=row.at("scaling");
                cell.samples=row.at("samples");cell.changedSamples=row.at("changed_samples");
                cell.trainBlocks=row.at("train_blocks");cell.checkBlocks=row.at("check_blocks");
                cell.checks={row.at("measured"),row.at("passed")};c.cells.push_back(cell);
            }
            FilmGrainPersistentEvidence evidence{request,c.modelId,{}};
            for (const auto& row : candidate.at("persistent")) {
                FilmGrainPersistentEvidenceTile tile;
                tile.tile={row.at("x"),row.at("y"),request.component};
                tile.measurement.samples=row.at("samples");tile.measurement.changedSamples=row.at("changed_samples");
                const auto means=row.at("mean").get<std::array<double,4>>();
                const auto covariance=row.at("covariance").get<std::array<double,16>>();
                std::copy(means.begin(),means.end(),tile.measurement.mean);
                std::copy(covariance.begin(),covariance.end(),tile.measurement.covariance);
                evidence.tiles.push_back(tile);
            }
            const auto a=film_grain_apply_persistent_veto(c,evidence,{.02,.125,.125,.5,.8},
                FilmGrainPersistentUnknownPolicy::UseIndependentCandidateChecks);
            const auto assessment=film_grain_assess_retention_candidate(request,c);
            evaluations.push_back({{"component",request.component},{"retain",request.retain},
                {"accepted",assessment.accepted()},{"reasons",assessment.reasons},
                {"persistent_reasons",a.reasons},{"unknown_samples",a.unknownSamples},
                {"conflict_samples",a.conflictSamples},{"samples",a.samples},
                {"changed_samples",a.changedSamples},{"independent_evidence_used",a.independentCandidateEvidenceUsed}});
            return c;
        };
        const auto joint=[&](const FilmGrainRetentionCombination& combination) {
            const auto j=item.at("joint");FilmGrainSourceLumaJointEvidence e;
            e.colour.combination=combination;
            if (combination.retain!=j.at("retain").get<std::array<float,3>>())
                throw std::runtime_error("unmeasured combination reached joint check");
            e.colour.checks={j.at("measured"),j.at("passed")};e.modelId=j.at("model_id");
            const auto p=j.at("parameters");auto& params=e.parameters;
            params.applyGrain=1;params.numYPoints=params.numCbPoints=params.numCrPoints=2;
            params.pointYValue[1]=params.pointCbValue[1]=params.pointCrValue[1]=255;
            params.arCoeffLag=3;params.arCoeffShiftMinus6=p.at("ar_shift").get<unsigned>()-6;
            params.grainScaleShift=p.at("grain_shift");params.grainScalingMinus8=3;
            params.overlapFlag=1;params.clipToRestrictedRange=1;
            params.cbMult=params.crMult=128;params.cbLumaMult=params.crLumaMult=192;params.cbOffset=params.crOffset=256;
            const auto scaling=p.at("scaling").get<std::array<unsigned,3>>();
            params.pointYScaling[0]=params.pointYScaling[1]=scaling[0];
            params.pointCbScaling[0]=params.pointCbScaling[1]=scaling[1];
            params.pointCrScaling[0]=params.pointCrScaling[1]=scaling[2];
            for (unsigned c=0;c<3;++c) {
                auto* coeff=c==0?params.arCoeffsYPlus128:c==1?params.arCoeffsCbPlus128:params.arCoeffsCrPlus128;
                const auto values=p.at("coefficients")[c].get<std::vector<int>>();
                if (values.size()!=(c?25:24)) throw std::runtime_error("wrong coefficient count");
                for (unsigned i=0;i<values.size();++i) {
                    if (values[i]<-128 || values[i]>127) throw std::runtime_error("coefficient out of range");
                    coeff[i]=values[i]+128;
                }
            }
            for (unsigned c=0;c<3;++c) {
                const size_t count=size_t(frame.width)*frame.height/(c?4:1);
                const auto source=plane(j.at("source")[c],count), base=plane(j.at("base")[c],count);
                e.sourceComponents[c]=film_grain_source_component_counts(frame,e.modelId,c,source.data(),base.data(),count);
            }
            return e;
        };
        const auto r=film_grain_select_with_source_luma(frame,evaluate,joint);
        const auto& q=r.selection;
        report["cases"].push_back({{"case",item.at("case")},{"source_frame",q.sourceFrame},
            {"source_mask",q.sourceMask},{"retain",q.selected.retain},{"before_joint",q.beforeJoint.retain},
            {"source_luma_proven",r.sourceLumaProven},{"joint_reasons",q.jointReasons},
            {"source_preserved_mask",r.sourcePreservedMask},
            {"evaluations",q.evaluations},{"joint_evaluations",q.jointEvaluations},{"candidates",evaluations}});
    }
    report["complete"]=true;std::ofstream(argv[2])<<report.dump(2)<<'\n';
}
