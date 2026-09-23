// Manual finite native-picture oracle, linked only to a pinned reference AOM.
// Not part of the encoder/runtime; actual encoded-output checks are separate.
#include <array>
#include <cassert>
#include <fstream>
#include <iostream>
#include <vector>
#include "json.hpp"
extern "C" {
#include "av1/decoder/grain_synthesis.h"
}
using nlohmann::json;
int main() {
    json j; std::cin >> j;
    const unsigned w=j.at("width"), h=j.at("height"), depth=j.at("depth");
    assert(w>=64 && h>=64 && w<=4096 && h<=2160 && !(w&1) && !(h&1));
    assert(depth==8 || depth==10);
    const auto seeds=j.at("seeds").get<std::vector<unsigned>>();
    assert(!seeds.empty() && seeds.size()<=128);
    const auto format=depth==8 ? AOM_IMG_FMT_I420 : AOM_IMG_FMT_I42016;
    aom_image_t src{}, dst{};
    assert(aom_img_alloc(&src,format,w,h,32)); assert(aom_img_alloc(&dst,format,w,h,32));
    src.bit_depth=dst.bit_depth=depth;
    src.mc=static_cast<aom_matrix_coefficients_t>(j.at("matrix").get<unsigned>());
    assert(src.mc==AOM_CICP_MC_BT_709 || src.mc==AOM_CICP_MC_BT_2020_NCL);
    std::array<std::vector<uint16_t>,3> base, output;
    for (unsigned c=0;c<3;++c) {
        const unsigned width=c?w/2:w, height=c?h/2:h;
        base[c].resize(width*height); output[c].resize(width*height);
        // The interchange files always contain little-endian uint16 native codes.
        std::ifstream file(j.at("base")[c].get<std::string>(),std::ios::binary); assert(file);
        file.read(reinterpret_cast<char*>(base[c].data()),base[c].size()*2);
        assert(file.gcount()==std::streamsize(base[c].size()*2)); char extra; assert(!file.get(extra));
        for (unsigned y=0;y<height;++y) for (unsigned x=0;x<width;++x) {
            const auto v=base[c][y*width+x]; assert(v<(1u<<depth));
            if (depth==8) src.planes[c][y*src.stride[c]+x]=v;
            else reinterpret_cast<uint16_t*>(src.planes[c]+y*src.stride[c])[x]=v;
        }
    }
    const auto p=j.at("parameters"); aom_film_grain_t g{};
    g.apply_grain=g.update_parameters=1; g.bit_depth=depth; g.ar_coeff_lag=3;
    g.ar_coeff_shift=p.at("shift"); g.scaling_shift=p.at("scaling_shift");
    g.grain_scale_shift=p.at("grain_shift"); g.overlap_flag=p.at("overlap");
    g.clip_to_restricted_range=p.at("restricted");
    assert(g.ar_coeff_shift>=6 && g.ar_coeff_shift<=9 && g.scaling_shift>=8 && g.scaling_shift<=11);
    assert(g.grain_scale_shift>=0 && g.grain_scale_shift<=3);
    g.cb_mult=g.cr_mult=128; g.cb_luma_mult=g.cr_luma_mult=192; g.cb_offset=g.cr_offset=256;
    int* coeff[3]={g.ar_coeffs_y,g.ar_coeffs_cb,g.ar_coeffs_cr};
    int(*points[3])[2]={g.scaling_points_y,g.scaling_points_cb,g.scaling_points_cr};
    int* counts[3]={&g.num_y_points,&g.num_cb_points,&g.num_cr_points};
    for (unsigned c=0;c<3;++c) {
        const auto ar=p.at("coefficients")[c].get<std::vector<int>>(); assert(ar.size()==(c?25:24));
        for (unsigned i=0;i<ar.size();++i) { assert(ar[i]>=-128 && ar[i]<=127); coeff[c][i]=ar[i]; }
        const auto curve=j.at("curves")[c].get<std::vector<std::array<int,2>>>();
        assert(curve.size()>=2 && curve.size()<=size_t(c?10:14)); *counts[c]=curve.size();
        for (unsigned i=0;i<curve.size();++i) {
            assert(curve[i][0]>=0 && curve[i][0]<=255 && curve[i][1]>=0 && curve[i][1]<=255);
            if(i) assert(curve[i][0]>curve[i-1][0]);
            points[c][i][0]=curve[i][0]; points[c][i][1]=curve[i][1];
        }
    }
    std::ofstream raw(j.at("output").get<std::string>(),std::ios::binary); assert(raw);
    json rows=json::array();
    for (unsigned seed:seeds) {
        assert(seed<=65535); g.random_seed=seed; assert(av1_add_film_grain(&g,&src,&dst)==0);
        std::array<uint64_t,3> changed{}, endpoints{};
        for (unsigned c=0;c<3;++c) {
            const unsigned width=c?w/2:w, height=c?h/2:h;
            for (unsigned y=0;y<height;++y) for (unsigned x=0;x<width;++x) {
                const auto v=depth==8 ? dst.planes[c][y*dst.stride[c]+x]
                    : reinterpret_cast<uint16_t*>(dst.planes[c]+y*dst.stride[c])[x];
                assert(v>=0 && unsigned(v)<(1u<<depth)); output[c][y*width+x]=v;
                changed[c]+=v!=base[c][y*width+x]; endpoints[c]+=v==0 || v==int((1u<<depth)-1);
            }
            raw.write(reinterpret_cast<const char*>(output[c].data()),output[c].size()*2);
        }
        rows.push_back({{"seed",seed},{"changed_from_base",changed},{"native_endpoints",endpoints}});
    }
    raw.flush(); assert(raw.good()); aom_img_free(&src); aom_img_free(&dst);
    std::cout << json({{"complete",true},{"frames",rows},{"depth",depth},
        {"restricted",bool(g.clip_to_restricted_range)},{"raw_bytes",uint64_t(w)*h*3*seeds.size()}}).dump() << '\n';
}
