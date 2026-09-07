#include "../../tools/fgs/display_mapping.h"
#include "../../tools/fgs/spatial_metrics.h"
#include <cassert>
#include <iostream>
#include <random>

using namespace fgs_inspect;
static bool near(double a,double b,double tolerance) { return std::abs(a-b)<tolerance; }
int main() {
    // Published ST 2084/BT.2100 reference points in absolute cd/m2.
    assert(near(pq_nits(0),0,1e-12));
    assert(near(pq_nits(.5),92.245708994,1e-8));
    assert(near(pq_nits(.751827096247041),1000,1e-7));
    assert(near(pq_nits(1),10000,1e-7));
    assert(near(hlg_scene(.5),1.0/12,1e-12));
    assert(near(hlg_scene(1),1,1e-7));
    assert(near(hlg_gamma(1000),1.2,1e-12));
    // HLG applies its OOTF through luminance. A saturated red patch must not
    // use the independent-component power curve of an ordinary SDR display.
    DisplayConfig config;config.transfer=18;config.matrix=9;config.primaries=9;
    DisplayMapper hlg(config);
    const auto red=hlg.values({1,0,0},true);
    const double red_nits=1000*std::pow(.2627,.2);
    assert(near(red[1],pu21(red_nits),1e-5));
    assert(near(red[0],pu21(.2627*red_nits),1e-5));
    assert(std::abs(red[1]-pu21(1000))>5);
    assert(near(hlg.values({.5,.5,.5},true)[0],pu21(50.697028491),1e-6));

    std::mt19937 random(71);std::uniform_real_distribution<double> signal(0,1);
    double worst=0;
    for(int transfer:{1,16,18})for(double peak:{400.0,1000.0,4000.0}) {
        config.transfer=transfer;config.peak_nits=peak;
        DisplayMapper mapper(config);
        for(int i=0;i<12000;++i) {
            const std::array<double,3> rgb{signal(random),signal(random),signal(random)};
            const auto fast=mapper.values(rgb),reference=mapper.values(rgb,true);
            for(int c=0;c<4;++c)worst=std::max(worst,std::abs(fast[c]-reference[c]));
        }
        for(double n:{0.,.00001,.001,.01,.1,.5,1.}) {
            const auto fast=mapper.values({n,n,n}),reference=mapper.values({n,n,n},true);
            for(int c=0;c<4;++c)worst=std::max(worst,std::abs(fast[c]-reference[c]));
        }
    }
    std::cout<<"maximum LUT error in PU21 units: "<<worst<<'\n';
    assert(worst<.01);

    // Equivalent video levels at every supported depth and full/limited range.
    for(int depth:{8,10,12})for(bool full:{false,true}) {
        config={};config.depth=depth;config.full_range=full;DisplayMapper mapper(config);
        const double scale=1 << (depth-8),center=128*scale;
        const auto black=mapper.rgb_signal(full?0:16*scale,center,center);
        const auto white=mapper.rgb_signal(full?(1<<depth)-1:235*scale,center,center);
        for(int c=0;c<3;++c) { assert(near(black[c],0,1e-12));assert(near(white[c],1,1e-12)); }
    }
    for(auto bad:std::vector<DisplayConfig>{{16,1,1},{18,10,9},{2,1,1},{1,2,2}}) {
        bool rejected=false;try { DisplayMapper invalid(bad); }catch(const std::runtime_error&) {rejected=true;}
        assert(rejected);
    }
    // Every pixel, including odd-width borders and tiny final strips, belongs
    // to exactly one tile; no downscale or overlap-counting inflates coverage.
    for(const auto dimensions:std::vector<std::array<int,2>>{{8,8},{49,49},{100,57},{1918,802},{1920,1080},{3840,2160}}) {
        const int width=dimensions[0],height=dimensions[1];std::vector<int> count(width*height);
        for(const auto& tile:full_tiles(width,height)) {
            assert(tile.w>=8 && tile.h>=8);
            for(int y=tile.y;y<tile.y+tile.h;++y)for(int x=tile.x;x<tile.x+tile.w;++x)++count[y*width+x];
        }
        for(const int n:count)assert(n==1);
    }
    std::vector<double> constant(48*48,7);
    assert(tile_metric(constant,48,48).score==0);
    std::vector<double> ripple(48*48);
    for(int y=0;y<48;++y)for(int x=0;x<48;++x)ripple[y*48+x]=(y%2?4:-4);
    const auto local=tile_metric(ripple,48,48);assert(near(local.score,4,1e-12));
    assert(near(local.directional_score,8,1e-12));
    FrameMetric frame;
    for(const auto& tile:full_tiles(1920,1080))frame.add(tile,tile.x==0 && tile.y==0 ? local : TileMetric{});
    frame.finish(1920*1080);
    assert(near(frame.peak_score,4,1e-12) && frame.peak_x==0 && frame.peak_y==0);
    assert(frame.rms<.15); // Averaging would hide this corner-only defect.
    // A defect at the very last row is still measured; excluding a common
    // three-pixel border from all lag products would lose this evidence.
    std::fill(ripple.begin(),ripple.end(),0);
    for(int x=0;x<48;++x)ripple[47*48+x]=(x%2?4:-4);
    assert(tile_metric(ripple,48,48).score>.5);
    std::cout<<"Reference-display mapping and complete spatial coverage checks passed\n";
}
