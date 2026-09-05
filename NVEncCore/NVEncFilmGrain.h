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
#include <cstdio>
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

// Reserve a temporary file next to the destination during initialization.
// Only write() publishes it; destruction after an aborted encode discards it.
class NVEncFilmGrainTableWriter {
public:
    static std::unique_ptr<NVEncFilmGrainTableWriter> create(const tstring& path, tstring& error);
    ~NVEncFilmGrainTableWriter();
    bool write(const std::vector<NVEncFilmGrainTableEntry>& entries, tstring& error);
    NVEncFilmGrainTableWriter(const NVEncFilmGrainTableWriter&) = delete;
    NVEncFilmGrainTableWriter& operator=(const NVEncFilmGrainTableWriter&) = delete;

private:
    NVEncFilmGrainTableWriter(const tstring& path, const tstring& temporary, FILE *file);
    tstring m_path;
    tstring m_temporary;
    FILE *m_file;
};

// Atomically replace a regular file with a standard AOM filmgrn1 table.
// Entries use increasing, non-overlapping [start,end) 10 MHz intervals.
// An empty model list writes one explicit grain-off interval, so reusing an
// output path for clean footage cannot leave an earlier source's model behind.
bool nvenc_film_grain_table_write(const tstring& path,
    const std::vector<NVEncFilmGrainTableEntry>& entries, tstring& error);

#endif // __NVENC_FILM_GRAIN_H__
