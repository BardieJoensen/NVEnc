// Native per-component residual blend for the experimental retention path.
// No encoder call sites. The caller owns all storage until stream completion.
#pragma once
#include "NVEncFilmGrainJointCollect.cuh"

namespace fgsmodel {
namespace retention_blend_detail {
struct Span { uintptr_t begin = 0, end = 0; };
inline Span span(const FilmGrainCollectFrame& frame, unsigned component) {
    const auto& p = frame.plane[component];
    const size_t rows = frame.height / (component ? 2 : 1);
    const size_t columns = frame.width / (component ? 2 : 1);
    const size_t bytes = frame.bitDepth == 8 ? 1 : 2;
    const auto begin = reinterpret_cast<uintptr_t>(p.data);
    const size_t tail = ((columns - 1) * p.pixelStride + 1) * bytes;
    if (p.pitchBytes > (std::numeric_limits<size_t>::max() - tail) / (rows - 1)) return {};
    const size_t length = p.pitchBytes * (rows - 1) + tail;
    if (!begin || begin > std::numeric_limits<uintptr_t>::max() - length) return {};
    return {begin, begin + length};
}
inline bool overlap(Span a, Span b) { return a.begin < b.end && b.begin < a.end; }
inline bool output_layout(const FilmGrainCollectFrame& output) {
    Span spans[3];
    for (unsigned p = 0; p < 3; ++p) {
        spans[p] = span(output, p);
        if (!spans[p].begin) return false;
    }
    if (overlap(spans[0], spans[1]) || overlap(spans[0], spans[2])) return false;
    if (overlap(spans[1], spans[2])) {
        const auto& cb = output.plane[1]; const auto& cr = output.plane[2];
        const size_t bytes = output.bitDepth == 8 ? 1 : 2;
        // Only adjacent, disjoint UV samples are an allowed overlapping span.
        if (cb.pixelStride != 2 || cr.pixelStride != 2 || cb.pitchBytes != cr.pitchBytes
            || (spans[1].begin > spans[2].begin ? spans[1].begin - spans[2].begin
                : spans[2].begin - spans[1].begin) != bytes) return false;
    }
    return true;
}
template<class T, unsigned shift>
__global__ void blend(FilmGrainCollectFrame source, FilmGrainCollectFrame base,
    FilmGrainCollectFrame output, unsigned component, float retain,
    unsigned long long* invalidSamples) {
    const unsigned width = source.width / (component ? 2 : 1);
    const unsigned height = source.height / (component ? 2 : 1);
    for (unsigned i = blockIdx.x * 256 + threadIdx.x; i < width * height; i += gridDim.x * 256) {
        const unsigned x = i % width, y = i / width;
        const int s = joint_collect_detail::code<T, shift>(source.plane[component], x, y);
        const int b = joint_collect_detail::code<T, shift>(base.plane[component], x, y);
        if (s >= (1 << source.bitDepth) || b >= (1 << source.bitDepth)) {
            atomicAdd(invalidSamples, 1ULL);
            continue; // Invalid output remains unusable; do not silently clamp corrupt input.
        }
        const auto& plane = output.plane[component];
        auto row = reinterpret_cast<T*>(static_cast<uint8_t*>(const_cast<void*>(plane.data)) + y * plane.pitchBytes);
        row[x * plane.pixelStride] = T(joint_collect_detail::retained(s, b, retain) << shift);
    }
}
} // namespace retention_blend_detail

// Out-of-place only: source/history and the original denoised base remain
// immutable so every candidate starts from the SAME B, never an already
// retained base. Output must be marked incomplete, with the source identity;
// the caller may mark it complete only after stream completion AND
// invalidSamples==0. A queued operation is not itself a validated frame.
// Fractions one/zero are exact native source/base endpoints. Measurements use
// the same explicit non-fused float operations and round-to-nearest-even.
inline cudaError_t film_grain_retention_blend_async(const FilmGrainCollectFrame& source,
    const FilmGrainCollectFrame& base, const FilmGrainCollectFrame& output,
    FilmGrainCollectRetention retain, unsigned long long* invalidSamples, cudaStream_t stream) {
    using namespace retention_blend_detail;
    auto layout = output; layout.complete = true;
    const auto counterBegin = reinterpret_cast<uintptr_t>(invalidSamples);
    if (!film_grain_collect_base_valid(source, base) || output.complete
        || !film_grain_collect_base_valid(source, layout)
        || !invalidSamples || !output_layout(output)
        || counterBegin % alignof(unsigned long long)
        || counterBegin > std::numeric_limits<uintptr_t>::max() - sizeof(*invalidSamples)
        || !std::isfinite(retain.y) || retain.y < 0 || retain.y > 1
        || !std::isfinite(retain.cb) || retain.cb < 0 || retain.cb > 1
        || !std::isfinite(retain.cr) || retain.cr < 0 || retain.cr > 1) return cudaErrorInvalidValue;
    const Span counter{counterBegin, counterBegin + sizeof(*invalidSamples)};
    for (unsigned p = 0; p < 3; ++p) {
        if (overlap(counter, span(source, p)) || overlap(counter, span(base, p))
            || overlap(counter, span(output, p))) return cudaErrorInvalidValue;
    }
    for (unsigned p = 0; p < 3; ++p) for (unsigned q = 0; q < 3; ++q) {
        const auto s = span(source, q), b = span(base, q);
        if (!s.begin || !b.begin || overlap(span(output, p), s) || overlap(span(output, p), b))
            return cudaErrorInvalidValue;
    }
    auto error = cudaMemsetAsync(invalidSamples, 0, sizeof(*invalidSamples), stream);
    if (error != cudaSuccess) return error;
    const float fractions[3] = {retain.y, retain.cb, retain.cr};
    for (unsigned p = 0; p < 3; ++p) {
        const unsigned samples = source.width * source.height / (p ? 4 : 1);
        const unsigned blocks = std::min(512u, (samples + 255) / 256);
        if (source.bitDepth == 8)
            blend<uint8_t, 0><<<blocks, 256, 0, stream>>>(source, base, output, p, fractions[p], invalidSamples);
        else if (source.storageShift == 6)
            blend<uint16_t, 6><<<blocks, 256, 0, stream>>>(source, base, output, p, fractions[p], invalidSamples);
        else
            blend<uint16_t, 0><<<blocks, 256, 0, stream>>>(source, base, output, p, fractions[p], invalidSamples);
        error = cudaGetLastError();
        if (error != cudaSuccess) return error;
    }
    return cudaSuccess;
}
} // namespace fgsmodel
