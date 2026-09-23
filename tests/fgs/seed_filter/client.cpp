// Manual client/API qualification against independently checked IVF fixtures.
#include "NVEncFilmGrainSeedGuard.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <vector>
static unsigned le(const uint8_t* p) { return p[0]|unsigned(p[1])<<8|unsigned(p[2])<<16|unsigned(p[3])<<24; }
int main(int argc,char** argv) {
    assert(argc==4);
    NVEncFilmGrainSeedGuard guard;
    assert(!guard.open(_T("/this-seed-library-does-not-exist.so")) && !guard.error().empty());
    const std::array<uint8_t,2> malformed{{0x32, 0x00}}; // Empty OBU_FRAME header.
    auto sentinel = malformed;
    assert(guard.process(sentinel.data(),sentinel.size())<0);
    assert(guard.open(argv[1]));
    FILE* source=fopen(argv[2],"rb"); FILE* reference=fopen(argv[3],"rb"); assert(source && reference);
    std::array<uint8_t,32> header{},expected{};
    assert(fread(header.data(),1,32,source)==32 && fread(expected.data(),1,32,reference)==32 && header==expected);
    unsigned frames=0,changed=0;
    for(;;) {
        std::array<uint8_t,12> h{},e{};
        const size_t count=fread(h.data(),1,12,source);
        if(!count && feof(source))break;
        assert(count==12 && fread(e.data(),1,12,reference)==12 && h==e);
        const unsigned bytes=le(h.data());assert(bytes && bytes<=32*1024*1024);
        std::vector<uint8_t> packet(bytes),control(bytes);
        assert(fread(packet.data(),1,bytes,source)==bytes && fread(control.data(),1,bytes,reference)==bytes);
        const auto before=packet;
        const int result=guard.process(packet.data(),packet.size());
        assert(result>=0 && packet==control && bool(result)==(packet!=before));
        changed+=result!=0;++frames;
    }
    assert(fgetc(reference)==EOF && frames==le(header.data()+24) && changed==guard.correctedPackets());
    fclose(source);fclose(reference);
    // Reopening must discard the old parser, its counters and prior failures.
    assert(!guard.open(_T("/this-seed-library-does-not-exist.so")));
    assert(guard.process(sentinel.data(),sentinel.size())<0 && guard.correctedPackets()==0);
    assert(guard.open(argv[1]) && guard.correctedPackets()==0);
    assert(guard.process(sentinel.data(),sentinel.size())<0 && sentinel==malformed);
    assert(guard.process(sentinel.data(),sentinel.size())<0 && sentinel==malformed);
    assert(!guard.error().empty());
    printf("{\"complete\":true,\"frames\":%u,\"changed_packets\":%u,\"client_lifecycle_pass\":true}\n",frames,changed);
}
