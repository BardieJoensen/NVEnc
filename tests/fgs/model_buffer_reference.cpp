// Manual CPU integration control. Models are supplied, not automatically admitted.
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include "NVEncFilmGrainModelBuffer.h"
using namespace fgsmodel;
using Json=nlohmann::json;
using Buffer=FilmGrainModelBuffer<Json>;
uint64_t little(const uint8_t* p,unsigned bytes) {
    uint64_t out=0;for(unsigned i=0;i<bytes;++i)out|=uint64_t(p[i])<<(i*8);return out;
}
void append(std::vector<uint8_t>& out,uint64_t value,unsigned bytes) {
    for(unsigned i=0;i<bytes;++i)out.push_back(uint8_t(value>>(i*8)));
}
int main() {
    std::unique_ptr<Buffer> buffer;Json result={{"complete",false},{"timeline",Json::array()}};
    try {
        Json config;std::cin>>config;
        const auto input=std::filesystem::u8path(config.at("input").get<std::string>());
        const auto output=std::filesystem::u8path(config.at("output").get<std::string>());
        if(std::filesystem::exists(output) || std::filesystem::file_size(input)>64u*1024*1024)throw std::runtime_error("invalid input/output path or budget");
        std::ifstream file(input,std::ios::binary);std::vector<uint8_t> raw{std::istreambuf_iterator<char>(file),{}};
        if(raw.size()<32 || std::memcmp(raw.data(),"DKIF",4))throw std::runtime_error("invalid IVF input");
        std::vector<std::pair<int64_t,std::vector<uint8_t>>> packets;
        for(size_t pos=32;pos<raw.size();) {
            if(raw.size()-pos<12)throw std::runtime_error("truncated IVF header");
            auto bytes=little(raw.data()+pos,4),pts=little(raw.data()+pos+4,8);pos+=12;
            if(!bytes || bytes>raw.size()-pos || pts>INT64_MAX)throw std::runtime_error("invalid IVF packet");
            packets.push_back({int64_t(pts),{raw.begin()+pos,raw.begin()+pos+bytes}});pos+=bytes;
        }
        std::map<uint64_t,Json> models;
        for(const auto& row:config.at("models")) {
            const auto id=row.at("input_ordinal").get<uint64_t>();
            if(!models.emplace(id,row.at("model")).second || id>=packets.size())throw std::runtime_error("invalid model picture");
        }
        buffer=std::make_unique<Buffer>(std::filesystem::u8path(config.at("library").get<std::string>()),config.value("total_packets",1000000ull),config.value("max_forward",32u),config.value("max_packets",64u),config.value("max_bytes",256ull*1024*1024));
        uint64_t received=0,released=0;std::vector<uint8_t> bytes(raw.begin(),raw.begin()+32);
        auto provider=[&](const FilmGrainPictureBinding& binding) {
            if(binding.inputOrdinal>received)throw std::runtime_error("provider called before reconstruction arrived");
            if(config.value("reject_input",uint64_t(-1))==binding.inputOrdinal)return FilmGrainModelDecision{FilmGrainModelReadiness::Reject,{}};
            if(config.value("pending_forever",false) || received<config.value("ready_after",uint64_t(0)))return FilmGrainModelDecision{};
            const auto found=models.find(binding.inputOrdinal);
            return found==models.end()?FilmGrainModelDecision{FilmGrainModelReadiness::Original,{}}:FilmGrainModelDecision{FilmGrainModelReadiness::Replace,found->second};
        };
        auto metadata=[&](uint64_t id){return Json{{"ordinal",id},{"pts",packets.at(id).first},{"dts",int64_t(id)-3},{"duration",id+1},{"sentinel",std::string(5,'x')}};};
        auto consume=[&](std::vector<Buffer::Output> out) {
            for(auto& packet:out) {
                if(packet.ordinal!=released || packet.token!=metadata(released))throw std::runtime_error("packet metadata/order changed");
                append(bytes,packet.bytes.size(),4);append(bytes,uint64_t(packet.token.at("pts").get<int64_t>()),8);bytes.insert(bytes.end(),packet.bytes.begin(),packet.bytes.end());++released;
            }
        };
        const auto count=std::min(packets.size(),config.value("process_packets",packets.size()));
        for(size_t i=0;i<count;++i) {
            received=i;auto& packet=packets[i];auto pts=packet.first;
            uint64_t input=config.contains("receive_ordinals")?config.at("receive_ordinals").at(i).get<uint64_t>():i;
            if(config.value("bad_pts_at",size_t(-1))==i)pts=INT64_MIN;
            const auto hashes=config.contains("expected_hashes")?config.at("expected_hashes").at(i).get<std::vector<std::string>>():std::vector<std::string>{};
            consume(buffer->push(metadata(i),packet.second.data(),packet.second.size(),input,pts,provider,hashes));
            result["timeline"].push_back({{"received",i},{"released",released},{"status",buffer->report()}});
        }
        consume(buffer->drain(provider));buffer->finish();buffer->finish();
        if(released!=packets.size())throw std::runtime_error("incomplete source packets");
        if(config.value("push_after_finish",false)) {
            const auto& packet=packets.front();buffer->push(metadata(0),packet.second.data(),packet.second.size(),0,packet.first,provider);
            throw std::runtime_error("after-finish push accepted");
        }
        std::ofstream destination(output,std::ios::binary);destination.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());destination.flush();
        if(!destination)throw std::runtime_error("output write failed");
        result["complete"]=true;result["status"]=buffer->report();std::cout<<result.dump()<<'\n';return 0;
    }catch(const std::exception& e) {
        result["error"]=e.what();
        if(buffer){
            try{result["status"]=buffer->report();}catch(...) {result["report_failed"]=true;}
            if(result.contains("status") && result["status"].value("failed",false)) {
                bool terminal=false;try{buffer->finish();}catch(const std::exception&){terminal=true;}
                result["finish_remains_failed"]=terminal;
            }
        }
        std::cout<<result.dump()<<'\n';return 1;
    }
}
