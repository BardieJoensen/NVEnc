// Complete, disjoint native 4:2:0 partitions for finite diagnostics.
// Geometry does not classify source content or grant population eligibility.
#pragma once
#include <array>
#include <cstdint>

namespace fgsmodel {
struct FilmGrainNativeTile {
    unsigned x=0,y=0,width=0,height=0;
};
struct FilmGrainNativeGrid {
    bool valid=false;
    unsigned width=0,height=0,columns=0,rows=0;
    std::array<uint64_t,2> blocks{},pixels{},lumaObservations{},colourObservations{};
private:
    static unsigned boundary(unsigned length,unsigned count,unsigned index) {
        return unsigned(2*(uint64_t(length/2)*index/count));
    }
public:
    FilmGrainNativeTile tile(unsigned x,unsigned y) const {
        if(!valid || x>=columns || y>=rows)return {};
        const auto left=boundary(width,columns,x),top=boundary(height,rows,y);
        return {left,top,boundary(width,columns,x+1)-left,boundary(height,rows,y+1)-top};
    }
};
inline FilmGrainNativeGrid film_grain_native_grid(unsigned width,unsigned height) {
    FilmGrainNativeGrid grid;
    if(width<64 || height<64 || width>4096 || height>2160 || (width&1) || (height&1))return grid;
    grid.valid=true;grid.width=width;grid.height=height;
    grid.columns=(width+63)/64;grid.rows=(height+63)/64;
    for(unsigned y=0;y<grid.rows;++y)for(unsigned x=0;x<grid.columns;++x) {
        const auto tile=grid.tile(x,y);const auto f=(x+y)&1;
        ++grid.blocks[f];grid.pixels[f]+=uint64_t(tile.width)*tile.height;
        grid.lumaObservations[f]+=uint64_t(tile.width-6)*(tile.height-6);
        grid.colourObservations[f]+=uint64_t(tile.width/2-6)*(tile.height/2-6);
    }
    return grid;
}
} // namespace fgsmodel
