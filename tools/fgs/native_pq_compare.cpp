// Explicit PQ/BT.2020/limited/left-sited 10-bit 4:2:0 paired diagnostics.
// Pixelwise grain phase affects RMS; 8x8 mean errors are separate descriptors.
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include "display_mapping.h"
struct Reader {
    std::ifstream input;int w=0,h=0;std::vector<uint16_t> y,u,v;
    explicit Reader(const char* path):input(path,std::ios::binary) {
        std::string line;std::getline(input,line);
        if(line.rfind("YUV4MPEG2 ",0))throw std::runtime_error("missing Y4M header");
        std::istringstream tokens(line);std::string t;bool ten=false;
        while(tokens>>t){if(t[0]=='W')w=std::stoi(t.substr(1));if(t[0]=='H')h=std::stoi(t.substr(1));if(t=="C420p10")ten=true;}
        if(!ten||w<=0||h<=0||w>8192||h>8192||w%8||h%8)throw std::runtime_error("require 10-bit 420 and dimensions divisible by 8");
        y.resize(w*h);u.resize(w*h/4);v.resize(w*h/4);
    }
    bool next() {
        std::string line;if(!std::getline(input,line))return false;
        if(line!="FRAME" && line.rfind("FRAME ",0))throw std::runtime_error("invalid frame delimiter");
        for(auto* plane:{&y,&u,&v}) {
            if(!input.read(reinterpret_cast<char*>(plane->data()),plane->size()*2))throw std::runtime_error("truncated frame");
            for(const auto value:*plane)if(value>1023)throw std::runtime_error("out-of-depth pixel");
        }
        return true;
    }
    double chroma(const std::vector<uint16_t>& plane,int x,int yy) const {
        const double px=x*.5,py=std::clamp((yy-.5)*.5,0.,double(h/2-1));
        const int x0=int(px),y0=int(py),x1=std::min(x0+1,w/2-1),y1=std::min(y0+1,h/2-1);
        const double fx=px-x0,fy=py-y0;
        return (1-fy)*((1-fx)*plane[y0*w/2+x0]+fx*plane[y0*w/2+x1])
            +fy*((1-fx)*plane[y1*w/2+x0]+fx*plane[y1*w/2+x1]);
    }
};
int main(int argc,char**argv)try {
    if(argc!=4)throw std::runtime_error("usage: native-display reference.y4m candidate.y4m peak_nits");
    Reader ref(argv[1]),enc(argv[2]);if(ref.w!=enc.w||ref.h!=enc.h)throw std::runtime_error("dimension mismatch");
    fgs_inspect::DisplayConfig config;config.transfer=16;config.matrix=config.primaries=9;config.peak_nits=std::stod(argv[3]);
    fgs_inspect::DisplayMapper mapper(config);
    int frame=0;while(ref.next()) {
        if(!enc.next())throw std::runtime_error("candidate frame count too small");
        std::array<double,4> energy{},coarse{},mean{};uint64_t refclip=0,encclip=0;
        for(int ty=0;ty<ref.h;ty+=8)for(int tx=0;tx<ref.w;tx+=8) {
            std::array<double,4> sum{};
            for(int yy=ty;yy<ty+8;++yy)for(int x=tx;x<tx+8;++x) {
                auto s=mapper.rgb_signal(ref.y[yy*ref.w+x],ref.chroma(ref.u,x,yy),ref.chroma(ref.v,x,yy));
                auto e=mapper.rgb_signal(enc.y[yy*enc.w+x],enc.chroma(enc.u,x,yy),enc.chroma(enc.v,x,yy));
                refclip+=mapper.clipped(s);encclip+=mapper.clipped(e);
                auto a=mapper.values(s),b=mapper.values(e);
                for(int c=0;c<4;++c){double delta=b[c]-a[c];energy[c]+=delta*delta;sum[c]+=delta;mean[c]+=delta;}
            }
            for(int c=0;c<4;++c)coarse[c]+=sum[c]*sum[c]/64;
        }
        const double pixels=double(ref.w)*ref.h;
        std::cout<<"{\"frame\":"<<frame++<<",\"peak_nits\":"<<config.peak_nits<<",\"reference_clipped_pixels\":"<<refclip
            <<",\"candidate_clipped_pixels\":"<<encclip<<",\"channels\":[";
        for(int c=0;c<4;++c)std::cout<<(c?",":"")<<"{\"rms\":"<<std::sqrt(energy[c]/pixels)
            <<",\"coarse8_rms\":"<<std::sqrt(coarse[c]/pixels)<<",\"bias\":"<<mean[c]/pixels<<"}";
        std::cout<<"]}\n";
    }
    if(!frame||enc.next())throw std::runtime_error("unequal or empty frame coverage");
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
