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
static bool stable(const std::array<int, 24>& values, unsigned shift = 7, unsigned lag = 3) {
    std::array<uint8_t, 24> encoded{};
    for (size_t i = 0; i < values.size(); ++i) encoded[i] = static_cast<uint8_t>(values[i] + 128);
    return fgsmodel::film_grain_ar_stable(encoded.data(), lag, shift);
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
    auto single = std::array<int, 24>{};
    single[23] = 63;
    expect(stable(single, 6), "strong stable same-row correlation is retained");
    single[23] = 64;
    expect(!stable(single, 6), "unit same-row pole after quantization is rejected");
    single[23] = -64;
    expect(!stable(single, 6), "alternating unit same-row pole is rejected");
    single[23] = 0; single[17] = 63;
    expect(stable(single, 6), "strong stable previous-row correlation is retained");
    single[17] = 64;
    expect(!stable(single, 6), "unit previous-row pole is rejected");
    single[17] = -65;
    expect(!stable(single, 6), "growing alternating row recurrence is rejected");
    expect(!stable({}, 5), "invalid coefficient shift is rejected");
    expect(!stable({}, 7, 4), "invalid lag is rejected");
    expect(!fgsmodel::film_grain_ar_stable(nullptr, 3, 7), "missing coefficients are rejected");
    if (failures) return EXIT_FAILURE;
    std::cout << "Film-grain feedback stability regression tests passed\n";
    return EXIT_SUCCESS;
}
