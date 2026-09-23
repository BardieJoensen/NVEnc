// Manually invoked measurement harness; never installs an encoder or reads library paths.
#include "NVEncFilmGrainPersistentCollect.cuh"
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
        if(argc!=3)throw std::runtime_error("usage: persistent-collect MANIFEST.json REPORT.json");
        json manifest;std::ifstream(argv[1])>>manifest;
        json report={{"complete",false},{"cases",json::array()}};
        if(manifest.at("cases").size()>2048)throw std::runtime_error("too many cases");
        for(const auto& c:manifest.at("cases")) {
            Storage storage;
            const auto source=frame(c.at("source"),storage),base=frame(c.at("base"),storage);
            FilmGrainPersistentHistory history;
            for(unsigned i=0;i<7;++i)history.source[i]=frame(c.at("history").at(i),storage);
            FilmGrainCollectRetention retain{c.at("retain").at(0),c.at("retain").at(1),c.at("retain").at(2)};
            std::vector<FilmGrainPersistentTile> tiles;
            for(const auto& t:c.at("tiles"))tiles.push_back({t.at(0),t.at(1),t.at(2)});
            if(tiles.empty()||tiles.size()>49152)throw std::runtime_error("invalid finite tile count");
            auto input=storage.allocate<FilmGrainPersistentTile>(tiles.size());
            checked(cudaMemcpy(input,tiles.data(),tiles.size()*sizeof(tiles[0]),cudaMemcpyHostToDevice));
            auto output=storage.allocate<FilmGrainPersistentResult>(tiles.size());
            // Poison reused output before every run; rejected histories/tiles must
            // clear stale statistics, and invalid host calls must not launch.
            checked(cudaMemset(output,0xa5,tiles.size()*sizeof(*output)));
            unsigned rejections=0;
            const auto reject=[&](cudaError_t value) {
                if(value!=cudaErrorInvalidValue)throw std::runtime_error("invalid call accepted");
                ++rejections;
            };
            reject(film_grain_collect_persistent_async(source,base,history,retain,input,1,output,0,nullptr));
            reject(film_grain_collect_persistent_async(source,base,history,retain,input,0,output,1,nullptr));
            reject(film_grain_collect_persistent_async(source,base,history,retain,input,513,output,513,nullptr));
            reject(film_grain_collect_persistent_async(source,base,history,retain,nullptr,1,output,1,nullptr));
            reject(film_grain_collect_persistent_async(source,base,history,retain,input,1,nullptr,1,nullptr));
            auto wrong=base;wrong.timestamp++;
            reject(film_grain_collect_persistent_async(source,wrong,history,retain,input,1,output,1,nullptr));
            for(unsigned component=0;component<3;++component)for(float value:{-0.01f,1.01f,std::numeric_limits<float>::quiet_NaN()}) {
                auto bad=retain;
                if(component==0)bad.y=value;else if(component==1)bad.cb=value;else bad.cr=value;
                reject(film_grain_collect_persistent_async(source,base,history,bad,input,1,output,1,nullptr));
            }
            cudaStream_t stream;checked(cudaStreamCreate(&stream));
            cudaEvent_t start,end;checked(cudaEventCreate(&start));checked(cudaEventCreate(&end));
            checked(cudaEventRecord(start,stream));
            for(size_t i=0;i<tiles.size();i+=FGS_COLLECT_MAX_TILES) {
                const unsigned n=unsigned(std::min(size_t(FGS_COLLECT_MAX_TILES),tiles.size()-i));
                checked(film_grain_collect_persistent_async(source,base,history,retain,input+i,n,output+i,n,stream));
            }
            checked(cudaEventRecord(end,stream));checked(cudaStreamSynchronize(stream));
            float ms=0;checked(cudaEventElapsedTime(&ms,start,end));
            std::vector<FilmGrainPersistentResult> rows(tiles.size());
            checked(cudaMemcpy(rows.data(),output,rows.size()*sizeof(rows[0]),cudaMemcpyDeviceToHost));
            json result={{"id",c.at("id")},{"milliseconds",ms},{"invalid_calls_rejected",rejections},{"tiles",json::array()}};
            for(const auto& row:rows)result["tiles"].push_back({{"reasons",row.reasons},{"samples",row.samples},
                {"changed_samples",row.changedSamples},{"reserved",row.reserved},{"mean",row.mean},{"covariance",row.covariance}});
            report["cases"].push_back(std::move(result));
            checked(cudaEventDestroy(start));checked(cudaEventDestroy(end));checked(cudaStreamDestroy(stream));
            std::cout<<c.at("id")<<" tiles="<<tiles.size()<<" ms="<<ms<<std::endl;
        }
        report["complete"]=true;std::ofstream output(argv[2]);output<<report.dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write report");
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
