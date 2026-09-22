// Analytic and independently simulated controls for coupled colour grain.
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <iostream>
#include <random>
#include <vector>
#include "NVEncFilmGrainJointSpectrum.h"

using namespace fgsmodel;
using Coeff = std::array<uint8_t, 25>;
static Coeff white() { Coeff c; c.fill(128); return c; }
static void near(double a, double b, double relative = 1e-8) {
    assert(std::isfinite(a) && std::abs(a-b) <= relative * std::max(1.0, std::abs(b)));
}

int main() {
    const auto w = white();
    for (unsigned lag = 0; lag <= 3; ++lag) for (unsigned shift = 6; shift <= 9; ++shift) {
        auto c = w;
        c[2*lag*(lag+1)] += 32;
        const double k = 32.0 / (1U << shift);
        const auto s = film_grain_joint_spectrum(w.data(), c.data(), w.data(), lag, shift);
        assert(s.valid);
        near(s.lumaPower, 1.0); near(s.averagedLumaPower, .25);
        near(s.chromaPower[0], 1.0+k*k*.25); near(s.chromaPower[1], 1.0);
        near(s.lumaChromaCovariance[0], k*.25); near(s.lumaChromaCovariance[1], 0.0);
    }
    // White luma is independent after 2x2 averaging. Its contribution passes
    // through the chroma recursion just like the independent innovation.
    auto c = w;
    c[23] += 64; c[24] += 64;
    const auto correlated = film_grain_joint_spectrum(w.data(), c.data(), w.data(), 3, 7);
    assert(correlated.valid);
    near(correlated.chromaPower[0], (1.0+.25*.25)/(1.0-.25));
    const double oldApproximation = 1.0/(1.0-.25)+.25*.25;
    assert(correlated.chromaPower[0] > oldApproximation + .02);
    // Verify coloured luma + coloured chroma against a separate spatial
    // recurrence with large independent innovations (no spectral code used).
    auto y = w;
    y[23] += 64;
    const auto coupled = film_grain_joint_spectrum(y.data(), c.data(), w.data(), 3, 7);
    assert(coupled.valid);
    near(coupled.lumaPower, 1.0/(1.0-.25));
    near(coupled.averagedLumaPower, (1.0/(1.0-.25)) * (1.0+.5)/4.0);
    std::mt19937 rng(61467);
    std::normal_distribution<double> gaussian;
    constexpr int width = 2048, height = 1024, margin = 64;
    std::vector<double> row0(width), row1(width);
    double cEnergy=0.0, pEnergy=0.0, cp=0.0; unsigned count=0;
    for (int yy=0; yy<height; yy+=2) {
        for (auto* row : {&row0, &row1}) {
            double last=0.0;
            for (int x=0; x<width; ++x) { last=gaussian(rng)+.5*last; (*row)[x]=last; }
        }
        double last=0.0;
        for (int x=0; x<width; x+=2) {
            const double p=(row0[x]+row0[x+1]+row1[x]+row1[x+1])*.25;
            last=gaussian(rng)+.5*last+.5*p;
            if (x<margin) continue;
            cEnergy+=last*last; pEnergy+=p*p; cp+=last*p; ++count;
        }
    }
    near(coupled.chromaPower[0], cEnergy/count, .015);
    near(coupled.averagedLumaPower, pEnergy/count, .015);
    near(coupled.lumaChromaCovariance[0], cp/count, .015);
    c[24] = 64; // Negative luma coupling keeps power, reverses covariance.
    const auto negative = film_grain_joint_spectrum(y.data(), c.data(), w.data(), 3, 7);
    near(negative.chromaPower[0], coupled.chromaPower[0]);
    near(negative.lumaChromaCovariance[0], -coupled.lumaChromaCovariance[0]);
    assert(!film_grain_joint_spectrum(nullptr,c.data(),w.data(),3,7).valid);
    assert(!film_grain_joint_spectrum(y.data(),nullptr,w.data(),3,7).valid);
    assert(!film_grain_joint_spectrum(y.data(),c.data(),w.data(),4,7).valid);
    assert(!film_grain_joint_spectrum(y.data(),c.data(),w.data(),3,5).valid);
    assert(!film_grain_joint_spectrum(y.data(),c.data(),w.data(),3,10).valid);
    y[23]=192; // Unit pole with shift 6 must be rejected.
    assert(!film_grain_joint_spectrum(y.data(),c.data(),w.data(),3,6).valid);
    std::cout << "Joint colour transfer: aliases, AR-filtered coupling, signs, poles and spatial simulation passed\n";
}
