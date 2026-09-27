#include <cassert>
#include <iostream>
#include "NVEncFilmGrainSourceFrame.h"
using namespace fgsdiagnostic;
template<class F> void rejects(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);}
int main() {
    uint64_t samples=0;
    for(unsigned depth:{8,10})for(unsigned stride:{1,2})for(unsigned padding:{0,7})for(unsigned shift:{0,6}) {
        if(depth==8 && shift)continue;
        const unsigned w=65,h=33,unit=depth==8?1:2;
        const size_t span=((w-1)*stride+1)*unit,row=span+padding;
        std::vector<uint8_t> bytes(row*(h-1)+span,0xbd);
        std::vector<uint16_t> expected(w*h),actual(w*h);
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
            const unsigned code=(x*71+y*149+x*y*13)&((1u<<depth)-1);expected[y*w+x]=code;
            const unsigned stored=code<<shift;const size_t i=y*row+x*stride*unit;
            bytes[i]=stored&255;if(unit==2)bytes[i+1]=stored>>8;
        }
        const auto before=bytes;unpackSourcePlane(bytes.data(),bytes.size(),row,stride,w,h,depth,shift,actual);
        assert(actual==expected && bytes==before);samples+=actual.size();
        rejects([&]{unpackSourcePlane(bytes.data(),bytes.size()-1,row,stride,w,h,depth,shift,actual);});
        rejects([&]{unpackSourcePlane(bytes.data(),bytes.size(),span-1,stride,w,h,depth,shift,actual);});
        rejects([&]{unpackSourcePlane(bytes.data(),bytes.size(),row,3,w,h,depth,shift,actual);});
        if(depth==10) {
            bytes[0]=shift?1:255;bytes[1]=shift?0:255;
            rejects([&]{unpackSourcePlane(bytes.data(),bytes.size(),row,stride,w,h,depth,shift,actual);});
        }
    }
    const auto bytes=NativeSourceFrame::nativeBytes(128,66,10);
    auto memory=std::make_shared<SourceMemory>(bytes);
    auto source=std::make_shared<NativeSourceFrame>(memory,3,15,150,1,24,128,66,10);
    source->requireIdentity(3,15,150,2,48,128,66,10);
    auto owned=source;source.reset();assert(memory->live==bytes && memory->peak==bytes);
    rejects([&]{std::make_shared<NativeSourceFrame>(memory,4,16,151,1,24,128,66,10);});
    for(unsigned failure=0;failure<9;++failure)rejects([&] {
        owned->requireIdentity(failure==0?4:3,failure==1?16:15,failure==2?151:150,
            failure==3?0:1,failure==4?25:24,failure==5?64:128,failure==6?64:66,failure==7?8:10);
        if(failure==8){owned->planes[1].pop_back();owned->requireIdentity(3,15,150,1,24,128,66,10);}
    });
    owned.reset();assert(memory->live==0);
    for(unsigned mask:{2u,4u,6u}) {
        auto proof=std::make_shared<NativeSourceFrame>(memory,0,0,0,1,24,128,66,10);
        for(unsigned c=1;c<3;++c)for(size_t i=0;i<proof->planes[c].size();++i)proof->planes[c][i]=uint16_t(480+i%65);
        rejects([&]{proof->requirePreservedChroma(mask);});proof->preservedChroma=mask;proof->requirePreservedChroma(mask);
        const auto c=(mask&2)?1:2;const auto value=proof->planes[c].back();
        proof->planes[c].back()=63;rejects([&]{proof->requirePreservedChroma(mask);});proof->planes[c].back()=value;
        proof->planes[c].pop_back();rejects([&]{proof->requirePreservedChroma(mask);});proof->planes[c].push_back(value);
        proof->copiedChroma.mask=mask;rejects([&]{proof->requirePreservedChroma(mask);});
        proof.reset();assert(memory->live==0);
    }
    rejects([&]{std::make_shared<NativeSourceFrame>(memory,0,-1,0,1,24,128,66,10);});assert(memory->live==0);
    rejects([&]{std::make_shared<NativeSourceFrame>(memory,0,0,INT64_MIN,1,24,128,66,10);});assert(memory->live==0);
    rejects([&]{std::make_shared<NativeSourceFrame>(memory,0,0,0,1,24,128,65,10);});assert(memory->live==0);
    auto again=std::make_shared<NativeSourceFrame>(memory,4,16,151,1,24,128,66,10);
    const std::weak_ptr<SourceMemory> lifetime=memory;memory.reset();assert(!lifetime.expired());again.reset();assert(lifetime.expired());
    std::cout<<"Original source transport: "<<samples<<" exact padded/planar/interleaved samples; identity, lifetime, budget and invalid-code/span controls passed\n";
}
