// Complete native quiet-region and final-clamp evidence for finite candidates.
// This does not classify arbitrary residual as grain or establish detail safety.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainNativeVariance.h"

namespace fgsmodel {
// The current native fitter emits three active constant two-endpoint curves.
// The caller must separately validate the full model and bind these strengths,
// all input pictures and their clocks to that exact emitted candidate.
struct FilmGrainQuietModel {
    bool apply=true, restricted=true;
    unsigned matrix=1;
    std::array<unsigned,3> strength{};
};
struct FilmGrainQuietRegions {
    uint64_t regions=0, samples=0, quietRegions=0, quietSamples=0;
    uint64_t changedQuiet=0, nonzeroQuiet=0, outputChangedQuiet=0;
    bool pass() const {return !changedQuiet && !nonzeroQuiet && !outputChangedQuiet;}
};
struct FilmGrainQuietRange {
    uint64_t samples=0, safe=0, ambiguous=0, failed=0;
    bool measured() const {return samples && (!ambiguous || failed);}
    bool pass() const {return samples && safe==samples;}
};
struct FilmGrainQuietComponent {
    FilmGrainQuietRegions fine{},coarse{};
    FilmGrainQuietRange range{};
    bool quietPass() const {return fine.pass() && coarse.pass();}
};
struct FilmGrainQuietEvidence {
    bool valid=false;
    std::array<FilmGrainQuietComponent,3> components{};
};

// All planes are native unpacked uint16 codes, including 8-bit inputs. Each
// grid covers every native pixel and partial border. Fine raw variance uses
// exact integer moments. Coarse detrended variance uses direct residual squares
// rather than subtracting nearly equal floating covariance estimates.
inline FilmGrainQuietEvidence film_grain_quiet_evidence(
    const std::array<FilmGrainNativePlane,3>& source,
    const std::array<FilmGrainNativePlane,3>& rounded,
    const std::array<FilmGrainNativePlane,3>& reconstructed,
    const std::array<FilmGrainNativePlane,3>& decoded,
    unsigned width,unsigned height,unsigned depth,const FilmGrainQuietModel& model) {
    FilmGrainQuietEvidence out;
    if(width<64 || height<64 || width>4096 || height>2160 || (width&1) || (height&1)
        || (depth!=8 && depth!=10) || (model.matrix!=1 && model.matrix!=9))return out;
    const unsigned scale=1u<<(depth-8),maximum=(1u<<depth)-1;
    for(unsigned c=0;c<3;++c) {
        if(model.strength[c]>255 || (!model.apply && model.strength[c]))return {};
        const unsigned w=c?width/2:width,h=c?height/2:height;
        for(const auto* frame:{&source,&rounded,&reconstructed,&decoded}) {
            const auto& p=(*frame)[c];
            if(!p.data || p.stride<w || p.stride>65536 || p.samples<p.stride*(h-1)+w)return {};
            for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x)
                if(p.data[size_t(y)*p.stride+x]>maximum)return {};
        }
    }
    for(unsigned c=0;c<3;++c) {
        const unsigned w=c?width/2:width,h=c?height/2:height;
        const auto& s=source[c];const auto& b=rounded[c];
        const auto& r=reconstructed[c];const auto& d=decoded[c];
        auto& result=out.components[c];
        const unsigned low=model.restricted?16*scale:0;
        const unsigned high=model.restricted?(c?240:235)*scale:maximum;
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
            const auto before=r.data[size_t(y)*r.stride+x],after=d.data[size_t(y)*d.stride+x];
            ++result.range.samples;
            if(!model.apply) {
                if(before==after)++result.range.safe;else ++result.range.failed;
            } else if(!model.strength[c]) {
                // A present zero curve still clamps. Equality at an endpoint
                // is safe only because its added grain is identically zero.
                if(before==after && before>=low && before<=high)++result.range.safe;
                else ++result.range.failed;
            } else if(after<low || after>high)++result.range.failed;
            else if(after==low || after==high)++result.range.ambiguous;
            else ++result.range.safe;
        }
        for(unsigned layer=0;layer<2;++layer) {
            const unsigned side=layer?(c?32:64):8;
            auto& regions=layer?result.coarse:result.fine;
            for(unsigned top=0;top<h;top+=side)for(unsigned left=0;left<w;left+=side) {
                const unsigned tw=std::min(side,w-left),th=std::min(side,h-top),n=tw*th;
                uint64_t sum=0,square=0;int64_t sumx=0,sumy=0;
                uint64_t normx=0,normy=0;
                for(unsigned y=0;y<th;++y)for(unsigned x=0;x<tw;++x) {
                    const auto value=s.data[size_t(top+y)*s.stride+left+x];
                    const int xx=int(2*x)-int(tw-1),yy=int(2*y)-int(th-1);
                    sum+=value;square+=uint64_t(value)*value;
                    sumx+=int64_t(value)*xx;sumy+=int64_t(value)*yy;
                    normx+=xx*xx;normy+=yy*yy;
                }
                bool quiet=false;
                if(!layer) {
                    // sigma <= .3 in eight-bit code units; no large floating
                    // moment subtraction, even for weak native ten-bit noise.
                    quiet=100*(uint64_t(n)*square-sum*sum)<=9ull*scale*scale*n*n;
                } else {
                    const double mean=double(sum)/n,sx=normx?double(sumx)/normx:0.,sy=normy?double(sumy)/normy:0.;
                    double residual=0.;
                    for(unsigned y=0;y<th;++y)for(unsigned x=0;x<tw;++x) {
                        const double v=s.data[size_t(top+y)*s.stride+left+x]-mean
                            -sx*(int(2*x)-int(tw-1))-sy*(int(2*y)-int(th-1));
                        residual+=v*v;
                    }
                    quiet=residual/(n*double(scale)*scale)<.04;
                }
                ++regions.regions;regions.samples+=n;
                if(!quiet)continue;
                ++regions.quietRegions;regions.quietSamples+=n;
                if(model.apply && model.strength[c])regions.nonzeroQuiet+=n;
                for(unsigned y=0;y<th;++y)for(unsigned x=0;x<tw;++x) {
                    regions.changedQuiet+=s.data[size_t(top+y)*s.stride+left+x]!=b.data[size_t(top+y)*b.stride+left+x];
                    regions.outputChangedQuiet+=r.data[size_t(top+y)*r.stride+left+x]!=d.data[size_t(top+y)*d.stride+left+x];
                }
            }
        }
    }
    out.valid=true;return out;
}
} // namespace fgsmodel
