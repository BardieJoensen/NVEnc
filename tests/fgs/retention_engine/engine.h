// Bounded development sequence engine. Pinned reference synthesis remains
// diagnostic/offline work, never ordinary production analysis. Source eligibility
// and the pre-encode retained fractions are supplied by separate experiments.
#pragma once
#include <functional>
#include <memory>
#include "NVEncFilmGrainNativePair.h"
#include "NVEncFilmGrainRetainedStrengthBatch.h"
#include "NVEncFilmGrainPreservedChroma.h"
#include "../native_moments_json.h"
extern "C" {
#include "av1/decoder/grain_synthesis.h"
}

namespace fgsdiagnostic {
using namespace fgsmodel;
class NativeSequenceEngine {
public:
    struct Config {
        unsigned width=0,height=0,depth=0,matrix=0,frames=0,shift=6,grainShift=0;
        unsigned copiedChroma=0,preservedChroma=0;
        unsigned seedOrdinalOffset=0;
        uint64_t maxNativeBytes=512ull*1024*1024;
        std::vector<uint16_t> trainingSeeds;
        FilmGrainMomentSpatialPolicy spatialPolicy=FilmGrainMomentSpatialPolicy::FrameWindow;
    };
    using Pictures=std::array<FilmGrainNativePlane,3>;
    using Witness=std::function<void(uint64_t,unsigned,const Pictures&)>;
private:
    struct OwnedPicture {
        std::array<std::vector<uint16_t>,3> data;
        Pictures view(unsigned width) const {
            Pictures p{};
            for(unsigned c=0;c<3;++c)p[c]={data[c].data(),data[c].size(),c?width/2:width};
            return p;
        }
        void copy(const Pictures& p,unsigned width,unsigned height) {
            for(unsigned c=0;c<3;++c) {
                const unsigned w=c?width/2:width,h=c?height/2:height;data[c].resize(size_t(w)*h);
                for(unsigned y=0;y<h;++y)std::copy_n(p[c].data+y*p[c].stride,w,data[c].data()+size_t(y)*w);
            }
        }
    };
    struct Pair { OwnedPicture source,base; };
    struct Images {
        aom_image_t source{},output{};
        ~Images(){aom_img_free(&source);aom_img_free(&output);}
    };
    Config config_;
    Witness witness_;
    std::deque<Pair> pending_;
    FilmGrainNativeShapeTraining training_;
    FilmGrainNativeShape shape_;
    FilmGrainMomentWindow window_;
    Images images_;
    OwnedPicture rendered_;
    uint64_t received_=0,selected_=0,nativeBytes_=0,peakNativeBytes_=0,segment_=0;
    int64_t pts_=0;
    bool failed_=false,finished_=false;
    std::string error_;
    Json rows_=Json::array(),models_=Json::array();
    std::vector<int64_t> readyAt_;
    static void require(bool b,const char* message){if(!b)throw std::runtime_error(message);}
    void fail(const std::exception& e) {failed_=true;if(error_.empty())error_=e.what();}
    uint64_t pairBytes() const {return uint64_t(config_.width)*config_.height*6;}

    void setBase(const Pictures& base) {
        for(unsigned c=0;c<3;++c)for(unsigned y=0;y<(c?config_.height/2:config_.height);++y)
            for(unsigned x=0;x<(c?config_.width/2:config_.width);++x) {
                const auto value=base[c].data[y*base[c].stride+x];
                if(config_.depth==8)images_.source.planes[c][y*images_.source.stride[c]+x]=uint8_t(value);
                else reinterpret_cast<uint16_t*>(images_.source.planes[c]+y*images_.source.stride[c])[x]=value;
            }
    }
    FilmGrainNativeVariance render(unsigned seed,const std::array<unsigned,3>& strengths) {
        aom_film_grain_t g{};g.apply_grain=g.update_parameters=1;g.bit_depth=config_.depth;
        g.ar_coeff_lag=3;g.ar_coeff_shift=config_.shift;g.grain_scale_shift=config_.grainShift;
        g.scaling_shift=11;g.overlap_flag=g.clip_to_restricted_range=1;g.random_seed=seed;
        g.num_y_points=g.num_cb_points=g.num_cr_points=2;
        g.cb_mult=g.cr_mult=128;g.cb_luma_mult=g.cr_luma_mult=192;g.cb_offset=g.cr_offset=256;
        int* coefficients[]={g.ar_coeffs_y,g.ar_coeffs_cb,g.ar_coeffs_cr};
        int(*points[3])[2]={g.scaling_points_y,g.scaling_points_cb,g.scaling_points_cr};
        for(unsigned c=0;c<3;++c) {
            require(strengths[c]<=255,"strength outside syntax range");
            if(config_.preservedChroma&(1u<<c))require(strengths[c]==0,"preserved chroma strength must be zero");
            for(unsigned i=0;i<(c?25:24);++i)coefficients[c][i]=int(c?shape_.colour[c-1].coefficients[i]:shape_.luma.luma.parameters().y[i])-128;
            points[c][0][0]=0;points[c][1][0]=255;points[c][0][1]=points[c][1][1]=strengths[c];
        }
        require(av1_add_film_grain(&g,&images_.source,&images_.output)==0,"reference synthesis failed");
        for(unsigned c=0;c<3;++c)for(unsigned y=0;y<(c?config_.height/2:config_.height);++y)
            for(unsigned x=0;x<(c?config_.width/2:config_.width);++x) {
                const auto value=config_.depth==8?images_.output.planes[c][y*images_.output.stride[c]+x]
                    :reinterpret_cast<uint16_t*>(images_.output.planes[c]+y*images_.output.stride[c])[x];
                if(config_.preservedChroma&(1u<<c)) {
                    const auto base=config_.depth==8?images_.source.planes[c][y*images_.source.stride[c]+x]
                        :reinterpret_cast<uint16_t*>(images_.source.planes[c]+y*images_.source.stride[c])[x];
                    require(value==base,"preserved chroma changed during synthesis");
                }
                rendered_.data[c][size_t(y)*(c?config_.width/2:config_.width)+x]=value;
            }
        const auto v=film_grain_native_variance(rendered_.view(config_.width),config_.width,config_.height,config_.depth);
        require(v.valid,"invalid synthesized variance");
        if(config_.copiedChroma)require(film_grain_same_constant_chroma(shape_.constants,v.constants,config_.copiedChroma,
            config_.width,config_.height,config_.depth),"copied chroma changed during synthesis");
        return v;
    }
    Json model(unsigned seed,const std::array<unsigned,3>& strengths) const {
        Json coefficients=Json::array(),curves=Json::array();
        for(unsigned c=0;c<3;++c) {
            std::vector<int> values;
            for(unsigned i=0;i<(c?25:24);++i)values.push_back(int(c?shape_.colour[c-1].coefficients[i]:shape_.luma.luma.parameters().y[i])-128);
            coefficients.push_back(values);curves.push_back(Json::array({{0,strengths[c]},{255,strengths[c]}}));
        }
        return {{"apply",true},{"seed",seed},{"ar_shift",config_.shift},{"grain_shift",config_.grainShift},
            {"scaling_shift",11},{"overlap",1},{"restricted",1},{"curves",curves},{"coefficients",coefficients}};
    }
    void select(const Pictures& source,const Pictures& base) {
        const auto target=film_grain_native_variance(source,config_.width,config_.height,config_.depth);
        const auto original=film_grain_native_variance(base,config_.width,config_.height,config_.depth);
        const auto sourceMoments=film_grain_native_moments(source,config_.width,config_.height,config_.depth);
        require(target.valid && original.valid && sourceMoments.valid,"invalid selection inputs");
        if(config_.copiedChroma) {
            require(film_grain_same_constant_chroma(target.constants,original.constants,config_.copiedChroma,
                config_.width,config_.height,config_.depth),"copied chroma source/base differs");
            require(film_grain_same_constant_chroma(shape_.constants,target.constants,config_.copiedChroma,
                config_.width,config_.height,config_.depth),"copied chroma changed within segment");
        }
        setBase(base);
        const unsigned indexes[3][2]={{0,1},{2,2},{3,3}};
        std::array<FilmGrainRetainedStrengthTarget,3> targets{};
        for(unsigned c=0;c<3;++c) {
            targets[c].channels=c?1:2;
            for(unsigned k=0;k<targets[c].channels;++k) {
                const auto i=indexes[c][k];targets[c].source[k]=target.variance[0][i];
                targets[c].missing[k]=target.variance[0][i]-original.variance[0][i];
            }
        }
        std::array<unsigned,4> seeds{};
        // Independent shape intervals must not restart the displayed seed phase.
        for(unsigned i=0;i<4;++i)seeds[i]=unsigned((27109+7919*((selected_+config_.seedOrdinalOffset)*4+i))%65536);
        Json candidates=Json::array();FilmGrainNativeMoments selectedMoments;
        const auto choice=film_grain_select_moment_seed(sourceMoments,seeds.data(),seeds.size(),[&](unsigned seed) {
            Json trace=Json::array();
            const auto fitted=film_grain_calibrate_retained_strength_batch(targets,[&](const std::array<unsigned,3>& strengths) {
                const auto stats=render(seed,strengths);trace.push_back({{"scales",strengths},{"total_variance",stats.variance[0]}});
                std::array<FilmGrainRetainedStrengthMeasurement,3> result{};
                for(unsigned c=0;c<3;++c) {result[c].valid=true;for(unsigned k=0;k<targets[c].channels;++k) {
                    const auto i=indexes[c][k];result[c].variance[k]=stats.variance[0][i]-original.variance[0][i];
                }}
                return result;
            },config_.copiedChroma,config_.preservedChroma);
            FilmGrainMomentCandidate candidate;candidate.calibrated=fitted.valid;
            for(unsigned c=0;c<3;++c)candidate.strengths[c]=fitted.components[c].strength;
            if(fitted.valid) {
                render(seed,candidate.strengths);
                candidate.moments=film_grain_native_moments(rendered_.view(config_.width),config_.width,config_.height,config_.depth);
                selectedMoments=candidate.moments;
                if(witness_)witness_(selected_,seed,rendered_.view(config_.width));
            }
            candidates.push_back({{"seed",seed},{"calibrated",fitted.valid},{"trace",trace},{"scales",candidate.strengths}});
            return candidate;
        },config_.spatialPolicy,config_.copiedChroma);
        rows_.push_back({{"ordinal",selected_},{"selection",fgsdiagnostic::selection(choice)},{"candidates",candidates}});
        require(choice.complete && choice.passesDiagnostic && choice.selected>=0,"candidate selection/check fold failed");
        require(window_.push(selected_,segment_,sourceMoments,selectedMoments),"frame/window diagnostics failed");
        const auto& picked=choice.attempts.at(size_t(choice.selected));models_.push_back(model(picked.seed,picked.strengths));
        ++selected_;
        if(window_.windows())rows_.back()["last_window"]=comparison(window_.lastWindow());
        for(size_t i=0;i<models_.size() && int64_t(i)<=window_.releaseThrough();++i)
            if(readyAt_[i]<0)readyAt_[i]=int64_t(received_-1);
    }
public:
    explicit NativeSequenceEngine(Config config,Witness witness={})
        :config_(std::move(config)),witness_(std::move(witness)),training_(config_.copiedChroma,config_.preservedChroma),window_(config_.copiedChroma) {
        const auto& c=config_;
        require(film_grain_copied_chroma_mask(c.copiedChroma),"only Cb/Cr may be explicitly copied");
        require(film_grain_copied_chroma_mask(c.preservedChroma) && !(c.copiedChroma && c.preservedChroma),
            "preserved chroma mask invalid or combined with constant mode");
        require(c.spatialPolicy==FilmGrainMomentSpatialPolicy::FrameWindow
            || c.spatialPolicy==FilmGrainMomentSpatialPolicy::FullPicture
            || c.spatialPolicy==FilmGrainMomentSpatialPolicy::FullPictureMeans
            || c.spatialPolicy==FilmGrainMomentSpatialPolicy::FrameWindowMeans,"unsupported spatial policy");
        const auto grid=film_grain_native_grid(c.width,c.height);
        require(grid.valid && grid.blocks[1] && (c.depth==8 || c.depth==10)
            && (c.matrix==1 || c.matrix==9) && c.frames>=8 && c.frames<=16
            && c.shift>=6 && c.shift<=9 && c.grainShift<=3,"unsupported sequence config");
        require(c.maxNativeBytes>0 && c.maxNativeBytes<=512ull*1024*1024 && pairBytes()*8<=c.maxNativeBytes,"native buffer budget");
        require(!c.trainingSeeds.empty() && c.trainingSeeds.size()<=32,"training seed budget");
        require(c.seedOrdinalOffset<=15 && c.seedOrdinalOffset+c.frames<=16,"seed interval outside finite sequence");
        for(size_t i=0;i<c.trainingSeeds.size();++i) {
            const auto seed=c.trainingSeeds[i];require(seed!=0 && seed!=18904 && seed!=46372,"degenerate training seed");
            for(size_t j=0;j<i;++j)require(seed!=c.trainingSeeds[j],"duplicate training seed");
        }
        readyAt_.assign(c.frames,-1);
        const auto format=c.depth==8?AOM_IMG_FMT_I420:AOM_IMG_FMT_I42016;
        require(aom_img_alloc(&images_.source,format,c.width,c.height,32)
            && aom_img_alloc(&images_.output,format,c.width,c.height,32),"image allocation failed");
        images_.source.bit_depth=images_.output.bit_depth=c.depth;images_.source.mc=static_cast<aom_matrix_coefficients_t>(c.matrix);
        for(unsigned i=0;i<3;++i)rendered_.data[i].resize(size_t(c.width)*c.height/(i?4:1));
    }
    NativeSequenceEngine(const NativeSequenceEngine&)=delete;
    NativeSequenceEngine& operator=(const NativeSequenceEngine&)=delete;
    void push(uint64_t ordinal,int64_t pts,uint64_t segment,const Pictures& source,const Pictures& base) {
        try {
            require(!failed_ && !finished_ && ordinal==received_ && received_<config_.frames,"sequence input identity/state");
            require(pts!=INT64_MIN && (!received_ || (pts>pts_ && segment==segment_)),"sequence clock/segment changed");
            const auto a=film_grain_native_variance(source,config_.width,config_.height,config_.depth);
            const auto b=film_grain_native_variance(base,config_.width,config_.height,config_.depth);
            require(a.valid && b.valid,"invalid native input planes");
            if(config_.copiedChroma)require(film_grain_same_constant_chroma(a.constants,b.constants,config_.copiedChroma,
                config_.width,config_.height,config_.depth),"copied chroma requires exact constant source and base in range");
            if(config_.preservedChroma)require(film_grain_preserved_chroma_range(source,config_.width,config_.height,config_.depth,config_.preservedChroma)
                && film_grain_preserved_chroma_range(base,config_.width,config_.height,config_.depth,config_.preservedChroma),
                "preserved chroma source/base outside decoder range");
            if(received_<8) {
                const auto moments=film_grain_native_pair(source,base,config_.width,config_.height,config_.depth);
                require(training_.push(ordinal,segment,moments),"invalid native shape training");
                require(nativeBytes_+pairBytes()<=config_.maxNativeBytes,"native buffer budget exceeded");
                auto pair=std::make_unique<Pair>();pair->source.copy(source,config_.width,config_.height);pair->base.copy(base,config_.width,config_.height);
                pending_.push_back(std::move(*pair));nativeBytes_+=pairBytes();peakNativeBytes_=std::max(peakNativeBytes_,nativeBytes_);
            }
            segment_=segment;pts_=pts;++received_;
            if(received_==8) {
                shape_=training_.fit(config_.shift,config_.grainShift,config_.trainingSeeds.data(),config_.trainingSeeds.size());
                require(shape_.valid(),"frozen native shape rejected");
                while(!pending_.empty()) {
                    select(pending_.front().source.view(config_.width),pending_.front().base.view(config_.width));
                    pending_.pop_front();nativeBytes_-=pairBytes();
                }
            } else if(received_>8) select(source,base);
            if(received_==config_.frames)finish();
        }catch(const std::exception& e){fail(e);throw;}
    }
    void finish() {
        try {
            require(!failed_,"sequence engine failed");if(finished_)return;
            require(received_==config_.frames && selected_==received_ && pending_.empty(),"sequence input incomplete");
            require(window_.finish(),"sequence window incomplete");finished_=true;
            for(auto& at:readyAt_)if(at<0)at=int64_t(received_-1);
        }catch(const std::exception& e){fail(e);throw;}
    }
    bool ready(uint64_t ordinal) const {
        return !failed_ && ordinal<models_.size() && readyAt_[ordinal]>=0;
    }
    const Json& selectedModel(uint64_t ordinal) const {
        require(ready(ordinal),"model is not ready");return models_.at(ordinal);
    }
    Json report() const {
        Json result={{"complete",finished_ && !failed_},{"failed",failed_},{"error",error_},
            {"spatial_policy",config_.spatialPolicy==FilmGrainMomentSpatialPolicy::FrameWindowMeans?"frame_window_means"
                :config_.spatialPolicy==FilmGrainMomentSpatialPolicy::FullPictureMeans?"full_picture_means"
                :config_.spatialPolicy==FilmGrainMomentSpatialPolicy::FullPicture?"full_picture":"frame_window"},
            {"received",received_},{"selected",selected_},{"windows",window_.windows()},
            {"release_through",window_.releaseThrough()},{"ready_at",readyAt_},
            {"native_buffer_bytes",nativeBytes_},{"peak_native_buffer_bytes",peakNativeBytes_},
            {"models",models_},{"rows",rows_},{"source_admission",false}};
        if(config_.copiedChroma) {
            result["copied_chroma_mask"]=config_.copiedChroma;
            result["copied_chroma_codes"]=shape_.constants.code;
        }
        if(config_.preservedChroma)result["preserved_chroma_mask"]=config_.preservedChroma;
        if(config_.seedOrdinalOffset)result["seed_ordinal_offset"]=config_.seedOrdinalOffset;
        return result;
    }
};
} // namespace fgsdiagnostic
