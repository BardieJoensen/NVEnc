// -----------------------------------------------------------------------------------------
// NVEnc by rigaya
// -----------------------------------------------------------------------------------------
// The MIT License
//
// Copyright (c) 2014-2026 rigaya
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
// ------------------------------------------------------------------------------------------

#pragma once
#ifndef __NVENC_FILM_GRAIN_H__
#define __NVENC_FILM_GRAIN_H__

#include <cstdint>
#include <memory>
#include <vector>

#include "rgy_osdep.h"
#include "rgy_tchar.h"

#pragma warning (push)
#pragma warning (disable: 4819)
#include "nvEncodeAPI.h"
#pragma warning (pop)

// An AOM filmgrn1 interval. startTime and endTime use the format's 10 MHz
// timebase and describe [startTime, endTime). params contains a fully resolved
// model even when the source entry used update_parameters=0.
struct NVEncFilmGrainTableEntry {
    int64_t startTime;
    int64_t endTime;
    uint16_t randomSeed;
    bool sourceUpdateParameters;
    NV_ENC_FILM_GRAIN_PARAMS_AV1 params;
};

// Immutable after construction so references returned by lookup() remain valid
// for the lifetime of the table.
class NVEncFilmGrainTable {
public:
    static std::unique_ptr<const NVEncFilmGrainTable> load(
        const tstring& path, bool clipToRestrictedRange, tstring& error);

    const NVEncFilmGrainTableEntry& lookup(int64_t timestamp10Mhz) const noexcept;
    const NVEncFilmGrainTableEntry& off() const noexcept;
    const std::vector<NVEncFilmGrainTableEntry>& entries() const noexcept;
    bool empty() const noexcept;
    bool clipToRestrictedRange() const noexcept;

private:
    NVEncFilmGrainTable(std::vector<NVEncFilmGrainTableEntry>&& entries,
        bool clipToRestrictedRange);

    std::vector<NVEncFilmGrainTableEntry> m_entries;
    NVEncFilmGrainTableEntry m_off;
    bool m_clipToRestrictedRange;
};

// Writes entries as an AOM filmgrn1 table readable by NVEncFilmGrainTable::load
// (and by other consumers of the format, e.g. SvtAv1EncApp --fgs-table).
// Entries must be apply_grain=1 with increasing, non-overlapping [start,end)
// in the 10 MHz timebase; grain-off periods are represented by gaps.
bool nvenc_film_grain_table_write(const tstring& path,
    const std::vector<NVEncFilmGrainTableEntry>& entries, tstring& error);

#endif // __NVENC_FILM_GRAIN_H__
