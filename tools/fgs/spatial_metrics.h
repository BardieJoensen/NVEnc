// Local residual measurements. Full tiles retain a local maximum so opposite
// directions in separate parts of a frame cannot cancel in a global average.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace fgs_inspect {
constexpr int correlation_offsets[][2] = {
    {1,0},{0,1},{1,1},{-1,1},{2,0},{0,2},{2,2},{-2,2},{3,0},{0,3},{3,3},{-3,3}};
struct Tile { int x, y, w, h; };
inline std::vector<std::array<int,2>> partition(int length, int side=48) {
    if (length < 8 || side < 8) throw std::runtime_error("image/tile dimension smaller than eight pixels");
    std::vector<std::array<int,2>> result;
    for (int at=0; at<length; at+=side) result.push_back({at,std::min(side,length-at)});
    if (result.size()>1 && result.back()[1]<8) {
        const int tail=result.back()[1]; result.pop_back(); result.back()[1]+=tail;
    }
    return result;
}
inline std::vector<Tile> full_tiles(int width, int height) {
    std::vector<Tile> result;
    for (const auto& y : partition(height)) for (const auto& x : partition(width))
        result.push_back({x[0],y[0],x[1],y[1]});
    return result;
}
struct TileMetric {
    double rms=0, correlation=0, score=0, directional_score=0;
    int dx=0, dy=0;
    std::array<double,12> acf{};
};
inline TileMetric tile_metric(const std::vector<double>& delta, int width, int height) {
    if (width<8 || height<8 || delta.size()!=size_t(width)*height)
        throw std::runtime_error("invalid residual tile");
    double sum=0;
    for (const auto v : delta) sum+=v;
    const double mean=sum/delta.size();
    std::vector<double> centered(delta.size()); double square=0;
    for (size_t i=0; i<delta.size(); ++i) { centered[i]=delta[i]-mean; square+=centered[i]*centered[i]; }
    TileMetric result; result.rms=std::sqrt(square/delta.size());
    for (int k=0; k<12; ++k) {
        const int dx=correlation_offsets[k][0],dy=correlation_offsets[k][1];
        double cross=0,left=0,right=0;
        for (int y=std::max(0,-dy); y<std::min(height,height-dy); ++y)
            for (int x=std::max(0,-dx); x<std::min(width,width-dx); ++x) {
                const double a=centered[y*width+x],b=centered[(y+dy)*width+x+dx];
                cross+=a*b;left+=a*a;right+=b*b;
            }
        const double corr=left*right>0 ? std::clamp(cross/std::sqrt(left*right),-1.0,1.0) : 0;
        result.acf[k]=corr;
        if (std::abs(corr)>std::abs(result.correlation)) {
            result.correlation=corr;result.dx=dx;result.dy=dy;
        }
    }
    result.score=result.rms*std::abs(result.correlation);
    // Compare directions at equal spatial distances. This distinguishes a
    // directional texture from ordinary isotropic coarse grain, but cannot
    // rule out symmetric grids; retain the ordinary correlation score too.
    double bias=0;
    for(int k=0;k<12;k+=2)bias=std::max(bias,std::abs(result.acf[k]-result.acf[k+1]));
    result.directional_score=result.rms*bias;
    return result;
}
struct FrameMetric {
    double rms=0, max_tile_rms=0, peak_score=0, p95_tile_score=0, p99_tile_score=0;
    int peak_x=-1,peak_y=-1;
    double peak_directional_score=0;
    int directional_x=-1,directional_y=-1;
    TileMetric peak;
    std::vector<std::pair<double,int>> area_scores;
    void add(const Tile& tile, const TileMetric& value) {
        rms+=value.rms*value.rms*tile.w*tile.h;
        max_tile_rms=std::max(max_tile_rms,value.rms);
        area_scores.emplace_back(value.score,tile.w*tile.h);
        if(value.directional_score>peak_directional_score) {
            peak_directional_score=value.directional_score;directional_x=tile.x;directional_y=tile.y;
        }
        if (value.score>peak_score) {
            peak_score=value.score;peak_x=tile.x;peak_y=tile.y;peak=value;
        }
    }
    void finish(int pixels) {
        rms=std::sqrt(rms/pixels);
        std::sort(area_scores.begin(),area_scores.end());
        int area=0;
        for(const auto& entry:area_scores) {
            const int before=area;area+=entry.second;
            if(before<.95*pixels && area>=.95*pixels)p95_tile_score=entry.first;
            if(before<.99*pixels && area>=.99*pixels)p99_tile_score=entry.first;
        }
    }
};
} // namespace fgs_inspect
