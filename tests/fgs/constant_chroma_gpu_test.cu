// Small native transfer/association controls, with no encoder or timed workload.
#include <iostream>
#include "NVEncFilmGrainSourceFrame.cuh"
using namespace fgsdiagnostic;
using namespace fgsmodel;
#include "native_source_gpu_fixture.cuh"
using namespace fgs_gpu_test;
int main() {
    try {
        unsigned cases=0,negative=0;uint64_t samples=0;
        for(unsigned depth:{8u,10u})for(bool semi:{false,true})for(bool padded:{false,true})
            for(unsigned mask:{2u,4u,6u})for(unsigned code8:{16u,128u,240u}) {
            const unsigned code=code8<<(depth-8);
            Picture source(depth,semi,padded,code),candidate(depth,semi,padded,code);
            const auto bytes=NativeSourceFrame::nativeBytes(Picture::w,Picture::h,depth);
            auto memory=std::make_shared<SourceMemory>(bytes);
            std::array<float,3> f{.1f,.25f,.25f};for(unsigned c=1;c<3;++c)if(mask&(1u<<c))f[c]=1;
            const auto decision=preEncodeRetentionDecision(f,true,true,false,0,false,7^mask);
            auto good=captureNativeSource(source.view,memory,7,1,24000,nullptr,decision,mask,&candidate.view);
            require(good->planes==source.planes,"source capture changed");good->requireCopiedChroma(mask);
            require(good->copiedChroma.mask==mask,"capture mask changed");++cases;
            samples+=uint64_t(Picture::w)*Picture::h/4*((mask&2?1:0)+(mask&4?1:0));good.reset();
            for(unsigned kind=0;kind<12;++kind) {
                const unsigned c=(mask&2)?1:2;
                auto fv=source.view,cv=candidate.view;auto d=decision;unsigned requested=mask;
                if(kind==0){candidate.planes[c].back()=code+(code8==240?-1:1);candidate.upload();cv=candidate.view;}
                if(kind==1)++cv.frameId;
                if(kind==2)++cv.timestamp;
                if(kind==3)cv.width-=2;
                if(kind==4)cv.plane[c].pixelStride=3;
                if(kind==5)requested|=1;
                if(kind==6)d.reasonMask|=PreEncodeRetentionDecision::OrdinaryFallback;
                if(kind==7)d.effective[c]=.5f;
                if(kind==8)d.preservedComponents^=1;
                if(kind==9) {
                    std::fill(candidate.planes[c].begin(),candidate.planes[c].end(),15u<<(depth-8));
                    std::fill(source.planes[c].begin(),source.planes[c].end(),15u<<(depth-8));
                    source.upload();candidate.upload();fv=source.view;cv=candidate.view;
                }
                if(kind==10) {
                    source.planes[c].back()=code+(code8==240?-1:1);candidate.planes[c]=source.planes[c];
                    source.upload();candidate.upload();fv=source.view;cv=candidate.view;
                }
                bool failed=false;
                try{captureNativeSource(fv,memory,7,1,24000,nullptr,d,requested,kind==11?nullptr:&cv);}catch(...){failed=true;}
                require(failed && memory->live==0,"invalid copied chroma accepted or source memory leaked");++negative;
                source.planes[c].assign(source.planes[c].size(),code);candidate.planes[c].assign(candidate.planes[c].size(),code);
                source.upload();candidate.upload();
            }
        }
        std::cout<<"{\"complete\":true,\"cases\":"<<cases<<",\"copied_samples\":"<<samples<<",\"negative_controls\":"<<negative<<"}\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
