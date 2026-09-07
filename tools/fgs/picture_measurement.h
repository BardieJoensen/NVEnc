#pragma once
#include "display_mapping.h"
#include "spatial_metrics.h"
#include <dav1d/dav1d.h>
#include <cstdint>
#include <ostream>

namespace fgs_inspect {
template<typename Pixel>
inline double chroma(const Dav1dPicture& p, int plane, int x, int y) {
    if (p.p.layout==DAV1D_PIXEL_LAYOUT_I400) return 128*(1 << (p.p.bpc-8));
    const int sx=p.p.layout==DAV1D_PIXEL_LAYOUT_I444 ? 0 : 1;
    const int sy=p.p.layout==DAV1D_PIXEL_LAYOUT_I420 ? 1 : 0;
    const int width=(p.p.w+(1<<sx)-1)>>sx, height=(p.p.h+(1<<sy)-1)>>sy;
    // Explicit bilinear display reconstruction. Unknown siting uses centered
    // chroma and is recorded as an assumption in the completion report.
    const double ox=sx && p.seq_hdr->chr==DAV1D_CHR_UNKNOWN ? .5 : 0;
    const double oy=sy && p.seq_hdr->chr!=DAV1D_CHR_COLOCATED ? .5 : 0;
    const double xx=std::clamp((x-ox)/(1<<sx),0.0,double(width-1));
    const double yy=std::clamp((y-oy)/(1<<sy),0.0,double(height-1));
    const int x0=int(xx),y0=int(yy),x1=std::min(x0+1,width-1),y1=std::min(y0+1,height-1);
    const double fx=xx-x0,fy=yy-y0;
    const auto* data=static_cast<const Pixel*>(p.data[plane]);
    const auto stride=p.stride[1]/sizeof(Pixel);
    return (1-fy)*((1-fx)*data[y0*stride+x0]+fx*data[y0*stride+x1])
              +fy*((1-fx)*data[y1*stride+x0]+fx*data[y1*stride+x1]);
}
template<typename Pixel>
inline std::array<double,3> pixel_signal(const Dav1dPicture& p, int x, int y, const DisplayMapper& mapper) {
    const auto* data=static_cast<const Pixel*>(p.data[0]);
    return mapper.rgb_signal(data[y*(p.stride[0]/sizeof(Pixel))+x],
                            chroma<Pixel>(p,1,x,y),chroma<Pixel>(p,2,x,y));
}
struct FullMeasurement {
    std::array<FrameMetric,4> channels{};
    int tiles=0;
    uint64_t pixels=0,clipped_base_pixels=0,clipped_grain_pixels=0;
};
template<typename Pixel>
inline FullMeasurement measure_full(const Dav1dPicture& off,const Dav1dPicture* on,
                                    const DisplayMapper& mapper,std::ostream* tile_csv,double seconds) {
    FullMeasurement result;result.pixels=uint64_t(off.p.w)*off.p.h;
    const auto tiles=full_tiles(off.p.w,off.p.h);result.tiles=int(tiles.size());
    std::array<std::vector<double>,4> delta;
    for (const auto& tile:tiles) {
        for(auto& plane:delta)plane.resize(tile.w*tile.h);
        for(int y=0; y<tile.h; ++y)for(int x=0; x<tile.w; ++x) {
            const auto base_signal=pixel_signal<Pixel>(off,tile.x+x,tile.y+y,mapper);
            const auto grain_signal=on ? pixel_signal<Pixel>(*on,tile.x+x,tile.y+y,mapper) : base_signal;
            result.clipped_base_pixels+=mapper.clipped(base_signal);
            result.clipped_grain_pixels+=mapper.clipped(grain_signal);
            if(on) {
                const auto base=mapper.values(base_signal),grain=mapper.values(grain_signal);
                for(int c=0;c<4;++c)delta[c][y*tile.w+x]=grain[c]-base[c];
            }
        }
        for(int c=0;c<4;++c) {
            const auto m=on ? tile_metric(delta[c],tile.w,tile.h) : TileMetric{};
            result.channels[c].add(tile,m);
            if(tile_csv) {
                *tile_csv<<seconds<<','<<tile.x<<','<<tile.y<<','<<tile.w<<','<<tile.h<<','<<c
                    <<','<<m.rms<<','<<m.correlation<<','<<m.score<<','<<m.dx<<','<<m.dy<<','<<m.directional_score<<'\n';
            }
        }
    }
    for(auto& c:result.channels)c.finish(int(result.pixels));
    return result;
}
} // namespace fgs_inspect
