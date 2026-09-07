#pragma once
#include <array>

// Semantic grain constraints which trace_headers can parse without enforcing.
// Independent of AR stability, grain strength, and whether the model is visible.
struct Av1GrainSyntax {
    std::array<int, 3> points{};
    std::array<int, 3> lastPoint{{-1, -1, -1}};
    bool fromLuma = false;
    bool orderedPoints = true;
    void point(int plane, int value) {
        orderedPoints &= value >= 0 && value <= 255 && value > lastPoint[plane];
        lastPoint[plane] = value;
    }
    const char *error(bool is420) const {
        if (!orderedPoints) return "grain scaling point positions are not strictly increasing";
        if (points[0] < 0 || points[0] > 14 || points[1] < 0 || points[1] > 10 || points[2] < 0 || points[2] > 10)
            return "grain scaling point count is outside AV1 limits";
        if (fromLuma && (points[1] || points[2]))
            return "chroma scaling from luma has explicit chroma points";
        if (is420 && !points[0] && (points[1] || points[2]))
            return "4:2:0 chroma grain has no luma scaling points";
        if (is420 && bool(points[1]) != bool(points[2]))
            return "4:2:0 grain must enable both chroma components or neither";
        return nullptr;
    }
};

struct Av1GrainLayout {
    int profile = -1, subsamplingX = -1, subsamplingY = -1;
    bool monochrome = false;
    void sequence(int value) { *this = Av1GrainLayout(); profile = value; }
    bool is420() const {
        // Profile 0 implies 4:2:0; profile 1 implies 4:4:4. Profile 2 is
        // 4:2:2 below 12-bit, with explicit subsampling bits at 12-bit.
        return !monochrome && (profile == 0 || (profile == 2 && subsamplingX == 1 && subsamplingY == 1));
    }
};
