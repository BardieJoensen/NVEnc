// Complete spatial/colour measurements for tile-aligned development pictures.
// These moments alone do not establish source eligibility or perceptual quality.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <algorithm>
#include "NVEncFilmGrainNativeVariance.h"

namespace fgsmodel {
struct FilmGrainNativeMomentFold {
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
inline void spatial(const double* tile,unsigned side,std::array<double,625>& matrix) {
    const auto positions=offsets();std::array<double,4225> integral{};const unsigned stride=side+1;
    for(int dy=0;dy<=3;++dy)for(int dx=-6;dx<=6;++dx) {
        bool used=false;
        for(unsigned i=0;i<25 && !used;++i)for(unsigned j=i;j<25;++j)
            if(positions[j].y-positions[i].y==dy && positions[j].x-positions[i].x==dx){used=true;break;}
        if(!used)continue;
        for(unsigned y=0;y<side;++y) {
            double row=0.;
            for(unsigned x=0;x<side;++x) {
                const int yy=int(y)+dy,xx=int(x)+dx;
                if(yy>=0 && yy<int(side) && xx>=0 && xx<int(side))row+=tile[y*side+x]*tile[unsigned(yy)*side+unsigned(xx)];
                integral[(y+1)*stride+x+1]=integral[y*stride+x+1]+row;
            }
        }
        for(unsigned i=0;i<25;++i)for(unsigned j=i;j<25;++j) {
            if(positions[j].y-positions[i].y!=dy || positions[j].x-positions[i].x!=dx)continue;
            const unsigned top=unsigned(3+positions[i].y),left=unsigned(3+positions[i].x);
            const unsigned bottom=unsigned(int(side)-3+positions[i].y),right=unsigned(int(side)-3+positions[i].x);
            const double value=integral[bottom*stride+right]-integral[top*stride+right]-integral[bottom*stride+left]+integral[top*stride+left];
            matrix[i*25+j]+=value;if(i!=j)matrix[j*25+i]+=value;
        }
    }
}
inline void detrend(double* tile,unsigned side) {
    const double center=(side-1)*.5;double sum=0.,sumx=0.,sumy=0.,norm=0.;
    for(unsigned y=0;y<side;++y)for(unsigned x=0;x<side;++x) {
        const double value=tile[y*side+x],dx=x-center,dy=y-center;
        sum+=value;sumx+=value*dx;sumy+=value*dy;norm+=dx*dx;
    }
    const auto mean=sum/(side*side),sx=sumx/norm,sy=sumy/norm;
    for(unsigned y=0;y<side;++y)for(unsigned x=0;x<side;++x)tile[y*side+x]-=mean+sx*(x-center)+sy*(y-center);
}
inline void load_tiles(const std::array<FilmGrainNativePlane,3>& planes,
    unsigned bx,unsigned by,unsigned depth,std::array<std::array<double,4096>,4>& tiles) {
    const double scale=double(1u<<(depth-8));
    for(unsigned field=0;field<4;++field) {
        const unsigned side=field?32:64,c=field<2?0:field-1;const auto& p=planes[c];auto& tile=tiles[field];
        for(unsigned y=0;y<side;++y)for(unsigned x=0;x<side;++x) {
            if(field==1) {
                const auto offset=size_t(by*64+y*2)*p.stride+bx*64+x*2;
                tile[y*side+x]=(unsigned(p.data[offset])+p.data[offset+1]+p.data[offset+p.stride]+p.data[offset+p.stride+1])/(4.*scale);
            } else tile[y*side+x]=p.data[size_t(by*side+y)*p.stride+bx*side+x]/scale;
        }
        detrend(tile.data(),side);
    }
}
} // namespace native_moments_detail

inline FilmGrainNativeMoments film_grain_native_moments(
    const std::array<FilmGrainNativePlane,3>& planes,unsigned width,unsigned height,unsigned depth) {
    FilmGrainNativeMoments result;const auto basic=film_grain_native_variance(planes,width,height,depth);
    if(!basic.valid)return result;
    result.width=width;result.height=height;result.depth=depth;result.mean=basic.mean;result.blocks=basic.blocks;
    const auto positions=native_moments_detail::offsets();
    std::array<std::array<double,4096>,4> tiles{};
    for(unsigned by=0;by<height/64;++by)for(unsigned bx=0;bx<width/64;++bx) {
        auto& fold=result.folds[(by+bx)&1];
        native_moments_detail::load_tiles(planes,bx,by,depth,tiles);
        native_moments_detail::spatial(tiles[0].data(),64,fold.y);
        for(unsigned c=0;c<2;++c) {
            std::array<double,625> marginal{};native_moments_detail::spatial(tiles[c+2].data(),32,marginal);
            auto& matrix=fold.colour[c];
            for(unsigned i=0;i<25;++i)for(unsigned j=0;j<25;++j)matrix[(i==24?25:i)*26+(j==24?25:j)]+=marginal[i*25+j];
            for(unsigned i=0;i<25;++i) {
                double sum=0.;
                for(unsigned y=3;y<29;++y)for(unsigned x=3;x<29;++x)
                    sum+=tiles[c+2][unsigned(int(y)+positions[i].y)*32+unsigned(int(x)+positions[i].x)]*tiles[1][y*32+x];
                const unsigned row=i==24?25:i;matrix[row*26+24]+=sum;matrix[24*26+row]+=sum;
            }
        }
        for(unsigned y=3;y<29;++y)for(unsigned x=3;x<29;++x) {
            for(unsigned i=0;i<3;++i)for(unsigned j=0;j<3;++j)fold.common[i*3+j]+=tiles[i+1][y*32+x]*tiles[j+1][y*32+x];
            for(int dy=-3;dy<=3;++dy)for(int dx=-3;dx<=3;++dx)
                fold.cross[unsigned(dy+3)*7+unsigned(dx+3)]+=tiles[2][y*32+x]*tiles[3][unsigned(int(y)+dy)*32+unsigned(int(x)+dx)];
        }
    }
    for(unsigned f=0;f<2;++f) {
        auto& fold=result.folds[f];const double yCount=result.blocks[f]*58*58,cCount=result.blocks[f]*26*26;
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
