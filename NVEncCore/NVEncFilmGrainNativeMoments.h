// Spatial/colour measurements on complete disjoint native partitions.
// These moments alone do not establish source eligibility or perceptual quality.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <algorithm>
#include "NVEncFilmGrainNativeVariance.h"

namespace fgsmodel {
struct FilmGrainNativeMomentFold {
    // Complete native samples in this fixed checkerboard half, before
    // detrending. Missing older diagnostic evidence is never a zero mean.
    bool meanValid=false;
    std::array<double,3> mean{};
    std::array<double,625> y{};
    std::array<std::array<double,676>,2> colour{};
    std::array<double,9> common{};
    std::array<double,49> cross{};
};
struct FilmGrainNativeMoments {
    bool valid=false;
    unsigned width=0,height=0,depth=0;
    std::array<double,3> mean{};
    std::array<uint64_t,2> blocks{};
    std::array<FilmGrainNativeMomentFold,2> folds{};
};

namespace native_moments_detail {
struct Offset {int y,x;};
inline std::array<Offset,25> offsets() {
    std::array<Offset,25> out{};unsigned i=0;
    for(int y=-3;y<=0;++y)for(int x=-3;x<=3;++x)if(y<0 || x<0)out[i++]={y,x};
    out[24]={0,0};return out;
}
// Every pair is an integral of the same displacement-product image over a
// shifted rectangle. Compute each displacement once per tile, then query all
// pairs that use it. This preserves the exact inner support of each variable;
// replacing a shifted covariance by the central autocorrelation would not.
inline void spatial(const double* tile,unsigned width,unsigned height,std::array<double,625>& matrix) {
    const auto positions=offsets();std::array<double,4225> integral{};const unsigned stride=width+1;
    for(int dy=0;dy<=3;++dy)for(int dx=-6;dx<=6;++dx) {
        bool used=false;
        for(unsigned i=0;i<25 && !used;++i)for(unsigned j=i;j<25;++j)
            if(positions[j].y-positions[i].y==dy && positions[j].x-positions[i].x==dx){used=true;break;}
        if(!used)continue;
        for(unsigned y=0;y<height;++y) {
            double row=0.;
            for(unsigned x=0;x<width;++x) {
                const int yy=int(y)+dy,xx=int(x)+dx;
                if(yy>=0 && yy<int(height) && xx>=0 && xx<int(width))row+=tile[y*width+x]*tile[unsigned(yy)*width+unsigned(xx)];
                integral[(y+1)*stride+x+1]=integral[y*stride+x+1]+row;
            }
        }
        for(unsigned i=0;i<25;++i)for(unsigned j=i;j<25;++j) {
            if(positions[j].y-positions[i].y!=dy || positions[j].x-positions[i].x!=dx)continue;
            const unsigned top=unsigned(3+positions[i].y),left=unsigned(3+positions[i].x);
            const unsigned bottom=unsigned(int(height)-3+positions[i].y),right=unsigned(int(width)-3+positions[i].x);
            const double value=integral[bottom*stride+right]-integral[top*stride+right]-integral[bottom*stride+left]+integral[top*stride+left];
            matrix[i*25+j]+=value;if(i!=j)matrix[j*25+i]+=value;
        }
    }
}
inline void spatial(const double* tile,unsigned side,std::array<double,625>& matrix) {
    spatial(tile,side,side,matrix);
}
inline void detrend(double* tile,unsigned width,unsigned height) {
    const double centerx=(width-1)*.5,centery=(height-1)*.5;double sum=0.,sumx=0.,sumy=0.,normx=0.,normy=0.;
    for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x) {
        const double value=tile[y*width+x],dx=x-centerx,dy=y-centery;
        sum+=value;sumx+=value*dx;sumy+=value*dy;normx+=dx*dx;normy+=dy*dy;
    }
    const auto mean=sum/(width*height),sx=sumx/normx,sy=sumy/normy;
    for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x)tile[y*width+x]-=mean+sx*(x-centerx)+sy*(y-centery);
}
inline void detrend(double* tile,unsigned side) {detrend(tile,side,side);}
inline void load_tiles(const std::array<FilmGrainNativePlane,3>& planes,
    const FilmGrainNativeTile& bounds,unsigned depth,std::array<std::array<double,4096>,4>& tiles,
    std::array<double,3>* meanSums=nullptr) {
    const double scale=double(1u<<(depth-8));
    for(unsigned field=0;field<4;++field) {
        const unsigned w=field?bounds.width/2:bounds.width,h=field?bounds.height/2:bounds.height,c=field<2?0:field-1;const auto& p=planes[c];auto& tile=tiles[field];
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
            if(field==1) {
                const auto offset=size_t(bounds.y+y*2)*p.stride+bounds.x+x*2;
                tile[y*w+x]=(unsigned(p.data[offset])+p.data[offset+1]+p.data[offset+p.stride]+p.data[offset+p.stride+1])/(4.*scale);
            } else tile[y*w+x]=p.data[size_t(bounds.y/(c?2:1)+y)*p.stride+bounds.x/(c?2:1)+x]/scale;
        }
        if(meanSums && field!=1) {
            double sum=0.;for(unsigned i=0;i<w*h;++i)sum+=tile[i];
            (*meanSums)[c]+=sum;
        }
        detrend(tile.data(),w,h);
    }
}
inline void load_tiles(const std::array<FilmGrainNativePlane,3>& planes,
    unsigned bx,unsigned by,unsigned depth,std::array<std::array<double,4096>,4>& tiles,
    std::array<double,3>* meanSums=nullptr) {
    load_tiles(planes,FilmGrainNativeTile{bx*64,by*64,64,64},depth,tiles,meanSums);
}
} // namespace native_moments_detail

inline FilmGrainNativeMoments film_grain_native_moments(
    const std::array<FilmGrainNativePlane,3>& planes,unsigned width,unsigned height,unsigned depth) {
    FilmGrainNativeMoments result;const auto basic=film_grain_native_variance(planes,width,height,depth);
    if(!basic.valid)return result;
    result.width=width;result.height=height;result.depth=depth;result.mean=basic.mean;result.blocks=basic.blocks;
    const auto positions=native_moments_detail::offsets();const auto grid=film_grain_native_grid(width,height);
    std::array<std::array<double,4096>,4> tiles{};
    for(unsigned by=0;by<grid.rows;++by)for(unsigned bx=0;bx<grid.columns;++bx) {
        const auto bounds=grid.tile(bx,by);const unsigned cw=bounds.width/2,ch=bounds.height/2;
        auto& fold=result.folds[(by+bx)&1];
        native_moments_detail::load_tiles(planes,bounds,depth,tiles,&fold.mean);
        native_moments_detail::spatial(tiles[0].data(),bounds.width,bounds.height,fold.y);
        for(unsigned c=0;c<2;++c) {
            std::array<double,625> marginal{};native_moments_detail::spatial(tiles[c+2].data(),cw,ch,marginal);
            auto& matrix=fold.colour[c];
            for(unsigned i=0;i<25;++i)for(unsigned j=0;j<25;++j)matrix[(i==24?25:i)*26+(j==24?25:j)]+=marginal[i*25+j];
            for(unsigned i=0;i<25;++i) {
                double sum=0.;
                for(unsigned y=3;y<ch-3;++y)for(unsigned x=3;x<cw-3;++x)
                    sum+=tiles[c+2][unsigned(int(y)+positions[i].y)*cw+unsigned(int(x)+positions[i].x)]*tiles[1][y*cw+x];
                const unsigned row=i==24?25:i;matrix[row*26+24]+=sum;matrix[24*26+row]+=sum;
            }
        }
        for(unsigned y=3;y<ch-3;++y)for(unsigned x=3;x<cw-3;++x) {
            for(unsigned i=0;i<3;++i)for(unsigned j=0;j<3;++j)fold.common[i*3+j]+=tiles[i+1][y*cw+x]*tiles[j+1][y*cw+x];
            for(int dy=-3;dy<=3;++dy)for(int dx=-3;dx<=3;++dx)
                fold.cross[unsigned(dy+3)*7+unsigned(dx+3)]+=tiles[2][y*cw+x]*tiles[3][unsigned(int(y)+dy)*cw+unsigned(int(x)+dx)];
        }
    }
    for(unsigned f=0;f<2;++f) {
        auto& fold=result.folds[f];const double yCount=grid.lumaObservations[f],cCount=grid.colourObservations[f];
        for(unsigned c=0;c<3;++c) {
            fold.mean[c]/=grid.pixels[f]/(c?4:1);
            if(!std::isfinite(fold.mean[c]))return result;
        }
        fold.meanValid=true;
        for(auto& matrix:fold.colour)matrix[24*26+24]=fold.common[0];
        for(auto& value:fold.y)value/=yCount;
        for(auto& matrix:fold.colour)for(auto& value:matrix)value/=cCount;
        for(auto& value:fold.common)value/=cCount;
        for(auto& value:fold.cross)value/=cCount;
        for(double value:fold.y)if(!std::isfinite(value))return result;
        for(const auto& matrix:fold.colour)for(double value:matrix)if(!std::isfinite(value))return result;
        for(double value:fold.common)if(!std::isfinite(value))return result;
        for(double value:fold.cross)if(!std::isfinite(value))return result;
    }
    result.valid=true;return result;
}
} // namespace fgsmodel
