// Bounded delayed model output. Policy readiness is separate from reconstruction
// availability; neither parsing nor successful serialization admits a source.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <cstring>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <utility>
#include "NVEncFilmGrainPacketIdentity.h"
#include "../json/json.hpp"
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace fgsmodel {
using ModelJson = nlohmann::json;

// Own both serial parser contexts. No FFmpeg allocations or types cross the ABI.
class FilmGrainModelLibrary {
    void* m_observer=nullptr;
    void* m_writer=nullptr;
#ifdef _WIN32
    HMODULE m_library=nullptr;
#else
    void* m_library=nullptr;
#endif
    int (*m_process)(void*,const uint8_t*,size_t,int64_t,const uint8_t**,size_t*)=nullptr;
    int (*m_queue)(void*,const char*,size_t)=nullptr;
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
        if(m_close){if(m_observer)m_close(m_observer);if(m_writer)m_close(m_writer);}
        m_observer=m_writer=nullptr;
        if(m_library){
#ifdef _WIN32
            FreeLibrary(m_library);
#else
            dlclose(m_library);
#endif
        }
        m_library=nullptr;
    }
    void check(int status,void* context) const {
        if(status>=0)return;
        const auto error=m_error(context);
        throw std::runtime_error(error && *error?error:"complete-model parser failed");
    }
    ModelJson report(void* context) const {
        const auto text=m_report(context);
        if(!text)throw std::runtime_error("missing complete-model report");
        auto result=ModelJson::parse(text);
        if(result.at("failed").get<bool>())throw std::runtime_error("complete-model context failed");
        return result;
    }
public:
    explicit FilmGrainModelLibrary(const std::filesystem::path& path,uint64_t packets) {
        try {
#ifdef _WIN32
            m_library=LoadLibraryW(path.c_str());
#else
            m_library=dlopen(path.c_str(),RTLD_NOW|RTLD_LOCAL);
#endif
            if(!m_library)throw std::runtime_error("cannot load complete-model library");
            const auto version=symbol<unsigned (*)()>("fgs_av1_model_abi_version");
            const auto open=symbol<void* (*)(uint64_t)>("fgs_av1_model_open");
            m_process=symbol<decltype(m_process)>("fgs_av1_model_process");
            m_queue=symbol<decltype(m_queue)>("fgs_av1_model_queue");
            m_finish=symbol<decltype(m_finish)>("fgs_av1_model_finish");
            m_report=symbol<decltype(m_report)>("fgs_av1_model_report");
            m_error=symbol<decltype(m_error)>("fgs_av1_model_error");
            m_close=symbol<decltype(m_close)>("fgs_av1_model_close");
            if(!version || !open || !m_process || !m_queue || !m_finish || !m_report || !m_error || !m_close || version()!=1)
                throw std::runtime_error("complete-model library requires ABI 1");
            m_observer=open(packets);m_writer=open(packets);
            if(!m_observer || !m_writer)throw std::runtime_error("cannot initialize complete-model contexts");
        } catch(...) {close();throw;}
    }
    ~FilmGrainModelLibrary(){close();}
    FilmGrainModelLibrary(const FilmGrainModelLibrary&)=delete;
    FilmGrainModelLibrary& operator=(const FilmGrainModelLibrary&)=delete;

    ModelJson observe(const uint8_t* data,size_t bytes,int64_t pts) {
        const uint8_t* output=nullptr;size_t count=0;
        const int status=m_process(m_observer,data,bytes,pts,&output,&count);check(status,m_observer);
        if(status || !output || count!=bytes || std::memcmp(data,output,bytes))
            throw std::runtime_error("observer unexpectedly changed original packet");
        auto state=report(m_observer);
        if(!state.at("last_packet_complete").get<bool>() || state.at("last_pts")!=pts)
            throw std::runtime_error("observer did not complete the expected packet");
        const auto hash=state.at("last_packet_sha256").get<std::string>();
        if(hash.size()!=64 || hash.find_first_not_of("0123456789abcdef")!=std::string::npos)
            throw std::runtime_error("observer lacks original packet hash");
        return state;
    }
    void queue(const ModelJson& request) {
        const auto text=request.dump();check(m_queue(m_writer,text.data(),text.size()),m_writer);
    }
    std::vector<uint8_t> write(const uint8_t* data,size_t bytes,int64_t pts) {
        const uint8_t* output=nullptr;size_t count=0;
        check(m_process(m_writer,data,bytes,pts,&output,&count),m_writer);
        if(!output || !count || count>32u*1024*1024)throw std::runtime_error("invalid complete-model output");
        return {output,output+count};
    }
    void finish(){check(m_finish(m_observer),m_observer);check(m_finish(m_writer),m_writer);}
    ModelJson writerReport() const {
        const auto text=m_report(m_writer);
        if(!text)throw std::runtime_error("missing complete-model report");
        return ModelJson::parse(text);
    }
};

enum class FilmGrainModelReadiness { Pending, Original, Replace, Reject };
struct FilmGrainModelDecision {
    FilmGrainModelReadiness state=FilmGrainModelReadiness::Pending;
    ModelJson model;
};

// Token owns caller metadata/storage (for example a shared bitstream). It is
// returned with the same packet, in order, after all required pictures and
// policy decisions are ready. The caller qualifies NVENC ordinal/PTS association
// before push. Keeping Original means preserving original encoded grain state;
// it is NOT a source-preserving fallback for a partially retained encode.
template<class Token> class FilmGrainModelBuffer {
public:
    struct Output { uint64_t ordinal;Token token;std::vector<uint8_t> bytes; };
private:
    struct Pending {
        uint64_t ordinal;Token token;int64_t pts;std::vector<uint8_t> bytes;
        ModelJson observation;std::vector<FilmGrainPictureBinding> bindings;
        bool reconstructed=false;
    };
    FilmGrainModelLibrary m_library;
    FilmGrainPacketIdentity m_identity;
    std::deque<Pending> m_pending;
    uint64_t m_bytes=0,m_peakBytes=0,m_received=0,m_released=0,m_totalLimit;
    uint64_t m_byteLimit;
    size_t m_packetLimit,m_peakPackets=0;
    bool m_failed=false,m_finished=false;
    std::string m_error;
    void ready() const {
        if(m_failed || m_finished)throw std::runtime_error(m_error.empty()?"model buffer failed or finished":m_error);
    }
    void fail(const std::exception& e) noexcept {m_failed=true;try{if(m_error.empty())m_error=e.what();}catch(...){} }
public:
    FilmGrainModelBuffer(const std::filesystem::path& library,uint64_t totalPackets,
                         unsigned forward=32,size_t packets=64,uint64_t bytes=256ull*1024*1024)
        :m_library(library,totalPackets),m_identity(forward,packets,bytes),m_totalLimit(totalPackets),
         m_byteLimit(bytes),m_packetLimit(packets) {
        if(!totalPackets || totalPackets>1000000 || !forward || forward>63 || !packets || packets>64 || !bytes || bytes>256ull*1024*1024)
            throw std::runtime_error("invalid complete-model buffer budget");
    }
    // Providers can return Pending even after reconstruction is available, e.g.
    // while an eight-picture measurement window is incomplete. Repeated calls
    // must be side-effect free; a successful decision is committed on release.
    template<class Provider> std::vector<Output> drain(Provider&& provider) {
        try {
            ready();std::vector<Output> outputs;
            while(!m_pending.empty() && m_pending.front().reconstructed) {
                auto& front=m_pending.front();std::vector<ModelJson> requests;
                bool waiting=false;
                for(size_t i=0;i<front.bindings.size();++i) {
                    const ModelJson& h=front.observation.at("last_headers").at(i);
                    if(h.at("show_existing").get<bool>())continue;
                    const auto decision=provider(front.bindings[i]);
                    if(decision.state==FilmGrainModelReadiness::Reject)throw std::runtime_error("complete-model policy rejected picture");
                    if(decision.state==FilmGrainModelReadiness::Pending){waiting=true;break;}
                    if(decision.state==FilmGrainModelReadiness::Original)continue;
                    if(decision.state!=FilmGrainModelReadiness::Replace)throw std::runtime_error("invalid model readiness state");
                    requests.push_back({{"schema",1},{"coded_index",front.bindings[i].coded},
                        {"expected_apply",h.at("apply")},{"expected_seed",h.at("seed")},
                        {"expected_order_hint",h.at("order_hint")},{"expected_pts",front.pts},
                        {"packet_sha256",front.observation.at("last_packet_sha256")},{"model",decision.model}});
                }
                if(waiting)break;
                if(requests.size()>16)throw std::runtime_error("too many model requests in packet");
                for(const auto& request:requests)m_library.queue(request);
                auto bytes=m_library.write(front.bytes.data(),front.bytes.size(),front.pts);
                outputs.push_back({front.ordinal,std::move(front.token),std::move(bytes)});
                m_bytes-=front.bytes.size();m_pending.pop_front();++m_released;
            }
            return outputs;
        }catch(const std::exception& e){fail(e);throw;}catch(...){m_failed=true;throw;}
    }
    template<class Provider> std::vector<Output> push(Token token,const uint8_t* data,size_t bytes,
            uint64_t receivedInput,int64_t pts,Provider&& provider,
            const std::vector<std::string>& expectedHashes={}) {
        try {
            ready();
            if(!data || !bytes || bytes>32u*1024*1024 || m_received>=m_totalLimit || m_pending.size()>=m_packetLimit || bytes>m_byteLimit-m_bytes)
                throw std::runtime_error("complete-model input/buffer budget exceeded");
            auto observation=m_library.observe(data,bytes,pts);std::vector<FilmGrainPacketHeader> headers;
            if(!expectedHashes.empty() && std::find(expectedHashes.begin(),expectedHashes.end(),observation.at("last_packet_sha256").get<std::string>())==expectedHashes.end())
                throw std::runtime_error("precomputed model packet hash mismatch");
            for(const auto& h:observation.at("last_headers"))headers.push_back({h.at("coded_index"),h.at("order_hint"),h.at("order_hint_bits"),h.at("refresh"),h.at("show_existing"),h.at("show"),h.at("showable")});
            auto identity=m_identity.observe(receivedInput,pts,bytes,headers);
            if(!identity.valid)throw std::runtime_error("complete-model packet identity rejected: "+std::to_string(int(identity.reason)));
            m_pending.push_back({m_received++,std::move(token),pts,{data,data+bytes},std::move(observation),std::move(identity.pictures),false});
            m_bytes+=bytes;m_peakBytes=std::max(m_peakBytes,m_bytes);m_peakPackets=std::max(m_peakPackets,m_pending.size());
            for(auto ordinal:identity.readyPackets) {
                const auto found=std::find_if(m_pending.begin(),m_pending.end(),[&](const auto& p){return p.ordinal==ordinal;});
                if(found==m_pending.end())throw std::runtime_error("missing reconstruction-ready packet");
                found->reconstructed=true;
            }
            return drain(std::forward<Provider>(provider));
        }catch(const std::exception& e){fail(e);throw;}catch(...){m_failed=true;throw;}
    }
    void finish() {
        try {
            if(m_finished && !m_failed)return;
            ready();
            if(!m_pending.empty() || !m_identity.finish() || m_received!=m_released)
                throw std::runtime_error("incomplete reconstructed/model output");
            m_library.finish();m_finished=true;
        }catch(const std::exception& e){fail(e);throw;}catch(...){m_failed=true;throw;}
    }
    const std::string& error() const{return m_error;}
    ModelJson report() const {
        return {{"complete",m_finished && !m_failed},{"failed",m_failed},{"error",m_error},
            {"received",m_received},{"released",m_released},{"pending_packets",m_pending.size()},
            {"pending_bytes",m_bytes},{"peak_packets",m_peakPackets},{"peak_bytes",m_peakBytes},
            {"writer",m_library.writerReport()}};
    }
};
} // namespace fgsmodel
