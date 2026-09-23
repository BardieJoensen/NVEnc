#include <filesystem>
#include <fstream>
#include "engine.h"
#include "NVEncFilmGrainNativeEngineAPI.h"
extern "C" {
#include "libavutil/mem.h"
#include "libavutil/sha.h"
}
using namespace fgsdiagnostic;
namespace {
thread_local std::string openError;
void require(bool b,const char* why){if(!b)throw std::runtime_error(why);}
uint64_t integer(const Json& j,const char* key,uint64_t low,uint64_t high) {
    const auto& v=j.at(key);require(v.is_number_integer() && v>=low && v<=high,"native engine integer range");return v.get<uint64_t>();
}
int64_t timestamp(const Json& value) {
    require(value.is_number_integer() && value!=INT64_MIN
        && (!value.is_number_unsigned() || value.get<uint64_t>()<=uint64_t(INT64_MAX)),"native engine timestamp range");return value.get<int64_t>();
}
std::string hash(const uint8_t* bytes,size_t count) {
    std::unique_ptr<AVSHA,decltype(&av_free)> sha(av_sha_alloc(),av_free);require(bool(sha),"hash allocation failed");
    require(av_sha_init(sha.get(),256)==0,"hash initialization failed");av_sha_update(sha.get(),bytes,count);
    uint8_t digest[32];av_sha_final(sha.get(),digest);constexpr char hex[]="0123456789abcdef";std::string result;
    for(auto b:digest){result+=hex[b>>4];result+=hex[b&15];}return result;
}
struct Context {
    struct Source {std::array<std::filesystem::path,3> paths;std::array<std::string,3> hashes;int64_t pts;};
    std::vector<Source> sources;
    NativeSequenceEngine::Config config;
    std::unique_ptr<NativeSequenceEngine> engine;
    unsigned received=0;
    bool failed=false;
    bool memorySource=false;
    std::string error,reportText,modelText;
    void fail(const std::exception& e){failed=true;if(error.empty())error=e.what();}
    void ready(){require(!failed,"native engine context failed");}
    void initialize(const char* data,size_t bytes) {
        require(data && bytes && bytes<=65536,"native engine manifest size");const auto j=Json::parse(data,data+bytes);
        const auto mode=j.value("source_mode",std::string("files"));
        require(mode=="files" || mode=="memory","native source mode must be files or memory");memorySource=mode=="memory";
        integer(j,"schema",1,1);config.width=integer(j,"width",64,4096);config.height=integer(j,"height",64,2160);
        config.depth=integer(j,"depth",8,10);config.matrix=integer(j,"matrix",1,9);config.frames=integer(j,"frame_count",8,16);
        config.shift=integer(j,"shift",6,9);config.grainShift=integer(j,"grain_shift",0,3);
        const auto spatial=j.value("spatial_policy",std::string("frame_window"));
        require(spatial=="frame_window" || spatial=="full_picture" || spatial=="full_picture_means","native spatial policy must be frame_window, full_picture or full_picture_means");
        config.spatialPolicy=spatial=="full_picture_means"?FilmGrainMomentSpatialPolicy::FullPictureMeans
            :spatial=="full_picture"?FilmGrainMomentSpatialPolicy::FullPicture:FilmGrainMomentSpatialPolicy::FrameWindow;
        if(j.contains("max_native_bytes"))config.maxNativeBytes=integer(j,"max_native_bytes",1,512ull*1024*1024);
        const auto& seeds=j.at("training_seeds");require(seeds.is_array() && !seeds.empty() && seeds.size()<=32,"native engine training seed count");
        for(const auto& seed:seeds) {require(seed.is_number_integer() && seed>0 && seed<=65535,"native engine seed range");config.trainingSeeds.push_back(seed.get<uint16_t>());}
        const auto& frames=j.at("sources");require(frames.is_array() && frames.size()==config.frames,"native engine source count");
        for(size_t i=0;i<frames.size();++i) {
            const auto& frame=frames[i];require(integer(frame,"ordinal",0,15)==i,"native source ordinal differs");
            Source source;source.pts=timestamp(frame.at("pts"));require(!i || source.pts>sources.back().pts,"native source clocks must increase");
            if(memorySource)require(!frame.contains("planes"),"memory sources must not supply source files");
            else {
                const auto& planes=frame.at("planes");require(planes.is_array() && planes.size()==3,"native source plane count");
                for(unsigned c=0;c<3;++c) {
                    source.paths[c]=std::filesystem::u8path(planes[c].at("path").get<std::string>());
                    source.hashes[c]=planes[c].at("sha256").get<std::string>();
                    require(source.paths[c].is_absolute() && source.hashes[c].size()==64
                        && source.hashes[c].find_first_not_of("0123456789abcdef")==std::string::npos,"native source path/hash invalid");
                }
            }
            sources.push_back(std::move(source));
        }
        engine=std::make_unique<NativeSequenceEngine>(config);
    }
    void push(uint64_t ordinal,int64_t pts,const FgsNativePlane* base) {
        ready();require(!memorySource,"file-source push used for memory sources");
        require(base && ordinal==received && ordinal<sources.size() && pts==sources[ordinal].pts,"native source/base identity differs");
        std::array<std::vector<uint16_t>,3> values;NativeSequenceEngine::Pictures source{},reconstruction{};
        for(unsigned c=0;c<3;++c) {
            const unsigned w=c?config.width/2:config.width,h=c?config.height/2:config.height;const size_t count=size_t(w)*h;
            const auto& path=sources[ordinal].paths[c];require(std::filesystem::file_size(path)==count*2,"native source plane byte count differs");
            values[c].resize(count);std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(values[c].data()),count*2);require(bool(file),"native source read failed");
            require(hash(reinterpret_cast<const uint8_t*>(values[c].data()),count*2)==sources[ordinal].hashes[c],"native source hash differs");
            source[c]={values[c].data(),count,w};reconstruction[c]={base[c].data,base[c].samples,base[c].stride};
        }
        engine->push(ordinal,pts,0,source,reconstruction);++received;
    }
    void pushPair(uint64_t ordinal,int64_t pts,const FgsNativePlane* source,const FgsNativePlane* base) {
        ready();require(memorySource,"memory-source push used for file sources");
        require(source && base && ordinal==received && ordinal<sources.size() && pts==sources[ordinal].pts,"native memory source/base identity differs");
        NativeSequenceEngine::Pictures original{},reconstruction{};
        for(unsigned c=0;c<3;++c) {
            original[c]={source[c].data,source[c].samples,source[c].stride};
            reconstruction[c]={base[c].data,base[c].samples,base[c].stride};
        }
        engine->push(ordinal,pts,0,original,reconstruction);++received;
    }
};
template<class F> int run(void* pointer,F f) {
    if(!pointer)return -1;
    auto& c=*static_cast<Context*>(pointer);
    try {c.ready();return f(c);}catch(const std::exception& e){c.fail(e);return -1;}
    catch(...){c.failed=true;return -1;}
}
}
extern "C" {
unsigned fgs_native_engine_abi_version(){return 2;}
void* fgs_native_engine_open(const char* json,size_t bytes) {
    try {openError.clear();auto c=std::make_unique<Context>();c->initialize(json,bytes);return c.release();}
    catch(const std::exception& e){openError=e.what();return nullptr;}catch(...){return nullptr;}
}
int fgs_native_engine_push(void* c,uint64_t ordinal,int64_t pts,const FgsNativePlane base[3]) {
    return run(c,[&](Context& context){context.push(ordinal,pts,base);return 0;});
}
int fgs_native_engine_push_pair(void* c,uint64_t ordinal,int64_t pts,const FgsNativePlane source[3],const FgsNativePlane base[3]) {
    return run(c,[&](Context& context){context.pushPair(ordinal,pts,source,base);return 0;});
}
int fgs_native_engine_model(void* c,uint64_t ordinal,const char** json,size_t* bytes) {
    if(json)*json=nullptr;
    if(bytes)*bytes=0;
    return run(c,[&](Context& context) {
        require(json && bytes && ordinal<context.config.frames,"native model output arguments");
        if(!context.engine->ready(ordinal))return 0;
        context.modelText=context.engine->selectedModel(ordinal).dump();*json=context.modelText.c_str();*bytes=context.modelText.size();return 1;
    });
}
int fgs_native_engine_finish(void* c) {
    return run(c,[](Context& context){require(context.received==context.sources.size(),"native engine missing source inputs");context.engine->finish();return 0;});
}
const char* fgs_native_engine_report(void* pointer) {
    if(!pointer)return nullptr;
    auto& c=*static_cast<Context*>(pointer);
    try {auto report=c.engine->report();report["complete"]=report.at("complete").get<bool>() && !c.failed;
        report["failed"]=report.at("failed").get<bool>() || c.failed;report["context_error"]=c.error;
        report["source_mode"]=c.memorySource?"memory":"files";report["source_frames"]=c.received;
        report["verified_source_frames"]=c.memorySource?0:c.received;
        c.reportText=report.dump();return c.reportText.c_str();
    }catch(...){c.failed=true;return nullptr;}
}
const char* fgs_native_engine_error(void* c){return c?static_cast<Context*>(c)->error.c_str():openError.c_str();}
void fgs_native_engine_close(void* c){delete static_cast<Context*>(c);}
}
