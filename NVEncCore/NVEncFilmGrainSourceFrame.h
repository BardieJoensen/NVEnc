// Immutable original input for explicit, bounded reconstruction diagnostics.
// Native unpacked uint16 samples, also for 8-bit input. Not a retention policy.
#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <memory>
#include <optional>
#include <stdexcept>
#include <vector>
#include "NVEncFilmGrainPreEncodeRetention.h"

namespace fgsdiagnostic {
struct SourceMemory {
    const uint64_t limit;
    std::atomic<uint64_t> live{0},peak{0};
    explicit SourceMemory(uint64_t bytes):limit(bytes) {
        if(!bytes || bytes>512ull*1024*1024)throw std::runtime_error("native source budget must be 1..512 MiB");
    }
    void acquire(uint64_t bytes) {
        auto current=live.load();
        do {if(bytes>limit || current>limit-bytes)throw std::runtime_error("native source memory budget exceeded");}
        while(!live.compare_exchange_weak(current,current+bytes));
        const auto used=current+bytes;auto prior=peak.load();
        while(prior<used && !peak.compare_exchange_weak(prior,used)){}
    }
};

class NativeSourceFrame {
    std::shared_ptr<SourceMemory> m_memory;
    uint64_t m_bytes=0;
public:
    const uint64_t ordinal;
    const int sourceId;
    const int64_t pts;
    const int timebaseNum,timebaseDen;
    const unsigned width,height,depth;
    const std::optional<PreEncodeRetentionDecision> retention;
    std::array<std::vector<uint16_t>,3> planes;

    static uint64_t nativeBytes(unsigned w,unsigned h,unsigned d) {
        if(w<64 || h<64 || w>4096 || h>2160 || (w&1) || (h&1) || (d!=8 && d!=10))
            throw std::runtime_error("native source requires progressive even 8/10-bit 4:2:0 up to 4096x2160");
        return uint64_t(w)*h*3;
    }
    NativeSourceFrame(std::shared_ptr<SourceMemory> memory,uint64_t index,int id,int64_t timestamp,
        int tbNum,int tbDen,unsigned w,unsigned h,unsigned d,std::optional<PreEncodeRetentionDecision> decision={})
        :m_memory(std::move(memory)),ordinal(index),sourceId(id),pts(timestamp),timebaseNum(tbNum),timebaseDen(tbDen),width(w),height(h),depth(d),retention(std::move(decision)) {
        if(!m_memory || index>10000000 || id<0 || timestamp==INT64_MIN || tbNum<=0 || tbDen<=0)
            throw std::runtime_error("native source identity invalid");
        const auto bytes=nativeBytes(w,h,d);m_memory->acquire(bytes);m_bytes=bytes;
        // Reserve ownership before allocating; constructor failures must release it.
        try {for(unsigned c=0;c<3;++c)planes[c].resize(size_t(c?w/2:w)*(c?h/2:h));}
        catch(...){m_memory->live.fetch_sub(m_bytes);m_bytes=0;throw;}
    }
    ~NativeSourceFrame(){if(m_bytes)m_memory->live.fetch_sub(m_bytes);}
    NativeSourceFrame(const NativeSourceFrame&)=delete;
    NativeSourceFrame& operator=(const NativeSourceFrame&)=delete;
    uint64_t liveBytes() const {return m_memory->live.load();}
    uint64_t peakBytes() const {return m_memory->peak.load();}
    void requireIdentity(uint64_t index,int id,int64_t timestamp,int tbNum,int tbDen,unsigned w,unsigned h,unsigned d) const {
        if(index!=ordinal || id!=sourceId || timestamp!=pts || tbNum<=0 || tbDen<=0
            || int64_t(tbNum)*timebaseDen!=int64_t(timebaseNum)*tbDen || w!=width || h!=height || d!=depth)
            throw std::runtime_error("native source does not match submitted picture identity/layout");
        for(unsigned c=0;c<3;++c)if(planes[c].size()!=size_t(c?w/2:w)*(c?h/2:h))
            throw std::runtime_error("native source plane span changed");
    }
};

// The same normalizer is used for GPU staging and CPU layout controls. The
// source span includes the last sample, not an assumed full interleaved row.
inline void unpackSourcePlane(const uint8_t* data,size_t bytes,size_t rowBytes,unsigned stride,
    unsigned width,unsigned height,unsigned depth,unsigned shift,std::vector<uint16_t>& out) {
    if(!data || !width || !height || width>4096 || height>2160 || (stride!=1 && stride!=2)
        || (depth!=8 && depth!=10) || (shift!=0 && !(depth==10 && shift==6)))
        throw std::runtime_error("native source staging layout invalid");
    const size_t unit=depth==8?1:2,span=(size_t(width)-1)*stride*unit+unit;
    if(rowBytes<span || rowBytes>65536 || bytes<rowBytes*(height-1)+span || out.size()!=size_t(width)*height)
        throw std::runtime_error("native source staging span invalid");
    const unsigned mask=(1u<<shift)-1,max=(1u<<depth)-1;
    for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x) {
        const size_t i=y*rowBytes+size_t(x)*stride*unit;
        const unsigned value=unit==1?data[i]:unsigned(data[i])|(unsigned(data[i+1])<<8);
        if((value&mask) || (value>>shift)>max)throw std::runtime_error("native source stored code is invalid");
        out[size_t(y)*width+x]=uint16_t(value>>shift);
    }
}
}
