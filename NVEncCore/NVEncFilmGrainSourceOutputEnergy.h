// Necessary post-NVENC energy/mean veto for explicit source-preserved rows.
// Copying source into a lossy encoder does not prove decoded grain retention.
// This is not a source classifier or a complete perceptual/detail guarantee.
#pragma once
#include "NVEncFilmGrainNativeVariance.h"

namespace fgsmodel {
struct FilmGrainSourceOutputEnergy {
    bool valid=false,pass=false;
    FilmGrainNativeVariance source{},actual{};
    std::array<double,3> meanError{};
    std::array<bool,3> constantSource{},actualMatchesSource{};
    // Complete local DC and the two discarded affine slopes must not hide
    // behind detrending or cancellation between regions. Errors are maxima
    // in normalized 8-bit units; slopes are measured at the tile's edges.
    std::array<double,3> localMeanError{};
    std::array<std::array<double,2>,3> localSlopeError{};
    std::array<std::array<unsigned,4>,3> localWorstTile{};
    std::array<bool,3> localPlanePass{};
    std::array<std::array<double,3>,2> foldMeanError{};
    std::array<std::array<double,4>,2> relativeVarianceError{};
    std::array<std::array<bool,4>,2> quiet{},variancePass{};
};

inline FilmGrainSourceOutputEnergy film_grain_source_output_energy(
    const std::array<FilmGrainNativePlane,3>& source,const std::array<FilmGrainNativePlane,3>& actual,
    unsigned width,unsigned height,unsigned depth) {
    FilmGrainSourceOutputEnergy result;
    result.source=film_grain_native_variance(source,width,height,depth);
    result.actual=film_grain_native_variance(actual,width,height,depth);
    if(!result.source.valid || !result.actual.valid)return result;
    const auto grid=film_grain_native_grid(width,height);
    const double scale=double(1u<<(depth-8));
    std::array<std::array<int64_t,3>,2> differences{};
    result.constantSource.fill(true);result.actualMatchesSource.fill(true);
    // Include every visible sample and every border. Padding cannot cancel
    // opposing changes in the independent halves; sum before normalization.
    for(unsigned by=0;by<grid.rows;++by)for(unsigned bx=0;bx<grid.columns;++bx) {
        const auto tile=grid.tile(bx,by);const unsigned fold=(bx+by)&1;
        for(unsigned c=0;c<3;++c) {
            const unsigned factor=c?2:1,w=tile.width/factor,h=tile.height/factor;
            std::array<int64_t,3> local{};
            for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
                const size_t yy=tile.y/factor+y,xx=tile.x/factor+x;
                const auto original=source[c].data[yy*source[c].stride+xx];
                const auto reconstructed=actual[c].data[yy*actual[c].stride+xx];
                const int64_t difference=int(reconstructed)-int(original);
                differences[fold][c]+=difference;
                local[0]+=difference;
                // Twice-centered coordinates keep the differences and moments
                // integral, including even dimensions and ragged edge tiles.
                local[1]+=difference*(2*int(x)-int(w-1));
                local[2]+=difference*(2*int(y)-int(h-1));
                result.constantSource[c]&=original==source[c].data[0];
                result.actualMatchesSource[c]&=reconstructed==original;
            }
            const double samples=double(uint64_t(w)*h);
            const double mean=std::abs(double(local[0]))/samples/scale;
            const double sx=w>1?std::abs(double(local[1]))/(samples*(double(w)*w-1)/3)*(w-1)/scale:0.;
            const double sy=h>1?std::abs(double(local[2]))/(samples*(double(h)*h-1)/3)*(h-1)/scale:0.;
            const double previous=std::max({result.localMeanError[c],result.localSlopeError[c][0],result.localSlopeError[c][1]});
            if(std::max({mean,sx,sy})>previous)
                result.localWorstTile[c]={tile.x/factor,tile.y/factor,w,h};
            result.localMeanError[c]=std::max(result.localMeanError[c],mean);
            result.localSlopeError[c][0]=std::max(result.localSlopeError[c][0],sx);
            result.localSlopeError[c][1]=std::max(result.localSlopeError[c][1],sy);
        }
    }
    result.valid=true;result.pass=true;
    for(unsigned c=0;c<3;++c) {
        // Tile detrending removes constant offsets. Opposite tile offsets can
        // cancel in both spatial-half means while adding a false block edge.
        // A truly constant original needs no noise classification: require
        // its actual samples, including all borders, to remain unchanged.
        result.pass&=!result.constantSource[c] || result.actualMatchesSource[c];
        // Subtract native integers before normalization, avoiding cancellation
        // between separately rounded large means at the acceptance boundary.
        result.meanError[c]=double(differences[0][c]+differences[1][c])
            /double(uint64_t(width)*height/(c?4:1))/scale;
        result.pass&=std::isfinite(result.meanError[c]) && std::abs(result.meanError[c])<=.125;
        // Bound each independent discarded basis component. Their signs or
        // errors elsewhere cannot compensate for a changed local picture.
        result.localPlanePass[c]=std::isfinite(result.localMeanError[c]) && result.localMeanError[c]<=.125;
        for(const auto slope:result.localSlopeError[c])
            result.localPlanePass[c]&=std::isfinite(slope) && slope<=.125;
        result.pass&=result.localPlanePass[c];
    }
    for(unsigned f=0;f<2;++f) {
        for(unsigned c=0;c<3;++c) {
            const double pixels=double(grid.pixels[f]/(c?4:1));
            result.foldMeanError[f][c]=double(differences[f][c])/pixels/scale;
            result.pass&=std::isfinite(result.foldMeanError[f][c]) && std::abs(result.foldMeanError[f][c])<=.125;
        }
        for(unsigned c=0;c<4;++c) {
            const double a=result.source.variance[f][c],b=result.actual.variance[f][c];
            // Existing native zero tolerance is numerical, not a grain floor.
            // A quiet source cannot turn added texture into a relative pass.
            result.quiet[f][c]=a<=1e-12;
            if(result.quiet[f][c])result.variancePass[f][c]=b<=1e-12;
            else {
                result.relativeVarianceError[f][c]=std::abs(b-a)/a;
                result.variancePass[f][c]=std::isfinite(result.relativeVarianceError[f][c])
                    && result.relativeVarianceError[f][c]<=.08;
            }
            result.pass&=result.variancePass[f][c];
        }
    }
    return result;
}
} // namespace fgsmodel
