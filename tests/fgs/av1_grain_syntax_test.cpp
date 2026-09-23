#include <iostream>
#include "av1_grain_syntax.h"
#include "av1_sequence_levels.h"

int main() {
    Av1GrainSyntax grain; grain.points = {14, 10, 10};
    if (grain.error(true)) return 1;
    grain.points[1] = 0;
    if (!grain.error(true) || grain.error(false)) return 2;
    grain.points = {14, 10, 0};
    if (!grain.error(true)) return 3;
    grain.points = {14, 0, 0};
    if (grain.error(true)) return 4;
    grain.points = {0, 10, 10};
    if (!grain.error(true)) return 5;
    grain = Av1GrainSyntax(); grain.points = {14, 10, 10}; grain.fromLuma = true;
    if (!grain.error(false)) return 6;
    grain = Av1GrainSyntax(); grain.point(0, 10); grain.point(0, 10);
    if (!grain.error(false)) return 7;
    Av1GrainLayout layout; layout.sequence(0);
    if (!layout.is420()) return 8;
    layout.monochrome = true;
    if (layout.is420()) return 9;
    layout.sequence(1);
    if (layout.is420()) return 10;
    layout.sequence(2); layout.subsamplingX = 1; layout.subsamplingY = 1;
    if (!layout.is420()) return 11;
    layout.subsamplingY = 0;
    if (layout.is420()) return 12;
    constexpr int defined[] = {0,1,4,5,8,9,12,13,14,15,16,17,18,19,31};
    for (int value=0; value<32; ++value) {
        bool expected=false;
        for (int level : defined) expected |= level==value;
        Av1SequenceLevels sequence;
        sequence.observe(31,value);
        if (sequence.accepted()!=expected || sequence.fields!=1
            || sequence.seen!=(uint32_t(1)<<value)) return 13;
    }
    Av1SequenceLevels sequence;
    if (sequence.accepted()) return 14;
    sequence.observe(0,31); sequence.observe(1,12);
    if (!sequence.accepted()) return 15;
    sequence.observe(0,23); sequence.observe(0,8);
    if (sequence.accepted() || sequence.undefined!=(uint32_t(1)<<23)) return 16;
    for (const auto& bad : {std::array<int,2>{-1,0}, {32,0}, {0,-1}, {0,32}}) {
        Av1SequenceLevels invalid;
        invalid.observe(bad[0],bad[1]); invalid.observe(0,8);
        if (invalid.accepted() || !invalid.invalid) return 17;
    }
    std::cout << "AV1 grain syntax and defined sequence-level checks passed\n";
}
