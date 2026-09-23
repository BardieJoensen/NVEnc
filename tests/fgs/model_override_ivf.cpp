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
extern "C" {
#include "libavcodec/avcodec.h"
#include "libavcodec/cbs.h"
// This pinned internal C header names its AVClass pointer "class".
#define class av_class
#include "libavcodec/cbs_av1.h"
#undef class
#include "libavutil/sha.h"
}
using Json=nlohmann::json;
namespace {
void require(bool ok,const char* text) { if (!ok) throw std::runtime_error(text); }
int integer(const Json& j,const char* key,int low,int high) {
    const auto& v=j.at(key);require(v.is_number_integer(),"expected integer model field");
    const int64_t n=v.get<int64_t>();require(n>=low && n<=high,"model field out of range");return int(n);
}
AV1RawFilmGrainParams model(const Json& j) {
    AV1RawFilmGrainParams g{};
    require(j.at("apply").is_boolean(),"apply must be boolean");
    g.apply_grain=j.at("apply").get<bool>();
    if (!g.apply_grain) return g;
    g.update_grain=1;g.grain_seed=integer(j,"seed",0,65535);
    g.ar_coeff_lag=3;g.ar_coeff_shift_minus_6=integer(j,"ar_shift",6,9)-6;
    g.grain_scale_shift=integer(j,"grain_shift",0,3);
    g.grain_scaling_minus_8=integer(j,"scaling_shift",8,11)-8;
    g.overlap_flag=integer(j,"overlap",0,1);
    g.clip_to_restricted_range=integer(j,"restricted",0,1);
    const auto& curves=j.at("curves");require(curves.is_array() && curves.size()==3,"expected three curves");
    uint8_t* values[]={g.point_y_value,g.point_cb_value,g.point_cr_value};
    uint8_t* scales[]={g.point_y_scaling,g.point_cb_scaling,g.point_cr_scaling};
    uint8_t* counts[]={&g.num_y_points,&g.num_cb_points,&g.num_cr_points};
    for(unsigned c=0;c<3;++c) {
        require(curves[c].is_array() && curves[c].size()<=(c?10:14),"curve point budget");
        *counts[c]=uint8_t(curves[c].size());int previous=-1;
        for(size_t i=0;i<curves[c].size();++i) {
            const auto& point=curves[c][i];require(point.is_array() && point.size()==2 && point[0].is_number_integer() && point[1].is_number_integer(),"invalid point");
            const int64_t x=point[0].get<int64_t>(),y=point[1].get<int64_t>();
            require(x>previous && x<=255 && y>=0 && y<=255,"invalid curve ordering/value");
            values[c][i]=uint8_t(x);scales[c][i]=uint8_t(y);previous=int(x);
        }
    }
    require((g.num_y_points || (!g.num_cb_points && !g.num_cr_points)) && ((g.num_cb_points==0)==(g.num_cr_points==0)),"invalid 4:2:0 point counts");
    const auto& coeff=j.at("coefficients");require(coeff.is_array() && coeff.size()==3,"expected three coefficient arrays");
    uint8_t* dst[]={g.ar_coeffs_y_plus_128,g.ar_coeffs_cb_plus_128,g.ar_coeffs_cr_plus_128};
    for(unsigned c=0;c<3;++c) {
        require(coeff[c].is_array() && coeff[c].size()==(c?25:24),"wrong lag-three coefficient count");
        for(size_t i=0;i<coeff[c].size();++i) {
            require(coeff[c][i].is_number_integer(),"coefficient must be integer");
            const int64_t x=coeff[c][i].get<int64_t>();require(x>=-128 && x<=127,"coefficient out of range");dst[c][i]=uint8_t(x+128);
        }
    }
    // Explicit lookup used by the existing independent constant-curve oracle.
    // Wider lookup equations need their own model contract, not guessed fields.
    g.cb_mult=g.cr_mult=128;g.cb_luma_mult=g.cr_luma_mult=192;g.cb_offset=g.cr_offset=256;
    return g;
}
Json semantic(AV1RawFilmGrainParams g) {
    if (!g.apply_grain) return Json{{"apply",false}};
    Json curves=Json::array(),coeff=Json::array();
    const unsigned counts[]={g.num_y_points,g.num_cb_points,g.num_cr_points};
    const uint8_t* values[]={g.point_y_value,g.point_cb_value,g.point_cr_value};
    const uint8_t* scales[]={g.point_y_scaling,g.point_cb_scaling,g.point_cr_scaling};
    const uint8_t* taps[]={g.ar_coeffs_y_plus_128,g.ar_coeffs_cb_plus_128,g.ar_coeffs_cr_plus_128};
    for(unsigned c=0;c<3;++c) {
        Json points=Json::array(),a=Json::array();
        for(unsigned i=0;i<counts[c];++i)points.push_back({values[c][i],scales[c][i]});
        const unsigned n=2*g.ar_coeff_lag*(g.ar_coeff_lag+1)+(c && g.num_y_points?1:0);
        if(counts[c] || (c && g.chroma_scaling_from_luma))for(unsigned i=0;i<n;++i)a.push_back(int(taps[c][i])-128);
        curves.push_back(points);coeff.push_back(a);
    }
    return Json{{"apply",true},{"curves",curves},{"coefficients",coeff},{"from_luma",g.chroma_scaling_from_luma},
        {"lag",g.ar_coeff_lag},{"ar_shift",g.ar_coeff_shift_minus_6+6},{"grain_shift",g.grain_scale_shift},
        {"scaling_shift",g.grain_scaling_minus_8+8},{"overlap",g.overlap_flag},{"restricted",g.clip_to_restricted_range},
        {"cb_lookup",{g.cb_mult,g.cb_luma_mult,g.cb_offset}},{"cr_lookup",{g.cr_mult,g.cr_luma_mult,g.cr_offset}}};
}
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
        require(packets && overrides.empty() && (!le32(header+24) || packets==le32(header+24)),"missing requested picture or IVF packet count mismatch");
        const int closed=fclose(out);out=nullptr;require(closed==0,"output close failed");
        report.update({{"complete",true},{"packets",packets},{"coded_pictures",coded},{"show_existing",shown},{"modified_models",modified},{"materialized_original_models",materialized}});
        std::cout<<report.dump()<<'\n';result=0;
    } catch(const std::exception& e) {std::cerr<<"model experiment failed at packet "<<packets<<": "<<e.what()<<'\n';}
    if(in)fclose(in);
    if(out)fclose(out);
    if(result && created)remove(argv[2]);
    ff_cbs_fragment_free(&fragment);ff_cbs_close(&reader);ff_cbs_close(&writer);av_packet_free(&packet);return result;
}
