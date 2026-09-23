// Manually invoked measurement harness; never installs an encoder or reads library paths.
#include "NVEncFilmGrainPersistentHistory.cuh"
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
static void same_pixels(const FilmGrainCollectFrame& a,const FilmGrainCollectFrame& b,cudaStream_t stream) {
    if(a.frameId!=b.frameId || a.timestamp!=b.timestamp || a.epoch!=b.epoch || !a.complete || !b.complete)
        throw std::runtime_error("history identity mismatch");
    const unsigned bytes=a.bitDepth==8 ? 1 : 2;
    for(unsigned c=0;c<3;++c) {
        const unsigned w=c ? a.width/2 : a.width,h=c ? a.height/2 : a.height;
        std::vector<uint8_t> left(a.plane[c].pitchBytes*h),right(b.plane[c].pitchBytes*h);
        checked(cudaMemcpyAsync(left.data(),a.plane[c].data,left.size(),cudaMemcpyDeviceToHost,stream));
        // Component pointers can have a UV offset; avoid reading beyond the final row.
        const size_t span=(size_t(w)-1)*b.plane[c].pixelStride*bytes+bytes;
        checked(cudaMemcpy2DAsync(right.data(),b.plane[c].pitchBytes,b.plane[c].data,b.plane[c].pitchBytes,span,h,cudaMemcpyDeviceToHost,stream));
        checked(cudaStreamSynchronize(stream));
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x)for(unsigned k=0;k<bytes;++k)
            if(left[y*a.plane[c].pitchBytes+x*bytes+k]!=right[y*b.plane[c].pitchBytes+x*b.plane[c].pixelStride*bytes+k])
                throw std::runtime_error("history native plane copy mismatch");
    }
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::runtime_error("usage: persistent-history MANIFEST.json REPORT.json");
        json manifest;std::ifstream(argv[1])>>manifest;json report={{"complete",false},{"cases",json::array()}};
        if(manifest.at("cases").size()>64)throw std::runtime_error("too many cases");
        for(const auto& c:manifest.at("cases")) {
            Storage storage;const auto current=frame(c.at("source"),storage);
            FilmGrainPersistentHistory direct;for(unsigned i=0;i<7;++i)direct.source[i]=frame(c.at("history").at(i),storage);
            cudaStream_t stream,other;checked(cudaStreamCreate(&stream));checked(cudaStreamCreate(&other));
            FilmGrainPersistentHistoryCache cache;checked(cache.configure(current));unsigned comparisons=0;
            if(cache.view(stream).source[0].complete)throw std::runtime_error("startup has history");
            const auto fill=[&]() {
                for(unsigned i=0;i<7;++i) {
                    checked(cache.save_async(direct.source[i],stream));
                    if(i<6 && cache.view(stream).source[0].complete)throw std::runtime_error("partial history became complete");
                }
                const auto result=cache.view(stream);
                if(!film_grain_persistent_history_valid(current,result))throw std::runtime_error("complete history rejected");
                for(unsigned i=0;i<7;++i){same_pixels(result.source[i],direct.source[i],stream);comparisons+=3;}
            };
            fill();
            if(cache.view(other).source[0].complete)throw std::runtime_error("history exposed on other stream");
            checked(cache.save_async(current,stream));
            auto result=cache.view(stream);
            for(unsigned i=0;i<7;++i){same_pixels(result.source[i],i==6 ? current : direct.source[i+1],stream);comparisons+=3;}
            // A cross-stream failed update invalidates the entire window.
            if(cache.save_async(current,other)!=cudaErrorInvalidValue || cache.view(stream).source[0].complete)
                throw std::runtime_error("failed cross-stream update left valid history");
            fill();cache.reset();if(cache.view(stream).source[0].complete)throw std::runtime_error("reset has history");
            fill();auto incomplete=current;incomplete.complete=false;
            if(cache.save_async(incomplete,stream)!=cudaErrorInvalidValue || cache.view(stream).source[0].complete)
                throw std::runtime_error("incomplete update left valid history");
            for(unsigned kind=0;kind<5;++kind) {
                fill();auto broken=current;
                if(kind==0)broken.epoch++;
                if(kind==1)broken.frameId+=2;
                if(kind==2)broken.frameId--;
                if(kind==3)broken.timestamp=direct.source[6].timestamp;
                if(kind==4)broken.timestamp=direct.source[6].timestamp-1;
                checked(cache.save_async(broken,stream));
                if(cache.view(stream).source[0].complete)throw std::runtime_error("discontinuity retained history");
                cache.reset();
            }
            auto large=current;large.width=large.height=8192;
            for(unsigned p=0;p<3;++p)large.plane[p].pitchBytes=32768;
            checked(cudaStreamSynchronize(stream));
            if(cache.configure(large)!=cudaErrorInvalidValue)throw std::runtime_error("history memory budget missing");
            if(cache.view(stream).source[0].complete)throw std::runtime_error("failed configure has history");
            cache.clear();checked(cudaStreamDestroy(other));checked(cudaStreamDestroy(stream));
            report["cases"].push_back({{"id",c.at("id")},{"exact_native_plane_comparisons",comparisons}});
            std::cout<<c.at("id")<<" exact plane comparisons="<<comparisons<<std::endl;
        }
        report["complete"]=true;std::ofstream out(argv[2]);out<<report.dump(2)<<'\n';if(!out)throw std::runtime_error("report write failed");
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
