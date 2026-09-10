// Eligibility diagnostics must retain the qualified colour-restoration policy.
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainModel.h"

using namespace fgsmodel;
using Reason = FilmGrainChromaRestoreReason;

int main() {
    FilmGrainGpuStats stats = {};
    NV_ENC_FILM_GRAIN_PARAMS_AV1 model = {};
    model.arCoeffLag = 3;
    for (auto* c : {model.arCoeffsCbPlus128, model.arCoeffsCrPlus128})
        std::fill(c, c + 25, 128);
    for (int plane : {1, 2}) {
        auto& c = stats.plane[plane];
        c.observations = 2048;
        c.binBlockCount[8] = 32;
        c.binVarSum[8] = 32 * 9;
        c.ata[tri_index(25, 24, 24)] = 2048 * 9;
    }
    const auto expect = [&](const FilmGrainGpuStats& s, const NV_ENC_FILM_GRAIN_PARAMS_AV1& p,
                            int plane, Reason reason) {
        const auto before = s;
        const auto paramsBefore = p;
        assert(chroma_restore_reason(s, p, plane) == reason);
        assert(can_restore_chroma_component(s, p, plane) == (reason == Reason::Eligible));
        assert(std::memcmp(&s, &before, sizeof(s)) == 0);
        assert(std::memcmp(&p, &paramsBefore, sizeof(p)) == 0);
    };
    expect(stats, model, 0, Reason::InvalidPlane);
    expect(stats, model, 3, Reason::InvalidPlane);
    for (int plane : {1, 2}) {
        expect(stats, model, plane, Reason::Eligible);
        auto p = model;
        p.chromaScalingFromLuma = 1;
        expect(stats, p, plane, Reason::ScalingFromLuma);
        p = model; p.arCoeffLag = 2;
        expect(stats, p, plane, Reason::UnsupportedLag);
        // The SDK stores the shift in two bits; an out-of-range value cannot
        // be represented in this structure (the defensive reason is reserved).
        p = model;
        auto* coefficients = plane == 1 ? p.arCoeffsCbPlus128 : p.arCoeffsCrPlus128;
        for (int sign : {-1, 1}) {
            coefficients[24] = 128 + sign * 4; // Exactly the permitted 1/16.
            expect(stats, p, plane, Reason::Eligible);
            coefficients[24] = 128 + sign * 5;
            expect(stats, p, plane, Reason::SignalledCoupling);
        }
        auto s = stats;
        s.plane[plane].observations = 1024;
        expect(s, model, plane, Reason::Eligible);
        s.plane[plane].observations = 1023;
        expect(s, model, plane, Reason::InsufficientObservations);
        // When several conditions fail, the reason names the first check reached.
        expect(s, p, plane, Reason::SignalledCoupling);
        for (double bad : {-1.0, std::numeric_limits<double>::infinity(),
                          std::numeric_limits<double>::quiet_NaN()}) {
            s = stats; s.plane[plane].binVarSum[0] = bad;
            expect(s, model, plane, Reason::InvalidVariance);
        }
        s = stats; s.plane[plane].binBlockCount[8] = 0;
        expect(s, model, plane, Reason::MissingEnergy);
        s = stats; s.plane[plane].binVarSum[8] = 0;
        expect(s, model, plane, Reason::MissingEnergy);
        s = stats; s.plane[plane].ata[tri_index(25, 24, 24)] = 0;
        expect(s, model, plane, Reason::MissingPredictor);
        for (int sign : {-1, 1}) {
            s = stats; s.plane[plane].atb[0] = sign * 3686;
            expect(s, model, plane, Reason::Eligible);
            s.plane[plane].atb[0] = sign * 3687;
            expect(s, model, plane, Reason::SpatialCorrelation);
            s = stats; s.plane[plane].atb[24] = sign * 921;
            expect(s, model, plane, Reason::Eligible);
            s.plane[plane].atb[24] = sign * 922;
            expect(s, model, plane, Reason::MeasuredCoupling);
        }
        // Underflow in the normalizer remains a rejection, with a distinct reason.
        s = stats; s.plane[plane].binVarSum[8] = std::numeric_limits<double>::denorm_min();
        expect(s, model, plane, Reason::InvalidCorrelation);
    }
    std::cout << "Colour eligibility reasons and threshold boundaries passed\n";
}
