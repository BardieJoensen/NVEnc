// Regression vectors from the emitted AV1 headers of the reported ripple.
// Coefficients are syntax data, not video media. No GPU or media dependency.
#include <array>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include "NVEncFilmGrainStability.h"

static int failures = 0;
static void expect(bool ok, const char *name) {
    if (!ok) { std::cerr << "FAIL: " << name << '\n'; ++failures; }
}
static bool stable(const std::array<int, 24>& values, unsigned shift = 7, unsigned lag = 3,
    double radius = 1.0) {
    std::array<uint8_t, 24> encoded{};
    for (size_t i = 0; i < values.size(); ++i) encoded[i] = static_cast<uint8_t>(values[i] + 128);
    return fgsmodel::film_grain_ar_within_radius(encoded.data(), lag, shift, radius);
}
int main() {
    expect(stable({}), "white grain is stable");
    expect(stable({}, 6, 0), "lag-zero grain is stable");
    const std::array<int, 24> ripple = {
        -33,-3,-43,22,-45,8,-19,-11,-18,27,-60,8,-10,-9,-24,42,-72,76,-42,15,10,26,-81,68};
    expect(!stable(ripple), "reported horizontal ripple is rejected");
    const std::array<int, 24> diagonal = {
        -29,3,-31,18,-32,7,-18,-2,-15,36,-56,4,-8,-8,-30,59,-81,88,-43,18,14,29,-79,72};
    expect(!stable(diagonal), "reported diagonal ripple is rejected");
    const std::array<int, 24> chroma = {
        0,-1,-4,23,4,0,-16,-6,-9,0,27,-9,1,13,-9,-11,-50,68,-3,-5,1,12,16,45};
    expect(!stable(chroma), "unstable chroma feedback is rejected");
    const std::array<int, 24> cleanScene = {
        -5,-3,-7,14,2,-1,-2,0,2,-11,-23,-14,1,-5,-5,-6,-14,80,5,-14,1,24,-21,78};
    expect(stable(cleanScene, 8), "neighbouring stable real-scene model is retained");
    expect(stable(cleanScene, 8, 3, 0.95), "ordinary real grain satisfies synthesis decay margin");
    const std::array<int, 24> jacket = {
        -22,12,-12,1,6,-1,-14,23,-12,15,-55,14,-25,21,0,18,-33,69,5,-11,15,25,-80,82};
    expect(stable(jacket), "34:06 diagonal mesh is mathematically stable");
    expect(!stable(jacket, 7, 3, 0.95), "stable but resonant jacket model is rejected for synthesis");
    expect(stable({-3,-1,-7,-8,17,-18,11,6,9,-13,6,-4,-11,1,-15,22,-38,49,-20,26,-11,1,-16,86}),
        "stable oscillatory model with a flat Schur minimum is retained");
    expect(stable({0,0,-3,4,-1,-3,-1,-3,6,-5,-5,-12,2,-1,-1,-4,-30,54,4,-7,-5,7,-7,74}),
        "stable chroma model with a flat Schur minimum is retained");
    expect(stable({-3,4,-2,7,6,-6,2,2,5,-2,-27,-13,5,-1,-6,1,-21,67,11,-5,-4,15,-30,71}),
        "stable mixed-sign high-order model is retained");
    auto single = std::array<int, 24>{};
    single[23] = 63;
    expect(stable(single, 6), "strong stable same-row correlation is retained");
    expect(!stable(single, 6, 3, 0.95), "slow same-row decay cannot bypass synthesis policy");
    single[23] = 60;
    expect(stable(single, 6, 3, 0.95), "same-row feedback below radius bound is accepted");
    single[23] = 61;
    expect(!stable(single, 6, 3, 0.95), "same-row feedback just above radius bound is rejected");
    single[23] = 64;
    expect(!stable(single, 6), "unit same-row pole after quantization is rejected");
    single[23] = -64;
    expect(!stable(single, 6), "alternating unit same-row pole is rejected");
    single[23] = 0; single[17] = 63;
    expect(stable(single, 6), "strong stable previous-row correlation is retained");
    expect(!stable(single, 6, 3, 0.95), "slow previous-row decay cannot bypass synthesis policy");
    single[17] = 64;
    expect(!stable(single, 6), "unit previous-row pole is rejected");
    single[17] = -65;
    expect(!stable(single, 6), "growing alternating row recurrence is rejected");
    single = {}; single[3] = 109;
    expect(stable(single, 7, 3, 0.95), "third-row feedback below cubed radius is accepted");
    single[3] = 110;
    expect(!stable(single, 7, 3, 0.95), "third-row feedback must scale by cubed radius");
    single = {}; single[21] = 110;
    expect(!stable(single, 7, 3, 0.95), "third same-row tap must scale by cubed radius");
    expect(!stable({}, 5), "invalid coefficient shift is rejected");
    expect(!stable({}, 7, 4), "invalid lag is rejected");
    expect(!stable({}, 7, 3, 0.0), "zero radius is rejected");
    expect(!stable({}, 7, 3, 1.01), "expanding radius is rejected");
    expect(!fgsmodel::film_grain_ar_stable(nullptr, 3, 7), "missing coefficients are rejected");
    if (failures) return EXIT_FAILURE;
    std::cout << "Film-grain feedback stability regression tests passed\n";
    return EXIT_SUCCESS;
}
