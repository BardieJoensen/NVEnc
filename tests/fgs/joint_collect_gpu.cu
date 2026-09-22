// Manually invoked measurement harness; never installs an encoder or reads library paths.
#include "NVEncFilmGrainJointCollect.cuh"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
using namespace fgsmodel;
using nlohmann::json;
static void checked(cudaError_t error) {
    if(error!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(error));
}
struct Storage {
    std::vector<void*> allocations;
    ~Storage(){for(auto p:allocations)cudaFree(p);}
    template<class T>T* allocate(size_t count) {
        T* p=nullptr;checked(cudaMalloc(&p,sizeof(T)*count));allocations.push_back(p);return p;
    }
};
static FilmGrainCollectFrame frame(const json& description,Storage& storage) {
    FilmGrainCollectFrame result;
    result.width=description.at("width");result.height=description.at("height");
    result.bitDepth=description.at("depth");result.storageShift=description.at("shift");
    result.frameId=description.at("frame_id");result.timestamp=description.at("pts");
    result.epoch=description.at("epoch");result.complete=description.at("complete");
    if(!result.complete)return result; // deliberate absent-history control
    for(unsigned p=0;p<3;++p) {
        const auto& plane=description.at("planes").at(p);
        std::ifstream input(plane.at("path").get<std::string>(),std::ios::binary|std::ios::ate);
        if(!input)throw std::runtime_error("cannot open input plane");
        const size_t size=size_t(input.tellg());input.seekg(0);
        const size_t pitch=plane.at("pitch");const size_t offset=plane.at("offset");
        const unsigned rows=p ? result.height/2 : result.height;
        const unsigned columns=p ? result.width/2 : result.width;
        const unsigned stride=plane.at("stride");const unsigned bytes=result.bitDepth==8 ? 1 : 2;
        if(size!=pitch*rows || offset+size_t(columns-1)*stride*bytes+bytes>pitch)
            throw std::runtime_error("invalid input plane extent");
        std::vector<uint8_t> host(size);input.read(reinterpret_cast<char*>(host.data()),size);
        if(!input)throw std::runtime_error("short input plane");
        auto device=storage.allocate<uint8_t>(size);checked(cudaMemcpy(device,host.data(),size,cudaMemcpyHostToDevice));
        result.plane[p]={device+offset,pitch,stride};
    }
    return result;
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::runtime_error("usage: joint-collect MANIFEST.json REPORT.json");
        json manifest;std::ifstream(argv[1])>>manifest;
        json report={{"complete",false},{"cases",json::array()}};
        for(const auto& c:manifest.at("cases")) {
            Storage storage;
            const auto source=frame(c.at("source"),storage),base=frame(c.at("base"),storage),previous=frame(c.at("previous"),storage);
            FilmGrainCollectRetention retain{c.at("retain").at(0),c.at("retain").at(1),c.at("retain").at(2)};
            std::vector<FilmGrainCollectTile> tiles;
            for(const auto& t:c.at("tiles"))tiles.push_back({t.at(0),t.at(1),t.at(2)});
            if(tiles.empty()||tiles.size()>8192)throw std::runtime_error("invalid finite tile count");
            auto input=storage.allocate<FilmGrainCollectTile>(tiles.size());
            checked(cudaMemcpy(input,tiles.data(),tiles.size()*sizeof(tiles[0]),cudaMemcpyHostToDevice));
            auto output=storage.allocate<FilmGrainCollectResult>(tiles.size());
            auto histogram=storage.allocate<FilmGrainCollectLookup>(1);
            auto groups=storage.allocate<FilmGrainCollectGroup>(FGS_COLLECT_GROUPS);
            const bool collectCommon=c.value("common_groups",false);
            auto common=collectCommon ? storage.allocate<FilmGrainCollectGroup>(FGS_COLLECT_GROUPS) : nullptr;
            if(collectCommon) {
                for(const auto count:{0u,FGS_COLLECT_MAX_TILES+1})
                    if(film_grain_collect_reduce_common_async(input,output,count,common,FGS_COLLECT_GROUPS,true,nullptr)!=cudaErrorInvalidValue)
                        throw std::runtime_error("common cohort count rejection failed");
                if(film_grain_collect_reduce_common_async(input,output,1,common,FGS_COLLECT_GROUPS-1,true,nullptr)!=cudaErrorInvalidValue
                    || film_grain_collect_reduce_common_async(input,output,1,nullptr,FGS_COLLECT_GROUPS,true,nullptr)!=cudaErrorInvalidValue)
                    throw std::runtime_error("common cohort capacity rejection failed");
            }
            // A missing output slot and changed base identity must fail before launch.
            if(film_grain_collect_joint_async(source,base,previous,retain,input,1,output,0,nullptr)!=cudaErrorInvalidValue)
                throw std::runtime_error("capacity rejection failed");
            auto wrongBase=base;wrongBase.timestamp++;
            if(film_grain_collect_joint_async(source,wrongBase,previous,retain,input,1,output,1,nullptr)!=cudaErrorInvalidValue)
                throw std::runtime_error("base identity rejection failed");
            cudaStream_t stream;checked(cudaStreamCreate(&stream));
            FilmGrainCollectHistory history;checked(history.configure(source));
            if(history.view(stream).complete)throw std::runtime_error("new history is valid");
            cudaEvent_t start,end;checked(cudaEventCreate(&start));checked(cudaEventCreate(&end));
            const unsigned repeats=c.value("repeats",1u);
            if(!repeats||repeats>10)throw std::runtime_error("invalid repeat count");
            checked(cudaEventRecord(start,stream));
            for(unsigned repeat=0;repeat<repeats;++repeat) {
                if(previous.complete)checked(history.save_async(previous,stream));
                else {
                    if(history.save_async(previous,stream)!=cudaErrorInvalidValue)
                        throw std::runtime_error("incomplete history update accepted");
                }
                if(history.view(nullptr).complete)throw std::runtime_error("cross-stream history was exposed");
                const auto copiedPrevious=history.view(stream);
                for(size_t i=0;i<tiles.size();i+=FGS_COLLECT_MAX_TILES) {
                    const unsigned n=unsigned(std::min(size_t(FGS_COLLECT_MAX_TILES),tiles.size()-i));
                    checked(film_grain_collect_joint_async(source,base,copiedPrevious,retain,input+i,n,output+i,n,stream));
                    checked(film_grain_collect_reduce_async(input+i,output+i,n,groups,FGS_COLLECT_GROUPS,i==0,stream));
                    if(collectCommon)checked(film_grain_collect_reduce_common_async(input+i,output+i,n,common,FGS_COLLECT_GROUPS,i==0,stream));
                }
                checked(film_grain_collect_lookup_async(source,base,retain.y,histogram,stream));
            }
            checked(cudaEventRecord(end,stream));checked(cudaStreamSynchronize(stream));
            float milliseconds=0;checked(cudaEventElapsedTime(&milliseconds,start,end));
            std::vector<FilmGrainCollectResult> rows(tiles.size());FilmGrainCollectLookup lookup;
            checked(cudaMemcpy(rows.data(),output,rows.size()*sizeof(rows[0]),cudaMemcpyDeviceToHost));
            checked(cudaMemcpy(&lookup,histogram,sizeof(lookup),cudaMemcpyDeviceToHost));
            std::vector<FilmGrainCollectGroup> grouped(FGS_COLLECT_GROUPS);
            checked(cudaMemcpy(grouped.data(),groups,grouped.size()*sizeof(grouped[0]),cudaMemcpyDeviceToHost));
            json result={{"id",c.at("id")},{"milliseconds",milliseconds/repeats},
                {"timing_scope","all-plane history copy, joint collection/reduction and full-picture histograms; excludes allocation, upload, result download and JSON"},
                {"common_groups_collected",collectCommon},
                {"repeat_count",repeats},{"output_bytes",rows.size()*sizeof(rows[0])},
                {"tiles",json::array()},{"lookup_y",lookup.luma},{"lookup_c",lookup.chroma},
                {"invalid_lookup_samples",lookup.invalidSamples}};
            result["groups"]=json::array();
            for(const auto& g:grouped)result["groups"].push_back({{"blocks",g.blocks},{"observations",g.observations},
                {"other_colour_supported_blocks",g.otherColourSupportedBlocks},{"moments",g.moments}});
            if(collectCommon) {
                checked(cudaMemcpy(grouped.data(),common,grouped.size()*sizeof(grouped[0]),cudaMemcpyDeviceToHost));
                result["common_groups"]=json::array();
                for(const auto& g:grouped)result["common_groups"].push_back({{"blocks",g.blocks},{"observations",g.observations},
                    {"other_colour_supported_blocks",g.otherColourSupportedBlocks},{"moments",g.moments}});
            }
            unsigned accepted=0;
            for(size_t i=0;i<rows.size();++i) {
                const auto& r=rows[i];if(!r.reasons)++accepted;
                if(c.value("include_tiles",true))result["tiles"].push_back({{"reasons",r.reasons},{"brightness_group",r.brightnessGroup},
                    {"check_fold",r.checkFold},{"observations",r.observations},{"mean",r.mean},
                    {"variance",r.variance},{"temporal_correlation",r.temporalCorrelation},{"coherence",r.coherence},
                    {"source",r.source},{"base",r.base},{"sourceBase",r.sourceBase},
                    {"other_colour_reasons",r.otherColourReasons},
                    {"colourSource",r.colourSource},{"colourBase",r.colourBase},{"colourSourceBase",r.colourSourceBase},
                    {"colourLagSource",r.colourLagSource},{"colourLagBase",r.colourLagBase},
                    {"colourLagSourceBase",r.colourLagSourceBase},{"colourLagBaseSource",r.colourLagBaseSource}});
            }
            if(previous.complete) {
                if(history.save_async(previous,nullptr)!=cudaErrorInvalidValue || history.view(stream).complete)
                    throw std::runtime_error("cross-stream update retained valid history");
                checked(history.save_async(previous,stream));
                if(!film_grain_collect_history_valid(source,history.view(stream)))
                    throw std::runtime_error("history did not recover on its owning stream");
                checked(cudaStreamSynchronize(stream));
            }
            history.reset();if(history.view(stream).complete)throw std::runtime_error("reset history is valid");
            checked(cudaEventDestroy(start));checked(cudaEventDestroy(end));checked(cudaStreamDestroy(stream));
            report["cases"].push_back(std::move(result));
            std::cout<<c.at("id")<<" tiles="<<tiles.size()<<" accepted="<<accepted<<" ms="<<milliseconds/repeats<<std::endl;
        }
        report["complete"]=true;std::ofstream output(argv[2]);output<<report.dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write measurement report");
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
