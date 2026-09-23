// Whole-component native source/base evidence, including partial image borders.
// No allocation, host transfer or synchronization. Experimental retention only.
#pragma once
#include "NVEncFilmGrainSourcePreservation.h"
#include "NVEncFilmGrainRetentionBlend.cuh" // Validated native frame spans.

namespace fgsmodel {
namespace source_preservation_detail {
__global__ void initialize(FilmGrainNativeComponentCounts* out) {
    const unsigned p = threadIdx.x;
    if (p < 3) { out[p] = {}; out[p].minimum = 0xffffffffu; }
}
template<class T, unsigned shift>
__global__ void count(FilmGrainCollectFrame source, FilmGrainCollectFrame base,
    unsigned component, FilmGrainNativeComponentCounts* output) {
    const unsigned width = source.width / (component ? 2 : 1);
    const unsigned height = source.height / (component ? 2 : 1);
    unsigned samples = 0, changed = 0, invalid = 0, low = 0xffffffffu, high = 0;
    for (unsigned i = blockIdx.x * 256 + threadIdx.x; i < width * height; i += gridDim.x * 256) {
        const unsigned x = i % width, y = i / width;
        const auto& s = source.plane[component]; const auto& b = base.plane[component];
        const unsigned sr = reinterpret_cast<const T*>(static_cast<const uint8_t*>(s.data) + y * s.pitchBytes)[x * s.pixelStride];
        const unsigned br = reinterpret_cast<const T*>(static_cast<const uint8_t*>(b.data) + y * b.pitchBytes)[x * b.pixelStride];
        const unsigned sv = sr >> shift, bv = br >> shift;
        ++samples; changed += sv != bv;
        invalid += sv >= (1u << source.bitDepth) || bv >= (1u << source.bitDepth)
            || ((sr | br) & ((1u << shift) - 1));
        low = min(low, sv); high = max(high, sv);
    }
    for (unsigned offset = 16; offset; offset >>= 1) {
        samples += __shfl_down_sync(0xffffffffu, samples, offset);
        changed += __shfl_down_sync(0xffffffffu, changed, offset);
        invalid += __shfl_down_sync(0xffffffffu, invalid, offset);
        low = min(low, __shfl_down_sync(0xffffffffu, low, offset));
        high = max(high, __shfl_down_sync(0xffffffffu, high, offset));
    }
    __shared__ FilmGrainNativeComponentCounts partial[8];
    if ((threadIdx.x & 31) == 0) partial[threadIdx.x >> 5] = {samples, changed, invalid, low, high};
    __syncthreads();
    if (threadIdx.x == 0) {
        auto& out = output[component];
        unsigned long long ns = 0, nc = 0, ni = 0; unsigned minimum = 0xffffffffu, maximum = 0;
        for (unsigned i = 0; i < 8; ++i) {
            ns += partial[i].samples; nc += partial[i].changedSamples; ni += partial[i].invalidSamples;
            minimum = min(minimum, partial[i].minimum); maximum = max(maximum, partial[i].maximum);
        }
        atomicAdd(&out.samples, ns); atomicAdd(&out.changedSamples, nc); atomicAdd(&out.invalidSamples, ni);
        atomicMin(&out.minimum, minimum); atomicMax(&out.maximum, maximum);
    }
}
} // namespace source_preservation_detail

// Exactly three device counters are required. Source and base may alias; the
// result must not overlap either input. Callers retain all buffers until stream
// completion, then validate counters before using them as preservation evidence.
// Metadata/layout failures return before touching result storage. Native code
// and P010 storage failures appear in invalidSamples, never a silent clamp.
inline cudaError_t film_grain_source_preservation_async(const FilmGrainCollectFrame& source,
    const FilmGrainCollectFrame& base, FilmGrainNativeComponentCounts* counts,
    size_t countCapacity, cudaStream_t stream) {
    using namespace retention_blend_detail;
    const auto address = reinterpret_cast<uintptr_t>(counts);
    constexpr size_t bytes = 3 * sizeof(FilmGrainNativeComponentCounts);
    if (!film_grain_collect_base_valid(source, base) || !counts || countCapacity != 3
        || address % alignof(FilmGrainNativeComponentCounts)
        || address > std::numeric_limits<uintptr_t>::max() - bytes) return cudaErrorInvalidValue;
    const Span result{address, address + bytes};
    for (unsigned p = 0; p < 3; ++p) {
        const auto a = span(source, p), b = span(base, p);
        if (!a.begin || !b.begin || overlap(result, a) || overlap(result, b)) return cudaErrorInvalidValue;
    }
    source_preservation_detail::initialize<<<1, 3, 0, stream>>>(counts);
    auto error = cudaGetLastError();
    if (error != cudaSuccess) return error;
    for (unsigned p = 0; p < 3; ++p) {
        const unsigned samples = source.width * source.height / (p ? 4 : 1);
        const unsigned blocks = std::min(128u, (samples + 255) / 256);
        if (source.bitDepth == 8)
            source_preservation_detail::count<uint8_t, 0><<<blocks, 256, 0, stream>>>(source, base, p, counts);
        else if (source.storageShift == 6)
            source_preservation_detail::count<uint16_t, 6><<<blocks, 256, 0, stream>>>(source, base, p, counts);
        else
            source_preservation_detail::count<uint16_t, 0><<<blocks, 256, 0, stream>>>(source, base, p, counts);
        error = cudaGetLastError();
        if (error != cudaSuccess) return error;
    }
    return cudaSuccess;
}
} // namespace fgsmodel
