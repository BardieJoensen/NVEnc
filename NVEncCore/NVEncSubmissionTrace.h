// Diagnostic-only AV1 submission receipts. No CUDA or hashing work when unset.
#pragma once

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <array>
#include <memory>
#include <new>
#include <string>
#include <utility>
#include <vector>
#include "rgy_err.h"
#include "nvEncodeAPI.h"
#include <cuda_runtime.h>
#if ENABLE_AVSW_READER
extern "C" {
#include <libavutil/md5.h>
#include <libavutil/mem.h>
}
#endif

class NVEncSubmissionTrace {
    struct Snapshot {
        uint32_t frameIdx, picVersion, encodePicFlags, grainUpdate;
        int inputFrameId;
        uint64_t timestamp, duration;
        NV_ENC_PIC_STRUCT pictureStruct;
        NV_ENC_BUFFER_FORMAT bufferFmt;
        uint32_t width, height;
        size_t pitch, rowBytes, rows;
        bool hasGrain;
        std::array<uint8_t, sizeof(NV_ENC_FILM_GRAIN_PARAMS_AV1)> grain;
        std::unique_ptr<uint8_t[]> surface;
    };
    // Bound retained diagnostic data; never spill or hash during submission.
    static constexpr size_t MAX_CAPTURE_BYTES = size_t(2) << 30;
    static constexpr size_t MAX_CAPTURE_FRAMES = 4096;
    const std::string m_path;
    std::unique_ptr<FILE, int (*)(FILE *)> m_file;
    std::vector<Snapshot> m_snapshots;
    size_t m_captureBytes;
    bool m_finished, m_hasInitialGrain;
    uint32_t m_enableFilmGrainParams;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 m_initialGrain;
#if ENABLE_AVSW_READER
    std::unique_ptr<AVMD5, decltype(&av_free)> m_md5;

    static std::string hex(const void *data, size_t size) {
        const auto *bytes = static_cast<const uint8_t *>(data);
        const char digits[] = "0123456789abcdef";
        std::string result(size * 2, '0');
        for (size_t i = 0; i < size; i++) {
            result[i * 2] = digits[bytes[i] >> 4];
            result[i * 2 + 1] = digits[bytes[i] & 15];
        }
        return result;
    }
    std::string hashRows(const uint8_t *data, size_t pitch, size_t rowBytes, size_t rows) {
        uint8_t result[16];
        av_md5_init(m_md5.get());
        for (size_t y = 0; y < rows; y++) {
            av_md5_update(m_md5.get(), data + y * pitch, rowBytes);
        }
        av_md5_final(m_md5.get(), result);
        return hex(result, sizeof(result));
    }
    void writeGrain(const NV_ENC_FILM_GRAIN_PARAMS_AV1 *grain) {
        if (!grain) {
            fprintf(m_file.get(), "null");
            return;
        }
        // Keep the exact pointed-to object representation AND named fields.
        // Raw bytes include SDK reserved bits/bytes and any ABI padding.
        fprintf(m_file.get(), "{\"object_bytes\":%zu,\"object_md5\":\"%s\",\"object_hex\":\"%s\"",
            sizeof(*grain), hashRows(reinterpret_cast<const uint8_t *>(grain), sizeof(*grain), sizeof(*grain), 1).c_str(),
            hex(grain, sizeof(*grain)).c_str());
#define TRACE_GRAIN_SCALAR(field) fprintf(m_file.get(), ",\"" #field "\":%u", static_cast<unsigned>(grain->field))
        TRACE_GRAIN_SCALAR(applyGrain);
        TRACE_GRAIN_SCALAR(chromaScalingFromLuma);
        TRACE_GRAIN_SCALAR(overlapFlag);
        TRACE_GRAIN_SCALAR(clipToRestrictedRange);
        TRACE_GRAIN_SCALAR(grainScalingMinus8);
        TRACE_GRAIN_SCALAR(arCoeffLag);
        TRACE_GRAIN_SCALAR(numYPoints);
        TRACE_GRAIN_SCALAR(numCbPoints);
        TRACE_GRAIN_SCALAR(numCrPoints);
        TRACE_GRAIN_SCALAR(arCoeffShiftMinus6);
        TRACE_GRAIN_SCALAR(grainScaleShift);
        TRACE_GRAIN_SCALAR(reserved1);
        TRACE_GRAIN_SCALAR(cbMult);
        TRACE_GRAIN_SCALAR(cbLumaMult);
        TRACE_GRAIN_SCALAR(cbOffset);
        TRACE_GRAIN_SCALAR(crMult);
        TRACE_GRAIN_SCALAR(crLumaMult);
        TRACE_GRAIN_SCALAR(crOffset);
#undef TRACE_GRAIN_SCALAR
#define TRACE_GRAIN_ARRAY(field) fprintf(m_file.get(), ",\"" #field "_hex\":\"%s\"", hex(grain->field, sizeof(grain->field)).c_str())
        TRACE_GRAIN_ARRAY(pointYValue);
        TRACE_GRAIN_ARRAY(pointYScaling);
        TRACE_GRAIN_ARRAY(pointCbValue);
        TRACE_GRAIN_ARRAY(pointCbScaling);
        TRACE_GRAIN_ARRAY(pointCrValue);
        TRACE_GRAIN_ARRAY(pointCrScaling);
        TRACE_GRAIN_ARRAY(arCoeffsYPlus128);
        TRACE_GRAIN_ARRAY(arCoeffsCbPlus128);
        TRACE_GRAIN_ARRAY(arCoeffsCrPlus128);
        TRACE_GRAIN_ARRAY(reserved2);
#undef TRACE_GRAIN_ARRAY
        fprintf(m_file.get(), "}");
    }
#endif
public:
    explicit NVEncSubmissionTrace(const char *path) : m_path(path), m_file(nullptr, &fclose),
        m_snapshots(), m_captureBytes(0), m_finished(false), m_hasInitialGrain(false),
        m_enableFilmGrainParams(0), m_initialGrain()
#if ENABLE_AVSW_READER
        , m_md5(av_md5_alloc(), &av_free)
#endif
    {}
    static std::unique_ptr<NVEncSubmissionTrace> fromEnvironment() {
        // Read once at encoder construction, not once per frame. An empty value
        // is disabled too. No file, capture buffer or digest allocation then.
        const char *path = std::getenv("NVENC_TRACE_SUBMISSION");
        return path && path[0] ? std::make_unique<NVEncSubmissionTrace>(path) : nullptr;
    }
    RGY_ERR capture(const NV_ENC_PIC_PARAMS& pic, const NV_ENC_CONFIG_AV1& config,
        const void *deviceSurface, uint32_t allocatedWidth, uint32_t allocatedHeight,
        uint32_t allocatedPitch, int inputFrameId, cudaStream_t producerStream) {
#if ENABLE_AVSW_READER
        if (!m_md5) return RGY_ERR_MEMORY_ALLOC;
        if (!deviceSurface || !pic.inputBuffer || pic.alphaBuffer
            || (pic.bufferFmt != NV_ENC_BUFFER_FORMAT_NV12 && pic.bufferFmt != NV_ENC_BUFFER_FORMAT_YUV420_10BIT)
            || !pic.inputWidth || !pic.inputHeight || (pic.inputWidth & 1) || (pic.inputHeight & 1)
            || pic.inputWidth != allocatedWidth || pic.inputHeight != allocatedHeight
            || pic.inputPitch != allocatedPitch || pic.pictureStruct != NV_ENC_PIC_STRUCT_FRAME) {
            return RGY_ERR_UNSUPPORTED;
        }
        const size_t pitch = allocatedPitch;
        const size_t rowBytes = static_cast<size_t>(pic.inputWidth) * (pic.bufferFmt == NV_ENC_BUFFER_FORMAT_NV12 ? 1 : 2);
        const size_t rows = static_cast<size_t>(pic.inputHeight) * 3 / 2;
        if (pitch < rowBytes || pitch > SIZE_MAX / rows) return RGY_ERR_INVALID_PARAM;
        if (m_finished) return RGY_ERR_INVALID_CALL;
        if (!m_file) {
            m_file.reset(fopen(m_path.c_str(), "wbx"));
            if (!m_file) return RGY_ERR_FILE_OPEN;
            m_enableFilmGrainParams = static_cast<uint32_t>(config.enableFilmGrainParams);
            m_hasInitialGrain = config.filmGrainParams != nullptr;
            if (m_hasInitialGrain) std::memcpy(&m_initialGrain, config.filmGrainParams, sizeof(m_initialGrain));
        }
        const size_t surfaceBytes = pitch * rows;
        try {
            if (m_snapshots.capacity() == 0) {
                m_snapshots.reserve(MAX_CAPTURE_FRAMES);
                m_captureBytes = m_snapshots.capacity() * sizeof(Snapshot);
            }
            if (m_snapshots.size() >= MAX_CAPTURE_FRAMES || m_captureBytes > MAX_CAPTURE_BYTES
                || surfaceBytes > MAX_CAPTURE_BYTES - m_captureBytes) {
                fprintf(stderr, "Submission trace snapshot limit exceeded (2 GiB including records, 4096 frames).\n");
                return RGY_ERR_NOT_ENOUGH_BUFFER;
            }
            Snapshot snapshot = {};
            snapshot.surface.reset(new uint8_t[surfaceBytes]);
            snapshot.frameIdx = pic.frameIdx;
            snapshot.inputFrameId = inputFrameId;
            snapshot.timestamp = pic.inputTimeStamp;
            snapshot.duration = pic.inputDuration;
            snapshot.picVersion = pic.version;
            snapshot.encodePicFlags = pic.encodePicFlags;
            snapshot.pictureStruct = pic.pictureStruct;
            snapshot.bufferFmt = pic.bufferFmt;
            snapshot.width = pic.inputWidth;
            snapshot.height = pic.inputHeight;
            snapshot.pitch = pitch;
            snapshot.rowBytes = rowBytes;
            snapshot.rows = rows;
            const auto& av1 = pic.codecPicParams.av1PicParams;
            snapshot.grainUpdate = static_cast<uint32_t>(av1.filmGrainParamsUpdate);
            snapshot.hasGrain = av1.filmGrainParams != nullptr;
            if (snapshot.hasGrain) std::memcpy(snapshot.grain.data(), av1.filmGrainParams, snapshot.grain.size());
            // The pipeline has already queued its producer-event waits on this
            // stream and mapped this same registered resource. This diagnostic
            // intentionally waits; it does not alter pixels or grain lifetimes.
            // Retain this exact completed snapshot until encoder drain. Do not
            // hash, write JSON, or retain the caller's grain pointer here.
            auto error = cudaMemcpy2DAsync(snapshot.surface.get(), pitch, deviceSurface, pitch,
                pitch, rows, cudaMemcpyDeviceToHost, producerStream);
            if (error == cudaSuccess) error = cudaStreamSynchronize(producerStream);
            if (error != cudaSuccess) return err_to_rgy(error);
            m_snapshots.push_back(std::move(snapshot));
            m_captureBytes += surfaceBytes;
        } catch (const std::bad_alloc&) {
            return RGY_ERR_MEMORY_ALLOC;
        }
        return RGY_ERR_NONE;
#else
        return RGY_ERR_UNSUPPORTED;
#endif
    }
    // Called only after successful encoder drain, with errors propagated by
    // sendFrame. Destruction must never manufacture a successful receipt.
    RGY_ERR finish() {
#if ENABLE_AVSW_READER
        if (m_finished) return RGY_ERR_NONE;
        if (!m_file || m_snapshots.empty()) return RGY_ERR_INVALID_CALL;
        try {
            fprintf(m_file.get(), "{\"type\":\"header\",\"schema\":1,\"hash\":\"md5\","
                "\"capture\":\"before_NvEncEncodePicture_after_producer_stream\","
                "\"padding_policy\":\"observe_full_pitch_no_initialization_or_normalization\","
                "\"visible_policy\":\"stored_Y_then_interleaved_UV_bytes_including_P010_low_bits\","
                "\"enableFilmGrainParams\":%u,\"initial_grain\":", m_enableFilmGrainParams);
            writeGrain(m_hasInitialGrain ? &m_initialGrain : nullptr);
            fprintf(m_file.get(), "}\n");
            for (const auto& snapshot : m_snapshots) {
                const auto *surface = snapshot.surface.get();
                const auto pitch = snapshot.pitch, rowBytes = snapshot.rowBytes, rows = snapshot.rows;
                fprintf(m_file.get(), "{\"type\":\"submit\",\"frameIdx\":%u,\"inputFrameId\":%d,"
                    "\"timestamp\":%llu,\"duration\":%llu,\"pic_version\":%u,\"encodePicFlags\":%u,"
                    "\"pictureStruct\":%u,\"bufferFmt\":%u,\"width\":%u,\"height\":%u,"
                    "\"pitch\":%zu,\"visible_row_bytes\":%zu,\"rows\":%zu,"
                    "\"surface_md5\":\"%s\",\"visible_md5\":\"%s\",\"y_md5\":\"%s\",\"uv_md5\":\"%s\","
                    "\"padding_md5\":\"%s\",\"filmGrainParamsUpdate\":%u,\"grain\":",
                    snapshot.frameIdx, snapshot.inputFrameId, static_cast<unsigned long long>(snapshot.timestamp),
                    static_cast<unsigned long long>(snapshot.duration), snapshot.picVersion, snapshot.encodePicFlags,
                    static_cast<unsigned>(snapshot.pictureStruct), static_cast<unsigned>(snapshot.bufferFmt), snapshot.width, snapshot.height,
                    pitch, rowBytes, rows, hashRows(surface, pitch, pitch, rows).c_str(),
                    hashRows(surface, pitch, rowBytes, rows).c_str(), hashRows(surface, pitch, rowBytes, snapshot.height).c_str(),
                    hashRows(surface + pitch * snapshot.height, pitch, rowBytes, snapshot.height / 2).c_str(),
                    hashRows(surface + rowBytes, pitch, pitch - rowBytes, rows).c_str(),
                    snapshot.grainUpdate);
                NV_ENC_FILM_GRAIN_PARAMS_AV1 grain;
                if (snapshot.hasGrain) std::memcpy(&grain, snapshot.grain.data(), sizeof(grain));
                writeGrain(snapshot.hasGrain ? &grain : nullptr);
                fprintf(m_file.get(), "}\n");
            }
            if (ferror(m_file.get()) || fflush(m_file.get()) != 0) return RGY_ERR_UNKNOWN;
            if (fclose(m_file.release()) != 0) return RGY_ERR_UNKNOWN;
            m_snapshots.clear();
            m_finished = true;
        } catch (const std::bad_alloc&) {
            return RGY_ERR_MEMORY_ALLOC;
        }
        return RGY_ERR_NONE;
#else
        return RGY_ERR_UNSUPPORTED;
#endif
    }
};
