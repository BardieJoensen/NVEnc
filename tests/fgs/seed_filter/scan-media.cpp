// Read-only full-stream qualification. Corrects owned packet copies in memory;
// no media output is opened. A second context must find the result idempotent.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <vector>
#include "json.hpp"
extern "C" {
#include <libavformat/avformat.h>
#include <libavutil/sha.h>
#include <libavutil/mem.h>
}
using nlohmann::json;
static void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
template<class T> static T symbol(void* lib,const char* name){auto f=reinterpret_cast<T>(dlsym(lib,name));require(f!=nullptr,"Missing parser symbol");return f;}
static std::string finish_hash(AVSHA* hash){uint8_t bytes[32];av_sha_final(hash,bytes);char text[65];for(unsigned i=0;i<32;++i)snprintf(text+2*i,3,"%02x",bytes[i]);return text;}
int main(int argc,char** argv){
    json report={{"complete",false},{"mode","Read-only header parsing; no pixel decode or media writes"},{"changes",json::array()}};
    AVFormatContext* format=nullptr;AVPacket* packet=nullptr;void* lib=nullptr;void* first=nullptr;void* again=nullptr;
    void(*close_context)(void*)=nullptr;AVSHA *original=nullptr,*corrected=nullptr;
    const auto begin=std::chrono::steady_clock::now();
    try{
        require(argc==3,"usage: scan-media PARSER_LIBRARY AV1_MEDIA");
        lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);require(lib!=nullptr,"Cannot load parser library");
        require(symbol<unsigned(*)()>(lib,"fgs_av1_seed_abi_version")()==1,"Unsupported parser ABI");
        auto open_context=symbol<void*(*)(const uint8_t*,size_t)>(lib,"fgs_av1_seed_open");
        auto process=symbol<int(*)(void*,uint8_t*,size_t)>(lib,"fgs_av1_seed_process");
        auto error=symbol<const char*(*)(void*)>(lib,"fgs_av1_seed_error");
        close_context=symbol<void(*)(void*)>(lib,"fgs_av1_seed_close");
        require(avformat_open_input(&format,argv[2],nullptr,nullptr)>=0,"Cannot open input container");
        int stream=-1;
        for(unsigned i=0;i<format->nb_streams;++i)if(format->streams[i]->codecpar->codec_type==AVMEDIA_TYPE_VIDEO){stream=int(i);break;}
        require(stream>=0,"Missing video stream");const auto* params=format->streams[stream]->codecpar;
        require(params->codec_id==AV_CODEC_ID_AV1,"First video stream is not AV1");
        first=open_context(params->extradata,params->extradata_size);again=open_context(params->extradata,params->extradata_size);
        require(first && again,"Cannot initialize parser with container extradata");
        packet=av_packet_alloc();original=av_sha_alloc();corrected=av_sha_alloc();require(packet && original && corrected,"Allocation failed");
        require(av_sha_init(original,256)==0 && av_sha_init(corrected,256)==0,"Hash initialization failed");
        uint64_t packets=0,bytes=0,changed=0,changed_bits=0,other_packets=0,max_packet=0;double parser_seconds=0;
        std::vector<uint8_t> buffer;int ret;
        while((ret=av_read_frame(format,packet))>=0){
            if(packet->stream_index!=stream){++other_packets;av_packet_unref(packet);continue;}
            require(packet->size>0,"Empty video packet");max_packet=std::max(max_packet,uint64_t(packet->size));
            buffer.assign(packet->data,packet->data+packet->size);av_sha_update(original,packet->data,packet->size);
            const auto start=std::chrono::steady_clock::now();const int status=process(first,buffer.data(),buffer.size());
            parser_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            if(status<0)throw std::runtime_error(std::string("Parser failed: ")+error(first));
            require((status!=0)==(memcmp(buffer.data(),packet->data,buffer.size())!=0),"Incorrect change result");
            if(status){
                ++changed;uint64_t bits=0;
                for(size_t i=0;i<buffer.size();++i)bits+=__builtin_popcount(unsigned(buffer[i]^packet->data[i]));
                changed_bits+=bits;
                if(report["changes"].size()<1024)report["changes"].push_back({{"packet",packets},{"pts",packet->pts},{"dts",packet->dts},{"changed_bits",bits}});
            }
            av_sha_update(corrected,buffer.data(),buffer.size());
            const auto before=buffer;
            require(process(again,buffer.data(),buffer.size())==0 && buffer==before,"Correction is not idempotent");
            ++packets;bytes+=packet->size;av_packet_unref(packet);
        }
        require(ret==AVERROR_EOF && packets>0,"Incomplete demux or missing video packets");
        struct rusage usage{};getrusage(RUSAGE_SELF,&usage);
        const auto tb=format->streams[stream]->time_base;
        report.update({{"complete",true},{"video_packets",packets},{"video_bytes",bytes},{"other_packets",other_packets},
            {"changed_packets",changed},{"changed_bits",changed_bits},{"max_packet_bytes",max_packet},{"extradata_bytes",params->extradata_size},
            {"parser_seconds",parser_seconds},{"parser_us_per_packet",parser_seconds*1e6/packets},{"peak_rss_kib",usage.ru_maxrss},
            {"timebase",{tb.num,tb.den}},{"video_payload_sha256",finish_hash(original)},{"corrected_payload_sha256",finish_hash(corrected)},
            {"whole_stream_idempotent",true}});
    }catch(const std::exception& e){report["error"]=e.what();}
    if(close_context){close_context(first);close_context(again);}if(lib)dlclose(lib);
    av_packet_free(&packet);avformat_close_input(&format);av_free(original);av_free(corrected);
    report["wall_seconds"]=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
    puts(report.dump(2).c_str());return report["complete"].get<bool>()?0:1;
}
