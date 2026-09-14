// Copyright (c) 2026 NVEnc contributors. SPDX-License-Identifier: MIT
#pragma once

#include <algorithm>
#include <charconv>
#include <cstdint>
#include <istream>
#include <limits>
#include <string>
#include <vector>

// Optional, explicit boundaries for a frame-preserving source pipeline. Loading
// and completion are checked, so a shortened or reordered input cannot silently
// use another frame's scene marker. No schedule means no behavior change.
class NVEncFilmGrainSceneSchedule {
public:
    bool load(std::istream& input, std::string& error) {
        *this = {};
        std::string line;
        if (!std::getline(input, line)) return fail(error, "missing scene schedule header");
        stripCR(line);
        const std::string prefix = "FGS_SCENE_CUTS_V1 ";
        int frames = 0;
        if (line.compare(0, prefix.size(), prefix) != 0
            || !number(line.substr(prefix.size()), frames) || frames <= 0)
            return fail(error, "expected FGS_SCENE_CUTS_V1 followed by a positive frame count");
        std::vector<int> cuts;
        while (std::getline(input, line)) {
            stripCR(line);
            if (line.empty()) continue;
            int frame = 0;
            if (!number(line, frame) || frame >= frames
                || (!cuts.empty() && frame <= cuts.back()))
                return fail(error, "scene indices must be unique, increasing, and within the declared frame count");
            cuts.push_back(frame);
        }
        if (!input.eof()) return fail(error, "could not read the complete scene schedule");
        m_frames = frames;
        m_cuts = std::move(cuts);
        return true;
    }

    bool consume(const int inputFrameId, bool& sceneCut) {
        sceneCut = false;
        if (!enabled()) return true;
        if (inputFrameId != m_seen || m_seen >= m_frames) return false;
        sceneCut = std::binary_search(m_cuts.begin(), m_cuts.end(), m_seen);
        ++m_seen;
        return true;
    }
    bool complete() const { return !enabled() || m_seen == m_frames; }
    bool enabled() const { return m_frames > 0; }
    int frames() const { return m_frames; }
    int seen() const { return m_seen; }
    size_t cuts() const { return m_cuts.size(); }

private:
    static bool fail(std::string& error, const char *message) { error = message; return false; }
    static void stripCR(std::string& line) { if (!line.empty() && line.back() == '\r') line.pop_back(); }
    static bool number(const std::string& value, int& result) {
        if (value.empty() || value.size() > 10 || value[0] < '0' || value[0] > '9') return false;
        const auto parsed = std::from_chars(value.data(), value.data() + value.size(), result);
        return parsed.ec == std::errc{} && parsed.ptr == value.data() + value.size() && result >= 0;
    }
    int m_frames = 0;
    int m_seen = 0;
    std::vector<int> m_cuts;
};
