#include "NVEncFilmGrainPopulationEnvelope.h"
#include <algorithm>
#include <cassert>
#include <iostream>
#include <random>
using namespace fgsmodel;
using Cell = FilmGrainRetentionPopulationCell;
static Cell cell(unsigned code, unsigned n, unsigned population=0, unsigned train=16, unsigned check=16) {
    Cell c; c.nativeLookup=code; c.samples=n;
    c.population=static_cast<FilmGrainRetentionPopulation>(population);
    c.trainBlocks=train;c.checkBlocks=check;return c;
}
int main() {
    FilmGrainRetentionFrame f{64,64,10,7,7,1,1};
    const auto check=[&](const std::vector<Cell>& c) {return film_grain_population_envelope(f,1,c);};
    auto c=std::vector<Cell>{cell(128,600),cell(128,1,2),cell(512,423)};
    auto e=check(c);
    assert(e.valid && e.samples==1024 && e.possibleSamples==423 && e.blockedSamples==601);
    assert(e.eligibleSamplesAtBlockedCodes==600 && !e.possible[128] && e.possible[512]);
    // Splitting or reordering a population cannot hide the one rejected pixel.
    auto split=std::vector<Cell>{cell(128,300),cell(512,423),cell(128,300),cell(128,1,2)};
    auto equivalent=check(split);
    assert(equivalent.occupancy==e.occupancy && equivalent.possible==e.possible);
    const uint8_t x[]={0,128,255}, y[]={0,40,0}; FilmGrainScalingLut lut;
    assert(lut.build(x,y,3,10)); auto curve=film_grain_population_curve_check(e,lut);
    assert(curve.valid && curve.nonzeroSamples==1024 && curve.blockedNonzeroSamples==601);
    // Exact native interpolation can add grain between a zero and nonzero node.
    const uint8_t hx[]={0,3,4,255}, hy[]={0,0,1,1};
    assert(lut.build(hx,hy,4,10));e=check({cell(14,1,3),cell(16,1023)});
    curve=film_grain_population_curve_check(e,lut);assert(curve.valid && curve.blockedNonzeroSamples==1);
    assert(lut.build(nullptr,nullptr,0,10));curve=film_grain_population_curve_check(e,lut);
    assert(curve.valid && !curve.nonzeroSamples && !curve.blockedNonzeroSamples);
    // Zero strength is not sufficient evidence for the separate coverage guard.
    auto untouched=cell(14,1024,3);auto coverage=film_grain_retention_coverage(f,1,{untouched});
    assert(coverage.reasons & FGS_RETAIN_UNMEASURED);
    for (unsigned population=1;population<4;++population) {
        auto bad=cell(128,1024,population);bad.checks={FGS_RETAIN_ALL_POPULATION_CHECKS,FGS_RETAIN_ALL_POPULATION_CHECKS};
        e=check({bad});assert(e.valid && !e.possibleCodes && e.blockedSamples==1024);
    }
    for (auto bad : {cell(128,1024,0,15,16),cell(128,1024,0,16,15)})
        assert(check({bad}).possibleSamples==0);
    assert(!check({}).valid && !check({cell(0,1023)}).valid && !check({cell(0,1025)}).valid);
    assert(!check({cell(1024,1024)}).valid && !check({cell(0,1024,4)}).valid);
    assert(!film_grain_population_envelope(f,3,{cell(0,1024)}).valid);
    auto broken=f;broken.bitDepth=12;assert(!film_grain_population_envelope(broken,1,{cell(0,1024)}).valid);
    assert(!film_grain_population_curve_check({},lut).valid);
    assert(lut.build(x,y,3,8));assert(!film_grain_population_curve_check(check(c),lut).valid);
    auto forged=check(c);forged.bitDepth=12;assert(lut.build(x,y,3,12));
    assert(!film_grain_population_curve_check(forged,lut).valid);
    forged=check(c);forged.possible[128]=true;assert(lut.build(x,y,3,10));
    assert(!film_grain_population_curve_check(forged,lut).valid);
    // Independent per-pixel oracle: a code is possible only if EVERY occupant
    // meets the source-only rule. Exercise aggregation, aliasing and boundaries.
    std::mt19937 random(19437);
    for (unsigned depth : {8u,10u}) for (unsigned trial=0;trial<100;++trial) {
        f.bitDepth=depth;const unsigned codes=1u<<depth;
        std::array<unsigned,1024> counts{};std::array<bool,1024> blocked{};std::vector<Cell> pixels;
        for (unsigned i=0;i<1024;++i) {
            unsigned code=random()%codes, pop=random()%4, train=random()%20, test=random()%20;
            pixels.push_back(cell(code,1,pop,train,test));++counts[code];
            blocked[code]=blocked[code] || pop!=0 || train<16 || test<16;
        }
        std::shuffle(pixels.begin(),pixels.end(),random);e=check(pixels);assert(e.valid);
        uint64_t possible=0;for(unsigned code=0;code<codes;++code) {
            assert(e.occupancy[code]==counts[code]);assert(e.possible[code]==(counts[code] && !blocked[code]));
            if(counts[code] && !blocked[code])possible+=counts[code];
        }
        assert(e.possibleSamples==possible && e.blockedSamples==1024-possible);
    }
    std::cout << "population envelope: alias, interpolation, missing-range and 204800 pixel-oracle controls passed\n";
}
