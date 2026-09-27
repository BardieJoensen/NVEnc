// Shared native CUDA plane-layout fixture for copied-source diagnostics.
#pragma once
#include "NVEncFilmGrainSourceFrame.cuh"
namespace fgs_gpu_test {
using namespace fgsdiagnostic;
using namespace fgsmodel;
static void require(bool b,const char* why){if(!b)throw std::runtime_error(why);}
static void check(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
struct Picture {
    static constexpr unsigned w=130,h=126;
    FilmGrainCollectFrame view;
    std::array<void*,3> allocation{};
    std::array<size_t,3> pitch{};
    bool semi,padded;
    std::array<std::vector<uint16_t>,3> planes;
    Picture(unsigned depth,bool interleaved,bool pad,unsigned code):semi(interleaved),padded(pad) {
        view.width=w;view.height=h;view.bitDepth=depth;view.storageShift=semi && depth==10?6:0;
        view.frameId=91;view.timestamp=123456;view.complete=true;
        for(unsigned c=0;c<3;++c)planes[c].assign(size_t(w)*h/(c?4:1),c?code:80*(1u<<(depth-8)));
        upload();
    }
    ~Picture(){for(auto p:allocation)if(p)cudaFree(p);}
    void upload() {
        const unsigned unit=view.bitDepth==8?1:2;
        for(unsigned c=0;c<(semi?2u:3u);++c) {
            const unsigned cols=c?w/2:w,rows=c?h/2:h,stride=semi && c?2:1;
            const size_t row=size_t(cols)*stride*unit+(padded?38:0);std::vector<uint8_t> host(row*rows,0xad);
            for(unsigned component=c;component<=((semi && c)?2:c);++component)
                for(unsigned y=0;y<rows;++y)for(unsigned x=0;x<cols;++x) {
                    const auto value=unsigned(planes[component][size_t(y)*cols+x])<<view.storageShift;
                    const size_t i=y*row+(x*stride+component-c)*unit;host[i]=value&255;if(unit==2)host[i+1]=value>>8;
                }
            if(!allocation[c])check(cudaMallocPitch(&allocation[c],&pitch[c],row,rows));
            check(cudaMemcpy2D(allocation[c],pitch[c],host.data(),row,row,rows,cudaMemcpyHostToDevice));
            view.plane[c]={allocation[c],pitch[c],stride};
            if(semi && c)view.plane[2]={static_cast<uint8_t*>(allocation[c])+unit,pitch[c],2};
        }
    }
};
} // namespace fgs_gpu_test
