// Finite GPU layout/lifetime control for the explicit original-source transport.
#include <iostream>
#include "NVEncFilmGrainSourceFrame.cuh"
using namespace fgsdiagnostic;
using namespace fgsmodel;
static void require(bool b,const char* why){if(!b)throw std::runtime_error(why);}
static void check(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
struct Allocation {
    void* data=nullptr;size_t pitch=0;
    ~Allocation(){if(data)cudaFree(data);}
};
int main() {
    try {
        constexpr unsigned w=128,h=66;uint64_t samples=0;unsigned rejected=0,cases=0;
        for(unsigned depth:{8,10})for(bool semi:{false,true})for(bool padded:{false,true}) {
            const unsigned unit=depth==8?1:2,shift=semi && depth==10?6:0;
            std::array<Allocation,3> allocations;std::array<std::vector<uint16_t>,3> expected;
            FilmGrainCollectFrame f;f.width=w;f.height=h;f.bitDepth=depth;f.storageShift=shift;
            f.frameId=91;f.timestamp=123456;f.complete=true;
            for(unsigned c=0;c<3;++c) {
                const unsigned cols=c?w/2:w,rows=c?h/2:h;
                expected[c].resize(size_t(cols)*rows);
                for(unsigned y=0;y<rows;++y)for(unsigned x=0;x<cols;++x)
                    expected[c][size_t(y)*cols+x]=(c*97+x*17+y*23)&((1u<<depth)-1);
            }
            for(unsigned c=0;c<(semi?2u:3u);++c) {
                const unsigned cols=c?w/2:w,rows=c?h/2:h,stride=semi && c?2:1;
                const size_t row=size_t(cols)*stride*unit+(padded?38:0);std::vector<uint8_t> host(row*rows,0xad);
                for(unsigned component=c;component<=((semi && c)?2:c);++component)
                    for(unsigned y=0;y<rows;++y)for(unsigned x=0;x<cols;++x) {
                        const auto value=unsigned(expected[component][size_t(y)*cols+x])<<shift;
                        const size_t i=y*row+(x*stride+component-c)*unit;host[i]=value&255;if(unit==2)host[i+1]=value>>8;
                    }
                auto& a=allocations[c];check(cudaMallocPitch(&a.data,&a.pitch,row,rows));
                check(cudaMemcpy2D(a.data,a.pitch,host.data(),row,row,rows,cudaMemcpyHostToDevice));
                f.plane[c]={a.data,a.pitch,stride};
                if(semi && c)f.plane[2]={static_cast<uint8_t*>(a.data)+unit,a.pitch,2};
            }
            const auto bytes=NativeSourceFrame::nativeBytes(w,h,depth);auto memory=std::make_shared<SourceMemory>(bytes);
            auto frame=captureNativeSource(f,memory,7,1,24000,nullptr);require(frame->planes==expected,"GPU source pixels differ");
            frame->requireIdentity(7,91,123456,2,48000,w,h,depth);samples+=w*h*3/2;++cases;
            auto alias=frame;frame.reset();require(memory->live==bytes,"source released before consumer");
            bool failed=false;try{captureNativeSource(f,memory,8,1,24000,nullptr);}catch(...){failed=true;}require(failed,"source budget did not reject");++rejected;
            alias.reset();require(memory->live==0 && memory->peak==bytes,"source ownership leaked");
            const auto decision=preEncodeRetentionDecision({{1,1,1}},true,true,false,0,false,7);
            auto copied=captureNativeSource(f,memory,7,1,24000,nullptr,decision,0,&f,0,true);
            require(copied->modeledSourceCopied && copied->planes==expected,"modeled source proof/pixels differ");
            copied->requireModeledSource();copied.reset();samples+=w*h*3/2;++cases;
            for(unsigned c=0;c<3;++c) {
                const unsigned cols=c?w/2:w,rows=c?h/2:h,stride=f.plane[c].pixelStride;
                const size_t span=(size_t(cols)-1)*stride*unit+unit;
                Allocation changed;check(cudaMallocPitch(&changed.data,&changed.pitch,span,rows));
                check(cudaMemcpy2D(changed.data,changed.pitch,f.plane[c].data,f.plane[c].pitchBytes,span,rows,cudaMemcpyDeviceToDevice));
                const uint16_t word=uint16_t((expected[c][0]^1u)<<shift);
                check(cudaMemcpy(changed.data,&word,unit,cudaMemcpyHostToDevice));
                auto candidate=f;candidate.plane[c]={changed.data,changed.pitch,stride};
                failed=false;try{captureNativeSource(f,memory,7,1,24000,nullptr,decision,0,&candidate,0,true);}catch(...){failed=true;}
                require(failed && memory->live==0,"changed modeled source plane accepted or leaked");++rejected;
            }
            if(depth==10) {
                const uint16_t invalid=shift?1:1024;check(cudaMemcpy(allocations[0].data,&invalid,2,cudaMemcpyHostToDevice));
                failed=false;try{captureNativeSource(f,memory,8,1,24000,nullptr);}catch(...){failed=true;}
                require(failed && memory->live==0,"invalid native source did not release/reject");++rejected;
            }
        }
        std::cout<<"{\"complete\":true,\"cases\":"<<cases<<",\"samples\":"<<samples<<",\"negative_controls\":"<<rejected<<"}\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
