// Manual proof tool, deliberately restricted to standalone AV1 IVF video.
// A serial FFmpeg trace_headers parser locates each field; this is not a
// production encoder hook or a Matroska/library repair program. Output is new.
#include "av1_seed_patch.h"
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>
#include <cerrno>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavcodec/bsf.h>
#include <libavutil/log.h>
}

namespace {
struct Field { size_t bit; uint16_t seed; };
const std::vector<uint8_t>* bytes = nullptr;
std::vector<fgsseed::Obu> obus;
std::vector<Field> fields;
size_t traced = 0;
unsigned types = 0, seeds = 0, active = 0;
bool expectedSeed = false;
std::string error;

void log_callback(void *, int level, const char *format, va_list args) {
    if (level > AV_LOG_TRACE) return;
    char line[2048];
    const int len = vsnprintf(line,sizeof(line),format,args);
    if (level <= AV_LOG_ERROR || len < 0 || size_t(len) >= sizeof(line)) {
        if (error.empty()) error = len < 0 ? "invalid parser log" : line;
        return;
    }
    if (!bytes) return;
    if (!strcmp(line,"OBU header\n")) {
        if (expectedSeed) error = "active grain missing its seed field";
        expectedSeed = false;
        if (++traced > obus.size()) error = "extra parser OBU";
        return;
    }
    size_t bit = 0;
    unsigned value = 0;
    char name[100]{}, bits[100]{};
    if (sscanf(line,"%zu %99s %99s = %u",&bit,name,bits,&value) != 4) return;
    if (!traced || traced > obus.size()) { error = "field without matching OBU"; return; }
    const auto& obu = obus[traced-1];
    if (!strcmp(name,"obu_type")) {
        ++types;
        if (bit != 1 || value != obu.type) error = "OBU type mismatch";
    } else if (!strcmp(name,"obu_size")) {
        if (value != obu.bytes-obu.headerBytes) error = "OBU size mismatch";
    } else if (!strcmp(name,"apply_grain")) {
        if (value > 1 || expectedSeed) error = "invalid/repeated grain flag";
        expectedSeed = value == 1;
        active += expectedSeed;
    } else if (!strcmp(name,"grain_seed")) {
        uint16_t read = 0;
        if (!expectedSeed || (obu.type != 3 && obu.type != 6 && obu.type != 7) ||
            strlen(bits) != 16 || value > 65535 || bit < obu.headerBytes*8 ||
            !fgsseed::read16(bytes->data()+obu.offset,obu.bytes,bit,read) || read != value) {
            error = "grain seed position/value mismatch"; return;
        }
        expectedSeed = false;
        ++seeds;
        const size_t absolute = obu.offset*8+bit;
        if (!fields.empty() && absolute < fields.back().bit+16) {
            error = "repeated/overlapping grain seed"; return;
        }
        fields.push_back({absolute,read});
    }
}

unsigned le16(const uint8_t *p) { return p[0] | unsigned(p[1])<<8; }
uint32_t le32(const uint8_t *p) { return le16(p) | uint32_t(le16(p+2))<<16; }
uint64_t le64(const uint8_t *p) { return le32(p) | uint64_t(le32(p+4))<<32; }
void require(bool condition, const char *message) { if (!condition) throw std::runtime_error(message); }
void write(FILE *f, const void *p, size_t n) { require(fwrite(p,1,n,f)==n,"output write failed"); }
}

int main(int argc,char **argv) {
    if (argc != 3) { fprintf(stderr,"usage: seed_patch_ivf INPUT.ivf NEW_OUTPUT.ivf\n"); return 2; }
    FILE *in=nullptr,*out=nullptr;
    bool created=false;
    AVBSFContext *filter=nullptr;
    AVPacket *packet=av_packet_alloc(),*decoded=av_packet_alloc();
    uint64_t packets=0,patched=0,totalSeeds=0;
    av_log_set_level(AV_LOG_TRACE);
    av_log_set_callback(log_callback);
    int result=2;
    try {
        require(packet && decoded,"packet allocation failed");
        in=fopen(argv[1],"rb"); require(in,"cannot open input");
        uint8_t header[32];
        require(fread(header,1,32,in)==32,"short IVF header");
        require(!memcmp(header,"DKIF",4) && le16(header+4)==0 && le16(header+6)==32 &&
            !memcmp(header+8,"AV01",4) && le16(header+12) && le16(header+14) &&
            le32(header+16) && le32(header+20),"expected version-0 32-byte AV1 IVF header");
        require(av_bsf_alloc(av_bsf_get_by_name("trace_headers"),&filter)>=0,"missing trace_headers");
        filter->par_in->codec_type=AVMEDIA_TYPE_VIDEO;
        filter->par_in->codec_id=AV_CODEC_ID_AV1;
        filter->par_in->width=int(le16(header+12));
        filter->par_in->height=int(le16(header+14));
        require(le32(header+16)<=INT32_MAX && le32(header+20)<=INT32_MAX,"invalid time base");
        filter->time_base_in={int(le32(header+20)),int(le32(header+16))};
        require(av_bsf_init(filter)>=0 && error.empty(),"cannot initialize parser");
        out=fopen(argv[2],"wbx"); require(out,"output exists or cannot be created"); created=true;
        write(out,header,32);
        for (;;) {
            uint8_t fh[12];
            const size_t n=fread(fh,1,12,in);
            if (!n && feof(in) && !ferror(in)) break;
            require(n==12,"short IVF frame header/read error");
            const uint32_t size=le32(fh);
            require(size && size<=32*1024*1024,"empty/oversized IVF packet");
            require(le64(fh+4)<=INT64_MAX,"IVF timestamp exceeds parser range");
            std::vector<uint8_t> data(size);
            require(fread(data.data(),1,size,in)==size,"short IVF frame");
            require(fgsseed::split_obus(data.data(),data.size(),obus),"unsupported/malformed OBU packet");
            traced=0; types=seeds=active=0; expectedSeed=false; fields.clear(); error.clear(); bytes=&data;
            require(av_new_packet(packet,int(size))>=0,"packet allocation failed");
            memcpy(packet->data,data.data(),size);
            packet->pts=packet->dts=int64_t(le64(fh+4));
            require(av_bsf_send_packet(filter,packet)>=0,"AV1 parser rejected packet");
            require(av_bsf_receive_packet(filter,decoded)>=0,"missing parser packet");
            require(error.empty(),"AV1 trace validation failed");
            require(!expectedSeed && active==seeds,"missing active-grain seed fields");
            require(traced==obus.size() && types==obus.size(),"parser did not visit every OBU");
            require(decoded->size==int(size) && !memcmp(decoded->data,data.data(),size),"parser altered packet");
            av_packet_unref(decoded);
            require(av_bsf_receive_packet(filter,decoded)==AVERROR(EAGAIN),"extra parser packet");
            bytes=nullptr;
            for (const auto& field : fields) {
                const auto next=fgsseed::replacement(field.seed);
                if (next==field.seed) continue;
                require(fgsseed::patch16(data.data(),data.size(),field.bit,field.seed),"seed patch mismatch");
                printf("{\"packet\":%llu,\"timestamp\":%llu,\"bit\":%zu,\"before\":%u,\"after\":%u}\n",
                    (unsigned long long)packets,(unsigned long long)le64(fh+4),field.bit,field.seed,next);
                ++patched;
            }
            write(out,fh,12); write(out,data.data(),size);
            ++packets; totalSeeds+=seeds;
        }
        require(packets && (!le32(header+24) || packets==le32(header+24)),"IVF packet count mismatch");
        require(av_bsf_send_packet(filter,nullptr)>=0 && av_bsf_receive_packet(filter,decoded)==AVERROR_EOF,
            "unexpected parser flush");
        require(error.empty(),"parser reported an error");
        const int closeStatus=fclose(out); out=nullptr;
        require(closeStatus==0,"output close failed");
        printf("{\"complete\":true,\"packets\":%llu,\"grain_seeds\":%llu,\"patched\":%llu,\"avcodec_version\":%u}\n",
            (unsigned long long)packets,(unsigned long long)totalSeeds,(unsigned long long)patched,avcodec_version());
        result=0;
    } catch (const std::exception& e) {
        fprintf(stderr,"seed experiment failed at packet %llu: %s; %s\n",
            (unsigned long long)packets,e.what(),error.c_str());
    }
    bytes=nullptr;
    if (in) fclose(in);
    if (out) fclose(out);
    if (result && created) remove(argv[2]);
    av_packet_free(&packet); av_packet_free(&decoded); av_bsf_free(&filter);
    av_log_set_callback(av_log_default_callback);
    return result;
}
