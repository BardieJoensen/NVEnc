// Read displayed AV1 grain state through FFmpeg's header parser, without
// decoding pixels. Header transitions are review candidates, not damage scores.
#include <algorithm>
#include <array>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/bsf.h>
#include <libavutil/log.h>
}
#include "av1_scan_packet.h"

namespace {
struct Grain { int apply=0, shift=0; std::array<int,3> scaling{}; };
struct Picture { bool valid=false; int type=-1; Grain grain; };
struct Header {
    bool active=false;
    int existing=-1, existingIndex=-1, type=-1, show=-1, showable=-1;
    int refresh=-1, apply=-1, update=1, grainIndex=-1;
    Grain grain;
};
Header current;
std::array<Picture,8> refs;
int grainPresent=-1, errors=0;
int64_t pts=AV_NOPTS_VALUE, previous=AV_NOPTS_VALUE, displayed=0, packets=0, headers=0;
AVRational timeBase{1,1000};

void error(const char *message) {
    if (++errors==1) std::fprintf(stderr,"grain transitions: %s\n",message);
}

void finish() {
    if (!current.active) return;
    const Header h=current; current=Header(); ++headers;
    if (errors) return;
    Picture picture;
    if (h.existing==1) {
        if (h.existingIndex<0 || h.existingIndex>=8 || !refs[h.existingIndex].valid) {
            error("unknown displayed reference"); return;
        }
        picture=refs[h.existingIndex];
        if (picture.type==0) refs.fill(picture);
    } else if (h.existing==0) {
        const int apply=h.apply>=0 ? h.apply : grainPresent==0 || (h.show==0 && h.showable==0) ? 0 : -1;
        const bool refreshAll=(h.type==0 && h.show==1) || h.type==3;
        if (apply<0 || h.type<0 || h.show<0 || (h.refresh<0 && !refreshAll)) {
            error("incomplete frame header"); return;
        }
        Grain grain;
        if (apply && h.update==0) {
            if (h.grainIndex<0 || h.grainIndex>=8 || !refs[h.grainIndex].valid || !refs[h.grainIndex].grain.apply) {
                error("unknown grain reference"); return;
            }
            grain=refs[h.grainIndex].grain;
        } else if (apply) { grain=h.grain; grain.apply=1; }
        picture={true,h.type,grain};
        const int refresh=refreshAll ? 255 : h.refresh;
        for (int i=0;i<8;++i) if (refresh & (1<<i)) refs[i]=picture;
    } else { error("missing show-existing flag"); return; }
    if (h.existing==1 || h.show==1) {
        if (pts==AV_NOPTS_VALUE || (previous!=AV_NOPTS_VALUE && pts<=previous)) {
            error("ambiguous displayed timestamps"); return;
        }
        previous=pts;
        const auto& g=picture.grain;
        const int effective=g.apply && *std::max_element(g.scaling.begin(),g.scaling.end())>0;
        std::printf("%lld,%lld,%.6f,%d,%d,%d,%d,%d,%d,%d\n",
            static_cast<long long>(displayed++),static_cast<long long>(av_rescale_q(pts,timeBase,{1,1000})),
            pts*av_q2d(timeBase),h.existing,g.apply,effective,g.scaling[0],g.scaling[1],g.scaling[2],g.shift);
    }
}

void trace(void*,int level,const char *fmt,va_list args) {
    char line[2048];std::vsnprintf(line,sizeof(line),fmt,args);
    if (level<=AV_LOG_ERROR || std::strstr(line,"File ended prematurely")) { error(line); return; }
    if (std::strstr(line,"Frame Header")) { finish(); current.active=true; return; }
    const char *eq=std::strrchr(line,'=');if (!eq) return;
    unsigned bit;char field[100];
    if (std::sscanf(line,"%u %99s",&bit,field)!=2) return;
    const int value=static_cast<int>(std::strtol(eq+1,nullptr,10));
    if (!std::strcmp(field,"film_grain_params_present")) { grainPresent=value; return; }
    if (!current.active) return;
    if (!std::strcmp(field,"show_existing_frame")) current.existing=value;
    else if (!std::strcmp(field,"frame_to_show_map_idx")) current.existingIndex=value;
    else if (!std::strcmp(field,"frame_type")) current.type=value;
    else if (!std::strcmp(field,"show_frame")) current.show=value;
    else if (!std::strcmp(field,"showable_frame")) current.showable=value;
    else if (!std::strcmp(field,"refresh_frame_flags")) current.refresh=value;
    else if (!std::strcmp(field,"apply_grain")) current.apply=value;
    else if (!std::strcmp(field,"update_grain")) current.update=value;
    else if (!std::strcmp(field,"film_grain_params_ref_idx")) current.grainIndex=value;
    else if (!std::strcmp(field,"grain_scaling_minus_8")) current.grain.shift=value+8;
    else {
        int index;
        for (int c=0;c<3;++c) {
            const char *pattern=c==0 ? "point_y_scaling[%d]" : c==1 ? "point_cb_scaling[%d]" : "point_cr_scaling[%d]";
            if (std::sscanf(field,pattern,&index)==1) current.grain.scaling[c]=std::max(current.grain.scaling[c],value);
        }
    }
}
}

int main(int argc,char **argv) {
    if (argc!=2) { std::fprintf(stderr,"usage: grain_transitions FILE > displayed-grain.csv\n");return 2; }
    av_log_set_callback(trace);av_log_set_level(AV_LOG_TRACE);
    AVFormatContext *format=nullptr;AVBSFContext *filter=nullptr;
    AVPacket *packet=av_packet_alloc(),*output=av_packet_alloc();
    if (!packet || !output) {
        av_packet_free(&packet);av_packet_free(&output);
        std::fprintf(stderr,"grain transitions: packet allocation failed\n");return 1;
    }
    int status=avformat_open_input(&format,argv[1],nullptr,nullptr),video=-1;
    if (status>=0) {
        for (unsigned i=0;i<format->nb_streams;++i) if (format->streams[i]->codecpar->codec_type==AVMEDIA_TYPE_VIDEO) {
            if (format->streams[i]->codecpar->codec_id==AV_CODEC_ID_AV1) video=i;
            break;
        }
        if (video<0) status=AVERROR_INVALIDDATA;
    }
    const AVBitStreamFilter *parser=av_bsf_get_by_name("trace_headers");
    if (status>=0) status=parser ? av_bsf_alloc(parser,&filter) : AVERROR_BSF_NOT_FOUND;
    if (status>=0) {
        status=avcodec_parameters_copy(filter->par_in,format->streams[video]->codecpar);
        filter->time_base_in=timeBase=format->streams[video]->time_base;
        if (status>=0) status=av_bsf_init(filter);
    }
    std::puts("frame,pts_ms,seconds,show_existing,apply_grain,effective_grain,max_y_scaling,max_cb_scaling,max_cr_scaling,scaling_shift");
    unsigned skipped=0;bool eof=false;
    if (status>=0) while ((status=av_read_frame(format,packet))>=0) {
        if (packet->stream_index!=video) { av_packet_unref(packet);continue; }
        pts=packet->pts;++packets;
        status=av_packet_make_writable(packet);
        if (status<0) break;
        size_t size=packet->size;bool sequence=false;
        if (!prepare_av1_scan_packet(packet->data,size,sequence,skipped)) { status=AVERROR_INVALIDDATA;break; }
        av_shrink_packet(packet,static_cast<int>(size));
        status=av_bsf_send_packet(filter,packet);
        if (status<0) break;
        while ((status=av_bsf_receive_packet(filter,output))>=0) av_packet_unref(output);
        finish();
        if (status!=AVERROR(EAGAIN) && status!=AVERROR_EOF) break;
        if (errors) break;
    }
    if (status==AVERROR_EOF && !errors && displayed>0 && displayed==packets) eof=true;
    if (!eof && !errors) error("incomplete scan or packet/display coverage mismatch");
    if (std::fflush(stdout)!=0 || std::ferror(stdout)) { error("output write failed");eof=false; }
    std::fprintf(stderr,"{\"complete\":%s,\"errors\":%d,\"displayed_frames\":%lld,\"packets\":%lld,\"headers\":%lld,\"metadata_obus_skipped\":%u}\n",
        eof?"true":"false",errors,static_cast<long long>(displayed),static_cast<long long>(packets),static_cast<long long>(headers),skipped);
    av_packet_free(&packet);av_packet_free(&output);av_bsf_free(&filter);avformat_close_input(&format);
    return eof ? 0 : 1;
}
