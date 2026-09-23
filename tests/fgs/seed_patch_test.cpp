#include "av1_seed_patch.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <limits>

int main() {
    unsigned changed = 0;
    for (unsigned seed = 0; seed < 65536; ++seed) {
        const auto next = fgsseed::replacement(uint16_t(seed));
        changed += next != seed;
        assert(next && next != 46372 && next != 18904);
        assert(fgsseed::replacement(next) == next);
        for (unsigned offset = 0; offset < 8; ++offset) {
            std::array<uint8_t, 6> data{{0x5a,0xa5,0x5a,0xa5,0x5a,0xa5}};
            const size_t begin = 8 + offset;
            for (unsigned i = 0; i < 16; ++i) {
                const auto mask = uint8_t(1 << (7-(begin+i)%8));
                auto& b = data[(begin+i)/8];
                b = uint8_t((b & ~mask) | (((seed >> (15-i)) & 1) ? mask : 0));
            }
            const auto before = data;
            assert(!fgsseed::patch16(data.data(), data.size(), begin, uint16_t(seed+1)));
            assert(data == before);
            assert(fgsseed::patch16(data.data(), data.size(), begin, uint16_t(seed)));
            uint16_t got = 0;
            assert(fgsseed::read16(data.data(), data.size(), begin, got) && got == next);
            for (size_t bit = 0; bit < 48; ++bit)
                if (bit < begin || bit >= begin+16)
                    assert(((data[bit/8] ^ before[bit/8]) & (1 << (7-bit%8))) == 0);
        }
    }
    assert(changed == 3);
    std::array<uint8_t,3> data{};
    for (size_t bit : {size_t(9), size_t(24), std::numeric_limits<size_t>::max()})
        assert(!fgsseed::patch16(data.data(), data.size(), bit, 0));
    assert(!fgsseed::patch16(nullptr, 3, 0, 0));
    std::vector<fgsseed::Obu> obus;
    const uint8_t valid[]{0x12,0,0x36,0x20,2,0,0};
    assert(fgsseed::split_obus(valid,sizeof(valid),obus));
    assert(obus.size()==2 && obus[1].offset==2 && obus[1].headerBytes==3 && obus[1].bytes==5);
    for (const auto& bad : std::vector<std::vector<uint8_t>>{
        {}, {0x92,0}, {0x13,0}, {0x04,0}, {0x36}, {0x36,7,0},
        {0x32,2,0}, {0x32,0x80}, {0x32,0xff,0xff,0xff,0xff,0x7f},
        {0x32,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80}})
        assert(!fgsseed::split_obus(bad.data(),bad.size(),obus));
    puts("seed patch: 524288 alignments, all seeds, neighbors and malformed spans passed");
}
