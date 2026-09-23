// Explicit finite output trial, nested in the reconstructed-picture diagnostic.
// Every model is supplied and every original packet/PTS is bound in advance.
// This is not automatic source eligibility or a production selection policy.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <fstream>
#include <set>
#include "NVEncFilmGrainModelBuffer.h"

struct NVEncFilmGrainModelConfig {
    using Json=nlohmann::json;
    struct Packet {int64_t pts;std::vector<std::string> hashes;};
    std::filesystem::path library;
    std::vector<Packet> packets;
    std::vector<Json> models;
    uint64_t readyAfter=0,maxBytes=256ull*1024*1024;
    size_t maxPackets=64;
    static uint64_t integer(const Json& j,const char* name,uint64_t low,uint64_t high) {
        const auto& value=j.at(name);
        if(!value.is_number_integer() || value<low || value>high)throw std::runtime_error(std::string("invalid model trial ")+name);
        return value.get<uint64_t>();
    }
    static NVEncFilmGrainModelConfig parse(const Json& j,const std::set<uint32_t>& captured) {
        NVEncFilmGrainModelConfig c;
        if(!j.is_object() || integer(j,"schema",1,1)!=1 || !j.at("packets").is_array()
            || j.at("packets").empty() || j.at("packets").size()>16 || !j.at("models").is_array()
            || j.at("models").size()!=j.at("packets").size() || captured.size()!=j.at("packets").size())
            throw std::runtime_error("model trial requires 1..16 complete packet/model/reconstruction entries");
        c.library=std::filesystem::u8path(j.at("library").get<std::string>());
        if(!c.library.is_absolute())throw std::runtime_error("model trial library must be absolute");
        if(j.contains("ready_after"))c.readyAfter=integer(j,"ready_after",0,j.at("packets").size()-1);
        if(j.contains("max_pending_packets"))c.maxPackets=integer(j,"max_pending_packets",1,64);
        if(j.contains("max_pending_bytes"))c.maxBytes=integer(j,"max_pending_bytes",1,256ull*1024*1024);
        for(size_t i=0;i<j.at("packets").size();++i) {
            const auto& row=j.at("packets").at(i);const auto& pts=row.at("pts");
            if(!captured.count(static_cast<uint32_t>(i)) || !pts.is_number_integer() || pts==INT64_MIN
                || (pts.is_number_unsigned() && pts.get<uint64_t>()>uint64_t(INT64_MAX)))
                throw std::runtime_error("model trial capture/PTS identity is invalid");
            const auto value=pts.get<int64_t>();
            if(i && value<=c.packets.back().pts)throw std::runtime_error("model trial clocks must increase");
            const auto& hashes=row.at("sha256");
            if(!hashes.is_array() || hashes.empty() || hashes.size()>2)throw std::runtime_error("model trial needs one or two exact original packet hashes");
            Packet packet{value,{}};
            for(const auto& hash:hashes) {
                const auto text=hash.get<std::string>();
                if(text.size()!=64 || text.find_first_not_of("0123456789abcdef")!=std::string::npos
                    || std::find(packet.hashes.begin(),packet.hashes.end(),text)!=packet.hashes.end())throw std::runtime_error("invalid/duplicate model trial packet hash");
                packet.hashes.push_back(text);
            }
            c.packets.push_back(std::move(packet));const auto& model=j.at("models").at(i);
            if(!model.is_null() && !model.is_object())throw std::runtime_error("model trial entry must be null or an explicit model");
            c.models.push_back(model);
        }
        return c;
    }
};

template<class Token> class NVEncFilmGrainModelProbe {
    using Json=nlohmann::json;
    using Buffer=fgsmodel::FilmGrainModelBuffer<Token>;
    NVEncFilmGrainModelConfig m_config;
    Buffer m_buffer;
    std::filesystem::path m_report;
    uint64_t m_received=0;
    bool m_failed=false,m_finished=false;
    std::string m_error;
    void status() {
        auto report=m_buffer.report();report["complete"]=m_finished && !m_failed && report.at("complete").template get<bool>();
        report["failed"]=m_failed || report.at("failed").template get<bool>();report["trial_error"]=m_error;
        report["expected_packets"]=m_config.packets.size();report["ready_after"]=m_config.readyAfter;
        auto temp=m_report;temp+=".tmp";
        {std::ofstream out(temp);out<<report.dump(2)<<'\n';out.flush();if(!out)throw std::runtime_error("model trial report write failed");}
        std::filesystem::rename(temp,m_report);
    }
public:
    NVEncFilmGrainModelProbe(NVEncFilmGrainModelConfig config,const std::filesystem::path& report)
        :m_config(std::move(config)),m_buffer(m_config.library,m_config.packets.size(),32,m_config.maxPackets,m_config.maxBytes),m_report(report){status();}
    std::vector<typename Buffer::Output> receive(Token token,const uint8_t* data,size_t bytes,uint64_t input,int64_t pts) {
        try {
            if(m_failed || m_finished || input!=m_received || input>=m_config.packets.size() || pts!=m_config.packets[input].pts)
                throw std::runtime_error("model trial callback identity mismatch");
            auto provider=[&](const fgsmodel::FilmGrainPictureBinding& binding) {
                if(binding.inputOrdinal>input || binding.inputOrdinal>=m_config.models.size())return fgsmodel::FilmGrainModelDecision{fgsmodel::FilmGrainModelReadiness::Reject,{}};
                if(input<m_config.readyAfter)return fgsmodel::FilmGrainModelDecision{};
                const auto& model=m_config.models[binding.inputOrdinal];
                return model.is_null()?fgsmodel::FilmGrainModelDecision{fgsmodel::FilmGrainModelReadiness::Original,{}}:fgsmodel::FilmGrainModelDecision{fgsmodel::FilmGrainModelReadiness::Replace,model};
            };
            auto output=m_buffer.push(std::move(token),data,bytes,input,pts,provider,m_config.packets[input].hashes);
            ++m_received;status();return output;
        }catch(const std::exception& e){fail(e.what());throw;}
    }
    void finish() {
        try {
            if(m_failed || m_received!=m_config.packets.size())throw std::runtime_error("model trial did not receive every expected packet");
            m_buffer.finish();m_finished=true;status();
        }catch(const std::exception& e){fail(e.what());throw;}
    }
    void fail(const std::string& error) noexcept {m_failed=true;try{if(m_error.empty())m_error=error;status();}catch(...){} }
};
