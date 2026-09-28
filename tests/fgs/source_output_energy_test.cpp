#include <cassert>
#include <iostream>
#include <vector>
#include "NVEncFilmGrainSourceOutputEnergy.h"
using namespace fgsmodel;
int main() {
    unsigned positives=0,negatives=0;
    for(unsigned depth:{8u,10u})for(auto size:{std::array<unsigned,2>{130,126},{1920,1080},{3840,2160}}) {
        const auto w=size[0],h=size[1],scale=1u<<(depth-8);
        std::array<std::vector<uint16_t>,3> a,b;
        std::array<FilmGrainNativePlane,3> av{},bv{};
        for(unsigned c=0;c<3;++c) {
            const unsigned cw=c?w/2:w,ch=c?h/2:h,as=cw+3,bs=cw+7;
            a[c].assign(size_t(as)*ch,65535);b[c].assign(size_t(bs)*ch,65535);
            for(unsigned y=0;y<ch;++y)for(unsigned x=0;x<cw;++x) {
                const auto value=uint16_t((120+(17*x+11*y+7*c+(x*y)%13)%17)*scale);
                a[c][size_t(y)*as+x]=value;b[c][size_t(y)*bs+x]=value;
            }
            av[c]={a[c].data(),size_t(ch-1)*as+cw,as};bv[c]={b[c].data(),size_t(ch-1)*bs+cw,bs};
        }
        auto same=film_grain_source_output_energy(av,bv,w,h,depth);
        assert(same.valid && same.pass);++positives;
        for(unsigned c=0;c<3;++c) {
            const auto saved=b[c];const unsigned cw=c?w/2:w,ch=c?h/2:h;
            // An unchanged component before encoding is not enough if the
            // compressed reconstruction removes nearly all of its energy.
            for(unsigned y=0;y<ch;++y)for(unsigned x=0;x<cw;++x)b[c][y*bv[c].stride+x]=128*scale;
            assert(!film_grain_source_output_energy(av,bv,w,h,depth).pass);++negatives;b[c]=saved;
            for(unsigned y=0;y<ch;++y)for(unsigned x=0;x<cw;++x)b[c][y*bv[c].stride+x]+=scale;
            const auto shifted=film_grain_source_output_energy(av,bv,w,h,depth);
            assert(shifted.valid && !shifted.pass && shifted.meanError[c]==1);++negatives;b[c]=saved;
            auto bad=av;--bad[c].samples;assert(!film_grain_source_output_energy(bad,bv,w,h,depth).valid);++negatives;
            bad=av;bad[c].data=nullptr;assert(!film_grain_source_output_energy(bad,bv,w,h,depth).valid);++negatives;
            const auto last=size_t(ch-1)*bv[c].stride+cw-1;b[c][last]=uint16_t(1u<<depth);
            assert(!film_grain_source_output_energy(av,bv,w,h,depth).valid);++negatives;b[c]=saved;
        }
        // Equal and opposite half means must not cancel into a frame pass.
        const auto grid=film_grain_native_grid(w,h);auto saved=b[0];
        for(unsigned by=0;by<grid.rows;++by)for(unsigned bx=0;bx<grid.columns;++bx) {
            const auto tile=grid.tile(bx,by);const int offset=((bx+by)&1)?int(scale):-int(scale);
            for(unsigned y=0;y<tile.height;++y)for(unsigned x=0;x<tile.width;++x)
                b[0][size_t(tile.y+y)*bv[0].stride+tile.x+x]=uint16_t(int(b[0][size_t(tile.y+y)*bv[0].stride+tile.x+x])+offset);
        }
        auto half=film_grain_source_output_energy(av,bv,w,h,depth);
        assert(half.valid && !half.pass && half.foldMeanError[0][0]==-1 && half.foldMeanError[1][0]==1);
        ++negatives;b[0]=saved;
        // Quiet rows permit exact preservation; adding alternating lines does
        // not become a variance pass by dividing by a fabricated noise floor.
        for(unsigned c=0;c<3;++c) {
            const unsigned cw=c?w/2:w,ch=c?h/2:h;
            for(unsigned y=0;y<ch;++y)for(unsigned x=0;x<cw;++x) {
                a[c][y*av[c].stride+x]=128*scale;b[c][y*bv[c].stride+x]=128*scale;
            }
        }
        same=film_grain_source_output_energy(av,bv,w,h,depth);assert(same.valid && same.pass);++positives;
        for(unsigned c=0;c<3;++c) {
            const auto copy=b[c];const unsigned factor=c?2:1;
            for(unsigned by=0;by<grid.rows;++by)for(unsigned bx=0;bx<grid.columns;++bx) {
                const auto tile=grid.tile(bx,by);
                const int offset=bx==0?-int(scale):bx==grid.columns-1?int(scale):0;
                for(unsigned y=0;y<tile.height/factor;++y)for(unsigned x=0;x<tile.width/factor;++x)
                    b[c][size_t(tile.y/factor+y)*bv[c].stride+tile.x/factor+x]=uint16_t(128*scale+offset);
            }
            const auto steps=film_grain_source_output_energy(av,bv,w,h,depth);
            assert(steps.valid && !steps.pass && steps.constantSource[c] && !steps.actualMatchesSource[c]);
            // The earlier aggregate test would accept these artificial edges:
            // detrending removes them and both half means cancel or stay tiny.
            for(unsigned f=0;f<2;++f) {
                for(unsigned k=0;k<4;++k)assert(steps.actual.variance[f][k]==0 && steps.variancePass[f][k]);
                for(unsigned k=0;k<3;++k)assert(std::abs(steps.foldMeanError[f][k])<=.125);
            }
            for(double mean:steps.meanError)assert(std::abs(mean)<=.125);
            ++negatives;b[c]=copy;
        }
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x)b[0][y*bv[0].stride+x]=uint16_t((y&1?129:127)*scale);
        const auto lines=film_grain_source_output_energy(av,bv,w,h,depth);
        assert(lines.valid && !lines.pass && lines.quiet[0][0] && !lines.variancePass[0][0]);++negatives;
        assert(!film_grain_source_output_energy(av,bv,w+1,h,depth).valid);++negatives;
        assert(!film_grain_source_output_energy(av,bv,w,h,12).valid);++negatives;
    }
    for(unsigned depth:{8u,10u}) {
        const unsigned scale=1u<<(depth-8);
        std::array<std::vector<uint16_t>,3> a,b;std::array<FilmGrainNativePlane,3> av{},bv{};
        for(unsigned c=0;c<3;++c) {
            const unsigned w=c?64:128,h=c?64:128;a[c].resize(w*h);b[c].resize(w*h);
            for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
                a[c][y*w+x]=uint16_t((120+(17*x+11*y+7*c+(x*y)%13)%17)*scale);
                b[c][y*w+x]=uint16_t(a[c][y*w+x]+(!c && x%8==0?scale:0));
            }
            av[c]={a[c].data(),a[c].size(),w};bv[c]={b[c].data(),b[c].size(),w};
        }
        auto edge=film_grain_source_output_energy(av,bv,128,128,depth);
        assert(edge.valid && edge.pass && edge.meanError[0]==.125
            && edge.foldMeanError[0][0]==.125 && edge.foldMeanError[1][0]==.125);++positives;
        ++b[0][0];edge=film_grain_source_output_energy(av,bv,128,128,depth);
        assert(edge.valid && !edge.pass && edge.meanError[0]>.125 && edge.foldMeanError[0][0]>.125);++negatives;
    }
    std::cout<<positives<<" native source-output energy positives and "<<negatives
        <<" loss/mean/quiet/border/layout negatives passed\n";
}
