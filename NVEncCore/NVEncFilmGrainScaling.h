// Exact AV1 integer strength lookup for offline retention model qualification.
// No encoder call sites. This lookup alone cannot qualify a grain model.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <array>
#include <cstdint>

namespace fgsmodel {
namespace scaling_detail {
inline int floor_shift(const int64_t value, const unsigned shift) {
    const int64_t divisor = int64_t(1) << shift;
    return static_cast<int>(value >= 0 ? value / divisor : -((-value + divisor - 1) / divisor));
}
}

class FilmGrainScalingLut {
public:
    bool valid() const { return m_bitDepth != 0; }
    unsigned bitDepth() const { return m_bitDepth; }

    // Accept only an actual native code; clamping invalid input would silently
    // certify the wrong population. On failure the strength is reset to zero
    // and the caller must treat the false return as missing evidence.
    bool lookup(unsigned nativeCode, unsigned& strength) const {
        strength = 0;
        if (!valid() || nativeCode >= (1U << m_bitDepth)) return false;
        const unsigned shift = m_bitDepth - 8;
        const unsigned x = nativeCode >> shift;
        int value = m_lut[x];
        if (shift && x != 255) {
            const int delta = int(m_lut[x + 1]) - value;
            value += scaling_detail::floor_shift(delta * int(nativeCode & ((1U << shift) - 1))
                + (1 << (shift - 1)), shift);
        }
        strength = static_cast<unsigned>(value);
        return true;
    }

    // count=0 is a valid all-zero curve. Inputs are byte-valued AV1 points;
    // require strictly increasing coordinates. The generic interpolation
    // supports up to 14 points; a chroma caller must also enforce its 10-point
    // syntax budget and chroma-from-luma/shared-parameter rules separately.
    // Every attempt discards the previous result, including invalid attempts.
    bool build(const uint8_t* values, const uint8_t* strengths, unsigned count, unsigned bitDepth) {
        *this = {};
        if ((bitDepth != 8 && bitDepth != 10 && bitDepth != 12)
            || count > 14 || (count && (!values || !strengths))) return false;
        for (unsigned i = 1; i < count; ++i)
            if (values[i] <= values[i - 1]) return false;
        if (count) {
            for (unsigned x = 0; x < values[0]; ++x) m_lut[x] = strengths[0];
            for (unsigned i = 1; i < count; ++i) {
                const unsigned width = unsigned(values[i]) - values[i - 1];
                const int deltaY = int(strengths[i]) - strengths[i - 1];
                const int64_t slope = int64_t(deltaY) * ((65536 + (width >> 1)) / width);
                for (unsigned x = 0; x < width; ++x) {
                    m_lut[values[i - 1] + x] = static_cast<uint8_t>(int(strengths[i - 1])
                        + scaling_detail::floor_shift(x * slope + 32768, 16));
                }
            }
            for (unsigned x = values[count - 1]; x < 256; ++x) m_lut[x] = strengths[count - 1];
        }
        m_bitDepth = bitDepth;
        return true;
    }

private:
    unsigned m_bitDepth = 0;
    std::array<uint8_t, 256> m_lut{};
};
} // namespace fgsmodel
