// Explicit experimental complete-model writer. Each context is one serial
// low-overhead AV1 stream; independent instances can run concurrently.
// No global FFmpeg callback, decoder, automatic admission or production hook.
#include <limits>
#include <map>
#include <memory>
#include <string>
#include "api.h"
#include "model.hpp"
using namespace fgsmodelwriter;
namespace {
constexpr size_t maxPacketBytes=32*1024*1024;
std::string hash(const uint8_t* data,size_t bytes) {
    AVSHA* ctx=av_sha_alloc();require(ctx,"hash allocation failed");
    if(av_sha_init(ctx,256)<0){av_free(ctx);throw std::runtime_error("hash init failed");}
    av_sha_update(ctx,data,bytes);uint8_t digest[32];av_sha_final(ctx,digest);av_free(ctx);
    constexpr char hex[]="0123456789abcdef";std::string result;
    for(auto b:digest){result+=hex[b>>4];result+=hex[b&15];}return result;
}
struct Request {
    unsigned beforeSeed,orderHint;bool beforeApply;int64_t pts;
    std::string packetHash;AV1RawFilmGrainParams grain;
};
struct Context {
    CodedBitstreamContext *reader=nullptr,*writer=nullptr;
    CodedBitstreamFragment fragment{};AVPacket* packet=nullptr;
    std::array<AV1RawFilmGrainParams,8> original{},changed{};
    std::array<bool,8> valid{};std::map<uint64_t,Request> requests;
    uint64_t limit=0,packets=0,coded=0,shown=0,modified=0,materialized=0;
    bool failed=false,finished=false;std::string error,report;
    std::vector<uint8_t> output;
    ~Context(){ff_cbs_fragment_free(&fragment);ff_cbs_close(&reader);ff_cbs_close(&writer);av_packet_free(&packet);}
    void initialize(uint64_t maxPackets) {
        require(maxPackets && maxPackets<=1000000,"packet limit out of range");limit=maxPackets;
        packet=av_packet_alloc();require(packet,"packet allocation failed");
        require(ff_cbs_init(&reader,AV_CODEC_ID_AV1,nullptr)>=0 && ff_cbs_init(&writer,AV_CODEC_ID_AV1,nullptr)>=0,"CBS initialization failed");
    }
    void ready(){require(!failed && !finished,"stream failed or finished");}
    void queue(const char* data,size_t bytes) {
        ready();require(data && bytes && bytes<=65536 && requests.size()<16,"request byte/count limit");
        const auto j=Json::parse(data,data+bytes);require(integer(j,"schema",1,1)==1,"request schema");
        const unsigned index=integer(j,"coded_index",0,1000000);require(index>=coded,"requested coded picture already processed");
        require(j.at("expected_apply").is_boolean(),"expected apply must be boolean");
        const auto& p=j.at("expected_pts");require(p.is_number_integer(),"expected PTS must be integer");
        // Avoid unsigned JSON narrowing into an apparently valid signed PTS.
        require(!p.is_number_unsigned() || p.get<uint64_t>()<=uint64_t(INT64_MAX),"expected PTS out of range");
        const auto h=j.at("packet_sha256").get<std::string>();require(h.size()==64 && h.find_first_not_of("0123456789abcdef")==std::string::npos,"packet hash required");
        Request r{unsigned(integer(j,"expected_seed",0,65535)),unsigned(integer(j,"expected_order_hint",0,255)),j.at("expected_apply").get<bool>(),p.get<int64_t>(),h,model(j.at("model"))};
        require(requests.emplace(index,std::move(r)).second,"duplicate coded picture");
    }
    int process(const uint8_t* data,size_t bytes,int64_t pts) {
        ready();require(data && bytes && bytes<=maxPacketBytes && packets<limit,"input packet/count limit");
        output.clear();require(av_new_packet(packet,int(bytes))>=0,"packet allocation failed");
        memcpy(packet->data,data,bytes);packet->pts=packet->dts=pts;
        require(ff_cbs_read_packet(reader,&fragment,packet)>=0,"CBS parse failed");
        bool packetChanged=false;std::string packetHash;
        for(int i=0;i<fragment.nb_units;++i) {
            auto& unit=fragment.units[i];
            require(unit.type!=AV1_OBU_REDUNDANT_FRAME_HEADER,"redundant headers unqualified");
            if(unit.type!=AV1_OBU_FRAME_HEADER && unit.type!=AV1_OBU_FRAME)continue;
            require(unit.content && ff_cbs_make_unit_writable(reader,&unit)>=0,"frame header not writable");
            auto* obu=static_cast<AV1RawOBU*>(unit.content);
            auto* h=unit.type==AV1_OBU_FRAME?&obu->obu.frame.header:&obu->obu.frame_header;
            require(!obu->header.spatial_id && !obu->header.temporal_id,"layered stream unqualified");
            AV1RawFilmGrainParams input{},result{};
            if(h->show_existing_frame) {
                const unsigned ref=h->frame_to_show_map_idx;require(ref<8 && valid[ref],"missing shown grain reference");
                input=original[ref];result=changed[ref];++shown;
            } else {
                input=h->film_grain;
                if(input.apply_grain && !input.update_grain) {
                    const unsigned ref=input.film_grain_params_ref_idx;require(ref<8 && valid[ref],"missing original grain reference");const auto seed=input.grain_seed;
                    input=original[ref];input.apply_grain=1;input.grain_seed=seed;input.update_grain=1;input.film_grain_params_ref_idx=0;
                    if(semantic(original[ref])!=semantic(changed[ref])){h->film_grain=input;packetChanged=true;++materialized;}
                }
                result=input;const auto found=requests.find(coded);
                if(found!=requests.end()) {
                    const auto& expected=found->second;const auto* state=static_cast<CodedBitstreamAV1Context*>(reader->priv_data);
                    require(state->sequence_header && state->sequence_header->film_grain_params_present && (h->show_frame || h->showable_frame),"sequence/frame cannot carry grain");
                    const auto& colour=state->sequence_header->color_config;
                    require(!colour.mono_chrome && colour.subsampling_x && colour.subsampling_y && state->bit_depth<=10,"unsupported grain layout");
                    if(packetHash.empty())packetHash=hash(data,bytes);
                    require(packetHash==expected.packetHash && pts==expected.pts && bool(input.apply_grain)==expected.beforeApply && (!input.apply_grain || input.grain_seed==expected.beforeSeed) && h->order_hint==expected.orderHint,"requested picture identity mismatch");
                    result=expected.grain;h->film_grain=result;packetChanged=true;++modified;requests.erase(found);
                }
                ++coded;
            }
            for(unsigned ref=0;ref<8;++ref)if(h->refresh_frame_flags&(1u<<ref)){original[ref]=input;changed[ref]=result;valid[ref]=true;}
        }
        require(ff_cbs_write_packet(writer,packet,&fragment)>=0,"CBS serialization failed");
        require(packet->size>0 && size_t(packet->size)<=maxPacketBytes,"serialized packet limit");
        if(packetChanged)output.assign(packet->data,packet->data+packet->size);
        else output.assign(data,data+bytes);
        ff_cbs_fragment_reset(&fragment);av_packet_unref(packet);++packets;return packetChanged?1:0;
    }
    void finish(){require(!failed,"stream failed");if(finished)return;ready();require(packets && coded && requests.empty(),"empty coded stream or missing requested picture");finished=true;}
    const char* describe() {
        report=Json{{"complete",finished && !failed},{"failed",failed},{"packets",packets},{"coded_pictures",coded},{"show_existing",shown},{"modified_models",modified},{"materialized_original_models",materialized},{"pending",requests.size()}}.dump();return report.c_str();
    }
    int fail(const std::exception& e) noexcept {
        failed=true;
        try{if(error.empty())error=e.what();}catch(...){}
        return -1;
    }
};
}
extern "C" unsigned fgs_av1_model_abi_version(){return 1;}
extern "C" void* fgs_av1_model_open(uint64_t limit) {
    try{auto c=std::make_unique<Context>();c->initialize(limit);return c.release();}catch(...){return nullptr;}
}
extern "C" void fgs_av1_model_close(void* p){delete static_cast<Context*>(p);}
extern "C" int fgs_av1_model_queue(void* p,const char* data,size_t bytes) {
    auto* c=static_cast<Context*>(p);if(!c)return -1;
    try{c->queue(data,bytes);return 0;}catch(const std::exception& e){return c->fail(e);}catch(...){c->failed=true;return -1;}
}
extern "C" int fgs_av1_model_process(void* p,const uint8_t* data,size_t bytes,int64_t pts,const uint8_t** out,size_t* count) {
    if(out)*out=nullptr;
    if(count)*count=0;
    auto* c=static_cast<Context*>(p);if(!c)return -1;
    try{require(out && count,"output pointers required");const int result=c->process(data,bytes,pts);*out=c->output.data();*count=c->output.size();return result;}
    catch(const std::exception& e){return c->fail(e);}catch(...){c->failed=true;return -1;}
}
extern "C" int fgs_av1_model_finish(void* p) {
    auto* c=static_cast<Context*>(p);if(!c)return -1;
    try{c->finish();return 0;}catch(const std::exception& e){return c->fail(e);}catch(...){c->failed=true;return -1;}
}
extern "C" const char* fgs_av1_model_error(void* p){auto* c=static_cast<Context*>(p);return c?c->error.c_str():"Missing model writer context";}
extern "C" const char* fgs_av1_model_report(void* p) {
    auto* c=static_cast<Context*>(p);if(!c)return nullptr;
    try{return c->describe();}catch(const std::exception& e){c->fail(e);return nullptr;}catch(...){c->failed=true;return nullptr;}
}
