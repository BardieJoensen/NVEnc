#pragma once
#include "NVEncFilmGrainSourceFrame.h"
#include "NVEncFilmGrainJointCollect.h"
#include <cuda_runtime.h>

namespace fgsdiagnostic {
inline std::shared_ptr<const NativeSourceFrame> captureNativeSource(const fgsmodel::FilmGrainCollectFrame& f,
    const std::shared_ptr<SourceMemory>& memory,uint64_t ordinal,int tbNum,int tbDen,cudaStream_t stream,
    std::optional<PreEncodeRetentionDecision> decision={},unsigned copiedChroma=0,
    const fgsmodel::FilmGrainCollectFrame* candidate=nullptr,unsigned preservedChroma=0,bool modeledSource=false) {
    if(!fgsmodel::film_grain_collect_layout_valid(f))throw std::runtime_error("native source GPU view invalid");
    const unsigned sourceChroma=copiedChroma|preservedChroma;
    if(!fgsmodel::film_grain_copied_chroma_mask(copiedChroma)
        || !fgsmodel::film_grain_copied_chroma_mask(preservedChroma) || (copiedChroma && preservedChroma)
        || (modeledSource && sourceChroma) || bool(candidate)!=bool(sourceChroma || modeledSource))
        throw std::runtime_error("copied chroma candidate/mask differs");
    if(sourceChroma || modeledSource) {
        if(!decision || !candidate || !fgsmodel::film_grain_collect_layout_valid(*candidate)
            || candidate->width!=f.width || candidate->height!=f.height || candidate->bitDepth!=f.bitDepth
            || candidate->frameId!=f.frameId || candidate->timestamp!=f.timestamp)
            throw std::runtime_error("copied chroma candidate identity/layout differs");
        if(modeledSource)requireModeledSourceRetention(*decision);
        else requirePartialRetentionModel(*decision,decision->requested,sourceChroma);
    }
    auto frame=std::make_shared<NativeSourceFrame>(memory,ordinal,f.frameId,f.timestamp,tbNum,tbDen,f.width,f.height,f.bitDepth,std::move(decision));
    const unsigned unit=f.bitDepth==8?1:2;
    for(unsigned c=0;c<3;++c) {
        const unsigned w=c?f.width/2:f.width,h=c?f.height/2:f.height;
        const auto& p=f.plane[c];const size_t row=size_t(w)*p.pixelStride*unit,span=(size_t(w)-1)*p.pixelStride*unit+unit;
        std::vector<uint8_t> staging(row*h);
        const auto copied=cudaMemcpy2DAsync(staging.data(),row,p.data,p.pitchBytes,span,h,cudaMemcpyDeviceToHost,stream);
        // Synchronize even after a failed enqueue so no staging storage can be
        // released while an earlier transfer still uses it.
        const auto waited=cudaStreamSynchronize(stream);
        if(copied!=cudaSuccess || waited!=cudaSuccess)throw std::runtime_error("native source GPU transfer failed");
        unpackSourcePlane(staging.data(),staging.size(),row,p.pixelStride,w,h,f.bitDepth,f.storageShift,frame->planes[c]);
    }
    if(sourceChroma || modeledSource) {
        // Explicit diagnostics only. Compare one native plane at a time so the
        // additional host storage stays bounded, including full-source luma.
        if(copiedChroma)frame->copiedChroma={f.width,f.height,f.bitDepth,0,{}};
        for(unsigned c=0;c<3;++c)if(modeledSource || (sourceChroma&(1u<<c))) {
            const unsigned w=c?f.width/2:f.width,h=c?f.height/2:f.height;const auto& p=candidate->plane[c];
            const size_t row=size_t(w)*p.pixelStride*unit,span=(size_t(w)-1)*p.pixelStride*unit+unit;
            std::vector<uint8_t> staging(row*h);std::vector<uint16_t> native(size_t(w)*h);
            const auto copied=cudaMemcpy2DAsync(staging.data(),row,p.data,p.pitchBytes,span,h,cudaMemcpyDeviceToHost,stream);
            const auto waited=cudaStreamSynchronize(stream);
            if(copied!=cudaSuccess || waited!=cudaSuccess)throw std::runtime_error("copied chroma GPU transfer failed");
            unpackSourcePlane(staging.data(),staging.size(),row,p.pixelStride,w,h,f.bitDepth,candidate->storageShift,native);
            if(native!=frame->planes[c])throw std::runtime_error(modeledSource
                ?"pre-encode modeled source pixels changed":"pre-encode copied chroma pixels changed");
            if(copiedChroma) {
                const auto code=native[0];
                if(!std::all_of(native.begin(),native.end(),[&](uint16_t v){return v==code;}))
                    throw std::runtime_error("pre-encode copied chroma is not constant");
                frame->copiedChroma.mask|=1u<<c;frame->copiedChroma.code[c-1]=code;
            } else if(!modeledSource)frame->preservedChroma|=1u<<c;
        }
        if(modeledSource) {frame->modeledSourceCopied=true;frame->requireModeledSource();}
        if(copiedChroma)frame->requireCopiedChroma(copiedChroma);
        if(preservedChroma)frame->requirePreservedChroma(preservedChroma);
    }
    return frame;
}
}
