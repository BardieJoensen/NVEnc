// Native source-only translation evidence and candidate detail-removal veto.
// A non-conflicting result never establishes grain or full detail admission.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainNativeVariance.h"
#include <vector>

namespace fgsmodel {
struct FilmGrainMotionDetailTile {
    unsigned x=0,y=0,width=0,height=0,fitSamples=0;
    int dx=0,dy=0;
    double trainingMse=0.;
    std::array<double,2> zeroMse{},shiftedMse{},improvement{};
    std::array<bool,2> relativeDefined{};
    bool motionSupported=false,anchorSupported=false,conflict=false;
    uint64_t samples=0,changedSamples=0,projectedSamples=0;
    double correlation=0.,contrastChange=0.,removedProjectionRms=0.,meanError=0.;
};
struct FilmGrainMotionDetailEvidence {
    bool valid=false;
    std::vector<FilmGrainMotionDetailTile> tiles;
};

// Finite CPU diagnostic. All planes contain native uint16 codes. The canonical
// side is 64 for Y and 32 for C; an explicitly declared smaller search also
// supports the retained 32x32 development controls. No output call site exists.
// Frame IDs/clocks describe one continuous epoch; resets must be split by the
// caller. The same source history/geometry must be used for every fraction.
inline FilmGrainMotionDetailEvidence film_grain_motion_detail(
    const std::array<FilmGrainNativePlane,8>& source,const FilmGrainNativePlane& base,
    unsigned width,unsigned height,unsigned depth,unsigned side,unsigned radius,unsigned step,
    const std::array<int64_t,8>& ids,const std::array<int64_t,8>& pts,bool nativeMatch=false) {
    FilmGrainMotionDetailEvidence out;
    if(width<32 || height<32 || width>4096 || height>2160 || (depth!=8 && depth!=10)
        || (side!=32 && side!=64) || radius<1 || radius>32 || (step!=2 && step!=4))return out;
    for(unsigned i=0;i<8;++i)
        if(ids[i]<0 || ids[i]>INT32_MAX || pts[i]==INT64_MIN
            || (i && (ids[i]!=ids[i-1]+1 || pts[i]<=pts[i-1])))return out;
    const unsigned scale=1u<<(depth-8),maximum=(1u<<depth)-1;
    auto valid=[&](const FilmGrainNativePlane& p) {
        if(!p.data || p.stride<width || p.stride>65536 || p.samples<p.stride*(height-1)+width)return false;
        for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x)
            if(p.data[size_t(y)*p.stride+x]>maximum)return false;
        return true;
    };
    if(!valid(base))return out;
    for(const auto& p:source)if(!valid(p))return out;
    for(unsigned top=0;top<height;top+=side)for(unsigned left=0;left<width;left+=side) {
        FilmGrainMotionDetailTile t;
        t.x=left;t.y=top;t.width=std::min(side,width-left);t.height=std::min(side,height-top);
        t.samples=uint64_t(t.width)*t.height;
        for(unsigned y=top;y<top+t.height;++y)for(unsigned x=left;x<left+t.width;++x)
            t.changedSamples+=source[7].data[size_t(y)*source[7].stride+x]!=base.data[size_t(y)*base.stride+x];
        std::vector<unsigned> xs,ys;
        for(unsigned x=left;x<left+t.width;x+=step)if(x>radius && x+radius+1<width)xs.push_back(x);
        for(unsigned y=top;y<top+t.height;y+=step)if(y>radius && y+radius+1<height)ys.push_back(y);
        t.fitSamples=unsigned(xs.size()*ys.size());
        if(t.fitSamples<16){out.tiles.push_back(t);continue;}
        // Native matching complements the smoothed search: [1,2,1] has an
        // exact alternating-line nullspace. Neither measurement may approve
        // detail, and a caller combining modes must retain either one's veto.
        // Cache only this tile's bounded source halo. Weighted sums and the
        // x16 native representation both fit exactly at native ten-bit.
        const unsigned x0=xs.front()-radius,y0=ys.front()-radius;
        const unsigned cw=xs.back()+radius-x0+1,ch=ys.back()+radius-y0+1;
        std::array<std::vector<uint16_t>,8> smooth;
        for(unsigned f=0;f<8;++f) {
            smooth[f].resize(size_t(cw)*ch);const auto& p=source[f];
            for(unsigned y=0;y<ch;++y)for(unsigned x=0;x<cw;++x) {
                unsigned value=0;
                if(nativeMatch)value=16*p.data[size_t(y+y0)*p.stride+x+x0];
                else for(int j=-1;j<=1;++j)for(int i=-1;i<=1;++i)
                    value+=p.data[size_t(int(y+y0)+j)*p.stride+int(x+x0)+i]*(j?1:2)*(i?1:2);
                smooth[f][size_t(y)*cw+x]=uint16_t(value);
            }
        }
        auto cost=[&](unsigned before,unsigned after,int dy,int dx,uint64_t stop=UINT64_MAX) {
            uint64_t sum=0;
            for(unsigned y:ys)for(unsigned x:xs) {
                const int delta=int(smooth[after][size_t(y-y0)*cw+x-x0])
                    -int(smooth[before][size_t(int(y-y0)+dy)*cw+int(x-x0)+dx]);
                sum+=uint64_t(int64_t(delta)*delta);
                if(sum>stop)return sum;
            }
            return sum;
        };
        uint64_t best=cost(0,1,0,0)+cost(2,3,0,0);
        for(int dy=-int(radius);dy<=int(radius);++dy)for(int dx=-int(radius);dx<=int(radius);++dx) {
            if(!dy && !dx)continue;
            auto sum=cost(0,1,dy,dx,best);
            if(sum<=best)sum+=cost(2,3,dy,dx,best-sum);
            if(sum<best){best=sum;t.dx=dx;t.dy=dy;}
        }
        const double denominator=double(t.fitSamples)*256*scale*scale;
        t.trainingMse=best/(2*denominator);
        t.motionSupported=t.dx || t.dy;
        for(unsigned i=0;i<2;++i) {
            t.zeroMse[i]=cost(4+2*i,5+2*i,0,0)/denominator;
            t.shiftedMse[i]=cost(4+2*i,5+2*i,t.dy,t.dx)/denominator;
            t.relativeDefined[i]=t.zeroMse[i]>0.;
            if(t.relativeDefined[i])t.improvement[i]=(t.zeroMse[i]-t.shiftedMse[i])/t.zeroMse[i];
            t.motionSupported=t.motionSupported && t.zeroMse[i]>.04 && t.improvement[i]>.2;
        }
        if(t.motionSupported) {
            int64_t ss=0,sa=0,sd=0,sss=0,saa=0,ssa=0,sda=0,n=0;
            // Evaluate full native samples, never the smoothed matching grid.
            for(unsigned y=top;y<top+t.height;++y)for(unsigned x=left;x<left+t.width;++x) {
                const int ay=int(y)+t.dy,ax=int(x)+t.dx;
                if(ay<0 || ax<0 || ay>=int(height) || ax>=int(width))continue;
                const int64_t s=source[7].data[size_t(y)*source[7].stride+x];
                const int64_t a=source[6].data[size_t(ay)*source[6].stride+ax];
                const int64_t d=s-base.data[size_t(y)*base.stride+x];
                ++n;ss+=s;sa+=a;sd+=d;sss+=s*s;saa+=a*a;ssa+=s*a;sda+=d*a;
            }
            if(n) {
                const auto vs=n*sss-ss*ss,va=n*saa-sa*sa,cov=n*ssa-ss*sa,removed=n*sda-sd*sa;
                t.meanError=double(sd)/(n*scale);
                if(vs>0 && va>0) {
                    t.correlation=cov/std::sqrt(double(vs)*va);
                    t.anchorSupported=t.correlation>=.5;
                    if(t.anchorSupported) {
                        t.projectedSamples=uint64_t(n);
                        t.contrastChange=double(removed)/cov;
                        t.removedProjectionRms=std::abs(double(removed))/(n*scale*std::sqrt(double(va)));
                        t.conflict=std::abs(t.contrastChange)>.02 || t.removedProjectionRms>.125 || std::abs(t.meanError)>.125;
                    }
                }
            }
        }
        out.tiles.push_back(t);
    }
    out.valid=true;return out;
}

struct FilmGrainMotionDetailVeto {
    bool valid=false;
    std::vector<bool> conflicts; // Canonical native raster; no positive pass bit.
};
// The combined guard retains both measurements' conflicts. Selecting the less
// restrictive matching mode would discard a previously observed detail loss.
inline FilmGrainMotionDetailVeto film_grain_motion_detail_veto(
    const std::array<FilmGrainNativePlane,8>& source,const FilmGrainNativePlane& base,
    unsigned width,unsigned height,unsigned depth,unsigned side,unsigned radius,unsigned step,
    const std::array<int64_t,8>& ids,const std::array<int64_t,8>& pts) {
    FilmGrainMotionDetailVeto out;
    const auto smoothed=film_grain_motion_detail(source,base,width,height,depth,side,radius,step,ids,pts);
    if(!smoothed.valid)return out;
    const auto native=film_grain_motion_detail(source,base,width,height,depth,side,radius,step,ids,pts,true);
    if(!native.valid || native.tiles.size()!=smoothed.tiles.size())return out;
    out.conflicts.reserve(native.tiles.size());
    for(size_t i=0;i<native.tiles.size();++i)out.conflicts.push_back(native.tiles[i].conflict || smoothed.tiles[i].conflict);
    out.valid=true;return out;
}
} // namespace fgsmodel
