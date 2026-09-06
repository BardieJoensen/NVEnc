#include <cassert>
#include <vector>
#include "av1_scan_packet.h"

int main() {
    std::vector<uint8_t> bytes{0x0a, 1, 0xab, 0x2a, 2, 0x81, 0x00, 0x32, 1, 0xcd};
    size_t size = bytes.size(); bool sequence = false; unsigned skipped = 0;
    assert(prepare_av1_scan_packet(bytes.data(), size, sequence, skipped));
    bytes.resize(size);
    assert((bytes == std::vector<uint8_t>{0x0a, 1, 0xab, 0x32, 1, 0xcd}));
    assert(sequence && skipped == 1);
    bytes = {0x32, 1, 0xcd}; size = bytes.size(); skipped = 0;
    assert(prepare_av1_scan_packet(bytes.data(), size, sequence, skipped));
    assert(!sequence && !skipped && size == 3);
    bytes = {0x2e, 0, 2, 1, 2}; size = bytes.size();
    assert(prepare_av1_scan_packet(bytes.data(), size, sequence, skipped));
    assert(!size && !sequence && skipped == 1);
    bytes = {0x30, 0xab, 0xcd}; size = bytes.size();
    assert(prepare_av1_scan_packet(bytes.data(), size, sequence, skipped));
    assert(size == 3); // last OBU may omit its size
    for (auto malformed : std::vector<std::vector<uint8_t>>{
        {0x2a, 5, 1}, {0x2a, 0x80}, {0x2e}, {0x80},
        {0x2a, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0}}) {
        size = malformed.size();
        assert(!prepare_av1_scan_packet(malformed.data(), size, sequence, skipped));
    }
}
