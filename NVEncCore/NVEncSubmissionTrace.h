// Diagnostic-only AV1 submission receipts. No CUDA or hashing work when unset.
#pragma once

#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
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
    const std::string m_path;
    std::unique_ptr<FILE, decltype(&fclose)> m_file;
    std::vector<uint8_t> m_surface;
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
    explicit NVEncSubmissionTrace(const char *path) : m_path(path), m_file(nullptr, &fclose), m_surface()
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
        if (!m_file) {
            m_file.reset(fopen(m_path.c_str(), "wbx"));
            if (!m_file) return RGY_ERR_FILE_OPEN;
            fprintf(m_file.get(), "{\"type\":\"header\",\"schema\":1,\"hash\":\"md5\","
                "\"capture\":\"before_NvEncEncodePicture_after_producer_stream\","
                "\"padding_policy\":\"observe_full_pitch_no_initialization_or_normalization\","
                "\"visible_policy\":\"stored_Y_then_interleaved_UV_bytes_including_P010_low_bits\","
                "\"enableFilmGrainParams\":%u,\"initial_grain\":", static_cast<unsigned>(config.enableFilmGrainParams));
            writeGrain(config.filmGrainParams);
            fprintf(m_file.get(), "}\n");
        }
        m_surface.resize(pitch * rows);
        // The pipeline has already queued its producer-event waits on this
        // stream and mapped this same registered resource. This diagnostic
        // intentionally waits; it does not alter pixels or grain lifetimes.
        auto error = cudaMemcpy2DAsync(m_surface.data(), pitch, deviceSurface, pitch,
            pitch, rows, cudaMemcpyDeviceToHost, producerStream);
        if (error == cudaSuccess) error = cudaStreamSynchronize(producerStream);
        if (error != cudaSuccess) return err_to_rgy(error);
        const auto *surface = m_surface.data();
        const auto& av1 = pic.codecPicParams.av1PicParams;
        fprintf(m_file.get(), "{\"type\":\"submit\",\"frameIdx\":%u,\"inputFrameId\":%d,"
            "\"timestamp\":%llu,\"duration\":%llu,\"pic_version\":%u,\"encodePicFlags\":%u,"
            "\"pictureStruct\":%u,\"bufferFmt\":%u,\"width\":%u,\"height\":%u,"
            "\"pitch\":%zu,\"visible_row_bytes\":%zu,\"rows\":%zu,"
            "\"surface_md5\":\"%s\",\"visible_md5\":\"%s\",\"y_md5\":\"%s\",\"uv_md5\":\"%s\","
            "\"padding_md5\":\"%s\",\"filmGrainParamsUpdate\":%u,\"grain\":",
            pic.frameIdx, inputFrameId, static_cast<unsigned long long>(pic.inputTimeStamp),
            static_cast<unsigned long long>(pic.inputDuration), pic.version, pic.encodePicFlags,
            static_cast<unsigned>(pic.pictureStruct), static_cast<unsigned>(pic.bufferFmt), pic.inputWidth, pic.inputHeight,
            pitch, rowBytes, rows, hashRows(surface, pitch, pitch, rows).c_str(),
            hashRows(surface, pitch, rowBytes, rows).c_str(), hashRows(surface, pitch, rowBytes, pic.inputHeight).c_str(),
            hashRows(surface + pitch * pic.inputHeight, pitch, rowBytes, pic.inputHeight / 2).c_str(),
            hashRows(surface + rowBytes, pitch, pitch - rowBytes, rows).c_str(),
            static_cast<unsigned>(av1.filmGrainParamsUpdate));
        writeGrain(av1.filmGrainParams);
        fprintf(m_file.get(), "}\n");
        if (ferror(m_file.get()) || fflush(m_file.get()) != 0) return RGY_ERR_UNKNOWN;
        return RGY_ERR_NONE;
#else
        return RGY_ERR_UNSUPPORTED;
#endif
    }
};
