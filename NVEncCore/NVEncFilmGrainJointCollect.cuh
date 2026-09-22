// Experimental asynchronous CUDA collector. No allocation or stream synchronization.
// The caller owns valid device plane/tile/output storage until the stream completes.
#pragma once
#include "NVEncFilmGrainJointCollect.h"
#include <cuda_runtime.h>
#include <cmath>

namespace fgsmodel {
namespace joint_collect_detail {
template<class T, unsigned shift>
__device__ int code(const FilmGrainCollectPlane& p, unsigned x, unsigned y) {
    return reinterpret_cast<const T*>(static_cast<const uint8_t*>(p.data) + y * p.pitchBytes)[x * p.pixelStride] >> shift;
}
template<class T>
__global__ void copy_component(FilmGrainCollectPlane input,FilmGrainCollectPlane output,
    unsigned width,unsigned height) {
    for(unsigned i=blockIdx.x*256+threadIdx.x;i<width*height;i+=gridDim.x*256) {
        const unsigned x=i%width,y=i/width;
        const auto row=reinterpret_cast<const T*>(static_cast<const uint8_t*>(input.data)+y*input.pitchBytes);
        auto target=reinterpret_cast<T*>(static_cast<uint8_t*>(const_cast<void*>(output.data))+y*output.pitchBytes);
        target[x]=row[x*input.pixelStride];
    }
}
__device__ int retained(int s, int b, float r) {
    // Explicit separate float operations match the measured native rounding contract.
    return __float2int_rn(__fadd_rn(float(b), __fmul_rn(r, float(s - b))));
}
template<class T, unsigned shift>
__device__ int retained_code(const FilmGrainCollectFrame& s, const FilmGrainCollectFrame& b,
    unsigned p, unsigned x, unsigned y, float r) {
    return retained(code<T,shift>(s.plane[p],x,y),code<T,shift>(b.plane[p],x,y),r);
}
__device__ double warp_sum(double v) {
    for (int d=16;d;d>>=1) v += __shfl_down_sync(0xffffffffu,v,d);
    return v;
}
__device__ unsigned variable_index(unsigned variable, unsigned sample) {
    const int x = 3 + sample % 26, y = 3 + sample / 26;
    if (variable < 21) return (y + int(variable / 7) - 3) * 32 + x + int(variable % 7) - 3;
    if (variable < 24) return y * 32 + x + int(variable) - 24;
    return y * 32 + x;
}

template<class T, unsigned shift>
__global__ void collect(FilmGrainCollectFrame source, FilmGrainCollectFrame base,
    FilmGrainCollectFrame previous, bool history, FilmGrainCollectRetention retain,
    const FilmGrainCollectTile *tiles, FilmGrainCollectResult *outputs) {
    const unsigned thread=threadIdx.x, lane=thread & 31, warp=thread >> 5;
    auto& out=outputs[blockIdx.x];
    const auto tile=tiles[blockIdx.x];
    // A rejected block has explicit zero observations and no reusable stale matrices.
    for(unsigned i=thread;i<FGS_COLLECT_MATRIX;i+=256)
        out.source[i]=out.base[i]=out.sourceBase[i]=0.0;
    if(thread<9)out.colourSource[thread]=out.colourBase[thread]=out.colourSourceBase[thread]=0;
    if(thread<49)out.colourLagSource[thread]=out.colourLagBase[thread]=out.colourLagSourceBase[thread]=out.colourLagBaseSource[thread]=0;
    if(thread==0) {
        out.reasons=0;out.observations=0;out.brightnessGroup=0;out.checkFold=0;
        out.otherColourReasons=0;
        for(unsigned i=0;i<9;++i)out.mean[i]=out.variance[i]=0.0;
        for(unsigned i=0;i<3;++i)out.temporalCorrelation[i]=out.coherence[i]=0.0;
        if(!history)out.reasons|=FGS_COLLECT_HISTORY;
        if(tile.component<1 || tile.component>2 || tile.x%32 || tile.y%32
            || tile.x>source.width/2-32 || tile.y>source.height/2-32)
            out.reasons|=FGS_COLLECT_COORDINATES;
    }
    __syncthreads();
    if(out.reasons)return; // no read from invalid/absent previous planes
    __shared__ float data[9][1024];
    __shared__ double partial[27][8], fit[9][3], exact[12];
    const float divisor=float(1u<<(source.bitDepth-8));
    const float rc=tile.component==1 ? retain.cb : retain.cr;
    const int maximum=(1<<source.bitDepth)-1;
    bool invalidCode=false;
    for(unsigned i=thread;i<1024;i+=256) {
        const unsigned x=tile.x+i%32,y=tile.y+i/32;
        int sy=0,by=0,py=0;
        for(unsigned dy=0;dy<2;++dy)for(unsigned dx=0;dx<2;++dx) {
            const int s=code<T,shift>(source.plane[0],2*x+dx,2*y+dy);
            const int b=code<T,shift>(base.plane[0],2*x+dx,2*y+dy);
            const int p=code<T,shift>(previous.plane[0],2*x+dx,2*y+dy);
            invalidCode|=s>maximum || b>maximum || p>maximum;
            sy+=s;by+=retained(s,b,retain.y);py+=p;
        }
        data[0][i]=sy/(4*divisor);data[2][i]=by/(4*divisor);data[4][i]=py/(4*divisor);
        const int s=code<T,shift>(source.plane[tile.component],x,y);
        const int b=code<T,shift>(base.plane[tile.component],x,y);
        const int p=code<T,shift>(previous.plane[tile.component],x,y);
        invalidCode|=s>maximum || b>maximum || p>maximum;
        data[1][i]=s/divisor;data[3][i]=retained(s,b,rc)/divisor;data[5][i]=p/divisor;
        const unsigned other=3-tile.component;
        const int os=code<T,shift>(source.plane[other],x,y),ob=code<T,shift>(base.plane[other],x,y),op=code<T,shift>(previous.plane[other],x,y);
        invalidCode|=os>maximum || ob>maximum || op>maximum;
        data[6][i]=os/divisor;data[7][i]=retained(os,ob,other==1 ? retain.cb : retain.cr)/divisor;data[8][i]=op/divisor;
    }
    if(invalidCode)atomicOr(&out.reasons,uint32_t(FGS_COLLECT_CODES));
    __syncthreads();
    if(out.reasons)return;
    for(unsigned f=0;f<9;++f) {
        double sum=0,sx=0,sy=0;
        for(unsigned i=thread;i<1024;i+=256) {
            const double value=data[f][i];
            sum+=value;sx+=value*(int(i%32)*2-31);sy+=value*(int(i/32)*2-31);
        }
        sum=warp_sum(sum);sx=warp_sum(sx);sy=warp_sum(sy);
        if(lane==0){partial[f*3][warp]=sum;partial[f*3+1][warp]=sx;partial[f*3+2][warp]=sy;}
    }
    __syncthreads();
    if(thread<27) {
        double sum=0;for(unsigned w=0;w<8;++w)sum+=partial[thread][w];
        fit[thread/3][thread%3]=sum/(thread%3==0 ? 1024.0 : 349184.0);
        if(thread%3==0)out.mean[thread/3]=sum/1024.0;
    }
    __syncthreads();
    // Native values and their products are exactly representable here. Form
    // scalar variance/temporal evidence before reducing detrended pixels to
    // float scratch; high-contrast rejected patches still need accurate stats.
    for(unsigned statistic=0;statistic<12;++statistic) {
        const unsigned a=statistic<9 ? statistic : (statistic==11 ? 6 : statistic-9);
        const unsigned b=statistic<9 ? statistic : (statistic==11 ? 8 : statistic-5);
        double sum=0;for(unsigned i=thread;i<1024;i+=256)sum+=double(data[a][i])*data[b][i];
        sum=warp_sum(sum);if(lane==0)partial[statistic][warp]=sum;
    }
    __syncthreads();
    if(thread<12) {
        const unsigned a=thread<9 ? thread : (thread==11 ? 6 : thread-9);
        const unsigned b=thread<9 ? thread : (thread==11 ? 8 : thread-5);
        double sum=0;for(unsigned w=0;w<8;++w)sum+=partial[thread][w];
        exact[thread]=sum/1024-fit[a][0]*fit[b][0]-341*(fit[a][1]*fit[b][1]+fit[a][2]*fit[b][2]);
        if(thread<9)out.variance[thread]=fmax(0.0,exact[thread]);
    }
    __syncthreads();
    for(unsigned f=0;f<9;++f)for(unsigned i=thread;i<1024;i+=256)
        data[f][i]=float(double(data[f][i])-fit[f][0]-fit[f][1]*(int(i%32)*2-31)-fit[f][2]*(int(i/32)*2-31));
    __syncthreads();
    for(unsigned statistic=0;statistic<9;++statistic) {
        double sum=0;
        for(unsigned i=thread;i<1024;i+=256) {
            if(i%32 && i%32<31 && i/32 && i/32<31) {
                const unsigned f=statistic<6 ? statistic/3 : 6,axis=statistic%3;
                const double gx=(double(data[f][i+1])-data[f][i-1])*0.5;
                const double gy=(double(data[f][i+32])-data[f][i-32])*0.5;
                sum+=axis==0 ? gx*gx : (axis==1 ? gy*gy : gx*gy);
            }
        }
        sum=warp_sum(sum);if(lane==0)partial[statistic][warp]=sum;
    }
    __syncthreads();
    if(thread==0) {
        double values[9]={};
        for(unsigned i=0;i<9;++i)for(unsigned w=0;w<8;++w)values[i]+=partial[i][w];
        out.brightnessGroup=min(19u,unsigned(fmax(0.0,fit[0][0])*20/256));
        out.checkFold=((tile.x/32)+(tile.y/32))&1;
        for(unsigned p=0;p<3;++p) {
            const unsigned index=p==2 ? 6 : p,reference=p==2 ? 8 : p+4,gradient=p*3;
            const double v=out.variance[index],r=out.variance[reference];
            const double ax=values[gradient],ay=values[gradient+1],xy=values[gradient+2];
            const double corr=(v>0 && r>0) ? exact[9+p]/sqrt(v*r) : 0;
            const double coherence=hypot(ax-ay,2*xy)/fmax(1e-12,ax+ay);
            out.temporalCorrelation[p]=corr;out.coherence[p]=coherence;
            auto& reason=p==2 ? out.otherColourReasons : out.reasons;
            if(v<0.04 || v>256 || r<=0)reason|=p ? FGS_COLLECT_CHROMA_ENERGY : FGS_COLLECT_LUMA_ENERGY;
            if(fabs(fit[index][0]-fit[reference][0])>1 || r<0.5*v || r>2*v)
                reason|=p ? FGS_COLLECT_CHROMA_LEVEL : FGS_COLLECT_LUMA_LEVEL;
            if(fabs(corr)>0.15)reason|=p ? FGS_COLLECT_CHROMA_PERSISTENT : FGS_COLLECT_LUMA_PERSISTENT;
            if(coherence>0.18)reason|=p ? FGS_COLLECT_CHROMA_DIRECTIONAL : FGS_COLLECT_LUMA_DIRECTIONAL;
        }
        if(!out.reasons)out.observations=26*26;
    }
    __syncthreads();
    if(out.reasons)return;
    const unsigned sourceFields[3]={0,tile.component==1 ? 1u : 6u,tile.component==2 ? 1u : 6u};
    const unsigned baseFields[3]={2,tile.component==1 ? 3u : 7u,tile.component==2 ? 3u : 7u};
    if(thread<9) {
        const unsigned a=thread/3,b=thread%3;double ss=0,bb=0,sb=0;
        for(unsigned sample=0;sample<676;++sample) {
            const unsigned i=variable_index(25,sample);
            const double s=data[sourceFields[a]][i],v=data[baseFields[a]][i];
            ss+=s*data[sourceFields[b]][i];bb+=v*data[baseFields[b]][i];sb+=s*data[baseFields[b]][i];
        }
        out.colourSource[thread]=ss;out.colourBase[thread]=bb;out.colourSourceBase[thread]=sb;
    }
    if(thread<49) {
        const int dx=int(thread%7)-3,dy=int(thread/7)-3;double ss=0,bb=0,sb=0,bs=0;
        for(unsigned sample=0;sample<676;++sample) {
            const unsigned i=variable_index(25,sample),j=int(i)+dy*32+dx;
            const double s=data[sourceFields[1]][i],b=data[baseFields[1]][i];
            ss+=s*data[sourceFields[2]][j];bb+=b*data[baseFields[2]][j];
            sb+=s*data[baseFields[2]][j];bs+=b*data[sourceFields[2]][j];
        }
        out.colourLagSource[thread]=ss;out.colourLagBase[thread]=bb;
        out.colourLagSourceBase[thread]=sb;out.colourLagBaseSource[thread]=bs;
    }
    // Sum in double; the finite GPU study profiles this correctness-first path.
    // Each matrix element has a fixed summation order and needs no atomics.
    for(unsigned k=thread;k<FGS_COLLECT_MATRIX;k+=256) {
        const unsigned a=k/26,b=k%26;
        double ss=0,bb=0,sb=0;
        for(unsigned sample=0;sample<26*26;++sample) {
            const unsigned ia=variable_index(a,sample),ib=variable_index(b,sample);
            const double sa=data[a==24 ? 0 : 1][ia],ba=data[a==24 ? 2 : 3][ia];
            const double sc=data[b==24 ? 0 : 1][ib],bc=data[b==24 ? 2 : 3][ib];
            ss+=sa*sc;bb+=ba*bc;sb+=sa*bc;
        }
        out.source[k]=ss;out.base[k]=bb;out.sourceBase[k]=sb;
    }
}

template<class T,unsigned shift,bool chroma>
__global__ void lookup(FilmGrainCollectFrame source,FilmGrainCollectFrame base,
    float retainY,unsigned long long *counts,unsigned long long *invalid) {
    __shared__ unsigned bins[FGS_COLLECT_LOOKUP_CODES];
    for(unsigned i=threadIdx.x;i<FGS_COLLECT_LOOKUP_CODES;i+=256)bins[i]=0;
    __syncthreads();
    const unsigned width=chroma ? source.width/2 : source.width;
    const unsigned height=chroma ? source.height/2 : source.height;
    for(unsigned i=blockIdx.x*256+threadIdx.x;i<width*height;i+=gridDim.x*256) {
        const unsigned x=i%width,y=i/width;
        int value;
        bool bad=false;
        const int maximum=(1<<source.bitDepth)-1;
        if(chroma) {
            const int s0=code<T,shift>(source.plane[0],2*x,2*y),b0=code<T,shift>(base.plane[0],2*x,2*y);
            const int s1=code<T,shift>(source.plane[0],2*x+1,2*y),b1=code<T,shift>(base.plane[0],2*x+1,2*y);
            bad=s0>maximum||b0>maximum||s1>maximum||b1>maximum;
            value=(retained(s0,b0,retainY)+retained(s1,b1,retainY)+1)>>1;
        } else {
            const int s=code<T,shift>(source.plane[0],x,y),b=code<T,shift>(base.plane[0],x,y);
            bad=s>maximum||b>maximum;value=retained(s,b,retainY);
        }
        if(bad || value<0 || value>maximum) { atomicAdd(invalid,1ULL);continue; }
        atomicAdd(&bins[value],1u);
    }
    __syncthreads();
    for(unsigned i=threadIdx.x;i<FGS_COLLECT_LOOKUP_CODES;i+=256)if(bins[i])atomicAdd(counts+i,(unsigned long long)bins[i]);
}
inline bool retention_valid(const FilmGrainCollectRetention& r) {
    return std::isfinite(r.y)&&std::isfinite(r.cb)&&std::isfinite(r.cr)
        &&r.y>=0&&r.y<=1&&r.cb>=0&&r.cb<=1&&r.cr>=0&&r.cr<=1;
}
__device__ double moment(const FilmGrainCollectResult& r,unsigned i) {
    if(i<676)return r.source[i];i-=676;
    if(i<676)return r.base[i];i-=676;
    if(i<676)return r.sourceBase[i];i-=676;
    if(i<9)return r.colourSource[i];i-=9;
    if(i<9)return r.colourBase[i];i-=9;
    if(i<9)return r.colourSourceBase[i];i-=9;
    if(i<49)return r.colourLagSource[i];i-=49;
    if(i<49)return r.colourLagBase[i];i-=49;
    if(i<49)return r.colourLagSourceBase[i];i-=49;
    return r.colourLagBaseSource[i];
}
__global__ void reduce(const FilmGrainCollectTile *tiles,const FilmGrainCollectResult *results,
    unsigned count,FilmGrainCollectGroup *groups) {
    __shared__ unsigned selected[FGS_COLLECT_MAX_TILES],size;
    const unsigned group=blockIdx.x;
    if(threadIdx.x==0) {
        size=0;unsigned other=0;
        for(unsigned i=0;i<count;++i) {
            const auto& r=results[i];const unsigned c=tiles[i].component;
            if(c<1||c>2||r.reasons||r.observations!=676||r.checkFold>1||r.brightnessGroup>=20)continue;
            if((c-1)*40+r.checkFold*20+r.brightnessGroup!=group)continue;
            selected[size++]=i;other+=r.otherColourReasons==0;
        }
        groups[group].blocks+=size;groups[group].observations+=size*676;
        groups[group].otherColourSupportedBlocks+=other;
    }
    __syncthreads();
    for(unsigned m=threadIdx.x;m<FGS_COLLECT_MOMENTS;m+=256) {
        double sum=0;for(unsigned i=0;i<size;++i)sum+=moment(results[selected[i]],m);
        groups[group].moments[m]+=sum;
    }
}
} // namespace joint_collect_detail

// Dedicated all-plane history for optional collection. Configure outside the
// per-picture path. Reads and saves must use the same stream; a different stream
// receives an invalid view, not a claim that unfinished copies are ready there.
// Consumers of the previous view must be queued before save_async overwrites it.
class FilmGrainCollectHistory {
    FilmGrainCollectFrame m_frame{};
    cudaStream_t m_owner=nullptr;
    bool m_bound=false;
public:
    FilmGrainCollectHistory()=default;
    FilmGrainCollectHistory(const FilmGrainCollectHistory&)=delete;
    FilmGrainCollectHistory& operator=(const FilmGrainCollectHistory&)=delete;
    ~FilmGrainCollectHistory(){clear();}
    void reset(){m_frame.complete=false;}
    void clear() {
        for(auto& p:m_frame.plane) { if(p.data)cudaFree(const_cast<void*>(p.data));p={}; }
        m_frame={};m_owner=nullptr;m_bound=false;
    }
    cudaError_t configure(const FilmGrainCollectFrame& format) {
        clear();
        if(!film_grain_collect_layout_valid(format))return cudaErrorInvalidValue;
        m_frame.width=format.width;m_frame.height=format.height;
        m_frame.bitDepth=format.bitDepth;m_frame.storageShift=format.storageShift;
        for(unsigned p=0;p<3;++p) {
            void *data=nullptr;size_t pitch=0;
            const unsigned bytes=format.bitDepth==8 ? 1 : 2;
            const auto error=cudaMallocPitch(&data,&pitch,size_t(p ? format.width/2 : format.width)*bytes,
                p ? format.height/2 : format.height);
            if(error!=cudaSuccess){clear();return error;}
            m_frame.plane[p]={data,pitch,1};
        }
        return cudaSuccess;
    }
    FilmGrainCollectFrame view(cudaStream_t stream) const {
        auto result=m_frame;if(stream!=m_owner)result.complete=false;return result;
    }
    cudaError_t save_async(const FilmGrainCollectFrame& source,cudaStream_t stream) {
        // Invalidates history even on a failed update, never leaves a stale valid flag.
        m_frame.complete=false;
        if((m_bound&&stream!=m_owner)||!film_grain_collect_layout_valid(source)||!film_grain_collect_same_geometry(source,m_frame)
            ||source.frameId<0||source.timestamp==std::numeric_limits<int64_t>::min())return cudaErrorInvalidValue;
        m_owner=stream;m_bound=true;
        for(unsigned p=0;p<3;++p) {
            if(!m_frame.plane[p].data)return cudaErrorInvalidValue;
            const unsigned width=p ? source.width/2 : source.width,height=p ? source.height/2 : source.height;
            if(source.bitDepth==8)joint_collect_detail::copy_component<uint8_t><<<256,256,0,stream>>>(source.plane[p],m_frame.plane[p],width,height);
            else joint_collect_detail::copy_component<uint16_t><<<256,256,0,stream>>>(source.plane[p],m_frame.plane[p],width,height);
            const auto error=cudaGetLastError();if(error!=cudaSuccess)return error;
        }
        m_owner=stream;m_frame.frameId=source.frameId;m_frame.timestamp=source.timestamp;
        m_frame.epoch=source.epoch;m_frame.complete=true;
        return cudaSuccess;
    }
};

// Tiles are device-resident, aligned 32x32 chroma blocks. Calls are bounded to
// 512 requested blocks and under 9 MiB of result storage, with no hidden allocation.
inline cudaError_t film_grain_collect_joint_async(const FilmGrainCollectFrame& source,
    const FilmGrainCollectFrame& base,const FilmGrainCollectFrame& previous,
    const FilmGrainCollectRetention& retain,const FilmGrainCollectTile *tiles,
    unsigned tileCount,FilmGrainCollectResult *output,size_t outputCapacity,cudaStream_t stream) {
    using namespace joint_collect_detail;
    if(!film_grain_collect_base_valid(source,base)||!retention_valid(retain)
        ||!tiles||!output||!tileCount||tileCount>FGS_COLLECT_MAX_TILES||outputCapacity<tileCount)
        return cudaErrorInvalidValue;
    const bool history=film_grain_collect_history_valid(source,previous);
    if(source.bitDepth==8)collect<uint8_t,0><<<tileCount,256,0,stream>>>(source,base,previous,history,retain,tiles,output);
    else if(source.storageShift==6)collect<uint16_t,6><<<tileCount,256,0,stream>>>(source,base,previous,history,retain,tiles,output);
    else collect<uint16_t,0><<<tileCount,256,0,stream>>>(source,base,previous,history,retain,tiles,output);
    return cudaGetLastError();
}
// Histogram inputs must obey the current Y-referred chroma-curve restriction
// described in FilmGrainCollectLookup. Counts include borders and rejected tiles.
inline cudaError_t film_grain_collect_lookup_async(const FilmGrainCollectFrame& source,
    const FilmGrainCollectFrame& base,float retainY,FilmGrainCollectLookup *output,cudaStream_t stream) {
    using namespace joint_collect_detail;
    if(!film_grain_collect_base_valid(source,base)||!std::isfinite(retainY)||retainY<0||retainY>1||!output)
        return cudaErrorInvalidValue;
    auto error=cudaMemsetAsync(output,0,sizeof(*output),stream);if(error!=cudaSuccess)return error;
    const unsigned blocks=256;
    if(source.bitDepth==8) {
        lookup<uint8_t,0,false><<<blocks,256,0,stream>>>(source,base,retainY,output->luma,&output->invalidSamples);
        error=cudaGetLastError();if(error!=cudaSuccess)return error;
        lookup<uint8_t,0,true><<<blocks,256,0,stream>>>(source,base,retainY,output->chroma,&output->invalidSamples);
    } else if(source.storageShift==6) {
        lookup<uint16_t,6,false><<<blocks,256,0,stream>>>(source,base,retainY,output->luma,&output->invalidSamples);
        error=cudaGetLastError();if(error!=cudaSuccess)return error;
        lookup<uint16_t,6,true><<<blocks,256,0,stream>>>(source,base,retainY,output->chroma,&output->invalidSamples);
    } else {
        lookup<uint16_t,0,false><<<blocks,256,0,stream>>>(source,base,retainY,output->luma,&output->invalidSamples);
        error=cudaGetLastError();if(error!=cudaSuccess)return error;
        lookup<uint16_t,0,true><<<blocks,256,0,stream>>>(source,base,retainY,output->chroma,&output->invalidSamples);
    }
    return cudaGetLastError();
}
// Reduces each <=512-tile batch on the device into fixed 80-group storage
// (~1.38 MiB). Clear for the first batch. Accumulated batches must belong to
// one source/base/retention decision, use unique coordinates and the same stream.
// This does not promote an unsupported brightness group or qualify image coverage.
inline cudaError_t film_grain_collect_reduce_async(const FilmGrainCollectTile *tiles,
    const FilmGrainCollectResult *results,unsigned count,FilmGrainCollectGroup *groups,
    size_t groupCapacity,bool clear,cudaStream_t stream) {
    if(!tiles||!results||!groups||!count||count>FGS_COLLECT_MAX_TILES||groupCapacity<FGS_COLLECT_GROUPS)
        return cudaErrorInvalidValue;
    if(clear) {
        const auto error=cudaMemsetAsync(groups,0,sizeof(*groups)*FGS_COLLECT_GROUPS,stream);
        if(error!=cudaSuccess)return error;
    }
    joint_collect_detail::reduce<<<FGS_COLLECT_GROUPS,256,0,stream>>>(tiles,results,count,groups);
    return cudaGetLastError();
}
} // namespace fgsmodel
