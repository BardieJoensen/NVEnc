// Isolated public-BSF API harness. Each worker owns its complete parser state.
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>
#include <future>
#include <chrono>
#include "av1_seed_patch.h"
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavcodec/bsf.h>
#include <libavutil/mem.h>
}
static void ok(bool x,const char* text){if(!x)throw std::runtime_error(text);}
static uint32_t le(const uint8_t* p){return p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;}
static void put(FILE* f,const void* p,size_t n){ok(fwrite(p,1,n,f)==n,"write failed");}
struct Frame { std::array<uint8_t,12> header;std::vector<uint8_t> bytes; };
static unsigned run(const std::array<uint8_t,32>& header,const std::vector<Frame>& frames,
                    const std::vector<uint8_t>& sequence,const std::string& path) {
 AVBSFContext* filter=nullptr;AVPacket* in=av_packet_alloc();AVPacket* out=av_packet_alloc();FILE* file=nullptr;unsigned changes=0;
 try{
  ok(av_bsf_alloc(av_bsf_get_by_name("av1_grain_seed"),&filter)>=0,"filter unavailable");
  filter->par_in->codec_type=AVMEDIA_TYPE_VIDEO;filter->par_in->codec_id=AV_CODEC_ID_AV1;
  filter->par_in->width=header[12]|int(header[13])<<8;filter->par_in->height=header[14]|int(header[15])<<8;
  filter->time_base_in={int(le(header.data()+20)),int(le(header.data()+16))};
  if(!sequence.empty()){
   filter->par_in->extradata=(uint8_t*)av_mallocz(sequence.size()+AV_INPUT_BUFFER_PADDING_SIZE);
   ok(filter->par_in->extradata,"extradata allocation");memcpy(filter->par_in->extradata,sequence.data(),sequence.size());filter->par_in->extradata_size=int(sequence.size());
  }
  ok(av_bsf_init(filter)>=0,"init failed");
  ok(filter->par_out->extradata_size==int(sequence.size()),"changed extradata size");
  if(!sequence.empty())ok(!memcmp(filter->par_out->extradata,sequence.data(),sequence.size()),"changed extradata");
  file=fopen(path.c_str(),"wbx");ok(file,"new output required");put(file,header.data(),32);
  for(size_t index=0;index<frames.size();++index){const auto& f=frames[index];
   ok(av_new_packet(in,int(f.bytes.size()))>=0,"packet allocation");memcpy(in->data,f.bytes.data(),f.bytes.size());
   in->pts=1000+int64_t(index)*43;in->dts=in->pts-4;in->duration=43;in->pos=222+index*100;
   in->flags=index%7==0?AV_PKT_FLAG_KEY:0;in->stream_index=3;in->time_base={1,1000};
   auto side=av_packet_new_side_data(in,AV_PKT_DATA_MATROSKA_BLOCKADDITIONAL,8);ok(side,"side allocation");memset(side,0x5a,8);
   if(index%17==0 && !sequence.empty()){
    side=av_packet_new_side_data(in,AV_PKT_DATA_NEW_EXTRADATA,sequence.size());ok(side,"side extradata allocation");memcpy(side,sequence.data(),sequence.size());
   }
   AVPacket* alias=av_packet_clone(in);ok(alias,"packet alias");
   ok(av_bsf_send_packet(filter,in)>=0 && av_bsf_receive_packet(filter,out)>=0,"filter packet failed");
   ok(alias->size==int(f.bytes.size()) && !memcmp(alias->data,f.bytes.data(),f.bytes.size()),"shared input buffer changed");av_packet_free(&alias);
   ok(out->pts==1000+int64_t(index)*43 && out->dts==out->pts-4 && out->duration==43 &&
      out->pos==222+int64_t(index)*100 && out->flags==(index%7==0?AV_PKT_FLAG_KEY:0) &&
      out->stream_index==3 && out->time_base.num==1 && out->time_base.den==1000,"packet properties changed");
   size_t size=0;side=av_packet_get_side_data(out,AV_PKT_DATA_MATROSKA_BLOCKADDITIONAL,&size);ok(side && size==8,"side lost");for(size_t i=0;i<size;++i)ok(side[i]==0x5a,"side changed");
   if(index%17==0 && !sequence.empty()){
    side=av_packet_get_side_data(out,AV_PKT_DATA_NEW_EXTRADATA,&size);ok(side && size==sequence.size() && !memcmp(side,sequence.data(),size),"side extradata changed");
   }
   ok(out->size==int(f.bytes.size()),"packet size changed");changes+=memcmp(out->data,f.bytes.data(),f.bytes.size())!=0;
   put(file,f.header.data(),12);put(file,out->data,out->size);av_packet_unref(out);
   ok(av_bsf_receive_packet(filter,out)==AVERROR(EAGAIN),"extra packet");
  }
  ok(av_bsf_send_packet(filter,nullptr)>=0 && av_bsf_receive_packet(filter,out)==AVERROR_EOF,"flush packet mismatch");
  const int status=fclose(file);file=nullptr;ok(status==0,"close failed");
 }catch(...){if(file){fclose(file);remove(path.c_str());}av_packet_free(&in);av_packet_free(&out);av_bsf_free(&filter);throw;}
 av_packet_free(&in);av_packet_free(&out);av_bsf_free(&filter);return changes;
}
int main(int argc,char** argv){
 if(argc!=4){fprintf(stderr,"usage: filter-ivf INPUT OUTPUT THREADS\n");return 2;}
 try{
  const unsigned threads=std::stoul(argv[3]);ok(threads && threads<=4,"threads 1..4");
  FILE* f=fopen(argv[1],"rb");ok(f,"input");std::array<uint8_t,32> h{};ok(fread(h.data(),1,32,f)==32 && !memcmp(h.data(),"DKIF",4) && !memcmp(h.data()+8,"AV01",4),"IVF header");
  std::vector<Frame> frames;std::vector<uint8_t> sequence;
  for(;;){Frame frame;size_t n=fread(frame.header.data(),1,12,f);if(!n && feof(f))break;ok(n==12,"frame header");unsigned size=le(frame.header.data());ok(size && size<=32*1024*1024,"frame size");frame.bytes.resize(size);ok(fread(frame.bytes.data(),1,size,f)==size,"frame data");
   if(frames.empty()){std::vector<fgsseed::Obu> obus;ok(fgsseed::split_obus(frame.bytes.data(),size,obus),"OBUs");for(const auto& obu:obus)if(obu.type==1)sequence.assign(frame.bytes.begin()+obu.offset,frame.bytes.begin()+obu.offset+obu.bytes);}
   frames.push_back(std::move(frame));
  }
  fclose(f);ok(frames.size()==le(h.data()+24),"frame count");auto begin=std::chrono::steady_clock::now();std::vector<std::future<unsigned>> futures;
  for(unsigned i=0;i<threads;++i)futures.push_back(std::async(std::launch::async,[&,i](){return run(h,frames,sequence,std::string(argv[2])+(threads>1?"."+std::to_string(i):""));}));
  unsigned changed=0;for(auto& future:futures)changed+=future.get();
  const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  printf("{\"complete\":true,\"frames\":%zu,\"threads\":%u,\"changed_packets_total\":%u,\"seconds\":%.6f,\"side_data_and_properties_exact\":true,\"extradata_bytes\":%zu}\n",frames.size(),threads,changed,seconds,sequence.size());return 0;
 }catch(const std::exception& e){fprintf(stderr,"%s\n",e.what());return 2;}
}
