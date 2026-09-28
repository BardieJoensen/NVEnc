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
    std::array<std::array<int64_t,3>,2> differences{};
    // Include every visible sample and every border. Padding cannot cancel
    // opposing changes in the independent halves; sum before normalization.
    for(unsigned by=0;by<grid.rows;++by)for(unsigned bx=0;bx<grid.columns;++bx) {
        const auto tile=grid.tile(bx,by);const unsigned fold=(bx+by)&1;
        for(unsigned c=0;c<3;++c) {
            const unsigned factor=c?2:1,w=tile.width/factor,h=tile.height/factor;
            for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
                const size_t yy=tile.y/factor+y,xx=tile.x/factor+x;
                differences[fold][c]+=int(actual[c].data[yy*actual[c].stride+xx])
                    -int(source[c].data[yy*source[c].stride+xx]);
            }
        }
    }
    const double scale=double(1u<<(depth-8));
    result.valid=true;result.pass=true;
    for(unsigned c=0;c<3;++c) {
        // Subtract native integers before normalization, avoiding cancellation
        // between separately rounded large means at the acceptance boundary.
        result.meanError[c]=double(differences[0][c]+differences[1][c])
            /double(uint64_t(width)*height/(c?4:1))/scale;
        result.pass&=std::isfinite(result.meanError[c]) && std::abs(result.meanError[c])<=.125;
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
