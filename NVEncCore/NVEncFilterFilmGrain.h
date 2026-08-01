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
#include "NVEncFilmGrain.h"
#include "NVEncFilmGrainModel.h"
#include "nvEncodeAPI.h"

enum FGSDenoiseEngine : int {
    FGS_DENOISE_FFT3D = 0,     // frequency-domain Wiener denoise on luma (NVEncFilterDenoiseFFT3D)
    FGS_DENOISE_BILATERAL = 1, // 5x5 edge-aware bilateral (weaker; kept for A/B and fallback)
    FGS_DENOISE_MOTION = 2,    // motion-compensated dual-surface degrain (original is retained for modelling)
};

// Quality-first defaults for the CUDA AV1 grain analyzer.  A denoiseLevel of
// zero selects the noise level measured from flat 32x32 luma blocks.  Positive
// values are expressed in 8-bit code-value units and are scaled for 10-bit
// input.  The parser intentionally does not own this type so the analyzer can
// also be exercised directly by tests and other frontends.
struct NVEncFilmGrainAnalyzerConfig {
    bool enable;
    bool analyzeChroma;
    bool clipToRestrictedRange;
    int denoiser;              // FGSDenoiseEngine
    int fft3dTemporal;         // FFT3D temporal radius bt: 1 (spatial) or 2 (prev+cur, delay-free)
    int motionRefs;            // causal motion references: 2 (default) or 1 (reduced cost)
    float residualRetain;      // fraction of the measured luma residual kept in the base layer (0.0 - 0.9),
                               // or -1.0 for content-adaptive auto retention; signalled luma synthesis
                               // is scaled by sqrt(1 - retain^2) so total grain variance is preserved
    bool modelFromSource;      // fit the AR model from plane-removed source flat blocks rather than
                               // from the denoiser's residual, which arrives already whitened
                               // (tests/fgs/FINDINGS-2026-08-01-SOURCE-FIT.md)
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
    std::pair<int, int> compute_capability;
    tstring tableOutPath;          // write measured grain as an AOM filmgrn1 table (empty = off)
    rgy_rational<int> timebase;    // timebase of the frame timestamps (for the table's 10 MHz intervals)

    NVEncFilterParamFilmGrain();
    virtual ~NVEncFilterParamFilmGrain();
    virtual tstring print() const override;
};

class NVEncFilterDenoiseFFT3D;
class NVEncFilterParamDenoiseFFT3D;
class NVEncFilterDegrain;
class NVEncFilterParamDegrain;

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

    void recordTableEntry(int64_t timestamp, int64_t duration, const NV_ENC_FILM_GRAIN_PARAMS_AV1& params);
    void writeTableFile();

    std::unique_ptr<CUFrameBuf> m_denoiseWork;
    std::unique_ptr<NVEncFilterDenoiseFFT3D> m_fft3d;
    std::shared_ptr<NVEncFilterParamDenoiseFFT3D> m_fft3dParam;
    float m_fft3dSigma;
    std::unique_ptr<NVEncFilterDegrain> m_motionDegrain;
    std::shared_ptr<NVEncFilterParamDegrain> m_motionDegrainParam;
    std::unique_ptr<CUMemBufPair> m_blockMetrics;
    std::unique_ptr<CUMemBufPair> m_blockMask;
    std::unique_ptr<CUMemBufPair> m_sigmaMap;
    std::unique_ptr<CUMemBufPair> m_strengthLut;
    std::unique_ptr<CUMemBufPair> m_sceneCounts;
    std::unique_ptr<CUMemBufPair> m_modelStats;
    std::unique_ptr<AnalyzerState> m_state;
    tstring m_tableOutPath;
    rgy_rational<int> m_tableTimebase;
    int64_t m_tableFrameDuration10MHz;
    std::vector<NVEncFilmGrainTableEntry> m_tableEntries;
    bool m_tableWritten;
    int m_blocksX;
    int m_blocksY;
};

