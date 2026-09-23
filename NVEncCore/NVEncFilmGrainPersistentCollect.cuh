// Bounded asynchronous native detail collection. No allocation or synchronization.
#pragma once
#include "NVEncFilmGrainPersistentCollect.h"
#include "NVEncFilmGrainJointCollect.cuh"

namespace fgsmodel {
namespace persistent_collect_detail {
template<class T, unsigned shift>
__global__ void collect(FilmGrainCollectFrame source, FilmGrainCollectFrame base,
    FilmGrainPersistentHistory history, bool validHistory, FilmGrainCollectRetention retain,
    const FilmGrainPersistentTile *tiles, FilmGrainPersistentResult *outputs) {
    const unsigned thread = threadIdx.x, lane = thread & 31, warp = thread >> 5;
    auto& out = outputs[blockIdx.x];
    const auto tile = tiles[blockIdx.x];
    if (thread < 16) out.covariance[thread] = 0;
    if (thread < 4) out.mean[thread] = 0;
    const unsigned side = tile.component ? 32 : 64;
    const unsigned width = tile.component ? source.width/2 : source.width;
    const unsigned height = tile.component ? source.height/2 : source.height;
    if (thread == 0) {
        out.reasons = validHistory ? 0 : FGS_COLLECT_HISTORY;
        out.samples = out.changedSamples = 0;
        if (tile.component > 2 || tile.x % side || tile.y % side
            || tile.x >= width || tile.y >= height) out.reasons |= FGS_COLLECT_COORDINATES;
    }
    __syncthreads();
    if (out.reasons) return; // No reads from missing or stale history.
    const unsigned columns = min(side, width-tile.x), rows = min(side, height-tile.y);
    const unsigned count = columns * rows;
    const double divisor = double(1u << (source.bitDepth-8));
    const int maximum = (1 << source.bitDepth)-1;
    const float fraction = tile.component == 0 ? retain.y : tile.component == 1 ? retain.cb : retain.cr;
    double sums[4]{}, products[10]{}, changed = 0;
    bool invalid = false;
    for (unsigned i = thread; i < count; i += 256) {
        const unsigned x = tile.x + i % columns, y = tile.y + i / columns;
        const int s = joint_collect_detail::code<T,shift>(source.plane[tile.component],x,y);
        const int b = joint_collect_detail::code<T,shift>(base.plane[tile.component],x,y);
        int oldest = 0, newer = 0;
        invalid |= s > maximum || b > maximum;
        for (unsigned h = 0; h < 7; ++h) {
            const int v = joint_collect_detail::code<T,shift>(history.source[h].plane[tile.component],x,y);
            invalid |= v > maximum;
            if (h < 3) oldest += v; else newer += v;
        }
        const int candidate = joint_collect_detail::retained(s,b,fraction);
        changed += candidate != s;
        // A fixed origin keeps raw products small without rounding the history
        // averages. All native pixels contribute, including incomplete borders.
        const double field[4] = {s/divisor-128, candidate/divisor-128,
            oldest/(3*divisor)-128, newer/(4*divisor)-128};
        unsigned k = 0;
        for (unsigned a = 0; a < 4; ++a) {
            sums[a] += field[a];
            for (unsigned b = a; b < 4; ++b) products[k++] += field[a]*field[b];
        }
    }
    if (invalid) atomicOr(&out.reasons, uint32_t(FGS_COLLECT_CODES));
    __syncthreads();
    if (out.reasons) return;
    __shared__ double partial[15][8];
    for (unsigned i = 0; i < 15; ++i) {
        double v = i < 4 ? sums[i] : i < 14 ? products[i-4] : changed;
        v = joint_collect_detail::warp_sum(v);
        if (lane == 0) partial[i][warp] = v;
    }
    __syncthreads();
    if (thread == 0) {
        double total[15]{};
        for (unsigned i = 0; i < 15; ++i)
            for (unsigned w = 0; w < 8; ++w) total[i] += partial[i][w];
        for (unsigned a = 0; a < 4; ++a) out.mean[a] = total[a]/count+128;
        unsigned k = 4;
        for (unsigned a = 0; a < 4; ++a) for (unsigned b = a; b < 4; ++b) {
            const double covariance = total[k++]/count-(total[a]/count)*(total[b]/count);
            out.covariance[a*4+b] = out.covariance[b*4+a] = covariance;
        }
        out.samples = count;
        out.changedSamples = unsigned(total[14]);
    }
}
} // namespace persistent_collect_detail

// base is the pre-retention base. The candidate is its explicitly rounded
// blend with source, exactly once. Fractions of one measure an exact source
// copy but do not authorize grain synthesis or waive decoder-range checks.
inline cudaError_t film_grain_collect_persistent_async(const FilmGrainCollectFrame& source,
    const FilmGrainCollectFrame& base, const FilmGrainPersistentHistory& history,
    FilmGrainCollectRetention retain, const FilmGrainPersistentTile *tiles, unsigned count,
    FilmGrainPersistentResult *output, unsigned capacity, cudaStream_t stream) {
    if (!film_grain_collect_base_valid(source,base) || !tiles || !output || !count
        || count > FGS_COLLECT_MAX_TILES || capacity < count) return cudaErrorInvalidValue;
    for (float r : {retain.y,retain.cb,retain.cr})
        if (!std::isfinite(r) || r < 0 || r > 1) return cudaErrorInvalidValue;
    const bool valid = film_grain_persistent_history_valid(source,history);
    if (source.bitDepth == 8)
        persistent_collect_detail::collect<uint8_t,0><<<count,256,0,stream>>>(source,base,history,valid,retain,tiles,output);
    else if (source.storageShift == 6)
        persistent_collect_detail::collect<uint16_t,6><<<count,256,0,stream>>>(source,base,history,valid,retain,tiles,output);
    else
        persistent_collect_detail::collect<uint16_t,0><<<count,256,0,stream>>>(source,base,history,valid,retain,tiles,output);
    return cudaGetLastError();
}
} // namespace fgsmodel
