// Read-only audit helper: remove unrelated metadata OBUs from a packet copy.
// Grain syntax is carried by sequence/frame headers, never metadata OBUs.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

inline bool prepare_av1_scan_packet(uint8_t *data, size_t& size,
    bool& hasSequence, unsigned& metadataSkipped) {
    size_t read = 0, write = 0;
    hasSequence = false;
    while (read < size) {
        const size_t begin = read;
        const uint8_t header = data[read++];
        if (header & 0x81) return false; // forbidden/reserved bits
        const unsigned type = (header >> 3) & 15;
        if (header & 4) {
            if (read == size) return false;
            ++read; // extension header
        }
        uint64_t payload = size - read;
        if (header & 2) {
            payload = 0;
            bool ended = false;
            for (unsigned i = 0; i < 8 && read < size; ++i) {
                const uint8_t byte = data[read++];
                payload |= static_cast<uint64_t>(byte & 127) << (i * 7);
                if (!(byte & 128)) { ended = true; break; }
            }
            if (!ended || payload > size - read) return false;
        }
        read += static_cast<size_t>(payload);
        if (type == 5) {
            ++metadataSkipped;
        } else {
            hasSequence |= type == 1;
            const size_t bytes = read - begin;
            memmove(data + write, data + begin, bytes);
            write += bytes;
        }
    }
    size = write;
    return true;
}
