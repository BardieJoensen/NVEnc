// Exact independent-AOM vectors and finite synthesis calibration controls.
#include <array>
#include <cassert>
#include <cmath>
#include <iostream>
#include "NVEncFilmGrainTemplate.h"
#include "NVEncFilmGrainJointSpectrum.h"
#include "luma_template_vectors.h"

static uint64_t hash(const fgsmodel::FilmGrainLumaTemplate& grain) {
    uint64_t result = 14695981039346656037ULL;
    for (int16_t value : grain.samples) for (unsigned shift : {0U, 8U}) {
        result ^= (static_cast<uint16_t>(value) >> shift) & 255U;
        result *= 1099511628211ULL;
    }
    return result;
}
int main() {
    using namespace fgsmodel;
    std::array<uint8_t,25> white{}; white.fill(128);
    for (const auto& v : aomTemplateVectors) {
        auto coeff = white;
        for (size_t i = 0; i < v.coefficients.size(); ++i) coeff[i] += v.coefficients[i];
        FilmGrainLumaTemplate actual;
        assert(film_grain_luma_template(coeff.data(),v.lag,v.shift,v.depth,v.grainShift,v.seed,actual));
        assert(hash(actual) == v.hash && actual.clipped == v.clipped);
        const auto power=film_grain_luma_template_power(coeff.data(),v.lag,v.shift,v.depth,v.grainShift,&v.seed,1);
        assert(power.valid);
        const std::array<double,4> measured={power.lumaPower,power.averagedLumaPower,power.roundedAverageLumaPower,power.lumaMean};
        for(size_t i=0;i<measured.size();++i)
            assert(std::abs(measured[i]-v.power[i])<1e-12*std::max(1.,std::abs(v.power[i])));
    }
    // Invalid parameters never leave a prior valid template in the output.
    FilmGrainLumaTemplate output;
    assert(film_grain_luma_template(white.data(),3,7,10,0,1,output));
    assert(!film_grain_luma_template(nullptr,3,7,10,0,1,output));
    assert(output.filtered == 0 && output.samples == FilmGrainLumaTemplate{}.samples);
    assert(!film_grain_luma_template(white.data(),4,7,10,0,1,output));
    assert(!film_grain_luma_template(white.data(),3,5,10,0,1,output));
    assert(!film_grain_luma_template(white.data(),3,10,10,0,1,output));
    assert(!film_grain_luma_template(white.data(),3,7,9,0,1,output));
    assert(!film_grain_luma_template(white.data(),3,7,10,4,1,output));
    std::array<uint16_t,256> seeds{};
    for (size_t i=0;i<seeds.size();++i) seeds[i]=static_cast<uint16_t>((i+1)*1031);
    assert(!film_grain_luma_template_power(white.data(),3,7,10,0,nullptr,1).valid);
    assert(!film_grain_luma_template_power(white.data(),3,7,10,0,seeds.data(),0).valid);
    assert(!film_grain_luma_template_power(white.data(),3,7,10,0,seeds.data(),65537).valid);
    const auto w=film_grain_luma_template_power(white.data(),3,7,10,0,seeds.data(),seeds.size());
    assert(w.valid && w.clippedFraction==0 && std::abs(w.lumaPower-1)<.02);
    assert(std::abs(w.averagedLumaPower-.25)<.01);
    // The decoder's rounded chroma driver differs at low innovation strength.
    const auto low=film_grain_luma_template_power(white.data(),3,7,8,3,seeds.data(),seeds.size());
    assert(low.valid && low.roundedAverageLumaPower>low.averagedLumaPower);
    // A legal, stable correlated AR model can clip its internal template.
    // Reducing the internal innovation removes that effect. Do not explain
    // it away by changing a tolerance or scaling the displayed picture.
    auto strong=white; strong[23]=244; // 116/128 same-row feedback
    const auto stationary=film_grain_joint_spectrum(strong.data(),white.data(),white.data(),3,7);
    const auto clipped=film_grain_luma_template_power(strong.data(),3,7,10,0,seeds.data(),seeds.size());
    const auto small=film_grain_luma_template_power(strong.data(),3,7,10,1,seeds.data(),seeds.size());
    assert(stationary.valid && clipped.valid && small.valid);
    assert(clipped.clippedFraction>.01 && small.clippedFraction<clipped.clippedFraction/10);
    assert(clipped.lumaPower<stationary.lumaPower*.9 && small.lumaPower>clipped.lumaPower*1.1);
    std::cout << "Finite luma template: 24 AOM vectors, rounding, clipping and parameter bounds passed\n";
}
