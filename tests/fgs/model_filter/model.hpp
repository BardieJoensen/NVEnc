// Shared complete-model syntax for the manual writer and streaming experiment.
// MIT adapter; the pinned private FFmpeg dependency remains LGPL-2.1-or-later.
#pragma once
#include <array>
#include <cstring>
#include <stdexcept>
#include <vector>
#include "json.hpp"
extern "C" {
#include "libavcodec/avcodec.h"
#include "libavcodec/cbs.h"
#define class av_class
#include "libavcodec/cbs_av1.h"
#undef class
#include "libavutil/sha.h"
}
namespace fgsmodelwriter {
using Json=nlohmann::json;
inline void require(bool ok,const char* text) { if (!ok) throw std::runtime_error(text); }
inline int integer(const Json& j,const char* key,int low,int high) {
    const auto& v=j.at(key);require(v.is_number_integer(),"expected integer model field");
    const int64_t n=v.get<int64_t>();require(n>=low && n<=high,"model field out of range");return int(n);
}
inline AV1RawFilmGrainParams model(const Json& j) {
    AV1RawFilmGrainParams g{};
    require(j.at("apply").is_boolean(),"apply must be boolean");
    g.apply_grain=j.at("apply").get<bool>();
    if (!g.apply_grain) return g;
    g.update_grain=1;g.grain_seed=integer(j,"seed",0,65535);
    g.ar_coeff_lag=3;g.ar_coeff_shift_minus_6=integer(j,"ar_shift",6,9)-6;
    g.grain_scale_shift=integer(j,"grain_shift",0,3);
    g.grain_scaling_minus_8=integer(j,"scaling_shift",8,11)-8;
    g.overlap_flag=integer(j,"overlap",0,1);
    g.clip_to_restricted_range=integer(j,"restricted",0,1);
    const auto& curves=j.at("curves");require(curves.is_array() && curves.size()==3,"expected three curves");
    uint8_t* values[]={g.point_y_value,g.point_cb_value,g.point_cr_value};
    uint8_t* scales[]={g.point_y_scaling,g.point_cb_scaling,g.point_cr_scaling};
    uint8_t* counts[]={&g.num_y_points,&g.num_cb_points,&g.num_cr_points};
    for(unsigned c=0;c<3;++c) {
        require(curves[c].is_array() && curves[c].size()<=(c?10:14),"curve point budget");
        *counts[c]=uint8_t(curves[c].size());int previous=-1;
        for(size_t i=0;i<curves[c].size();++i) {
            const auto& point=curves[c][i];require(point.is_array() && point.size()==2 && point[0].is_number_integer() && point[1].is_number_integer(),"invalid point");
            const int64_t x=point[0].get<int64_t>(),y=point[1].get<int64_t>();
            require(x>previous && x<=255 && y>=0 && y<=255,"invalid curve ordering/value");
            values[c][i]=uint8_t(x);scales[c][i]=uint8_t(y);previous=int(x);
        }
    }
    require((g.num_y_points || (!g.num_cb_points && !g.num_cr_points)) && ((g.num_cb_points==0)==(g.num_cr_points==0)),"invalid 4:2:0 point counts");
    const auto& coeff=j.at("coefficients");require(coeff.is_array() && coeff.size()==3,"expected three coefficient arrays");
    uint8_t* dst[]={g.ar_coeffs_y_plus_128,g.ar_coeffs_cb_plus_128,g.ar_coeffs_cr_plus_128};
    for(unsigned c=0;c<3;++c) {
        require(coeff[c].is_array() && coeff[c].size()==(c?25:24),"wrong lag-three coefficient count");
        for(size_t i=0;i<coeff[c].size();++i) {
            require(coeff[c][i].is_number_integer(),"coefficient must be integer");
            const int64_t x=coeff[c][i].get<int64_t>();require(x>=-128 && x<=127,"coefficient out of range");dst[c][i]=uint8_t(x+128);
        }
    }
    // Explicit lookup used by the existing independent constant-curve oracle.
    // Wider lookup equations need their own model contract, not guessed fields.
    g.cb_mult=g.cr_mult=128;g.cb_luma_mult=g.cr_luma_mult=192;g.cb_offset=g.cr_offset=256;
    return g;
}
inline Json semantic(AV1RawFilmGrainParams g) {
    if (!g.apply_grain) return Json{{"apply",false}};
    Json curves=Json::array(),coeff=Json::array();
    const unsigned counts[]={g.num_y_points,g.num_cb_points,g.num_cr_points};
    const uint8_t* values[]={g.point_y_value,g.point_cb_value,g.point_cr_value};
    const uint8_t* scales[]={g.point_y_scaling,g.point_cb_scaling,g.point_cr_scaling};
    const uint8_t* taps[]={g.ar_coeffs_y_plus_128,g.ar_coeffs_cb_plus_128,g.ar_coeffs_cr_plus_128};
    for(unsigned c=0;c<3;++c) {
        Json points=Json::array(),a=Json::array();
        for(unsigned i=0;i<counts[c];++i)points.push_back({values[c][i],scales[c][i]});
        const unsigned n=2*g.ar_coeff_lag*(g.ar_coeff_lag+1)+(c && g.num_y_points?1:0);
        if(counts[c] || (c && g.chroma_scaling_from_luma))for(unsigned i=0;i<n;++i)a.push_back(int(taps[c][i])-128);
        curves.push_back(points);coeff.push_back(a);
    }
    return Json{{"apply",true},{"curves",curves},{"coefficients",coeff},{"from_luma",g.chroma_scaling_from_luma},
        {"lag",g.ar_coeff_lag},{"ar_shift",g.ar_coeff_shift_minus_6+6},{"grain_shift",g.grain_scale_shift},
        {"scaling_shift",g.grain_scaling_minus_8+8},{"overlap",g.overlap_flag},{"restricted",g.clip_to_restricted_range},
        {"cb_lookup",{g.cb_mult,g.cb_luma_mult,g.cb_offset}},{"cr_lookup",{g.cr_mult,g.cr_luma_mult,g.cr_offset}}};
}
}
