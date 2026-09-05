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

#include "NVEncFilmGrain.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <charconv>
#include <cstdio>
#include <filesystem>
#include <fcntl.h>
#include <sstream>
#include <string>
#include <utility>
#if defined(_WIN32)
#include <io.h>
#include <process.h>
#include <share.h>
#include <sys/stat.h>
#else
#include <unistd.h>
#endif

// The filmgrn1 grammar and AV1 field semantics follow libaom's grain table
// implementation:
// https://aomedia.googlesource.com/aom/+/refs/heads/main/aom_dsp/grain_table.c
// Copyright (c) 2016, Alliance for Open Media. All rights reserved. The source
// is available under the BSD 2-Clause License and the Alliance for Open Media
// Patent License 1.0.

namespace {

static constexpr const char *FILM_GRAIN_MAGIC = "filmgrn1";

struct FilmGrainToken {
    std::string text;
    size_t line;
    size_t column;
};

class FilmGrainTokenReader {
public:
    explicit FilmGrainTokenReader(const std::string& text) :
        m_text(text),
        m_pos(0),
        m_line(1),
        m_column(1) {
    }

    bool read(FilmGrainToken& token) {
        skipWhitespace();
        if (m_pos == m_text.size()) {
            return false;
        }

        token.line = m_line;
        token.column = m_column;
        const size_t start = m_pos;
        while (m_pos < m_text.size() && !isWhitespace(m_text[m_pos])) {
            advance();
        }
        token.text.assign(m_text.data() + start, m_pos - start);
        return true;
    }

    size_t line() const noexcept {
        return m_line;
    }

    size_t column() const noexcept {
        return m_column;
    }

private:
    static bool isWhitespace(char c) noexcept {
        switch (c) {
        case ' ':
        case '\t':
        case '\r':
        case '\n':
        case '\f':
        case '\v':
            return true;
        default:
            return false;
        }
    }

    void advance() noexcept {
        if (m_text[m_pos++] == '\n') {
            ++m_line;
            m_column = 1;
        } else {
            ++m_column;
        }
    }

    void skipWhitespace() noexcept {
        while (m_pos < m_text.size() && isWhitespace(m_text[m_pos])) {
            advance();
        }
    }

    const std::string& m_text;
    size_t m_pos;
    size_t m_line;
    size_t m_column;
};

static tstring toTString(const std::string& str) {
    return tstring(str.begin(), str.end());
}

static bool fail(tstring& error, size_t line, size_t column,
    const std::string& message) {
    std::ostringstream stream;
    stream << "Invalid film grain table at line " << line << ", column "
           << column << ": " << message;
    error = toTString(stream.str());
    return false;
}

static bool readToken(FilmGrainTokenReader& reader, FilmGrainToken& token,
    const char *description, tstring& error) {
    if (!reader.read(token)) {
        std::ostringstream stream;
        stream << "expected " << description << ", but reached end of file";
        return fail(error, reader.line(), reader.column(), stream.str());
    }
    return true;
}

static bool expect(FilmGrainTokenReader& reader, const char *expected,
    tstring& error) {
    FilmGrainToken token;
    if (!readToken(reader, token, expected, error)) {
        return false;
    }
    if (token.text != expected) {
        std::ostringstream stream;
        stream << "expected '" << expected << "', found '" << token.text << "'";
        return fail(error, token.line, token.column, stream.str());
    }
    return true;
}

static bool parseIntegerToken(const FilmGrainToken& token, int64_t& value,
    const char *description, tstring& error) {
    const char *first = token.text.data();
    const char *last = first + token.text.size();
    bool positiveSign = false;
    if (first != last && *first == '+') {
        positiveSign = true;
        ++first;
    }
    if (first == last) {
        std::ostringstream stream;
        stream << description << " must be an integer, found '" << token.text << "'";
        return fail(error, token.line, token.column, stream.str());
    }

    int64_t parsed = 0;
    const auto result = std::from_chars(first, last, parsed, 10);
    if (result.ec != std::errc() || result.ptr != last ||
        (positiveSign && parsed < 0)) {
        std::ostringstream stream;
        stream << description << " must be an integer, found '" << token.text << "'";
        return fail(error, token.line, token.column, stream.str());
    }
    value = parsed;
    return true;
}

static bool readInteger(FilmGrainTokenReader& reader, int64_t& value,
    const char *description, int64_t minimum, int64_t maximum, tstring& error) {
    FilmGrainToken token;
    if (!readToken(reader, token, description, error) ||
        !parseIntegerToken(token, value, description, error)) {
        return false;
    }
    if (value < minimum || value > maximum) {
        std::ostringstream stream;
        stream << description << " must be in [" << minimum << ", " << maximum
               << "], found " << value;
        return fail(error, token.line, token.column, stream.str());
    }
    return true;
}

static bool readBool(FilmGrainTokenReader& reader, bool& value,
    const char *description, tstring& error) {
    int64_t integer = 0;
    if (!readInteger(reader, integer, description, 0, 1, error)) {
        return false;
    }
    value = integer != 0;
    return true;
}

template<size_t N>
static bool readScalingPoints(FilmGrainTokenReader& reader, const char *label,
    const char *planeName, uint32_t maximumCount, uint32_t& count,
    uint8_t (&pointValue)[N], uint8_t (&pointScaling)[N], tstring& error) {
    static_assert(N <= 14, "Unexpected AV1 scaling point array size.");
    if (!expect(reader, label, error)) {
        return false;
    }

    int64_t parsedCount = 0;
    std::string countDescription = std::string(planeName) + " scaling point count";
    if (!readInteger(reader, parsedCount, countDescription.c_str(), 0,
        maximumCount, error)) {
        return false;
    }
    count = static_cast<uint32_t>(parsedCount);

    int previousValue = -1;
    for (uint32_t i = 0; i < count; ++i) {
        int64_t x = 0;
        int64_t y = 0;
        std::ostringstream xDescription;
        xDescription << planeName << " scaling point " << i << " x";
        std::ostringstream yDescription;
        yDescription << planeName << " scaling point " << i << " y";
        if (!readInteger(reader, x, xDescription.str().c_str(), 0, 255, error) ||
            !readInteger(reader, y, yDescription.str().c_str(), 0, 255, error)) {
            return false;
        }
        if (x <= previousValue) {
            std::ostringstream stream;
            stream << planeName << " scaling point x values must be strictly "
                   << "increasing (point " << i << " is " << x
                   << ", previous is " << previousValue << ")";
            return fail(error, reader.line(), reader.column(), stream.str());
        }
        pointValue[i] = static_cast<uint8_t>(x);
        pointScaling[i] = static_cast<uint8_t>(y);
        previousValue = static_cast<int>(x);
    }
    return true;
}

template<size_t N>
static bool readCoefficients(FilmGrainTokenReader& reader, const char *label,
    const char *planeName, uint32_t count, uint8_t (&destination)[N],
    tstring& error) {
    if (!expect(reader, label, error)) {
        return false;
    }
    if (count > N) {
        return fail(error, reader.line(), reader.column(),
            std::string("internal coefficient count overflow for ") + planeName);
    }
    for (uint32_t i = 0; i < count; ++i) {
        int64_t coefficient = 0;
        std::ostringstream description;
        description << planeName << " AR coefficient " << i;
        if (!readInteger(reader, coefficient, description.str().c_str(),
            -128, 127, error)) {
            return false;
        }
        destination[i] = static_cast<uint8_t>(coefficient + 128);
    }
    return true;
}

static bool parseUpdatedParameters(FilmGrainTokenReader& reader,
    bool applyGrain, bool clipToRestrictedRange,
    NV_ENC_FILM_GRAIN_PARAMS_AV1& params, tstring& error) {
    params = {};
    params.applyGrain = applyGrain ? 1u : 0u;
    params.clipToRestrictedRange = clipToRestrictedRange ? 1u : 0u;

    if (!expect(reader, "p", error)) {
        return false;
    }

    int64_t arCoeffLag = 0;
    int64_t arCoeffShift = 0;
    int64_t grainScaleShift = 0;
    int64_t scalingShift = 0;
    bool chromaScalingFromLuma = false;
    bool overlapFlag = false;
    int64_t cbMult = 0;
    int64_t cbLumaMult = 0;
    int64_t cbOffset = 0;
    int64_t crMult = 0;
    int64_t crLumaMult = 0;
    int64_t crOffset = 0;
    if (!readInteger(reader, arCoeffLag, "AR coefficient lag", 0, 3, error) ||
        !readInteger(reader, arCoeffShift, "AR coefficient shift", 6, 9, error) ||
        !readInteger(reader, grainScaleShift, "grain scale shift", 0, 3, error) ||
        !readInteger(reader, scalingShift, "scaling shift", 8, 11, error) ||
        !readBool(reader, chromaScalingFromLuma, "chroma scaling from luma", error) ||
        !readBool(reader, overlapFlag, "overlap flag", error) ||
        !readInteger(reader, cbMult, "Cb multiplier", 0, 255, error) ||
        !readInteger(reader, cbLumaMult, "Cb luma multiplier", 0, 255, error) ||
        !readInteger(reader, cbOffset, "Cb offset", 0, 511, error) ||
        !readInteger(reader, crMult, "Cr multiplier", 0, 255, error) ||
        !readInteger(reader, crLumaMult, "Cr luma multiplier", 0, 255, error) ||
        !readInteger(reader, crOffset, "Cr offset", 0, 511, error)) {
        return false;
    }

    params.arCoeffLag = static_cast<uint32_t>(arCoeffLag);
    params.arCoeffShiftMinus6 = static_cast<uint32_t>(arCoeffShift - 6);
    params.grainScaleShift = static_cast<uint32_t>(grainScaleShift);
    params.grainScalingMinus8 = static_cast<uint32_t>(scalingShift - 8);
    params.chromaScalingFromLuma = chromaScalingFromLuma ? 1u : 0u;
    params.overlapFlag = overlapFlag ? 1u : 0u;
    params.cbMult = static_cast<uint8_t>(cbMult);
    params.cbLumaMult = static_cast<uint8_t>(cbLumaMult);
    params.cbOffset = static_cast<uint16_t>(cbOffset);
    params.crMult = static_cast<uint8_t>(crMult);
    params.crLumaMult = static_cast<uint8_t>(crLumaMult);
    params.crOffset = static_cast<uint16_t>(crOffset);

    uint32_t numYPoints = 0;
    uint32_t numCbPoints = 0;
    uint32_t numCrPoints = 0;
    if (!readScalingPoints(reader, "sY", "Y", 14, numYPoints,
            params.pointYValue, params.pointYScaling, error) ||
        !readScalingPoints(reader, "sCb", "Cb", 10, numCbPoints,
            params.pointCbValue, params.pointCbScaling, error) ||
        !readScalingPoints(reader, "sCr", "Cr", 10, numCrPoints,
            params.pointCrValue, params.pointCrScaling, error)) {
        return false;
    }

    if (chromaScalingFromLuma && (numCbPoints != 0 || numCrPoints != 0)) {
        return fail(error, reader.line(), reader.column(),
            "Cb and Cr scaling point counts must be zero when chroma scaling "
            "from luma is enabled");
    }
    // NVENC AV1 currently supports YUV 4:2:0. In 4:2:0 AV1 does not signal
    // chroma scaling points when there are no luma scaling points.
    if (numYPoints == 0 && (numCbPoints != 0 || numCrPoints != 0)) {
        return fail(error, reader.line(), reader.column(),
            "Cb and Cr scaling point counts must be zero for 4:2:0 when the "
            "Y scaling point count is zero");
    }
    if ((numCbPoints == 0) != (numCrPoints == 0)) {
        return fail(error, reader.line(), reader.column(),
            "Cb and Cr scaling point counts must both be zero or both be "
            "non-zero for 4:2:0");
    }
    params.numYPoints = numYPoints;
    params.numCbPoints = numCbPoints;
    params.numCrPoints = numCrPoints;

    const uint32_t lumaCoefficientCount =
        2u * params.arCoeffLag * (params.arCoeffLag + 1u);
    const uint32_t chromaCoefficientCount = lumaCoefficientCount + 1u;
    if (!readCoefficients(reader, "cY", "Y", lumaCoefficientCount,
            params.arCoeffsYPlus128, error) ||
        !readCoefficients(reader, "cCb", "Cb", chromaCoefficientCount,
            params.arCoeffsCbPlus128, error) ||
        !readCoefficients(reader, "cCr", "Cr", chromaCoefficientCount,
            params.arCoeffsCrPlus128, error)) {
        return false;
    }
    return true;
}

static bool parseTable(const std::string& text, bool clipToRestrictedRange,
    std::vector<NVEncFilmGrainTableEntry>& entries, tstring& error) {
    FilmGrainTokenReader reader(text);
    if (!expect(reader, FILM_GRAIN_MAGIC, error)) {
        return false;
    }

    NV_ENC_FILM_GRAIN_PARAMS_AV1 inheritedParams = {};
    bool haveInheritedParams = false;
    int64_t previousStart = -1;
    int64_t previousEnd = -1;

    for (;;) {
        FilmGrainToken marker;
        if (!reader.read(marker)) {
            break;
        }
        if (marker.text != "E") {
            std::ostringstream stream;
            stream << "expected entry marker 'E', found '" << marker.text << "'";
            return fail(error, marker.line, marker.column, stream.str());
        }

        NVEncFilmGrainTableEntry entry = {};
        bool applyGrain = false;
        bool updateParameters = false;
        int64_t randomSeed = 0;
        if (!readInteger(reader, entry.startTime, "entry start time", 0,
                INT64_MAX, error) ||
            !readInteger(reader, entry.endTime, "entry end time", 0,
                INT64_MAX, error) ||
            !readBool(reader, applyGrain, "apply grain", error) ||
            !readInteger(reader, randomSeed, "random seed", 0, UINT16_MAX,
                error) ||
            !readBool(reader, updateParameters, "update parameters", error)) {
            return false;
        }
        if (entry.endTime <= entry.startTime) {
            return fail(error, marker.line, marker.column,
                "entry end time must be greater than its start time");
        }
        if (!entries.empty()) {
            if (entry.startTime < previousStart) {
                return fail(error, marker.line, marker.column,
                    "entries must be ordered by increasing start time");
            }
            if (entry.startTime < previousEnd) {
                std::ostringstream stream;
                stream << "entry [" << entry.startTime << ", " << entry.endTime
                       << ") overlaps previous entry ending at " << previousEnd;
                return fail(error, marker.line, marker.column, stream.str());
            }
        }

        entry.randomSeed = static_cast<uint16_t>(randomSeed);
        entry.sourceUpdateParameters = updateParameters;
        if (updateParameters) {
            if (!parseUpdatedParameters(reader, applyGrain,
                    clipToRestrictedRange, entry.params, error)) {
                return false;
            }
            // Parameters on an apply_grain=0 frame are not present in the AV1
            // bitstream, so they cannot become an inheritance source.
            if (applyGrain) {
                inheritedParams = entry.params;
                haveInheritedParams = true;
            } else {
                entry.params = {};
            }
        } else if (applyGrain) {
            if (!haveInheritedParams) {
                return fail(error, marker.line, marker.column,
                    "update_parameters=0 cannot inherit before an active "
                    "entry supplies parameters");
            }
            entry.params = inheritedParams;
            entry.params.applyGrain = 1;
            entry.params.clipToRestrictedRange =
                clipToRestrictedRange ? 1u : 0u;
        } else {
            entry.params = {};
        }

        entries.push_back(entry);
        previousStart = entry.startTime;
        previousEnd = entry.endTime;
    }
    return true;
}

static bool readFile(const tstring& path, std::string& text, tstring& error) {
    FILE *file = nullptr;
    const int openError = _tfopen_s(&file, path.c_str(), _T("rb"));
    if (openError != 0 || file == nullptr) {
        error = tstring(_T("Unable to open film grain table: ")) + path;
        return false;
    }

    std::array<char, 64 * 1024> buffer;
    for (;;) {
        const size_t bytesRead = std::fread(buffer.data(), 1, buffer.size(), file);
        text.append(buffer.data(), bytesRead);
        if (bytesRead != buffer.size()) {
            if (std::ferror(file)) {
                std::fclose(file);
                error = tstring(_T("Unable to read film grain table: ")) + path;
                return false;
            }
            break;
        }
    }
    std::fclose(file);
    return true;
}

} // namespace

NVEncFilmGrainTable::NVEncFilmGrainTable(
    std::vector<NVEncFilmGrainTableEntry>&& entries,
    bool clipToRestrictedRange) :
    m_entries(std::move(entries)),
    m_off(),
    m_clipToRestrictedRange(clipToRestrictedRange) {
}

std::unique_ptr<const NVEncFilmGrainTable> NVEncFilmGrainTable::load(
    const tstring& path, bool clipToRestrictedRange, tstring& error) {
    error.clear();
    std::string text;
    if (!readFile(path, text, error)) {
        return nullptr;
    }

    std::vector<NVEncFilmGrainTableEntry> entries;
    if (!parseTable(text, clipToRestrictedRange, entries, error)) {
        return nullptr;
    }
    return std::unique_ptr<const NVEncFilmGrainTable>(
        new NVEncFilmGrainTable(std::move(entries), clipToRestrictedRange));
}

const NVEncFilmGrainTableEntry& NVEncFilmGrainTable::lookup(
    int64_t timestamp10Mhz) const noexcept {
    const auto entry = std::lower_bound(m_entries.begin(), m_entries.end(),
        timestamp10Mhz,
        [](const NVEncFilmGrainTableEntry& candidate, int64_t timestamp) {
            return candidate.endTime <= timestamp;
        });
    if (entry != m_entries.end() &&
        entry->startTime <= timestamp10Mhz && timestamp10Mhz < entry->endTime) {
        return *entry;
    }
    return m_off;
}

const NVEncFilmGrainTableEntry& NVEncFilmGrainTable::off() const noexcept {
    return m_off;
}

const std::vector<NVEncFilmGrainTableEntry>&
NVEncFilmGrainTable::entries() const noexcept {
    return m_entries;
}

bool NVEncFilmGrainTable::empty() const noexcept {
    return m_entries.empty();
}

bool NVEncFilmGrainTable::clipToRestrictedRange() const noexcept {
    return m_clipToRestrictedRange;
}

static bool tableOutputIsRegular(const tstring& path, tstring& error) {
    std::error_code ec;
    const auto status = std::filesystem::symlink_status(path, ec);
    if (ec && ec != std::errc::no_such_file_or_directory) {
        error = _T("cannot inspect film grain table destination: ") + path;
        return false;
    }
    // Never atomically replace a device, directory, or symlink such as /dev/full.
    if (std::filesystem::exists(status) && !std::filesystem::is_regular_file(status)) {
        error = _T("film grain table destination must be a regular file: ") + path;
        return false;
    }
    return true;
}

NVEncFilmGrainTableWriter::NVEncFilmGrainTableWriter(
    const tstring& path, const tstring& temporary, FILE *file) :
    m_path(path), m_temporary(temporary), m_file(file) {
}

NVEncFilmGrainTableWriter::~NVEncFilmGrainTableWriter() {
    if (m_file) fclose(m_file);
    if (!m_temporary.empty()) _tremove(m_temporary.c_str());
}

std::unique_ptr<NVEncFilmGrainTableWriter> NVEncFilmGrainTableWriter::create(
    const tstring& path, tstring& error) {
    error.clear();
    if (!tableOutputIsRegular(path, error)) return nullptr;
    static std::atomic<uint64_t> serial{0};
    for (int attempt = 0; attempt < 100; ++attempt) {
#if defined(_WIN32)
        const auto processId = _getpid();
#else
        const auto processId = getpid();
#endif
        std::basic_ostringstream<TCHAR> suffix;
        suffix << _T(".fgs-") << processId << _T("-") << serial++ << _T(".tmp");
        const auto temporary = path + suffix.str();
        int fd = -1;
#if defined(_WIN32)
        const auto openError = _tsopen_s(&fd, temporary.c_str(),
            _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY, _SH_DENYRW, _S_IREAD | _S_IWRITE);
#else
        fd = open(temporary.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0666);
        const int openError = fd < 0 ? errno : 0;
#endif
        if (openError == EEXIST) continue;
        if (fd < 0) {
            error = _T("failed to create temporary film grain table beside: ") + path;
            return nullptr;
        }
#if defined(_WIN32)
        FILE *file = _tfdopen(fd, _T("wb"));
        if (!file) _close(fd);
#else
        FILE *file = fdopen(fd, "wb");
        if (!file) ::close(fd);
#endif
        if (!file) {
            _tremove(temporary.c_str());
            error = _T("failed to open temporary film grain table: ") + path;
            return nullptr;
        }
        return std::unique_ptr<NVEncFilmGrainTableWriter>(
            new NVEncFilmGrainTableWriter(path, temporary, file));
    }
    error = _T("could not reserve a temporary film grain table: ") + path;
    return nullptr;
}

bool NVEncFilmGrainTableWriter::write(
    const std::vector<NVEncFilmGrainTableEntry>& entries, tstring& error) {
    error.clear();
    if (!m_file) {
        error = _T("film grain table has already been finalized: ") + m_path;
        return false;
    }
    std::ostringstream out;
    out << "filmgrn1\n";
    if (entries.empty()) {
        out << "E 0 " << INT64_MAX << " 0 0 0\n";
    }
    int64_t previousEnd = -1;
    for (const auto& entry : entries) {
        if (entry.startTime < 0 || entry.endTime <= entry.startTime || entry.startTime < previousEnd) {
            error = _T("table entries must have increasing, non-overlapping [start,end) intervals");
            return false;
        }
        previousEnd = entry.endTime;
        const auto& p = entry.params;
        if (!p.applyGrain) {
            out << "E " << entry.startTime << " " << entry.endTime << " 0 0 0\n";
            continue;
        }
        out << "E " << entry.startTime << " " << entry.endTime << " 1 "
            << entry.randomSeed << " 1\n";
        out << "p " << p.arCoeffLag << " " << (p.arCoeffShiftMinus6 + 6) << " "
            << p.grainScaleShift << " " << (p.grainScalingMinus8 + 8) << " "
            << p.chromaScalingFromLuma << " " << p.overlapFlag << " "
            << static_cast<int>(p.cbMult) << " " << static_cast<int>(p.cbLumaMult) << " "
            << static_cast<int>(p.cbOffset) << " " << static_cast<int>(p.crMult) << " "
            << static_cast<int>(p.crLumaMult) << " " << static_cast<int>(p.crOffset) << "\n";
        auto writePoints = [&out](const char *marker, const uint32_t count,
            const uint8_t *values, const uint8_t *scalings) {
            out << marker << " " << count;
            for (uint32_t i = 0; i < count; ++i) {
                out << " " << static_cast<int>(values[i]) << " " << static_cast<int>(scalings[i]);
            }
            out << "\n";
        };
        writePoints("sY", p.numYPoints, p.pointYValue, p.pointYScaling);
        writePoints("sCb", p.numCbPoints, p.pointCbValue, p.pointCbScaling);
        writePoints("sCr", p.numCrPoints, p.pointCrValue, p.pointCrScaling);
        const uint32_t lumaCoefficients = 2u * p.arCoeffLag * (p.arCoeffLag + 1u);
        auto writeCoefficients = [&out](const char *marker, const uint32_t count, const uint8_t *plus128) {
            out << marker;
            for (uint32_t i = 0; i < count; ++i) {
                out << " " << (static_cast<int>(plus128[i]) - 128);
            }
            out << "\n";
        };
        writeCoefficients("cY", lumaCoefficients, p.arCoeffsYPlus128);
        writeCoefficients("cCb", lumaCoefficients + 1, p.arCoeffsCbPlus128);
        writeCoefficients("cCr", lumaCoefficients + 1, p.arCoeffsCrPlus128);
    }
    const auto text = out.str();
    bool ok = fwrite(text.data(), 1, text.size(), m_file) == text.size();
    if (fflush(m_file) != 0) ok = false;
    if (fclose(m_file) != 0) ok = false;
    m_file = nullptr;
    if (!ok) {
        error = _T("failed to write or flush film grain table: ") + m_path;
        return false;
    }
    if (!tableOutputIsRegular(m_path, error)) return false;
#if defined(_WIN32)
    ok = MoveFileEx(m_temporary.c_str(), m_path.c_str(), MOVEFILE_REPLACE_EXISTING) != 0;
#else
    ok = rename(m_temporary.c_str(), m_path.c_str()) == 0;
#endif
    if (!ok) {
        error = _T("failed to replace film grain table: ") + m_path;
        return false;
    }
    m_temporary.clear();
    return true;
}

bool nvenc_film_grain_table_write(const tstring& path,
    const std::vector<NVEncFilmGrainTableEntry>& entries, tstring& error) {
    auto writer = NVEncFilmGrainTableWriter::create(path, error);
    return writer && writer->write(entries, error);
}
