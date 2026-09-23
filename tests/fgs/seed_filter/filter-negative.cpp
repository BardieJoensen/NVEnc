#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavcodec/bsf.h>
}
int main(int argc,char** argv){
 assert(argc==2);FILE* file=fopen(argv[1],"rb");assert(file);uint8_t header[44];assert(fread(header,1,44,file)==44);
 unsigned size=header[32]|unsigned(header[33])<<8|unsigned(header[34])<<16|unsigned(header[35])<<24;
 std::vector<uint8_t> good(size);assert(fread(good.data(),1,size,file)==size);fclose(file);
 std::vector<std::vector<uint8_t>> bad={good,{0x32,0},{0x32,0x80},std::vector<uint8_t>(32*1024*1024+1,0),good};
 bad[0][0]|=0x80;bad[4].push_back(0x32);bad[4].push_back(0);unsigned rejected=0;
 for(unsigned index=0;index<bad.size()+1;++index){
  AVBSFContext* ctx=nullptr;assert(av_bsf_alloc(av_bsf_get_by_name("av1_grain_seed"),&ctx)>=0);
  ctx->par_in->codec_id=AV_CODEC_ID_AV1;ctx->par_in->codec_type=AVMEDIA_TYPE_VIDEO;assert(av_bsf_init(ctx)>=0);
  auto submit=[&](const std::vector<uint8_t>& bytes,bool invalidSide){
   AVPacket* in=av_packet_alloc();AVPacket* out=av_packet_alloc();assert(av_new_packet(in,bytes.size())>=0);memcpy(in->data,bytes.data(),bytes.size());
   if(invalidSide){auto side=av_packet_new_side_data(in,AV_PKT_DATA_NEW_EXTRADATA,1);assert(side);*side=0xff;}
   AVPacket* alias=av_packet_clone(in);assert(alias);int e=av_bsf_send_packet(ctx,in);assert(e>=0);e=av_bsf_receive_packet(ctx,out);
   assert(alias->size==int(bytes.size()) && !memcmp(alias->data,bytes.data(),bytes.size()));
   if(e<0)assert(!out->data && !out->size);
   av_packet_free(&alias);av_packet_free(&in);av_packet_free(&out);return e;
  };
  assert(submit(index<bad.size()?bad[index]:good,index==bad.size())<0);++rejected;
  // Neither a clean next packet nor a new sequence may silently clear failure.
  assert(submit(good,false)<0);++rejected;
  av_bsf_flush(ctx);assert(submit(good,false)>=0);
  av_bsf_free(&ctx);
 }
 printf("{\"complete\":true,\"invalid_or_stale_packets_rejected\":%u,\"flush_reinitializations\":%zu,\"shared_input_unchanged\":true}\n",rejected,bad.size()+1);
}
