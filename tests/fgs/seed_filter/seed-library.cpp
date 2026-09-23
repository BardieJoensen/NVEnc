// C ABI boundary around a private, symbol-hidden FFmpeg parser build.
// The caller's FFmpeg installation and global log callback are independent.
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <new>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavcodec/bsf.h>
#include <libavutil/mem.h>
#include <libavutil/error.h>
}
struct SeedContext { AVBSFContext* filter=nullptr; AVPacket *in=nullptr,*out=nullptr,*spare=nullptr; bool failed=false; char error[128]{}; };
extern "C" unsigned fgs_av1_seed_abi_version() { return 1; }
extern "C" void fgs_av1_seed_close(void* handle) {
 auto* ctx=static_cast<SeedContext*>(handle);if(!ctx)return;
 av_packet_free(&ctx->in);av_packet_free(&ctx->out);av_packet_free(&ctx->spare);av_bsf_free(&ctx->filter);delete ctx;
}
extern "C" void* fgs_av1_seed_open(const uint8_t* extra,size_t bytes) {
 if((!extra && bytes) || bytes>32*1024*1024)return nullptr;
 auto* ctx=new(std::nothrow) SeedContext;if(!ctx)return nullptr;
 int err=av_bsf_alloc(av_bsf_get_by_name("av1_grain_seed"),&ctx->filter);
 if(err>=0){
  ctx->filter->par_in->codec_type=AVMEDIA_TYPE_VIDEO;ctx->filter->par_in->codec_id=AV_CODEC_ID_AV1;
  if(bytes){ctx->filter->par_in->extradata=static_cast<uint8_t*>(av_mallocz(bytes+AV_INPUT_BUFFER_PADDING_SIZE));
   if(!ctx->filter->par_in->extradata)err=AVERROR(ENOMEM);
   else {memcpy(ctx->filter->par_in->extradata,extra,bytes);ctx->filter->par_in->extradata_size=int(bytes);}}
 }
 if(err>=0)err=av_bsf_init(ctx->filter);
 ctx->in=av_packet_alloc();ctx->out=av_packet_alloc();ctx->spare=av_packet_alloc();
 if(err<0 || !ctx->in || !ctx->out || !ctx->spare){fgs_av1_seed_close(ctx);return nullptr;}
 return ctx;
}
// 0 unchanged, 1 changed, negative error. No caller bytes change on any error.
// Each context belongs to one serial AV1 stream; independent contexts may run
// concurrently. An error is terminal for the context; close/open starts afresh.
extern "C" int fgs_av1_seed_process(void* handle,uint8_t* data,size_t bytes) {
 auto* ctx=static_cast<SeedContext*>(handle);if(!ctx)return AVERROR(EINVAL);
 int err=0,changed=0;
 if(ctx->failed)return AVERROR_INVALIDDATA;
 if(!data || !bytes || bytes>32*1024*1024){err=AVERROR(EINVAL);goto fail;}
 err=av_new_packet(ctx->in,int(bytes));if(err<0)goto fail;
 memcpy(ctx->in->data,data,bytes);
 err=av_bsf_send_packet(ctx->filter,ctx->in);if(err<0)goto fail;
 err=av_bsf_receive_packet(ctx->filter,ctx->out);if(err<0)goto fail;
 if(ctx->out->size!=int(bytes)){err=AVERROR_INVALIDDATA;goto fail;}
 changed=memcmp(data,ctx->out->data,bytes)!=0;
 // Verify that this is exactly one output before committing caller changes.
 err=av_bsf_receive_packet(ctx->filter,ctx->spare);
 if(err!=AVERROR(EAGAIN)){if(err>=0)err=AVERROR_INVALIDDATA;goto fail;}
 if(changed)memcpy(data,ctx->out->data,bytes);
 av_packet_unref(ctx->out);ctx->error[0]=0;return changed;
fail:
 ctx->failed=true;av_strerror(err,ctx->error,sizeof(ctx->error));av_packet_unref(ctx->in);av_packet_unref(ctx->out);av_packet_unref(ctx->spare);return err;
}
extern "C" const char* fgs_av1_seed_error(void* handle) {
 auto* ctx=static_cast<SeedContext*>(handle);return ctx?ctx->error:"Missing AV1 seed parser context";
}
