// Finite independent decoder comparison through the public AOM API.
// Unlike FFmpeg's AOM wrapper, this explicitly controls synthesis in both modes.
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>
extern "C" {
#include <aom/aom_decoder.h>
#include <aom/aomdx.h>
#include <libavformat/avformat.h>
#include <libavutil/sha.h>
#include <libavutil/mem.h>
}
int main(int argc,char** argv) {
    if(argc!=4 || (std::string(argv[2])!="0" && std::string(argv[2])!="1")) return 2;
    char *end=nullptr;const auto expected=std::strtoul(argv[3],&end,10);
    if(!end || *end || !expected || expected>500000) return 2;
    AVFormatContext *format=nullptr;AVPacket *packet=av_packet_alloc();AVSHA *sha=av_sha_alloc();
    aom_codec_ctx_t decoder{};bool initialized=false;unsigned frames=0;int status=1;
    try {
        if(!packet || !sha || avformat_open_input(&format,argv[1],nullptr,nullptr)<0)
            throw std::runtime_error("cannot open input");
        int video=-1;
        for(unsigned i=0;i<format->nb_streams;++i)
            if(format->streams[i]->codecpar->codec_id==AV_CODEC_ID_AV1) {
                if(video>=0)throw std::runtime_error("expected one AV1 stream");
                video=int(i);
            }
        if(video<0)throw std::runtime_error("missing AV1 stream");
        aom_codec_dec_cfg_t config{};config.threads=2;config.allow_lowbitdepth=1;
        if(aom_codec_dec_init(&decoder,aom_codec_av1_dx(),&config,0)!=AOM_CODEC_OK)
            throw std::runtime_error("AOM initialization failed");
        initialized=true;
        if(aom_codec_control(&decoder,AV1D_SET_SKIP_FILM_GRAIN,std::string(argv[2])=="0")!=AOM_CODEC_OK)
            throw std::runtime_error("AOM grain control failed");
        const auto drain=[&]() {
            aom_codec_iter_t iterator=nullptr;
            while(auto *img=aom_codec_get_frame(&decoder,&iterator)) {
                if(++frames>expected || !img->d_w || !img->d_h || img->d_w>8192 || img->d_h>8192
                    || (img->d_w&1) || (img->d_h&1) || img->x_chroma_shift!=1 || img->y_chroma_shift!=1
                    || img->monochrome || (img->bit_depth!=8 && img->bit_depth!=10))
                    throw std::runtime_error("unsupported decoded extent or picture count");
                const bool wide=(img->fmt&AOM_IMG_FMT_HIGHBITDEPTH)!=0;
                if(img->bit_depth==10 && !wide)throw std::runtime_error("invalid 10-bit storage");
                if(av_sha_init(sha,256)<0)throw std::runtime_error("SHA initialization failed");
                for(unsigned c=0;c<3;++c) {
                    const unsigned w=c ? img->d_w/2 : img->d_w,h=c ? img->d_h/2 : img->d_h;
                    if(!img->planes[c] || img->stride[c]<int(w*(wide ? 2 : 1)))
                        throw std::runtime_error("invalid decoded plane");
                    std::vector<uint8_t> row(w*(img->bit_depth==8 ? 1 : 2));
                    for(unsigned y=0;y<h;++y) {
                        const auto *p=img->planes[c]+size_t(y)*img->stride[c];
                        for(unsigned x=0;x<w;++x) {
                            const unsigned value=wide ? reinterpret_cast<const uint16_t*>(p)[x] : p[x];
                            if(value>=(1u<<img->bit_depth))throw std::runtime_error("invalid decoded code");
                            if(img->bit_depth==8)row[x]=uint8_t(value);
                            else {row[2*x]=uint8_t(value);row[2*x+1]=uint8_t(value>>8);}
                        }
                        av_sha_update(sha,row.data(),row.size());
                    }
                }
                uint8_t hash[32];av_sha_final(sha,hash);
                for(auto byte:hash)std::printf("%02x",byte);
                std::printf("\n");
            }
        };
        int read=0;
        while((read=av_read_frame(format,packet))>=0) {
            if(packet->stream_index==video) {
                if(aom_codec_decode(&decoder,packet->data,packet->size,nullptr)!=AOM_CODEC_OK)
                    throw std::runtime_error(aom_codec_error(&decoder));
                drain();
            }
            av_packet_unref(packet);
        }
        if(read!=AVERROR_EOF || aom_codec_decode(&decoder,nullptr,0,nullptr)!=AOM_CODEC_OK)
            throw std::runtime_error("input ended with an error");
        drain();if(frames!=expected)throw std::runtime_error("decoded frame count mismatch");
        std::fprintf(stderr,"AOM %s: %u pictures; grain=%s\n",aom_codec_version_str(),frames,argv[2]);status=0;
    } catch(const std::exception& e) {std::fprintf(stderr,"%s\n",e.what());}
    if(initialized)aom_codec_destroy(&decoder);
    av_packet_free(&packet);avformat_close_input(&format);av_free(sha);
    return status;
}
