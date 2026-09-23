// Seven complete source frames on one CUDA stream, oldest-first when exposed.
// The owner must finish outstanding stream work before clear/destruction.
#pragma once
#include "NVEncFilmGrainPersistentCollect.cuh"

namespace fgsmodel {
class FilmGrainPersistentHistoryCache {
    FilmGrainCollectHistory m_frames[7];
    FilmGrainCollectFrame m_format{};
    cudaStream_t m_owner = nullptr;
    unsigned m_next = 0, m_count = 0;
    bool m_configured = false, m_bound = false;
public:
    FilmGrainPersistentHistoryCache() = default;
    FilmGrainPersistentHistoryCache(const FilmGrainPersistentHistoryCache&) = delete;
    FilmGrainPersistentHistoryCache& operator=(const FilmGrainPersistentHistoryCache&) = delete;
    void reset() {
        for (auto& f : m_frames) f.reset();
        m_count = m_next = 0;
    }
    void clear() {
        for (auto& f : m_frames) f.clear();
        m_format = {}; m_owner = nullptr; m_count = m_next = 0;
        m_configured = m_bound = false;
    }
    cudaError_t configure(const FilmGrainCollectFrame& format) {
        clear();
        // Bound history independently of the frame-layout maximum. This is
        // 174.2 MB of native payload at UHD 10 bit, with CUDA pitch overhead.
        if (!film_grain_collect_layout_valid(format)
            || uint64_t(format.width)*format.height*(format.bitDepth==8 ? 3 : 6)*7/2
                > 512ULL*1024*1024) return cudaErrorInvalidValue;
        for (auto& f : m_frames) {
            const auto error = f.configure(format);
            if (error != cudaSuccess) { clear(); return error; }
        }
        m_format = format; m_configured = true;
        return cudaSuccess;
    }
    FilmGrainPersistentHistory view(cudaStream_t stream) const {
        FilmGrainPersistentHistory result;
        if (!m_bound || stream != m_owner || m_count != 7) return result;
        for (unsigned i = 0; i < 7; ++i) result.source[i] = m_frames[(m_next+i)%7].view(stream);
        return result;
    }
    cudaError_t save_async(const FilmGrainCollectFrame& source, cudaStream_t stream) {
        if (!m_configured || (m_bound && stream != m_owner)
            || !film_grain_collect_layout_valid(source)
            || !film_grain_collect_same_geometry(source,m_format) || source.frameId < 0
            || source.timestamp == std::numeric_limits<int64_t>::min()) {
            reset(); return cudaErrorInvalidValue;
        }
        if (m_count && !film_grain_collect_history_valid(source,m_frames[(m_next+6)%7].view(stream)))
            reset(); // A valid discontinuous input begins a fresh seven-frame window.
        m_owner = stream; m_bound = true;
        const auto error = m_frames[m_next].save_async(source,stream);
        if (error != cudaSuccess) { reset(); return error; }
        m_next = (m_next+1)%7; m_count = std::min(7u,m_count+1);
        return cudaSuccess;
    }
};
} // namespace fgsmodel
