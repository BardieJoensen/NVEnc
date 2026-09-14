// Offline AV1 Dolby RPU round-trip checker. SPDX-License-Identifier: MIT
// Link to the pinned libdovi. Input: low-overhead AV1 OBUs from ffmpeg -f obu.
// Output: dovi_tool-compatible RPU binary, including all Dolby display trims.
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <vector>
#include "rpu_parser.h"

static uint8_t byte() {
    const auto value = std::cin.get();
    if (value == EOF) throw std::runtime_error("truncated AV1 OBU");
    return static_cast<uint8_t>(value);
}
static uint64_t leb() {
    uint64_t value = 0;
    for (int i = 0; i < 8; ++i) {
        const auto b = byte();
        value |= uint64_t(b & 0x7f) << (i * 7);
        if (!(b & 0x80)) return value;
    }
    throw std::runtime_error("oversized AV1 leb128");
}
int main() {
    size_t count = 0;
    std::map<std::pair<int, std::string>, uint64_t> staticHdr;
    try {
        while (std::cin.peek() != EOF) {
            const auto header = byte();
            if ((header & 0x81) || !(header & 2)) throw std::runtime_error("unsupported OBU header");
            if (header & 4) byte();
            const auto size = leb();
            if (size > 256 * 1024 * 1024) throw std::runtime_error("oversized OBU");
            if (((header >> 3) & 15) != 5) {
                std::cin.ignore(static_cast<std::streamsize>(size));
                if (std::cin.gcount() != static_cast<std::streamsize>(size)) throw std::runtime_error("truncated picture OBU");
                continue;
            }
            std::vector<uint8_t> payload(size);
            std::cin.read(reinterpret_cast<char *>(payload.data()), static_cast<std::streamsize>(size));
            if (std::cin.gcount() != static_cast<std::streamsize>(size)) throw std::runtime_error("truncated metadata OBU");
            if (!payload.empty() && (payload[0] == 1 || payload[0] == 2)) {
                if (payload.size() != (payload[0] == 1 ? 6 : 26) || payload.back() != 0x80)
                    throw std::runtime_error("unsupported static HDR metadata framing");
                std::ostringstream hex;
                for (const auto value : payload) hex << std::hex << std::setw(2) << std::setfill('0') << int(value);
                ++staticHdr[{payload[0], hex.str()}];
            }
            const std::array<uint8_t, 8> prefix = {4, 0xb5, 0, 0x3b, 0, 0, 8, 0};
            if (payload.size() < prefix.size() || std::memcmp(payload.data(), prefix.data(), prefix.size())) continue;
            auto *rpu = dovi_parse_itu_t35_dovi_metadata_obu(payload.data() + 1, payload.size() - 1);
            if (!rpu) throw std::runtime_error("RPU parser returned null");
            const auto *data = dovi_write_unspec62_nalu(rpu);
            if (!data) {
                const char *message = dovi_rpu_get_error(rpu);
                const std::string error = message ? message : "RPU conversion failed";
                dovi_rpu_free(rpu);
                throw std::runtime_error(error);
            }
            if (data->len < 3 || data->data[0] != 0x7c || data->data[1] != 1) {
                dovi_data_free(data); dovi_rpu_free(rpu);
                throw std::runtime_error("unexpected RPU output framing");
            }
            const char start[] = {0, 0, 0, 1};
            std::cout.write(start, 4);
            std::cout.write(reinterpret_cast<const char *>(data->data + 2), data->len - 2);
            dovi_data_free(data); dovi_rpu_free(rpu);
            if (!std::cout) throw std::runtime_error("could not write round-trip RPU");
            ++count;
        }
        if (!count) throw std::runtime_error("no Dolby RPUs found");
        std::cerr << "{\"complete\":true,\"rpus\":" << count << ",\"static_hdr\":[";
        bool comma = false;
        for (const auto& [key, occurrences] : staticHdr) {
            if (comma) std::cerr << ',';
            comma = true;
            std::cerr << "{\"type\":" << key.first << ",\"payload_hex\":\"" << key.second
                      << "\",\"count\":" << occurrences << '}';
        }
        std::cerr << "]}\n";
    } catch (const std::exception& error) {
        std::cerr << "RPU round-trip failed after " << count << " RPUs: " << error.what() << "\n";
        return 1;
    }
}
