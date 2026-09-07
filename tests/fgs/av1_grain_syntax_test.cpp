#include <iostream>
#include "av1_grain_syntax.h"

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
    std::cout << "AV1 grain point order and chroma syntax checks passed\n";
}
