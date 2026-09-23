// Finite live reconstruction-to-model diagnostic. Original sources are explicit
// native planes bound by hashes/PTS; this does not select pre-encode retention.
// The expensive reference engine is loaded only for this explicit option.
#pragma once
#include "NVEncFilmGrainNativeEngineAPI.h"
#include "NVEncFilmGrainModelProbe.h"
#include "NVEncFilmGrainSourceFrame.h"

struct NVEncFilmGrainNativeConfig {
    NVEncFilmGrainModelConfig packets;
    std::filesystem::path engineLibrary;
    nlohmann::json engine;
    bool memorySource() const {return engine.value("source_mode",std::string("files"))=="memory";}
    std::string spatialPolicy() const {return engine.value("spatial_policy",std::string("frame_window"));}
    static NVEncFilmGrainNativeConfig parse(const nlohmann::json& j,const std::set<uint32_t>& captured) {
        if(!j.is_object() || j.contains("models") || j.contains("ready_after") || captured.size()<8)
            throw std::runtime_error("native model trial needs 8..16 pictures and runtime model readiness");
        auto common=j;common["models"]=nlohmann::json::array();
        for(size_t i=0;i<captured.size();++i)common["models"].push_back(nullptr);
        NVEncFilmGrainNativeConfig c;c.packets=NVEncFilmGrainModelConfig::parse(common,captured);
        c.engineLibrary=std::filesystem::u8path(j.at("engine_library").get<std::string>());
        if(!c.engineLibrary.is_absolute())throw std::runtime_error("native engine library must be absolute");
        c.engine=j.at("engine");
        if(c.spatialPolicy()!="frame_window" && c.spatialPolicy()!="full_picture" && c.spatialPolicy()!="full_picture_means" && c.spatialPolicy()!="frame_window_means")
            throw std::runtime_error("native spatial policy must be frame_window, full_picture, full_picture_means or frame_window_means");
        const auto mode=c.engine.value("source_mode",std::string("files"));
        if(mode!="files" && mode!="memory")throw std::runtime_error("native source mode must be files or memory");
        if(!c.engine.is_object() || NVEncFilmGrainModelConfig::integer(c.engine,"frame_count",8,16)!=captured.size()
            || !c.engine.at("sources").is_array() || c.engine.at("sources").size()!=captured.size())
            throw std::runtime_error("native source/model packet count differs");
        for(size_t i=0;i<captured.size();++i) {
            const auto& source=c.engine.at("sources").at(i);
            if(NVEncFilmGrainModelConfig::integer(source,"ordinal",0,15)!=i
                || source.at("pts")!=c.packets.packets[i].pts)
                throw std::runtime_error("native source/packet identity differs");
        }
        return c;
    }
    void requireLayout(unsigned width,unsigned height,unsigned depth) const {
        if(width%64 || height%64 || engine.at("width")!=width || engine.at("height")!=height || engine.at("depth")!=depth)
            throw std::runtime_error("native model trial layout differs from reconstruction");
    }
};

class NVEncFilmGrainNativeLibrary {
    using Json=nlohmann::json;
    void* m_context=nullptr;
#ifdef _WIN32
    HMODULE m_library=nullptr;
#else
    void* m_library=nullptr;
#endif
    int (*m_push)(void*,uint64_t,int64_t,const FgsNativePlane*)=nullptr;
    int (*m_pushPair)(void*,uint64_t,int64_t,const FgsNativePlane*,const FgsNativePlane*)=nullptr;
    int (*m_model)(void*,uint64_t,const char**,size_t*)=nullptr;
    int (*m_finish)(void*)=nullptr;
    const char* (*m_report)(void*)=nullptr;
    const char* (*m_error)(void*)=nullptr;
    void (*m_close)(void*)=nullptr;
    template<class T> T symbol(const char* name) {
#ifdef _WIN32
        return reinterpret_cast<T>(GetProcAddress(m_library,name));
#else
        return reinterpret_cast<T>(dlsym(m_library,name));
#endif
    }
    void close() noexcept {
        if(m_context && m_close)m_close(m_context);
        m_context=nullptr;
        if(m_library) {
#ifdef _WIN32
            FreeLibrary(m_library);
#else
            dlclose(m_library);
#endif
        }
        m_library=nullptr;
    }
    void check(int rc) const {
        if(rc>=0)return;
        const auto message=m_error(m_context);
        throw std::runtime_error(message && *message?message:"native model engine failed");
    }
public:
    NVEncFilmGrainNativeLibrary(const std::filesystem::path& path,const Json& config) {
        try {
#ifdef _WIN32
            m_library=LoadLibraryW(path.c_str());
#else
            m_library=dlopen(path.c_str(),RTLD_NOW|RTLD_LOCAL);
#endif
            if(!m_library)throw std::runtime_error("cannot load native model engine");
            const auto version=symbol<unsigned (*)()>("fgs_native_engine_abi_version");
            const auto open=symbol<void* (*)(const char*,size_t)>("fgs_native_engine_open");
            m_push=symbol<decltype(m_push)>("fgs_native_engine_push");m_model=symbol<decltype(m_model)>("fgs_native_engine_model");
            m_pushPair=symbol<decltype(m_pushPair)>("fgs_native_engine_push_pair");
            m_finish=symbol<decltype(m_finish)>("fgs_native_engine_finish");m_report=symbol<decltype(m_report)>("fgs_native_engine_report");
            m_error=symbol<decltype(m_error)>("fgs_native_engine_error");m_close=symbol<decltype(m_close)>("fgs_native_engine_close");
            if(!version || (version()!=1 && version()!=2) || !open || !m_push || !m_model || !m_finish || !m_report || !m_error || !m_close
                || (version()==2 && !m_pushPair) || (config.value("source_mode",std::string("files"))=="memory" && version()!=2))
                throw std::runtime_error("native model engine requires ABI 1 files or ABI 2 source pairs");
            const auto text=config.dump();m_context=open(text.data(),text.size());
            if(!m_context)check(-1);
        }catch(...){close();throw;}
    }
    ~NVEncFilmGrainNativeLibrary(){close();}
    NVEncFilmGrainNativeLibrary(const NVEncFilmGrainNativeLibrary&)=delete;
    NVEncFilmGrainNativeLibrary& operator=(const NVEncFilmGrainNativeLibrary&)=delete;
    void push(uint64_t ordinal,int64_t pts,const FgsNativePlane base[3]) {check(m_push(m_context,ordinal,pts,base));}
    void pushPair(uint64_t ordinal,int64_t pts,const FgsNativePlane source[3],const FgsNativePlane base[3]) {
        if(!m_pushPair)throw std::runtime_error("native pair ABI is unavailable");
        check(m_pushPair(m_context,ordinal,pts,source,base));
    }
    fgsmodel::FilmGrainModelDecision model(uint64_t ordinal) {
        const char* text=nullptr;size_t count=0;const int rc=m_model(m_context,ordinal,&text,&count);check(rc);
        if(rc==0) {
            if(text || count)throw std::runtime_error("pending native model has output");
            return {};
        }
        if(rc!=1 || !text || !count || count>65536)throw std::runtime_error("invalid native model output");
        return {fgsmodel::FilmGrainModelReadiness::Replace,Json::parse(text,text+count)};
    }
    void finish(){check(m_finish(m_context));}
    Json report() const {
        const auto text=m_report(m_context);if(!text)throw std::runtime_error("native model engine report missing");return Json::parse(text);
    }
};

template<class Token> class NVEncFilmGrainNativeProbe {
    using Json=nlohmann::json;
    using Buffer=fgsmodel::FilmGrainModelBuffer<Token>;
    NVEncFilmGrainNativeConfig m_config;
    NVEncFilmGrainNativeLibrary m_engine;
    Buffer m_buffer;
    std::filesystem::path m_report;
    unsigned m_width,m_height,m_depth;
    std::optional<std::array<float,3>> m_retention;
    uint64_t m_reconstructed=0,m_received=0;
    bool m_failed=false,m_finished=false;
    std::string m_error;
    void status() {
        const auto engine=m_engine.report();auto report=m_buffer.report();report["native_engine"]=engine;
        report["complete"]=m_finished && !m_failed && report.at("complete").template get<bool>() && engine.at("complete").template get<bool>();
        report["failed"]=m_failed || report.at("failed").template get<bool>() || engine.at("failed").template get<bool>();
        report["trial_error"]=m_error;report["reconstructed"]=m_reconstructed;
        if(m_retention)report["pre_encode_retention"]=*m_retention;
        auto temp=m_report;temp+=".tmp";
        {std::ofstream out(temp);out<<report.dump(2)<<'\n';out.flush();if(!out)throw std::runtime_error("native model report write failed");}
        std::filesystem::rename(temp,m_report);
    }
public:
    NVEncFilmGrainNativeProbe(NVEncFilmGrainNativeConfig config,const std::filesystem::path& report,
        unsigned width,unsigned height,unsigned depth,std::optional<std::array<float,3>> retention={})
        :m_config(std::move(config)),m_engine(m_config.engineLibrary,m_config.engine),
        m_buffer(m_config.packets.library,m_config.packets.packets.size(),32,m_config.packets.maxPackets,m_config.packets.maxBytes),
        m_report(report),m_width(width),m_height(height),m_depth(depth),m_retention(std::move(retention)) {
        m_config.requireLayout(width,height,depth);
        if(m_retention && !m_config.memorySource())throw std::runtime_error("native retention requires memory sources");
        if(m_retention)for(float f:*m_retention)if(!std::isfinite(f)||f<0||f>=1)
            throw std::runtime_error("native retention requires finite all-partial fractions");
        // Older ABI-compatible libraries ignore unknown configuration keys.
        // A stricter requested policy needs explicit runtime confirmation.
        if(m_config.spatialPolicy()!="frame_window"
            && m_engine.report().value("spatial_policy",std::string())!=m_config.spatialPolicy())
            throw std::runtime_error("native engine did not confirm "+m_config.spatialPolicy()+" spatial policy");
        status();
    }
    void reconstruction(uint64_t ordinal,int64_t pts,const uint8_t* raw,size_t bytes,
        const fgsdiagnostic::NativeSourceFrame* source=nullptr) {
        try {
            const unsigned unit=m_depth==10?2:1;const uint64_t expected=uint64_t(m_width)*m_height*3/2*unit;
            if(m_failed || m_finished || ordinal!=m_reconstructed || ordinal>=m_config.packets.packets.size()
                || pts!=m_config.packets.packets[ordinal].pts || !raw || bytes!=expected)
                throw std::runtime_error("native reconstruction identity/span differs");
            std::array<std::vector<uint16_t>,3> data;std::array<FgsNativePlane,3> planes{};
            const auto code=[&](size_t index) {
                if(unit==1)return uint16_t(raw[index]);
                const uint16_t word=uint16_t(raw[index*2])|uint16_t(raw[index*2+1])<<8;
                if(word&63)throw std::runtime_error("native P010 reconstruction has unexpected low bits");
                return uint16_t(word>>6);
            };
            for(unsigned c=0;c<3;++c) {
                const unsigned w=c?m_width/2:m_width,h=c?m_height/2:m_height;const size_t n=size_t(w)*h;data[c].resize(n);
                for(size_t i=0;i<n;++i)data[c][i]=code(c?size_t(m_width)*m_height+2*i+c-1:i);
                planes[c]={data[c].data(),n,w};
            }
            if(m_config.memorySource()) {
                if(!source)throw std::runtime_error("native model requires original memory source");
                source->requireIdentity(ordinal,source->sourceId,pts,source->timebaseNum,source->timebaseDen,m_width,m_height,m_depth);
                if(bool(source->retention)!=bool(m_retention))throw std::runtime_error("native model retention decision is missing or unexpected");
                if(m_retention)fgsdiagnostic::requirePartialRetentionModel(*source->retention,*m_retention);
                std::array<FgsNativePlane,3> original{};
                for(unsigned c=0;c<3;++c)original[c]={source->planes[c].data(),source->planes[c].size(),c?m_width/2:m_width};
                m_engine.pushPair(ordinal,pts,original.data(),planes.data());
            } else {
                if(source)throw std::runtime_error("native file mode received unexpected memory source");
                m_engine.push(ordinal,pts,planes.data());
            }
            ++m_reconstructed;status();
        }catch(const std::exception& e){fail(e.what());throw;}
    }
    std::vector<typename Buffer::Output> receive(Token token,const uint8_t* data,size_t bytes,uint64_t input,int64_t pts) {
        try {
            if(m_failed || m_finished || input!=m_received || m_reconstructed!=input+1 || input>=m_config.packets.packets.size()
                || pts!=m_config.packets.packets[input].pts)throw std::runtime_error("native model packet lacks matching reconstruction");
            const auto provider=[&](const fgsmodel::FilmGrainPictureBinding& binding){return m_engine.model(binding.inputOrdinal);};
            auto output=m_buffer.push(std::move(token),data,bytes,input,pts,provider,m_config.packets.packets[input].hashes);
            ++m_received;status();return output;
        }catch(const std::exception& e){fail(e.what());throw;}
    }
    void finish() {
        try {
            if(m_failed || m_received!=m_config.packets.packets.size() || m_reconstructed!=m_received)
                throw std::runtime_error("native model trial incomplete");
            m_engine.finish();m_buffer.finish();m_finished=true;status();
        }catch(const std::exception& e){fail(e.what());throw;}
    }
    void fail(const std::string& error) noexcept {m_failed=true;try{if(m_error.empty())m_error=error;status();}catch(...){} }
};
