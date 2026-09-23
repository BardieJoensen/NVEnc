#pragma once
#include "NVEncFilmGrainSourceFrame.h"
#include "NVEncFilmGrainJointCollect.h"
#include <cuda_runtime.h>

namespace fgsdiagnostic {
inline std::shared_ptr<const NativeSourceFrame> captureNativeSource(const fgsmodel::FilmGrainCollectFrame& f,
    const std::shared_ptr<SourceMemory>& memory,uint64_t ordinal,int tbNum,int tbDen,cudaStream_t stream) {
    if(!fgsmodel::film_grain_collect_layout_valid(f))throw std::runtime_error("native source GPU view invalid");
    auto frame=std::make_shared<NativeSourceFrame>(memory,ordinal,f.frameId,f.timestamp,tbNum,tbDen,f.width,f.height,f.bitDepth);
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
    return frame;
}
}
