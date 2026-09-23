// Bounded, explicitly requested integration probe. It never changes image/model decisions.
// MIT license, as NVEncFilmGrainModel.h. Not a production retention policy.
#pragma once
#include "NVEncFilmGrainJointCollect.cuh"
#include "NVEncFilmGrainModelEvidence.h"
#include "NVEncFilmGrainSourcePreservation.cuh"
#include "NVEncFilmGrainPersistentHistory.cuh"
#include "../json/json.hpp"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace fgsmodel {
class FilmGrainJointProbe {
    using Json=nlohmann::json;
    using Path=std::filesystem::path;
    Path m_directory;
    std::set<int64_t> m_requested,m_captured;
    std::set<int64_t> m_finalCaptured;
    std::map<int64_t,std::pair<int64_t,uint64_t>> m_captureIdentity;
    std::vector<uint16_t> m_templateSeeds;
    FilmGrainCollectRetention m_retention{};
    FilmGrainCollectHistory m_history;
    FilmGrainPersistentHistoryCache m_persistentHistory;
    bool m_persistentDetail=false;
    FilmGrainPersistentTile *m_persistentTiles=nullptr;
    FilmGrainPersistentResult *m_persistentResults=nullptr;
    FilmGrainCollectTile *m_tiles=nullptr;
    FilmGrainCollectResult *m_results=nullptr;
    FilmGrainCollectGroup *m_groups=nullptr;
    FilmGrainCollectGroup *m_commonGroups=nullptr;
    FilmGrainCollectLookup *m_lookup=nullptr;
    FilmGrainNativeComponentCounts *m_sourceCounts=nullptr;
    cudaStream_t m_stream=nullptr;
    cudaEvent_t m_ready=nullptr,m_consumed=nullptr;
    bool m_configured=false;
    uint64_t m_epoch=1,m_maxBytes=0;
    int64_t m_visited=-1;
    unsigned m_width=0,m_height=0,m_depth=0,m_shift=0;
    int m_timebaseNum=0,m_timebaseDen=0;

    static void check(cudaError_t e) {if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
    static void binary(const Path& path,const void *data,size_t bytes) {
        std::ofstream output(path,std::ios::binary);output.write(static_cast<const char*>(data),bytes);
        if(!output)throw std::runtime_error("joint probe output write failed");
    }
    static void json_file(const Path& path,const Json& value) {
        auto temporary=path;temporary+=".tmp";
        {std::ofstream file(temporary);file<<value.dump(2)<<'\n';if(!file)throw std::runtime_error("joint probe JSON write failed");}
        std::filesystem::rename(temporary,path);
    }
    void begin(cudaStream_t sourceStream) {
        check(cudaEventRecord(m_ready,sourceStream));check(cudaStreamWaitEvent(m_stream,m_ready,0));
    }
    void end(cudaStream_t sourceStream) {
        check(cudaEventRecord(m_consumed,m_stream));check(cudaStreamWaitEvent(sourceStream,m_consumed,0));
    }
    void configure(const FilmGrainCollectFrame& source) {
        if(m_configured) {
            if(!film_grain_collect_layout_valid(source)||source.width!=m_width||source.height!=m_height
                ||source.bitDepth!=m_depth||source.storageShift!=m_shift)
                throw std::runtime_error("joint probe layout changed or became invalid");
            return;
        }
        if(!film_grain_collect_layout_valid(source))throw std::runtime_error("joint probe requires supported GPU 4:2:0 input");
        const uint64_t bytesPerFrame=uint64_t(source.width)*source.height*(source.bitDepth==8 ? 3 : 6)/2;
        const bool finalModel=!m_templateSeeds.empty();
        const uint64_t persistentTiles=3ULL*((source.width+63)/64)*((source.height+63)/64);
        const uint64_t maximum=m_requested.size()*((finalModel ? 4 : 3)*bytesPerFrame
            +(finalModel ? 2 : 1)*sizeof(FilmGrainCollectGroup)*FGS_COLLECT_GROUPS+sizeof(FilmGrainCollectLookup)+65536
            +(m_persistentDetail ? persistentTiles*sizeof(FilmGrainPersistentResult)+4096 : 0));
        if(maximum>m_maxBytes)throw std::runtime_error("joint probe exceeds declared output budget");
        check(m_history.configure(source));
        if(m_persistentDetail) {
            check(m_persistentHistory.configure(source));
            check(cudaMalloc(&m_persistentTiles,sizeof(*m_persistentTiles)*FGS_COLLECT_MAX_TILES));
            check(cudaMalloc(&m_persistentResults,sizeof(*m_persistentResults)*FGS_COLLECT_MAX_TILES));
        }
        check(cudaMalloc(&m_tiles,sizeof(*m_tiles)*FGS_COLLECT_MAX_TILES));
        check(cudaMalloc(&m_results,sizeof(*m_results)*FGS_COLLECT_MAX_TILES));
        check(cudaMalloc(&m_groups,sizeof(*m_groups)*FGS_COLLECT_GROUPS));
        if(finalModel)check(cudaMalloc(&m_commonGroups,sizeof(*m_commonGroups)*FGS_COLLECT_GROUPS));
        if(finalModel)check(cudaMalloc(&m_sourceCounts,3*sizeof(*m_sourceCounts)));
        check(cudaMalloc(&m_lookup,sizeof(*m_lookup)));
        m_width=source.width;m_height=source.height;m_depth=source.bitDepth;m_shift=source.storageShift;m_configured=true;
    }
    Json dump_frame(const FilmGrainCollectFrame& f,const std::string& prefix) {
        Json description={{"width",f.width},{"height",f.height},{"depth",f.bitDepth},
            {"shift",f.storageShift},{"frame_id",f.frameId},{"pts",f.timestamp},{"epoch",f.epoch},
            {"complete",f.complete},{"planes",Json::array()}};
        if(!f.complete)return description;
        const unsigned bytes=f.bitDepth==8 ? 1 : 2;
        for(unsigned p=0;p<3;++p) {
            const unsigned width=p ? f.width/2 : f.width,height=p ? f.height/2 : f.height;
            const size_t row=size_t(width)*f.plane[p].pixelStride*bytes;
            const size_t span=(size_t(width)-1)*f.plane[p].pixelStride*bytes+bytes;
            std::vector<uint8_t> staged(row*height),planar(size_t(width)*height*bytes);
            check(cudaMemcpy2DAsync(staged.data(),row,f.plane[p].data,f.plane[p].pitchBytes,span,height,cudaMemcpyDeviceToHost,m_stream));
            check(cudaStreamSynchronize(m_stream));
            for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x)
                for(unsigned b=0;b<bytes;++b)planar[(size_t(y)*width+x)*bytes+b]=staged[y*row+size_t(x)*f.plane[p].pixelStride*bytes+b];
            const auto path=m_directory/(prefix+"-"+std::to_string(p)+".raw");
            binary(path,planar.data(),planar.size());
            description["planes"].push_back({{"path",path.u8string()},{"pitch",size_t(width)*bytes},{"stride",1},{"offset",0}});
        }
        return description;
    }
    Json persistent_detail(const FilmGrainCollectFrame& source,const FilmGrainCollectFrame& base,
        const std::string& prefix) {
        const auto history=m_persistentHistory.view(m_stream);
        std::vector<FilmGrainPersistentTile> tiles;
        for(unsigned p=0;p<3;++p) {
            const unsigned side=p ? 32 : 64,width=p ? source.width/2 : source.width,height=p ? source.height/2 : source.height;
            for(unsigned y=0;y<height;y+=side)for(unsigned x=0;x<width;x+=side)tiles.push_back({x,y,p});
        }
        std::vector<FilmGrainPersistentResult> rows(tiles.size());
        for(size_t i=0;i<tiles.size();i+=FGS_COLLECT_MAX_TILES) {
            const unsigned n=unsigned(std::min(size_t(FGS_COLLECT_MAX_TILES),tiles.size()-i));
            check(cudaMemcpyAsync(m_persistentTiles,tiles.data()+i,n*sizeof(tiles[0]),cudaMemcpyHostToDevice,m_stream));
            check(film_grain_collect_persistent_async(source,base,history,m_retention,m_persistentTiles,n,m_persistentResults,n,m_stream));
            check(cudaMemcpyAsync(rows.data()+i,m_persistentResults,n*sizeof(rows[0]),cudaMemcpyDeviceToHost,m_stream));
        }
        check(cudaStreamSynchronize(m_stream));
        const auto path=m_directory/(prefix+"-persistent.bin");binary(path,rows.data(),rows.size()*sizeof(rows[0]));
        Json frames=Json::array();
        for(const auto& f:history.source)frames.push_back({{"frame_id",f.frameId},{"pts",f.timestamp},{"epoch",f.epoch},{"complete",f.complete}});
        return {{"schema",1},{"file",path.u8string()},{"row_bytes",sizeof(FilmGrainPersistentResult)},
            {"mean_offset",offsetof(FilmGrainPersistentResult,mean)},{"covariance_offset",offsetof(FilmGrainPersistentResult,covariance)},
            {"tiles",tiles.size()},{"order","component, native y, native x; Y64/C32 including partial borders"},
            {"history",frames},{"history_valid",film_grain_persistent_history_valid(source,history)},
            {"candidate","pre-retention base plus declared native rounded fraction, applied once"},
            {"scope","measurement only; no population or model admission and no output change"}};
    }
public:
    FilmGrainJointProbe(const Path& manifestPath,int timebaseNum,int timebaseDen)
        :m_timebaseNum(timebaseNum),m_timebaseDen(timebaseDen) {
        if(timebaseNum<=0||timebaseDen<=0)throw std::runtime_error("joint probe needs a valid source timebase");
        Json manifest;std::ifstream input(manifestPath);if(!input)throw std::runtime_error("cannot read joint probe manifest");
        input>>manifest;
        if(manifest.contains("persistent_detail")) {
            if(!manifest.at("persistent_detail").is_boolean())throw std::runtime_error("persistent_detail must be boolean");
            m_persistentDetail=manifest.at("persistent_detail").get<bool>();
        }
        m_templateSeeds=film_grain_probe_template_seeds(manifest);
        if(manifest.at("schema")!=1||!manifest.at("frames").is_array()
            ||manifest.at("frames").empty()||manifest.at("frames").size()>16)
            throw std::runtime_error("joint probe requires 1..16 explicit frame IDs");
        for(const auto& id:manifest.at("frames")) {
            if(!id.is_number_integer())throw std::runtime_error("joint probe frame ID is not an integer");
            const auto frame=id.get<int64_t>();
            if(frame<0||frame>10000000||!m_requested.insert(frame).second)
                throw std::runtime_error("invalid or duplicate joint probe frame ID");
        }
        const auto& r=manifest.at("retain");
        if(!r.is_array()||r.size()!=3)throw std::runtime_error("joint probe requires three residual fractions");
        m_retention={r.at(0).get<float>(),r.at(1).get<float>(),r.at(2).get<float>()};
        if(!joint_collect_detail::retention_valid(m_retention))throw std::runtime_error("invalid joint probe residual fraction");
        if(!manifest.at("max_output_bytes").is_number_unsigned())throw std::runtime_error("joint probe needs an unsigned byte budget");
        m_maxBytes=manifest.at("max_output_bytes").get<uint64_t>();
        if(!m_maxBytes||m_maxBytes>2ULL*1024*1024*1024)throw std::runtime_error("joint probe budget must be at most 2 GiB");
        m_directory=std::filesystem::u8path(manifest.at("output_directory").get<std::string>());
        if(!m_directory.is_absolute()||!std::filesystem::create_directory(m_directory))
            throw std::runtime_error("joint probe requires a new absolute output directory");
        json_file(m_directory/"manifest.json",manifest);
        json_file(m_directory/"status.json",{{"complete",false},{"expected_frames",m_requested}});
        // Allocate stream resources last; later CUDA allocation failures are handled
        // by the owning filter's normal close path after successful construction.
        auto error=cudaStreamCreateWithFlags(&m_stream,cudaStreamNonBlocking);
        if(error==cudaSuccess)error=cudaEventCreateWithFlags(&m_ready,cudaEventDisableTiming);
        if(error==cudaSuccess)error=cudaEventCreateWithFlags(&m_consumed,cudaEventDisableTiming);
        if(error!=cudaSuccess) {
            if(m_consumed)cudaEventDestroy(m_consumed);
            if(m_ready)cudaEventDestroy(m_ready);
            if(m_stream)cudaStreamDestroy(m_stream);
            check(error);
        }
    }
    ~FilmGrainJointProbe() {
        if(m_stream)cudaStreamSynchronize(m_stream);
        m_history.clear();
        m_persistentHistory.clear();
        if(m_persistentTiles)cudaFree(m_persistentTiles);if(m_persistentResults)cudaFree(m_persistentResults);
        if(m_tiles)cudaFree(m_tiles);if(m_results)cudaFree(m_results);
        if(m_groups)cudaFree(m_groups);if(m_lookup)cudaFree(m_lookup);
        if(m_commonGroups)cudaFree(m_commonGroups);
        if(m_sourceCounts)cudaFree(m_sourceCounts);
        if(m_consumed)cudaEventDestroy(m_consumed);if(m_ready)cudaEventDestroy(m_ready);
        if(m_stream)cudaStreamDestroy(m_stream);
    }
    void reset(){++m_epoch;m_visited=-1;m_history.reset();m_persistentHistory.reset();}
    bool visited(int64_t id) const{return m_visited==id;}
    void collect(FilmGrainCollectFrame source,FilmGrainCollectFrame base,cudaStream_t stream,bool sceneReset,const char *stage) {
        if(sceneReset)reset();m_visited=source.frameId;
        if(!m_requested.count(source.frameId)||m_captured.count(source.frameId))return;
        configure(source);source.epoch=base.epoch=m_epoch;
        if(!film_grain_collect_base_valid(source,base))throw std::runtime_error("joint probe lost source/base frame correspondence");
        begin(stream);
        const auto previous=m_history.view(m_stream);
        std::vector<FilmGrainCollectTile> tiles;
        for(unsigned p=1;p<=2;++p)for(unsigned y=0;y+32<=source.height/2;y+=32)
            for(unsigned x=0;x+32<=source.width/2;x+=32)tiles.push_back({x,y,p});
        for(size_t i=0;i<tiles.size();i+=FGS_COLLECT_MAX_TILES) {
            const unsigned n=unsigned(std::min(size_t(FGS_COLLECT_MAX_TILES),tiles.size()-i));
            check(cudaMemcpyAsync(m_tiles,tiles.data()+i,n*sizeof(tiles[0]),cudaMemcpyHostToDevice,m_stream));
            check(film_grain_collect_joint_async(source,base,previous,m_retention,m_tiles,n,m_results,n,m_stream));
            check(film_grain_collect_reduce_async(m_tiles,m_results,n,m_groups,FGS_COLLECT_GROUPS,i==0,m_stream));
            if(m_commonGroups)check(film_grain_collect_reduce_common_async(m_tiles,m_results,n,m_commonGroups,FGS_COLLECT_GROUPS,i==0,m_stream));
        }
        check(film_grain_collect_lookup_async(source,base,m_retention.y,m_lookup,m_stream));
        std::vector<FilmGrainCollectGroup> groups(FGS_COLLECT_GROUPS);FilmGrainCollectLookup lookup;
        check(cudaMemcpyAsync(groups.data(),m_groups,groups.size()*sizeof(groups[0]),cudaMemcpyDeviceToHost,m_stream));
        check(cudaMemcpyAsync(&lookup,m_lookup,sizeof(lookup),cudaMemcpyDeviceToHost,m_stream));
        check(cudaStreamSynchronize(m_stream));
        if(lookup.invalidSamples)throw std::runtime_error("joint probe encountered invalid native picture codes");
        const std::string prefix="frame-"+std::to_string(source.frameId);
        Json record={{"schema",1},{"frame_id",source.frameId},{"stage",stage},{"scene_reset",sceneReset},
            {"source",dump_frame(source,prefix+"-source")},{"base",dump_frame(base,prefix+"-base")},
            {"previous",dump_frame(previous,prefix+"-previous")},{"retain",{m_retention.y,m_retention.cb,m_retention.cr}},
            {"timebase",{m_timebaseNum,m_timebaseDen}},{"tiles",tiles.size()},{"group_count",FGS_COLLECT_GROUPS},{"group_bytes",sizeof(FilmGrainCollectGroup)},
            {"moment_count",FGS_COLLECT_MOMENTS},{"lookup_y",lookup.luma},{"lookup_c",lookup.chroma},
            {"groups_file",(m_directory/(prefix+"-groups.bin")).u8string()}};
        binary(m_directory/(prefix+"-groups.bin"),groups.data(),groups.size()*sizeof(groups[0]));
        if(m_commonGroups) {
            check(cudaMemcpyAsync(groups.data(),m_commonGroups,groups.size()*sizeof(groups[0]),cudaMemcpyDeviceToHost,m_stream));
            check(cudaStreamSynchronize(m_stream));
            record["common_groups_file"]=(m_directory/(prefix+"-common-groups.bin")).u8string();
            binary(m_directory/(prefix+"-common-groups.bin"),groups.data(),groups.size()*sizeof(groups[0]));
        }
        if(m_persistentDetail)record["persistent_detail"]=persistent_detail(source,base,prefix);
        end(stream);
        json_file(m_directory/(prefix+".json"),record);m_captured.insert(source.frameId);
        if(!m_templateSeeds.empty())m_captureIdentity.emplace(source.frameId,std::make_pair(source.timestamp,source.epoch));
    }
    void final_model(FilmGrainCollectFrame source,FilmGrainCollectFrame base,
        const NV_ENC_FILM_GRAIN_PARAMS_AV1& params,cudaStream_t stream,const Json& retention=Json()) {
        if(m_templateSeeds.empty()||!m_requested.count(source.frameId))return;
        configure(source);source.epoch=base.epoch=m_epoch;
        const auto identity=m_captureIdentity.find(source.frameId);
        if(!film_grain_collect_base_valid(source,base)||identity==m_captureIdentity.end()
            ||identity->second!=std::make_pair(source.timestamp,source.epoch)||m_finalCaptured.count(source.frameId))
            throw std::runtime_error("joint probe lost final model/frame correspondence");
        const auto model=film_grain_final_model_evidence(params,source.bitDepth,m_templateSeeds);
        const std::string prefix="frame-"+std::to_string(source.frameId);
        begin(stream);
        check(film_grain_source_preservation_async(source,base,m_sourceCounts,3,m_stream));
        Json record={{"schema",1},{"frame_id",source.frameId},{"pts",source.timestamp},{"epoch",source.epoch},
            {"timebase",{m_timebaseNum,m_timebaseDen}},{"model",model},
            {"base",dump_frame(base,prefix+"-encoder-base")},
            {"base_stage","final native input to NVENC; after source retention/recovery, before lossy compression"}};
        if(!retention.is_null())record["pre_encode_retention"]=retention;
        std::array<FilmGrainNativeComponentCounts,3> counts{};
        check(cudaMemcpyAsync(counts.data(),m_sourceCounts,sizeof(counts),cudaMemcpyDeviceToHost,m_stream));
        check(cudaStreamSynchronize(m_stream));
        record["source_component_counts"]=Json::array();
        for(unsigned p=0;p<3;++p) {
            const auto& c=counts[p];
            if(c.samples!=uint64_t(source.width)*source.height/(p ? 4 : 1)||c.invalidSamples)
                throw std::runtime_error("joint probe final source/base has invalid native samples");
            record["source_component_counts"].push_back({{"samples",c.samples},{"changed_samples",c.changedSamples},
                {"invalid_samples",c.invalidSamples},{"minimum",c.minimum},{"maximum",c.maximum}});
        }
        record["source_component_counts_scope"]="whole native component including borders; curve/range and colour compatibility checks remain separate";
        end(stream);
        json_file(m_directory/(prefix+"-final.json"),record);m_finalCaptured.insert(source.frameId);
    }
    void save(FilmGrainCollectFrame source,cudaStream_t stream) {
        if(m_captured==m_requested)return;
        configure(source);source.epoch=m_epoch;begin(stream);check(m_history.save_async(source,m_stream));
        if(m_persistentDetail)check(m_persistentHistory.save_async(source,m_stream));
        end(stream);
    }
    void finish() {
        if(m_captured!=m_requested)throw std::runtime_error("joint probe did not receive every requested frame");
        if(!m_templateSeeds.empty()&&m_finalCaptured!=m_requested)
            throw std::runtime_error("joint probe did not receive every requested final model");
        check(cudaStreamSynchronize(m_stream));
        json_file(m_directory/"status.json",{{"complete",true},{"captured_frames",m_captured},{"final_model_frames",m_finalCaptured}});
    }
};
} // namespace fgsmodel
