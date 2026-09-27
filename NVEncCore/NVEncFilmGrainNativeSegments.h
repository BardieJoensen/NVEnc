// Finite explicit whole-source/model intervals. Not an automatic admission rule.
#pragma once
#include <algorithm>
#include <memory>
#include "NVEncFilmGrainNativeEngineAPI.h"
#include "NVEncFilmGrainNativeGrid.h"
#include "NVEncFilmGrainModelBuffer.h"
#include "NVEncFilmGrainPreEncodeRetention.h"

namespace fgsdiagnostic {
// Engine is the private native library adapter; tests can supply an independent
// stateful fake. Each modeled interval owns its own fitter and local ordinals.
// Global source/packet identity remains the caller's immutable binding.
template<class Engine> class NativeModelSegments {
    using Json=nlohmann::json;
    struct Segment {
        PreEncodeRetentionPlan::Segment range;
        std::unique_ptr<Engine> engine;
    };
    std::unique_ptr<Engine> legacy_;
    std::vector<Segment> segments_;
    Json config_;
    uint64_t received_=0;
    size_t count_=0;
    unsigned width_=0,height_=0,depth_=0;
    bool finished_=false,failed_=false;
    static uint64_t integer(const Json& j,const char* key,uint64_t low,uint64_t high) {
        const auto& v=j.at(key);
        if(!v.is_number_integer() || v<low || v>high)
            throw std::runtime_error("native segment integer range");
        return v.template get<uint64_t>();
    }
    static int64_t timestamp(const Json& value) {
        if(!value.is_number_integer() || value==INT64_MIN
            || (value.is_number_unsigned() && value.template get<uint64_t>()>uint64_t(INT64_MAX)))
            throw std::runtime_error("native segment timestamp range");
        return value.template get<int64_t>();
    }
    Segment& segment(uint64_t ordinal) {
        if(ordinal>=count_)throw std::runtime_error("native segment ordinal outside plan");
        for(auto& s:segments_)if(ordinal>=s.range.begin && ordinal-s.range.begin<s.range.count)return s;
        throw std::runtime_error("native segment plan has uncovered input");
    }
    void confirm(const Engine& engine) const {
        const auto policy=config_.value("spatial_policy",std::string("frame_window"));
        if(policy!="frame_window" && engine.report().value("spatial_policy",std::string())!=policy)
            throw std::runtime_error("native engine did not confirm "+policy+" spatial policy");
        const auto copied=config_.value("copied_chroma_mask",0u);
        if(copied && engine.report().value("copied_chroma_mask",0u)!=copied)
            throw std::runtime_error("native engine did not confirm copied chroma policy");
        const auto preserved=config_.value("preserved_chroma_mask",0u);
        if(preserved && engine.report().value("preserved_chroma_mask",0u)!=preserved)
            throw std::runtime_error("native engine did not confirm preserved chroma policy");
    }
    void sourcePlanes(const FgsNativePlane* planes) const {
        if(!planes)throw std::runtime_error("source segment has missing planes");
        for(unsigned c=0;c<3;++c) {
            const size_t w=c?width_/2:width_,h=c?height_/2:height_;const auto& p=planes[c];
            if(!p.data || p.stride<w || p.stride>65536 || p.samples<(h-1)*p.stride+w)
                throw std::runtime_error("source segment plane span differs");
            for(size_t y=0;y<h;++y)for(size_t x=0;x<w;++x)if(p.data[y*p.stride+x]>=(1u<<depth_))
                throw std::runtime_error("source segment native code exceeds depth");
        }
    }
public:
    NativeModelSegments(const std::filesystem::path& path,const Json& config,
        const PreEncodeRetentionPlan& plan):config_(config) {
        const auto copied=config.contains("copied_chroma_mask")?unsigned(integer(config,"copied_chroma_mask",0,6)):0u;
        if(!fgsmodel::film_grain_copied_chroma_mask(copied) || copied!=plan.copiedChroma())
            throw std::runtime_error("native fitter and pre-encode copied chroma differ");
        const auto preserved=config.contains("preserved_chroma_mask")?unsigned(integer(config,"preserved_chroma_mask",0,6)):0u;
        if(!fgsmodel::film_grain_copied_chroma_mask(preserved) || preserved!=plan.preservedChroma()
            || (copied && preserved))throw std::runtime_error("native fitter and pre-encode preserved chroma differ");
        if(!plan.sourceSegments()) {legacy_=std::make_unique<Engine>(path,config);confirm(*legacy_);return;}
        integer(config,"schema",1,1);
        count_=size_t(integer(config,"frame_count",8,16));
        width_=unsigned(integer(config,"width",64,4096));height_=unsigned(integer(config,"height",64,2160));
        depth_=unsigned(integer(config,"depth",8,10));
        const auto grid=fgsmodel::film_grain_native_grid(width_,height_);
        if(config.value("source_mode",std::string("files"))!="memory" || count_<8 || count_>16
            || count_!=plan.size() || !grid.valid || !grid.blocks[1] || (depth_!=8 && depth_!=10)
            || !config.at("sources").is_array() || config.at("sources").size()!=count_)
            throw std::runtime_error("source segments require matching finite memory-source configuration");
        for(size_t i=0;i<count_;++i) {
            const auto& source=config.at("sources").at(i);
            if(integer(source,"ordinal",0,15)!=i || source.contains("planes"))
                throw std::runtime_error("source segment global identity differs");
            const auto pts=timestamp(source.at("pts"));
            if(i && pts<=timestamp(config.at("sources").at(i-1).at("pts")))
                throw std::runtime_error("source segment clock is not increasing");
        }
        for(const auto& range:plan.modelSegments()) {
            Segment s{range,nullptr};
            if(!range.source) {
                auto local=config;local["frame_count"]=range.count;local["sources"]=Json::array();
                for(size_t i=0;i<range.count;++i) {
                    auto row=config.at("sources").at(range.begin+i);row["ordinal"]=i;local["sources"].push_back(std::move(row));
                }
                s.engine=std::make_unique<Engine>(path,local);confirm(*s.engine);
            }
            segments_.push_back(std::move(s));
        }
    }
    void push(uint64_t ordinal,int64_t pts,const FgsNativePlane* base) {
        if(!legacy_) {failed_=true;throw std::runtime_error("source segments require original memory sources");}
        legacy_->push(ordinal,pts,base);
    }
    void pushPair(uint64_t ordinal,int64_t pts,const FgsNativePlane* source,const FgsNativePlane* base) {
        if(legacy_) {legacy_->pushPair(ordinal,pts,source,base);return;}
        try {
            if(failed_ || finished_ || ordinal!=received_ || ordinal>=count_
                || config_.at("sources").at(ordinal).at("pts")!=pts)
                throw std::runtime_error("source segment reconstruction identity differs");
            auto& s=segment(ordinal);
            if(s.range.source) {sourcePlanes(source);sourcePlanes(base);}
            else s.engine->pushPair(ordinal-s.range.begin,pts,source,base);
            ++received_;
        }catch(...){failed_=true;throw;}
    }
    fgsmodel::FilmGrainModelDecision model(uint64_t ordinal) {
        if(legacy_)return legacy_->model(ordinal);
        try {
            if(failed_)throw std::runtime_error("native source/model segments failed");
            auto& s=segment(ordinal);
            if(ordinal>=received_)return {};
            if(s.range.source)return {fgsmodel::FilmGrainModelReadiness::Replace,{{"apply",false}}};
            return s.engine->model(ordinal-s.range.begin);
        }catch(...){failed_=true;throw;}
    }
    void finish() {
        if(legacy_) {legacy_->finish();return;}
        try {
            if(failed_ || received_!=count_)throw std::runtime_error("source/model segment inputs incomplete");
            if(finished_)return;
            for(auto& s:segments_)if(s.engine)s.engine->finish();
            finished_=true;
        }catch(...){failed_=true;throw;}
    }
    Json report() const {
        if(legacy_)return legacy_->report();
        Json segments=Json::array(),models=Json::array(),ready=Json::array(),rows=Json::array();
        for(size_t i=0;i<count_;++i) {models.push_back(nullptr);ready.push_back(-1);}
        size_t preserved=0,selected=0;bool complete=finished_ && !failed_,failed=failed_;
        for(const auto& s:segments_) {
            Json entry={{"begin",s.range.begin},{"count",s.range.count},{"source",s.range.source}};
            if(s.engine) {
                const auto child=s.engine->report();entry["engine"]=child;
                complete=complete && child.at("complete").template get<bool>();failed=failed || child.at("failed").template get<bool>();
                selected+=child.at("selected").template get<size_t>();
                for(size_t i=0;i<child.at("models").size();++i)models.at(s.range.begin+i)=child.at("models").at(i);
                for(size_t i=0;i<child.at("ready_at").size();++i) {
                    const int64_t at=child.at("ready_at").at(i);
                    if(at>=0)ready.at(s.range.begin+i)=int64_t(s.range.begin)+at;
                }
                for(auto row:child.at("rows")) {
                    const size_t local=row.at("ordinal");row["segment_ordinal"]=local;row["ordinal"]=s.range.begin+local;rows.push_back(std::move(row));
                }
            } else {
                const size_t count=received_>s.range.begin?std::min<size_t>(s.range.count,received_-s.range.begin):0;
                preserved+=count;
                for(size_t i=0;i<count;++i) {
                    const auto ordinal=s.range.begin+i;models.at(ordinal)={{"apply",false}};ready.at(ordinal)=ordinal;
                    rows.push_back({{"ordinal",ordinal},{"source_preserved",true}});
                }
            }
            segments.push_back(std::move(entry));
        }
        Json result={{"complete",complete && !failed},{"failed",failed},{"received",received_},
            {"selected",selected+preserved},{"modeled_selected",selected},{"source_preserved",preserved},
            {"mode","explicit_source_segments"},{"source_admission",false},
            {"spatial_policy",config_.value("spatial_policy",std::string("frame_window"))},
            {"segments",segments},{"models",models},{"ready_at",ready},{"rows",rows}};
        if(config_.value("copied_chroma_mask",0u))result["copied_chroma_mask"]=config_.at("copied_chroma_mask");
        if(config_.value("preserved_chroma_mask",0u))result["preserved_chroma_mask"]=config_.at("preserved_chroma_mask");
        return result;
    }
};
} // namespace fgsdiagnostic
