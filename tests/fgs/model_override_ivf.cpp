// Manual compressed-base model experiment. Link only to the pinned, private
// FFmpeg CBS build used by tests/fgs/seed_filter. No encoder/library call sites.
// MIT license for this adapter; FFmpeg remains LGPL-2.1-or-later.
#include <array>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <vector>
#include "json.hpp"
#include "model_filter/model.hpp"
using Json=nlohmann::json;
namespace {
using namespace fgsmodelwriter;
unsigned le16(const uint8_t* p){return p[0]|unsigned(p[1])<<8;}
uint32_t le32(const uint8_t* p){return le16(p)|uint32_t(le16(p+2))<<16;}
uint64_t le64(const uint8_t* p){return le32(p)|uint64_t(le32(p+4))<<32;}
void put32(uint8_t* p,uint32_t n){for(unsigned i=0;i<4;++i)p[i]=uint8_t(n>>(8*i));}
void write(FILE* f,const void* data,size_t bytes){require(fwrite(data,1,bytes,f)==bytes,"output write failed");}
std::string sourceHash(FILE* file) {
    AVSHA* context=av_sha_alloc();require(context,"hash allocation failed");
    const int initialized=av_sha_init(context,256);
    if(initialized<0){av_free(context);throw std::runtime_error("hash initialization failed");}
    std::array<uint8_t,65536> data{};size_t bytes;
    while((bytes=fread(data.data(),1,data.size(),file))!=0)av_sha_update(context,data.data(),bytes);
    std::array<uint8_t,32> digest{};av_sha_final(context,digest.data());av_free(context);
    require(!ferror(file) && fseek(file,0,SEEK_SET)==0,"source hash read/rewind failed");
    constexpr char hex[]="0123456789abcdef";std::string result;
    for(const auto v:digest){result+=hex[v>>4];result+=hex[v&15];}return result;
}
struct Override { unsigned beforeSeed,orderHint; bool beforeApply; AV1RawFilmGrainParams grain; };
}
int main(int argc,char** argv) {
    if(argc!=4){std::cerr<<"usage: model_override_ivf INPUT.ivf NEW_OUTPUT.ivf MANIFEST.json\n";return 2;}
    FILE* in=nullptr;FILE* out=nullptr;bool created=false;
    CodedBitstreamContext *reader=nullptr,*writer=nullptr;CodedBitstreamFragment fragment{};
    AVPacket* packet=av_packet_alloc();uint64_t packets=0,coded=0,shown=0,modified=0,materialized=0;
    Json report={{"complete",false},{"headers",Json::array()}};int result=2;
    try {
        require(packet,"packet allocation failed");
        require(std::filesystem::file_size(argv[3])<=65536,"manifest too large");
        Json manifest;std::ifstream(argv[3])>>manifest;
        require(integer(manifest,"schema",1,1)==1,"manifest schema");
        const unsigned maxPackets=integer(manifest,"max_packets",1,1000000);
        const auto& items=manifest.at("models");require(items.is_array() && items.size()<=16,"model budget");
        std::map<uint64_t,Override> overrides;
        for(const auto& j:items) {
            const unsigned index=integer(j,"coded_index",0,1000000);
            require(j.at("expected_apply").is_boolean(),"expected apply must be boolean");
            Override v{unsigned(integer(j,"expected_seed",0,65535)),unsigned(integer(j,"expected_order_hint",0,255)),j.at("expected_apply").get<bool>(),model(j.at("model"))};
            require(overrides.emplace(index,v).second,"duplicate coded picture");
        }
        std::array<AV1RawFilmGrainParams,8> original{},changed{};std::array<bool,8> valid{};
        in=fopen(argv[1],"rb");require(in,"input open failed");uint8_t header[32];
        if(!overrides.empty() || manifest.contains("source_sha256")) {
            const auto& expected=manifest.at("source_sha256");require(expected.is_string(),"source hash required for model overrides");
            const auto hash=expected.get<std::string>();require(hash.size()==64 && hash==sourceHash(in),"source hash mismatch");
        }
        require(fread(header,1,32,in)==32 && !memcmp(header,"DKIF",4) && le16(header+4)==0 && le16(header+6)==32 && !memcmp(header+8,"AV01",4) && le16(header+12) && le16(header+14) && le32(header+16) && le32(header+20),"invalid AV1 IVF header");
        require(ff_cbs_init(&reader,AV_CODEC_ID_AV1,nullptr)>=0 && ff_cbs_init(&writer,AV_CODEC_ID_AV1,nullptr)>=0,"CBS initialization failed");
        out=fopen(argv[2],"wbx");require(out,"output already exists or open failed");created=true;write(out,header,32);
        for(;;) {
            uint8_t fh[12];const size_t n=fread(fh,1,12,in);
            if(!n && feof(in) && !ferror(in))break;
            require(n==12 && packets<maxPackets,"short packet or packet budget exceeded");
            const uint32_t bytes=le32(fh);require(bytes && bytes<=32*1024*1024 && le64(fh+4)<=INT64_MAX,"invalid packet length/timestamp");
            std::vector<uint8_t> originalPacket(bytes);require(fread(originalPacket.data(),1,bytes,in)==bytes,"short packet");
            require(av_new_packet(packet,int(bytes))>=0,"packet allocation failed");memcpy(packet->data,originalPacket.data(),bytes);packet->pts=packet->dts=int64_t(le64(fh+4));
            require(ff_cbs_read_packet(reader,&fragment,packet)>=0,"CBS parse failed");bool packetChanged=false;
            for(int i=0;i<fragment.nb_units;++i) {
                auto& unit=fragment.units[i];
                require(unit.type!=AV1_OBU_REDUNDANT_FRAME_HEADER,"redundant headers require separate qualification");
                if(unit.type!=AV1_OBU_FRAME_HEADER && unit.type!=AV1_OBU_FRAME)continue;
                require(unit.content && ff_cbs_make_unit_writable(reader,&unit)>=0,"frame header not writable");
                auto* obu=static_cast<AV1RawOBU*>(unit.content);auto* h=unit.type==AV1_OBU_FRAME?&obu->obu.frame.header:&obu->obu.frame_header;
                require(!obu->header.spatial_id && !obu->header.temporal_id,"layered stream requires separate qualification");
                AV1RawFilmGrainParams input{},output{};
                if(h->show_existing_frame) {
                    const unsigned ref=h->frame_to_show_map_idx;require(ref<8 && valid[ref],"missing shown grain reference");input=original[ref];output=changed[ref];++shown;
                } else {
                    input=h->film_grain;
                    if(input.apply_grain && !input.update_grain) {
                        const unsigned ref=input.film_grain_params_ref_idx;require(ref<8 && valid[ref],"missing original grain reference");const auto seed=input.grain_seed;
                        input=original[ref];input.apply_grain=1;input.grain_seed=seed;input.update_grain=1;input.film_grain_params_ref_idx=0;
                        // A changed reference must never silently replace the
                        // original model of a later, unselected coded picture.
                        if(semantic(original[ref])!=semantic(changed[ref])) {h->film_grain=input;packetChanged=true;++materialized;}
                    }
                    output=input;const auto found=overrides.find(coded);
                    if(found!=overrides.end()) {
                        const auto& expected=found->second;const auto* state=static_cast<CodedBitstreamAV1Context*>(reader->priv_data);
                        require(state->sequence_header && state->sequence_header->film_grain_params_present && (h->show_frame || h->showable_frame),"sequence/frame cannot carry grain");
                        const auto& colour=state->sequence_header->color_config;
                        require(!colour.mono_chrome && colour.subsampling_x && colour.subsampling_y && state->bit_depth<=10,"unsupported grain layout");
                        require(bool(input.apply_grain)==expected.beforeApply && (!input.apply_grain || input.grain_seed==expected.beforeSeed) && h->order_hint==expected.orderHint,"requested picture identity mismatch");
                        output=expected.grain;h->film_grain=output;packetChanged=true;++modified;overrides.erase(found);
                    }
                    if(report["headers"].size()<4096)report["headers"].push_back({{"packet",packets},{"coded_index",coded},{"pts",packet->pts},{"order_hint",h->order_hint},{"show",h->show_frame},{"apply",input.apply_grain},{"seed",input.grain_seed},{"output_seed",output.grain_seed},{"refresh",h->refresh_frame_flags}});
                    ++coded;
                }
                for(unsigned ref=0;ref<8;++ref)if(h->refresh_frame_flags&(1u<<ref)){original[ref]=input;changed[ref]=output;valid[ref]=true;}
            }
            // Independent read/write contexts retain their own syntax state.
            // Exercise serialization even for a no-op, but preserve no-op bytes.
            require(ff_cbs_write_packet(writer,packet,&fragment)>=0,"CBS serialization failed");
            require(packet->size>0 && packet->size<=32*1024*1024,"serialized packet budget");
            if(packetChanged){put32(fh,uint32_t(packet->size));write(out,fh,12);write(out,packet->data,packet->size);}
            else {write(out,fh,12);write(out,originalPacket.data(),originalPacket.size());}
            ff_cbs_fragment_reset(&fragment);av_packet_unref(packet);++packets;
        }
        require(packets && coded && overrides.empty() && (!le32(header+24) || packets==le32(header+24)),"empty coded stream, missing requested picture or IVF packet count mismatch");
        const int closed=fclose(out);out=nullptr;require(closed==0,"output close failed");
        report.update({{"complete",true},{"packets",packets},{"coded_pictures",coded},{"show_existing",shown},{"modified_models",modified},{"materialized_original_models",materialized}});
        std::cout<<report.dump()<<'\n';result=0;
    } catch(const std::exception& e) {std::cerr<<"model experiment failed at packet "<<packets<<": "<<e.what()<<'\n';}
    if(in)fclose(in);
    if(out)fclose(out);
    if(result && created)remove(argv[2]);
    ff_cbs_fragment_free(&fragment);ff_cbs_close(&reader);ff_cbs_close(&writer);av_packet_free(&packet);return result;
}
