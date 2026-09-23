// In-process pinned AOM/native measurement adapter for automatic calibration.
// Shape/source eligibility and independent final quality checks remain external.
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>
#include "NVEncFilmGrainNativeVariance.h"
#include "NVEncFilmGrainRetainedStrengthBatch.h"
#include "json.hpp"
extern "C" {
#include "av1/decoder/grain_synthesis.h"
}
using Json=nlohmann::json;
using namespace fgsmodel;
static void require(bool value,const char* why){if(!value)throw std::runtime_error(why);}
struct Images {
    aom_image_t source{},output{};
    ~Images(){aom_img_free(&source);aom_img_free(&output);}
};
int main() {
    try {
        Json j;std::cin>>j;const unsigned w=j.at("width"),h=j.at("height"),depth=j.at("depth");
        require(w>=64 && h>=64 && w<=4096 && h<=2160 && w%64==0 && h%64==0 && (depth==8 || depth==10),"unsupported native layout");
        const auto seeds=j.at("seeds").get<std::vector<unsigned>>();require(!seeds.empty() && seeds.size()<=4,"seed budget");
        for(auto seed:seeds)require(seed<=65535 && seed!=0 && seed!=18904 && seed!=46372,"invalid/degenerate seed");
        require(std::set<unsigned>(seeds.begin(),seeds.end()).size()==seeds.size(),"duplicate seeds");
        const auto prefix=std::filesystem::u8path(j.at("output_prefix").get<std::string>());require(prefix.is_absolute(),"absolute output prefix required");
        std::array<std::vector<uint16_t>,3> source,base,rendered;
        std::array<FilmGrainNativePlane,3> sourcePlanes{},basePlanes{},outputPlanes{};
        for(unsigned c=0;c<3;++c) {
            const unsigned width=c?w/2:w,height=c?h/2:h;const size_t count=size_t(width)*height;
            for(auto pair:{std::make_pair(&source[c],"source"),std::make_pair(&base[c],"base")}) {
                const auto path=std::filesystem::u8path(j.at(pair.second).at(c).get<std::string>());require(std::filesystem::file_size(path)==count*2,"native plane byte count differs");
                pair.first->resize(count);std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(pair.first->data()),count*2);require(bool(file),"native plane read failed");
            }
            rendered[c].resize(count);sourcePlanes[c]={source[c].data(),count,width};basePlanes[c]={base[c].data(),count,width};outputPlanes[c]={rendered[c].data(),count,width};
        }
        const auto target=film_grain_native_variance(sourcePlanes,w,h,depth),original=film_grain_native_variance(basePlanes,w,h,depth);
        require(target.valid && original.valid,"invalid native measurement");
        Images images;const auto format=depth==8?AOM_IMG_FMT_I420:AOM_IMG_FMT_I42016;
        require(aom_img_alloc(&images.source,format,w,h,32) && aom_img_alloc(&images.output,format,w,h,32),"image allocation failed");
        images.source.bit_depth=images.output.bit_depth=depth;const unsigned matrix=j.at("matrix");require(matrix==1 || matrix==9,"unsupported matrix");images.source.mc=static_cast<aom_matrix_coefficients_t>(matrix);
        for(unsigned c=0;c<3;++c)for(unsigned y=0;y<(c?h/2:h);++y)for(unsigned x=0;x<(c?w/2:w);++x) {
            const auto value=base[c][size_t(y)*(c?w/2:w)+x];
            if(depth==8)images.source.planes[c][y*images.source.stride[c]+x]=uint8_t(value);
            else reinterpret_cast<uint16_t*>(images.source.planes[c]+y*images.source.stride[c])[x]=value;
        }
        aom_film_grain_t grain{};grain.apply_grain=grain.update_parameters=1;grain.bit_depth=depth;grain.ar_coeff_lag=3;
        const auto& p=j.at("parameters");grain.ar_coeff_shift=p.at("shift");grain.scaling_shift=p.at("scaling_shift");grain.grain_scale_shift=p.at("grain_shift");grain.overlap_flag=p.at("overlap");grain.clip_to_restricted_range=p.at("restricted");
        require(grain.ar_coeff_shift>=6 && grain.ar_coeff_shift<=9 && grain.scaling_shift>=8 && grain.scaling_shift<=11 && grain.grain_scale_shift>=0 && grain.grain_scale_shift<=3,"invalid model shifts");
        require(grain.overlap_flag==1 && grain.clip_to_restricted_range==1,"unqualified overlap/range");
        grain.cb_mult=grain.cr_mult=128;grain.cb_luma_mult=grain.cr_luma_mult=192;grain.cb_offset=grain.cr_offset=256;
        int* coeff[3]={grain.ar_coeffs_y,grain.ar_coeffs_cb,grain.ar_coeffs_cr};int(*points[3])[2]={grain.scaling_points_y,grain.scaling_points_cb,grain.scaling_points_cr};
        grain.num_y_points=grain.num_cb_points=grain.num_cr_points=2;
        for(unsigned c=0;c<3;++c) {
            const auto a=p.at("coefficients").at(c).get<std::vector<int>>();require(a.size()==(c?25:24),"coefficient count");
            for(size_t i=0;i<a.size();++i){require(a[i]>=-128 && a[i]<=127,"coefficient range");coeff[c][i]=a[i];}
            points[c][0][0]=0;points[c][1][0]=255;
        }
        const unsigned indexes[3][2]={{0,1},{2,2},{3,3}};std::array<FilmGrainRetainedStrengthTarget,3> targets{};
        for(unsigned c=0;c<3;++c){targets[c].channels=c?1:2;for(unsigned k=0;k<targets[c].channels;++k){const auto i=indexes[c][k];targets[c].source[k]=target.variance[0][i];targets[c].missing[k]=target.variance[0][i]-original.variance[0][i];}}
        auto render=[&](unsigned seed,const std::array<unsigned,3>& strengths) {
            grain.random_seed=seed;for(unsigned c=0;c<3;++c){require(strengths[c]<=255,"strength range");points[c][0][1]=points[c][1][1]=strengths[c];}
            require(av1_add_film_grain(&grain,&images.source,&images.output)==0,"AOM synthesis failed");
            for(unsigned c=0;c<3;++c)for(unsigned y=0;y<(c?h/2:h);++y)for(unsigned x=0;x<(c?w/2:w);++x) {
                const auto value=depth==8?images.output.planes[c][y*images.output.stride[c]+x]:reinterpret_cast<uint16_t*>(images.output.planes[c]+y*images.output.stride[c])[x];rendered[c][size_t(y)*(c?w/2:w)+x]=value;
            }
            const auto measurement=film_grain_native_variance(outputPlanes,w,h,depth);require(measurement.valid,"invalid synthesized measurement");return measurement;
        };
        const auto start=std::chrono::steady_clock::now();Json rows=Json::array();
        for(auto seed:seeds) {
            Json trace=Json::array();
            const auto fitted=film_grain_calibrate_retained_strength_batch(targets,[&](const std::array<unsigned,3>& strengths) {
                const auto stats=render(seed,strengths);trace.push_back({{"scales",strengths},{"total_variance",stats.variance[0]}});
                std::array<FilmGrainRetainedStrengthMeasurement,3> result;
                for(unsigned c=0;c<3;++c){result[c].valid=true;for(unsigned k=0;k<targets[c].channels;++k){const auto i=indexes[c][k];result[c].variance[k]=stats.variance[0][i]-original.variance[0][i];}}
                return result;
            });
            std::array<unsigned,3> strengths{};Json components=Json::array();for(unsigned c=0;c<3;++c){const auto& f=fitted.components[c];strengths[c]=f.strength;components.push_back({{"valid",f.valid},{"strength",f.strength},{"error",f.error},{"evaluations",f.samples.size()}});}
            Json row={{"seed",seed},{"complete",fitted.complete},{"valid",fitted.valid},{"components",components},{"trace",trace},{"scales",strengths}};
            if(fitted.valid) {
                const auto stats=render(seed,strengths);const auto path=std::filesystem::u8path(prefix.u8string()+"-"+std::to_string(seed)+".raw");require(!std::filesystem::exists(path),"output exists");std::ofstream output(path,std::ios::binary);for(const auto& a:rendered)output.write(reinterpret_cast<const char*>(a.data()),a.size()*2);output.flush();require(bool(output),"output write failed");
                row["output"]=path.u8string();row["final_variance"]=stats.variance;row["mean"]=stats.mean;
            }
            rows.push_back(row);
        }
        Json probes=Json::array();
        if(j.contains("independence_scales")) {
            const auto& scales=j.at("independence_scales");require(scales.is_array() && scales.size()<=16,"probe budget");
            for(size_t index=0;index<scales.size();++index) {
                const auto strengths=scales.at(index).get<std::array<unsigned,3>>();const auto stats=render(seeds.front(),strengths);
                const auto path=std::filesystem::u8path(prefix.u8string()+"-probe"+std::to_string(index)+".raw");require(!std::filesystem::exists(path),"probe output exists");std::ofstream output(path,std::ios::binary);for(const auto& a:rendered)output.write(reinterpret_cast<const char*>(a.data()),a.size()*2);output.flush();require(bool(output),"probe output write failed");
                probes.push_back({{"scales",strengths},{"output",path.u8string()},{"variance",stats.variance},{"mean",stats.mean}});
            }
        }
        for(unsigned c=0;c<3;++c)for(unsigned y=0;y<(c?h/2:h);++y)for(unsigned x=0;x<(c?w/2:w);++x) {
            const auto value=depth==8?images.source.planes[c][y*images.source.stride[c]+x]:reinterpret_cast<uint16_t*>(images.source.planes[c]+y*images.source.stride[c])[x];
            require(value==base[c][size_t(y)*(c?w/2:w)+x],"AOM changed its base input");
        }
        std::cout<<Json({{"complete",true},{"source_variance",target.variance},{"base_variance",original.variance},{"source_mean",target.mean},{"base_mean",original.mean},{"rows",rows},{"independence",probes},{"seconds",std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()}}).dump()<<'\n';return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
