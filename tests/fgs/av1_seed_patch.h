// Bounded helpers for the manual IVF seed experiment; no encoder call sites.
#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>

namespace fgsseed {
// AV1's luma RNG uses the seed directly. Chroma's template initializers
// XOR the seed with the row-7 / row-11 constants. A zero state stays zero.
inline uint16_t replacement(uint16_t seed) {
    return seed == 0 || seed == 46372 || seed == 18904 ? seed + 1 : seed;
}

struct Obu { size_t offset, bytes, headerBytes; unsigned type; };
inline bool split_obus(const uint8_t *data, size_t size, std::vector<Obu>& obus) {
    obus.clear();
    if (!data || !size || size > 32 * 1024 * 1024) return false;
    size_t pos = 0;
    while (pos < size) {
        const size_t begin = pos;
        const uint8_t h = data[pos++];
        if (h & 0x81) return false;
        const unsigned type = (h >> 3) & 15;
        if (!type || (type >= 9 && type <= 14)) return false;
        if (h & 4) {
            if (pos == size || (data[pos] & 7)) return false;
            ++pos;
        }
        uint64_t payload = size - pos;
        if (h & 2) {
            bool ended = false;
            payload = 0;
            for (unsigned i = 0; i < 8 && pos < size; ++i) {
                const uint8_t b = data[pos++];
                payload |= uint64_t(b & 127) << (7 * i);
                if (!(b & 128)) { ended = true; break; }
            }
            if (!ended || payload > UINT32_MAX || payload > size - pos) return false;
        }
        const size_t headerBytes = pos - begin;
        pos += size_t(payload);
        obus.push_back({begin, pos - begin, headerBytes, type});
        if (obus.size() > 4096) return false;
    }
    return true;
}

inline bool read16(const uint8_t *data, size_t size, size_t bit, uint16_t& value) {
    if (!data || size < 2 || bit / 8 >= size ||
        (size - bit / 8) < (16 + bit % 8 + 7) / 8) return false;
    value = 0;
    for (size_t i = 0; i < 16; ++i)
        value = uint16_t((value << 1) | ((data[(bit+i)/8] >> (7-(bit+i)%8)) & 1));
    return true;
}

// Caller must locate the field with a real AV1 parser and validate the OBU.
// Expected-value mismatch never writes; the surrounding bits are untouched.
inline bool patch16(uint8_t *data, size_t size, size_t bit, uint16_t expected) {
    uint16_t found;
    if (!read16(data, size, bit, found) || found != expected) return false;
    const uint16_t next = replacement(found);
    for (size_t i = 0; i < 16; ++i) {
        const auto mask = uint8_t(1u << (7-(bit+i)%8));
        auto& byte = data[(bit+i)/8];
        byte = uint8_t((byte & ~mask) | (((next >> (15-i)) & 1) ? mask : 0));
    }
    return true;
}
}
