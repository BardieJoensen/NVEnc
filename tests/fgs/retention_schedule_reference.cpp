// Finite manual evidence-to-plan adapter. This does not classify a source or
// authorize media installation. Candidate/joint proofs remain explicit inputs;
// missing measurements yield source preservation, never assumed success.
#include "NVEncFilmGrainRetentionSchedule.h"
#include "NVEncFilmGrainSourceBinding.h"
#include "NVEncFilmGrainSourceDigest.h"
#include <filesystem>
#include <fstream>
#include <iostream>
using namespace fgsmodel;using namespace fgsdiagnostic;using Json=nlohmann::json;
static void require(bool b,const char* s){if(!b)throw std::runtime_error(s);}
static int64_t integer(const Json& j,int64_t low,int64_t high) {
    require(j.is_number_integer() && j>=low && j<=high,"invalid evidence integer");return j.get<int64_t>();
}
static float fraction(const Json& j) {
    require(j.is_number(),"invalid evidence fraction type");const auto d=j.get<double>();
    require(std::isfinite(d) && d>=0 && d<=1,"invalid evidence fraction");return float(d);
}
static FilmGrainRetentionFrame frame(const Json& f) {
    return {unsigned(integer(f.at("width"),64,4096)),unsigned(integer(f.at("height"),64,2160)),
        unsigned(integer(f.at("depth"),8,10)),integer(f.at("source_id"),0,INT_MAX),
        integer(f.at("pts"),INT64_MIN+1,INT64_MAX),uint64_t(integer(f.at("epoch"),0,INT64_MAX)),
        uint64_t(integer(f.at("population_id"),1,INT64_MAX))};
}
static FilmGrainRetentionChecks checks(const Json& j) {
    return {uint32_t(integer(j.at("measured"),0,UINT32_MAX)),uint32_t(integer(j.at("passed"),0,UINT32_MAX))};
}
static Json assessment(const FilmGrainRetentionAssessment& a) {
    return {{"accepted",a.accepted()},{"reasons",a.reasons},{"unmeasured",a.unmeasuredChecks},{"failed",a.failedChecks}};
}
static FilmGrainRetentionRequest request(const Json& j) {
    return {frame(j.at("frame")),unsigned(integer(j.at("component"),0,2)),fraction(j.at("luma_retain")),fraction(j.at("retain"))};
}
int main(){try {
    Json input;std::cin>>input;require(integer(input.at("schema"),1,1)==1,"invalid evidence schema");
    const auto kind=input.at("evidence_kind").get<std::string>();
    require(kind=="unit_mechanism_fixture" || kind=="measured_development","evidence kind must be explicit");
    const auto& items=input.at("inputs");require(items.is_array() && items.size()>=8 && items.size()<=16,"evidence input count");
    std::vector<FilmGrainRetentionFrame> frames;
    for(const auto& item:items)frames.push_back(frame(item.at("frame")));
    FilmGrainRetentionSchedule schedule(frames);
    const auto binding=PreEncodeSourceBinding::parse(input,items.size());require(binding.enabled(),"plan requires exact original-source binding");
    const auto& tb=input.at("pre_encode_source_binding").at("timebase");
    auto memory=std::make_shared<SourceMemory>(512ull*1024*1024);
    Json trace=Json::array();
    for(size_t i=0;i<items.size();++i) {
        const auto& item=items[i];const auto& f=frames[i];
        NativeSourceFrame original(memory,i,int(f.frameId),f.timestamp,tb[0],tb[1],f.width,f.height,f.bitDepth);
        const auto& paths=item.at("source_planes");require(paths.is_array() && paths.size()==3,"three original planes required");
        for(unsigned c=0;c<3;++c) {
            const auto path=std::filesystem::u8path(paths[c].get<std::string>());auto& plane=original.planes[c];
            require(path.is_absolute() && std::filesystem::file_size(path)==plane.size()*2,"original source plane span differs");
            std::vector<uint8_t> raw(plane.size()*2);std::ifstream file(path,std::ios::binary);
            file.read(reinterpret_cast<char*>(raw.data()),raw.size());require(bool(file),"original source read failed");
            for(size_t x=0;x<plane.size();++x)plane[x]=uint16_t(unsigned(raw[x*2])|(unsigned(raw[x*2+1])<<8));
        }
        binding.require(original,nativeSourceDigest);
        const auto& candidates=item.at("candidates");require(candidates.is_array() && candidates.size()<=11,"candidate evidence exceeds bounded search");
        std::vector<FilmGrainRetentionRequest> keys;
        for(const auto& candidate:candidates) {
            const auto r=request(candidate.at("request"));
            for(const auto& old:keys)require(!(r==old),"duplicate candidate evidence");
            keys.push_back(r);
        }
        Json calls=Json::array();
        schedule.push(f,fraction(item.at("luma_retain")),[&](const FilmGrainRetentionRequest& r) {
            FilmGrainRetentionCandidate c;c.request=r;const Json* found=nullptr;
            for(size_t n=0;n<keys.size();++n)if(keys[n]==r)found=&candidates[n];
            if(found) {
                c.modelId=uint64_t(integer(found->at("model_id"),1,INT64_MAX));c.checks=checks(found->at("checks"));
                const auto& cells=found->at("cells");require(cells.is_array() && cells.size()<=16384,"population cell count");
                for(const auto& j:cells) {
                    FilmGrainRetentionPopulationCell cell;cell.population=FilmGrainRetentionPopulation(integer(j.at("population"),0,3));
                    cell.nativeLookup=unsigned(integer(j.at("native_lookup"),0,1023));cell.scaling=unsigned(integer(j.at("scaling"),0,255));
                    cell.samples=uint64_t(integer(j.at("samples"),0,INT64_MAX));cell.changedSamples=uint64_t(integer(j.at("changed_samples"),0,INT64_MAX));
                    cell.trainBlocks=unsigned(integer(j.at("train_blocks"),0,UINT32_MAX));cell.checkBlocks=unsigned(integer(j.at("check_blocks"),0,UINT32_MAX));
                    cell.checks=checks(j.at("checks"));c.cells.push_back(cell);
                }
            }
            calls.push_back({{"component",r.component},{"retain",r.retain},{"evidence_found",bool(found)}});return c;
        },[&](const FilmGrainRetentionCombination& combination) {
            FilmGrainRetentionJointEvidence e;
            if(item.contains("joint")) {
                const auto& j=item.at("joint");e.combination.frame=frame(j.at("frame"));
                require(j.at("retain").is_array() && j.at("retain").size()==3
                    && j.at("model_id").is_array() && j.at("model_id").size()==3,"joint combination shape");
                for(unsigned c=0;c<3;++c){e.combination.retain[c]=fraction(j.at("retain")[c]);e.combination.modelId[c]=uint64_t(integer(j.at("model_id")[c],0,INT64_MAX));}
                e.checks=checks(j.at("checks"));
            }else e.combination=combination;
            return e;
        });
        trace.push_back(calls);
    }
    schedule.finish();Json rows=Json::array();
    for(size_t i=0;i<items.size();++i) {
        const auto& row=schedule.rows()[i];const auto& s=row.selection;Json attempts=Json::array();
        for(unsigned c=0;c<2;++c){Json a=Json::array();for(unsigned n=0;n<s.evaluations[c+1];++n)a.push_back(assessment(s.attempts[c][n]));attempts.push_back(a);}
        rows.push_back({{"ordinal",i},{"frame",items[i].at("frame")},{"retain",row.retain},{"preservation_reasons",row.reasons},
            {"selector_retain",s.selected.retain},{"selector_model_id",s.selected.modelId},{"before_joint",s.beforeJoint.retain},
            {"source_frame",s.sourceFrame},{"source_mask",s.sourceMask},{"evaluations",s.evaluations},{"joint_evaluations",s.jointEvaluations},
            {"rejection_reasons",s.rejectionReasons},{"joint_reasons",s.jointReasons},{"joint_unmeasured",s.jointUnmeasured},{"joint_failed",s.jointFailed},
            {"luma",assessment(s.luma)},{"attempts",attempts},{"calls",trace[i]}});
    }
    Json plan={{"pre_encode_retention_frames",schedule.fractions()},{"pre_encode_source_segments",true},
        {"pre_encode_source_binding",input.at("pre_encode_source_binding")}};
    PreEncodeRetentionPlan::parse(plan,items.size()).modelSegments();
    std::cout<<Json({{"complete",true},{"evidence_kind",kind},{"source_admission",false},{"plan",plan},{"decisions",rows},
        {"source_peak_bytes",memory->peak.load()}}).dump(2)<<'\n';
}catch(const std::exception& e){std::cout<<Json({{"complete",false},{"error",e.what()}}).dump()<<'\n';return 1;}}
