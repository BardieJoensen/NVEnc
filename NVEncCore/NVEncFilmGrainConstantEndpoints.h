// Exact endpoint evidence is separate from statistical active-image noise.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainSourceGuard.h"
#include "NVEncFilmGrainSyntax.h"

namespace fgsmodel {

inline bool film_grain_chroma_uses_luma_lookup(const NV_ENC_FILM_GRAIN_PARAMS_AV1& p,
    unsigned component) {
    if (p.chromaScalingFromLuma || component < 1 || component > 2) return false;
    return component == 1
        ? p.cbMult == 128 && p.cbLumaMult == 192 && p.cbOffset == 256
        : p.crMult == 128 && p.crLumaMult == 192 && p.crOffset == 256;
}

class FilmGrainConstantEndpoints {
public:
    void reset() { caps_.reset(); depth_ = 0; observed_.fill(0); colourLookup_.fill(false); }

    void advance(bool fresh, unsigned depth, const NV_ENC_FILM_GRAIN_PARAMS_AV1& p) {
        // A shared Y curve would also suppress unmeasured colour grain. This
        // narrowly scoped guard requires independent component curves.
        if (p.chromaScalingFromLuma) { reset(); return; }
        if (depth_ != depth || restricted_ != bool(p.clipToRestrictedRange)) caps_.reset();
        depth_ = depth;
        restricted_ = p.clipToRestrictedRange != 0;
        observed_.fill(0);
        for (unsigned c = 1; c < 3; ++c) {
            colourLookup_[c-1] = film_grain_chroma_uses_luma_lookup(p, c);
            // A strength code in a different lookup domain is not the same
            // population. Never carry colour caps through that change.
            if (!colourLookup_[c-1]) caps_.resetPlane(c);
        }
        caps_.advance(fresh);
    }

    void noModel() { observed_.fill(0); }

    int lumaCode(double minimum, double maximum, int width, int height) const {
        if ((depth_ != 8 && depth_ != 10) || width < 8 || height < 8
            || minimum != maximum || !std::isfinite(minimum)) return -1;
        const unsigned scale = 1u << (depth_-8);
        const unsigned black = restricted_ ? 16u*scale : 0u;
        const unsigned white = restricted_ ? 235u*scale : (1u << depth_)-1;
        return minimum == black ? (restricted_ ? 16 : 0)
            : minimum == white ? (restricted_ ? 235 : 255) : -1;
    }

    int observeLuma(double minimum, double maximum, int width, int height) {
        const int code = lumaCode(minimum, maximum, width, height);
        if (code >= 0) {
            caps_.preserveRange(0, code, code);
            ++observed_[0];
        }
        return code;
    }

    bool observeChroma(unsigned component, int lumaCode, double mean, double sigma,
        int width, int height) {
        if ((depth_ != 8 && depth_ != 10) || component < 1 || component > 2
            || !colourLookup_[component-1] || width < 8 || height < 8
            || sigma != 0.0 || !std::isfinite(mean) || mean != std::floor(mean)
            || (lumaCode != (restricted_ ? 16 : 0) && lumaCode != (restricted_ ? 235 : 255))) return false;
        const unsigned scale = 1u << (depth_-8);
        // Zero direct source variance establishes constancy; clipped luma
        // alone never establishes the colour observation. Keep the supported
        // decoder range separate from this exact source fact.
        const unsigned low = restricted_ ? 16u*scale : 0u;
        const unsigned high = restricted_ ? 240u*scale : (1u << depth_)-1;
        if (mean < low || mean > high) return false;
        caps_.preserveRange(component, lumaCode, lumaCode);
        ++observed_[component];
        return true;
    }

    uint32_t refitCurve(int plane, uint8_t* values, uint8_t* scalings,
        uint32_t count, uint32_t capacity, bool& changed) const {
        return caps_.refitCurve(plane, values, scalings, count, capacity, changed);
    }
    uint64_t observed(unsigned component) const { return observed_[component]; }
    double gain(int component, int code) const { return caps_.gain(component, code); }

private:
    FilmGrainSourceCaps caps_;
    unsigned depth_ = 0;
    bool restricted_ = false;
    std::array<bool, 2> colourLookup_{};
    std::array<uint64_t, 3> observed_{};
};
} // namespace fgsmodel
