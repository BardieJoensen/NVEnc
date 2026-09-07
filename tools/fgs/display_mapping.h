// Reference-display mapping for diagnostics; this is not a television tone mapper.
// BT.2100-3 PQ/HLG, zero display black. SDR uses a 2.4-power reference display.
// PU21 banding_glare equation/parameters: gfxdisp/pu21, BSD-3-Clause;
// copyright (c) 2021 Graphics and Displays group, University of Cambridge.
// See LICENSE-PU21.txt and README.md for attribution and display assumptions.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace fgs_inspect {
inline double pq_nits(double signal) {
    const double p = std::pow(std::clamp(signal, 0.0, 1.0), 1.0 / 78.84375);
    return 10000 * std::pow(std::max(p - .8359375, 0.0) / (18.8515625 - 18.6875*p),
                           1.0 / .1593017578125);
}
inline double pq_signal(double nits) {
    const double y=std::pow(std::clamp(nits/10000,0.0,1.0),.1593017578125);
    return std::pow((.8359375+18.8515625*y)/(1+18.6875*y),78.84375);
}
inline double hlg_scene(double signal) {
    const double x = std::clamp(signal, 0.0, 1.0);
    constexpr double a = .17883277;
    const double b = 1-4*a, c = .5-a*std::log(4*a);
    return x <= .5 ? x*x/3 : (std::exp((x-c)/a)+b)/12;
}
inline double hlg_gamma(double peak) {
    return peak >= 400 && peak <= 2000 ? 1.2 + .42*std::log10(peak/1000)
         : 1.2*std::pow(1.111, std::log2(peak/1000));
}
inline double pu21(double nits) {
    const double y = std::pow(std::clamp(nits, .005, 10000.0), .9062562627);
    return std::max(596.3148142*(std::pow((.353487901+.3734658629*y)/
                        (1+8.277049286e-5*y), .09150303166)-.9099517204), 0.0);
}

struct DisplayConfig {
    int transfer = 1, matrix = 1, primaries = 1, depth = 10;
    bool full_range = false;
    double peak_nits = 1000, sdr_white_nits = 100;
};

class DisplayMapper {
    // Linear interpolation on fine LUTs avoids pow() per component and pixel.
    // PU lookup spacing is quadratic in luminance, retaining precision near black.
    static constexpr int steps = 65536;
    std::vector<double> linear_, pu_;
    double kr_, kb_, peak_signal_;
    static double lookup(const std::vector<double>& lut, double x) {
        const double p = std::clamp(x, 0.0, 1.0)*steps;
        const int i = std::min(int(p), steps-1);
        return lut[i] + (lut[i+1]-lut[i])*(p-i);
    }
public:
    DisplayConfig config;
    explicit DisplayMapper(DisplayConfig c) : config(c) {
        if (!std::isfinite(c.peak_nits) || c.peak_nits < 100 || c.peak_nits > 10000 ||
            !std::isfinite(c.sdr_white_nits) || c.sdr_white_nits < 20 || c.sdr_white_nits > 1000)
            throw std::runtime_error("invalid reference-display luminance");
        if (c.depth != 8 && c.depth != 10 && c.depth != 12)
            throw std::runtime_error("unsupported component depth");
        if (c.transfer == 16 || c.transfer == 18) {
            if (c.matrix != 9 || c.primaries != 9)
                throw std::runtime_error("PQ/HLG reference mode requires BT.2020 non-constant-luminance YCbCr and primaries");
        } else if (c.transfer != 1 && c.transfer != 6 && c.transfer != 14 && c.transfer != 15) {
            throw std::runtime_error("unspecified or unsupported transfer characteristic");
        }
        if (!((c.matrix == 1 && c.primaries == 1) || (c.matrix == 9 && c.primaries == 9)))
            throw std::runtime_error("reference mode supports explicitly tagged BT.709 or BT.2020 NCL");
        kr_ = c.matrix == 9 ? .2627 : .2126;
        kb_ = c.matrix == 9 ? .0593 : .0722;
        peak_signal_=pq_signal(c.peak_nits);
        linear_.resize(steps+1); pu_.resize(steps+1);
        for (int i = 0; i <= steps; ++i) {
            const double x = double(i)/steps;
            linear_[i] = c.transfer == 16 ? std::min(pq_nits(x), c.peak_nits)
                       : c.transfer == 18 ? hlg_scene(x) : c.sdr_white_nits*std::pow(x, 2.4);
            pu_[i] = pu21(10000*x*x);
        }
    }
    const char* transfer_name() const {
        return config.transfer == 16 ? "pq" : config.transfer == 18 ? "hlg" : "sdr_gamma24";
    }
    std::array<double,3> rgb_signal(double y, double u, double v) const {
        const double scale = double(1 << (config.depth-8));
        const double maximum = double((1 << config.depth)-1);
        const double yy = config.full_range ? y/maximum : (y-16*scale)/(219*scale);
        const double cb = (u-128*scale)/(config.full_range ? maximum : 224*scale);
        const double cr = (v-128*scale)/(config.full_range ? maximum : 224*scale);
        return {yy+2*(1-kr_)*cr, yy-2*kb_*(1-kb_)/(1-kr_-kb_)*cb
                    -2*kr_*(1-kr_)/(1-kr_-kb_)*cr, yy+2*(1-kb_)*cb};
    }
    std::array<double,4> values(std::array<double,3> signal, bool analytic=false) const {
        std::array<double,3> light{};
        for (int i=0; i<3; ++i) {
            const double x = std::clamp(signal[i], 0.0, 1.0);
            light[i] = !analytic ? lookup(linear_, x)
                     : config.transfer == 16 ? std::min(pq_nits(x), config.peak_nits)
                     : config.transfer == 18 ? hlg_scene(x) : config.sdr_white_nits*std::pow(x, 2.4);
        }
        if (config.transfer == 18) {
            // Apply system gamma to luminance, not separately to RGB components.
            const double luminance = kr_*light[0]+(1-kr_-kb_)*light[1]+kb_*light[2];
            const double gain = luminance > 0 ? config.peak_nits*std::pow(luminance, hlg_gamma(config.peak_nits)-1) : 0;
            for (auto& value : light) value *= gain;
        }
        const double luminance = kr_*light[0]+(1-kr_-kb_)*light[1]+kb_*light[2];
        std::array<double,4> result{luminance,light[0],light[1],light[2]};
        for (auto& value : result) value = analytic ? pu21(value) : lookup(pu_,std::sqrt(std::clamp(value,0.0,10000.0)/10000));
        return result;
    }
    bool clipped(const std::array<double,3>& signal) const {
        for (const auto value : signal) {
            if (value < 0 || value > 1) return true;
            if (config.transfer == 16 && value > peak_signal_) return true;
        }
        return false;
    }
};
} // namespace fgs_inspect
