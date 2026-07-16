// -----------------------------------------------------------------------------------------
// NVEnc by rigaya
// -----------------------------------------------------------------------------------------
//
// The MIT License
//
// Copyright (c) 2026 NVEnc contributors
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.
//
// The statistical model and parameter quantization are derived from the
// Alliance for Open Media libaom noise model (aom_dsp/noise_model.c), which is
// distributed under the BSD 2-Clause License and AOM Patent License 1.0:
// https://aomedia.googlesource.com/aom/+/refs/heads/main/aom_dsp/noise_model.c
// ------------------------------------------------------------------------------------------

#pragma once

#include <array>
#include <cstdint>
#include <memory>

#include "NVEncFilter.h"
#include "nvEncodeAPI.h"

// Quality-first defaults for the CUDA AV1 grain analyzer.  A denoiseLevel of
// zero selects the noise level measured from flat 32x32 luma blocks.  Positive
// values are expressed in 8-bit code-value units and are scaled for 10-bit
// input.  The parser intentionally does not own this type so the analyzer can
// also be exercised directly by tests and other frontends.
struct NVEncFilmGrainAnalyzerConfig {
    bool enable;
    bool analyzeChroma;
    bool clipToRestrictedRange;
    float denoiseLevel;
    int denoisePasses;
    int modelWindow;
    int minModelFrames;
    int minFlatBlocks;
    float minFlatFraction;
    float minNoiseLevel;
    float maxNoiseLevel;

    NVEncFilmGrainAnalyzerConfig();
    bool operator==(const NVEncFilmGrainAnalyzerConfig& other) const;
    bool operator!=(const NVEncFilmGrainAnalyzerConfig& other) const { return !(*this == other); }
    tstring print() const;
};

struct NVEncFilmGrainDiagnostics {
    int flatBlocks;
    int totalBlocks;
    int modelFrames;
    std::array<float, 3> noiseStdDev;
    std::array<uint64_t, 3> observations;
    bool reliable;
    bool sceneReset;
    bool modelHeld;

    NVEncFilmGrainDiagnostics();
};

// Per-picture result attached to RGYFrameInfo::dataList.  It deliberately uses
// dynamic_cast rather than a new RGYFrameDataType value, keeping this module
// self-contained until the encoder-side integration is enabled.
//
// Consumers must submit every attached result as a parameter update, including
// applyGrain == 0.  The latter explicitly disables a model inherited from the
// previous AV1 frame when analysis is not reliable; reliable() is diagnostic
// and must not be used to skip that update.
class RGYFrameDataFilmGrain : public RGYFrameData {
public:
    RGYFrameDataFilmGrain();
    RGYFrameDataFilmGrain(const NV_ENC_FILM_GRAIN_PARAMS_AV1& params,
        const NVEncFilmGrainDiagnostics& diagnostics, int64_t timestamp, int inputFrameId);
    virtual ~RGYFrameDataFilmGrain();

    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params() const { return m_params; }
    const NVEncFilmGrainDiagnostics& diagnostics() const { return m_diagnostics; }
    bool hasUpdate() const { return true; }
    bool applyGrain() const { return m_params.applyGrain != 0; }
    bool reliable() const { return m_diagnostics.reliable; }
    int64_t timestamp() const { return m_timestamp; }
    int inputFrameId() const { return m_inputFrameId; }

private:
    NV_ENC_FILM_GRAIN_PARAMS_AV1 m_params;
    NVEncFilmGrainDiagnostics m_diagnostics;
    int64_t m_timestamp;
    int m_inputFrameId;
};

std::shared_ptr<RGYFrameDataFilmGrain> nvenc_film_grain_get_frame_data(const RGYFrameInfo *frame);
void nvenc_film_grain_erase_frame_data(std::vector<std::shared_ptr<RGYFrameData>>& dataList);

class NVEncFilterParamFilmGrain : public NVEncFilterParam {
public:
    NVEncFilmGrainAnalyzerConfig filmGrain;

    NVEncFilterParamFilmGrain();
    virtual ~NVEncFilterParamFilmGrain();
    virtual tstring print() const override;
};

class NVEncFilterFilmGrain : public NVEncFilter {
public:
    NVEncFilterFilmGrain();
    virtual ~NVEncFilterFilmGrain();

    virtual RGY_ERR init(std::shared_ptr<NVEncFilterParam> pParam, std::shared_ptr<RGYLog> pPrintMes) override;
    virtual void resetTemporalState() override;

protected:
    virtual RGY_ERR run_filter(const RGYFrameInfo *pInputFrame, RGYFrameInfo **ppOutputFrames,
        int *pOutputFrameNum, cudaStream_t stream) override;
    virtual void close() override;

private:
    struct AnalyzerState;

    std::unique_ptr<CUFrameBuf> m_denoiseWork;
    std::unique_ptr<CUMemBufPair> m_blockMetrics;
    std::unique_ptr<CUMemBufPair> m_blockMask;
    std::unique_ptr<CUMemBufPair> m_sigmaMap;
    std::unique_ptr<CUMemBufPair> m_modelStats;
    std::unique_ptr<AnalyzerState> m_state;
    int m_blocksX;
    int m_blocksY;
};

