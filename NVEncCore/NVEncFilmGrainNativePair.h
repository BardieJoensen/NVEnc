// Oriented native source/reconstructed-base moments for a bounded shape fit.
// Whole-picture measurements do not identify grain or approve populations.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainMomentComparison.h"
#include "NVEncFilmGrainRetainedModel.h"

namespace fgsmodel {
struct FilmGrainNativePairMoments {
    bool valid = false;
    unsigned width = 0, height = 0, depth = 0;
    FilmGrainConstantChroma sourceConstants{},baseConstants{};
    std::array<FilmGrainRetainedLumaMoments,2> luma{};
    // Component first, then disjoint spatial fold.
    std::array<std::array<FilmGrainJointMoments,2>,2> colour{};
};

namespace native_pair_detail {
// Unlike autocovariance, S_i * B_j has no i/j symmetry. Query every oriented
// pair on its own shifted support; negative displacements are needed too.
inline void spatial(const double* source, const double* base, unsigned width,unsigned height,
    std::array<double,625>& matrix) {
    const auto positions = native_moments_detail::offsets();
    std::array<double,4225> integral{}; const unsigned stride = width+1;
    for (int dy = -3; dy <= 3; ++dy) for (int dx = -6; dx <= 6; ++dx) {
        bool used = false;
        for (unsigned i = 0; i < 25 && !used; ++i) for (unsigned j = 0; j < 25; ++j)
            if (positions[j].y-positions[i].y == dy && positions[j].x-positions[i].x == dx) { used = true; break; }
        if (!used) continue;
        for (unsigned y = 0; y < height; ++y) {
            double row = 0.;
            for (unsigned x = 0; x < width; ++x) {
                const int yy = int(y)+dy, xx = int(x)+dx;
                if (yy >= 0 && yy < int(height) && xx >= 0 && xx < int(width))
                    row += source[y*width+x]*base[unsigned(yy)*width+unsigned(xx)];
                integral[(y+1)*stride+x+1] = integral[y*stride+x+1]+row;
            }
        }
        for (unsigned i = 0; i < 25; ++i) for (unsigned j = 0; j < 25; ++j) {
            if (positions[j].y-positions[i].y != dy || positions[j].x-positions[i].x != dx) continue;
            const unsigned top = unsigned(3+positions[i].y), left = unsigned(3+positions[i].x);
            const unsigned bottom = unsigned(int(height)-3+positions[i].y), right = unsigned(int(width)-3+positions[i].x);
            matrix[i*25+j] += integral[bottom*stride+right]-integral[top*stride+right]
                -integral[bottom*stride+left]+integral[top*stride+left];
        }
    }
}
inline void spatial(const double* source,const double* base,unsigned side,std::array<double,625>& matrix) {
    spatial(source,base,side,side,matrix);
}
} // namespace native_pair_detail

inline FilmGrainNativePairMoments film_grain_native_pair(
    const std::array<FilmGrainNativePlane,3>& sourcePlanes,
    const std::array<FilmGrainNativePlane,3>& basePlanes,
    unsigned width, unsigned height, unsigned depth) {
    FilmGrainNativePairMoments result;
    const auto source = film_grain_native_moments(sourcePlanes,width,height,depth);
    const auto base = film_grain_native_moments(basePlanes,width,height,depth);
    if (!film_grain_moment_same_layout(source,base)) return result;
    result.width = width; result.height = height; result.depth = depth;
    result.sourceConstants=source.constants;result.baseConstants=base.constants;
    const auto grid=film_grain_native_grid(width,height);
    for (unsigned f = 0; f < 2; ++f) {
        auto& y = result.luma[f]; y.blocks = source.blocks[f]; y.observations = grid.lumaObservations[f];
        for (unsigned i = 0; i < 625; ++i) {
            y.source[i] = source.folds[f].y[i]*y.observations;
            y.base[i] = base.folds[f].y[i]*y.observations;
        }
        for (unsigned c = 0; c < 2; ++c) {
            auto& m = result.colour[c][f]; m.blocks = y.blocks; m.observations = grid.colourObservations[f];
            for (unsigned i = 0; i < 676; ++i) {
                m.source[i] = source.folds[f].colour[c][i]*m.observations;
                m.base[i] = base.folds[f].colour[c][i]*m.observations;
            }
        }
    }
    const auto positions = native_moments_detail::offsets();
    std::array<std::array<double,4096>,4> s{}, b{};
    for (unsigned by = 0; by < grid.rows; ++by) for (unsigned bx = 0; bx < grid.columns; ++bx) {
        const auto bounds=grid.tile(bx,by);const unsigned cw=bounds.width/2,ch=bounds.height/2;
        const unsigned fold = (by+bx)&1;
        native_moments_detail::load_tiles(sourcePlanes,bounds,depth,s);
        native_moments_detail::load_tiles(basePlanes,bounds,depth,b);
        native_pair_detail::spatial(s[0].data(),b[0].data(),bounds.width,bounds.height,result.luma[fold].sourceBase);
        for (unsigned c = 0; c < 2; ++c) {
            auto& cross = result.colour[c][fold].sourceBase;
            std::array<double,625> marginal{};
            native_pair_detail::spatial(s[c+2].data(),b[c+2].data(),cw,ch,marginal);
            for (unsigned i = 0; i < 25; ++i) for (unsigned j = 0; j < 25; ++j)
                cross[(i==24?25:i)*26+(j==24?25:j)] += marginal[i*25+j];
            for (unsigned i = 0; i < 25; ++i) {
                double colourLuma = 0., lumaColour = 0.;
                for (unsigned y = 3; y < ch-3; ++y) for (unsigned x = 3; x < cw-3; ++x) {
                    const unsigned at = unsigned(int(y)+positions[i].y)*cw+unsigned(int(x)+positions[i].x);
                    colourLuma += s[c+2][at]*b[1][y*cw+x];
                    lumaColour += s[1][y*cw+x]*b[c+2][at];
                }
                const unsigned row = i==24?25:i;
                cross[row*26+24] += colourLuma; cross[24*26+row] += lumaColour;
            }
            for (unsigned y = 3; y < ch-3; ++y) for (unsigned x = 3; x < cw-3; ++x)
                cross[24*26+24] += s[1][y*cw+x]*b[1][y*cw+x];
        }
    }
    for (const auto& m : result.luma) for (double v : m.sourceBase) if (!std::isfinite(v)) return result;
    for (const auto& component : result.colour) for (const auto& m : component)
        for (double v : m.sourceBase) if (!std::isfinite(v)) return result;
    result.valid = true;
    return result;
}

struct FilmGrainNativeShape {
    FilmGrainRetainedLumaFit luma{};
    std::array<FilmGrainRetainedChroma,2> colour{};
    uint32_t reasons = FGS_RETAIN_MODEL_INVALID;
    unsigned copiedChroma=0,preservedChroma=0;
    FilmGrainConstantChroma constants{};
    bool valid() const {
        if(reasons || !luma.valid() || !film_grain_copied_chroma_mask(copiedChroma)
            || !film_grain_copied_chroma_mask(preservedChroma) || (copiedChroma && preservedChroma))return false;
        if(copiedChroma && !constants.covers(copiedChroma,constants.width,constants.height,constants.depth))return false;
        for(unsigned c=0;c<2;++c) {
            if(!((copiedChroma|preservedChroma)&(2u<<c))) {if(!colour[c].valid())return false;}
            else {
                // No colour regression was fitted. These coefficients are
                // neutral placeholders for a separately proved zero curve.
                if(colour[c].constructed || colour[c].reasons)return false;
                for(auto v:colour[c].coefficients)if(v!=128)return false;
            }
        }
        return true;
    }
};

class FilmGrainNativeShapeTraining {
    unsigned width_ = 0, height_ = 0, depth_ = 0, frames_ = 0;
    uint64_t segment_ = 0;
    bool failed_ = false;
    FilmGrainRetainedLumaMoments luma_{};
    std::array<FilmGrainJointMoments,2> colour_{};
    unsigned copiedChroma_=0,preservedChroma_=0;
    FilmGrainConstantChroma constants_{};
    bool reject() { failed_ = true; return false; }
    template<class Moments> static bool add(Moments& to, const Moments& from,
        uint64_t blocks, uint64_t observations) {
        if (from.blocks != blocks || from.observations != observations) return false;
        to.blocks += from.blocks; to.observations += from.observations;
        for (size_t i = 0; i < to.source.size(); ++i) {
            if (!std::isfinite(from.source[i]) || !std::isfinite(from.base[i])
                || !std::isfinite(from.sourceBase[i])) return false;
            to.source[i] += from.source[i]; to.base[i] += from.base[i]; to.sourceBase[i] += from.sourceBase[i];
            if (!std::isfinite(to.source[i]) || !std::isfinite(to.base[i])
                || !std::isfinite(to.sourceBase[i])) return false;
        }
        return true;
    }
public:
    // Preserved nonconstant colour gets no fitted regression. The caller must
    // prove native range/zero synthesis and run the ordinary complete joint
    // comparisons; this flag does not waive any source/quality requirement.
    explicit FilmGrainNativeShapeTraining(unsigned copiedChroma=0,unsigned preservedChroma=0):
        copiedChroma_(copiedChroma),preservedChroma_(preservedChroma) {}
    // Fixed first-eight training half only. It neither reads the check half
    // nor chooses which pictures/populations make a convenient fit.
    bool push(uint64_t ordinal, uint64_t segment, const FilmGrainNativePairMoments& m) {
        if (failed_) return false;
        FilmGrainNativeMoments layout;
        layout.valid = m.valid; layout.width = m.width; layout.height = m.height; layout.depth = m.depth;
        layout.blocks = {m.luma[0].blocks,m.luma[1].blocks};
        if (frames_ >= 8 || ordinal != frames_ || !film_grain_moment_layout(layout)
            || (frames_ && (width_ != m.width || height_ != m.height || depth_ != m.depth || segment_ != segment)))
            return reject();
        if(!film_grain_copied_chroma_mask(copiedChroma_) || !film_grain_copied_chroma_mask(preservedChroma_)
            || (copiedChroma_ && preservedChroma_))return reject();
        if(copiedChroma_) {
            if(!film_grain_same_constant_chroma(m.sourceConstants,m.baseConstants,copiedChroma_,m.width,m.height,m.depth)
                || (frames_ && !film_grain_same_constant_chroma(constants_,m.sourceConstants,copiedChroma_,m.width,m.height,m.depth)))return reject();
            // A constant's entire source/base/cross row is zero, including
            // its relation to Y. Inconsistent moment evidence must not skip a
            // singular fit and silently become an accepted model.
            for(unsigned c=0;c<2;++c)if(copiedChroma_&(2u<<c))for(const auto& f:m.colour[c])
                for(unsigned i=0;i<26;++i)for(unsigned j=0;j<26;++j)if(i!=24 || j!=24)
                    if(f.source[i*26+j]!=0. || f.base[i*26+j]!=0. || f.sourceBase[i*26+j]!=0.)return reject();
            constants_=m.sourceConstants;
        }
        const auto grid=film_grain_native_grid(m.width,m.height);
        if (!add(luma_,m.luma[0],layout.blocks[0],grid.lumaObservations[0])
            || !add(colour_[0],m.colour[0][0],layout.blocks[0],grid.colourObservations[0])
            || !add(colour_[1],m.colour[1][0],layout.blocks[0],grid.colourObservations[0])) return reject();
        width_ = m.width; height_ = m.height; depth_ = m.depth; segment_ = segment; ++frames_;
        return true;
    }
    FilmGrainNativeShape fit(unsigned shift, unsigned grainShift, const uint16_t* seeds, size_t count) const {
        FilmGrainNativeShape result;
        if (failed_ || frames_ != 8 || !seeds || !count || count > 32) return result;
        for (size_t i = 0; i < count; ++i) {
            if (seeds[i] == 0 || seeds[i] == 18904 || seeds[i] == 46372) return result;
            for (size_t j = 0; j < i; ++j) if (seeds[i] == seeds[j]) return result;
        }
        result.luma = film_grain_fit_retained_luma({luma_},depth_,shift,grainShift,seeds,count);
        result.copiedChroma=copiedChroma_;result.preservedChroma=preservedChroma_;result.constants=constants_;
        result.reasons = result.luma.reasons;
        if (!result.luma.valid()) { result.reasons |= FGS_RETAIN_MODEL_LUMA; return result; }
        for (unsigned c = 0; c < 2; ++c) {
            if((copiedChroma_|preservedChroma_)&(2u<<c)) {result.colour[c].coefficients.fill(128);continue;}
            result.colour[c] = film_grain_fit_retained_chroma({colour_[c]},result.luma.luma);
            result.reasons |= result.colour[c].reasons;
        }
        return result;
    }
    unsigned frames() const { return frames_; }
    const FilmGrainRetainedLumaMoments& luma() const { return luma_; }
    const std::array<FilmGrainJointMoments,2>& colour() const { return colour_; }
};
} // namespace fgsmodel
