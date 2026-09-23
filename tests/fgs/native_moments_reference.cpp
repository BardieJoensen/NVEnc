// Independent native-pixel comparison adapter, with no automatic admission.
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
#include "native_moments_json.h"
using Json=nlohmann::json;
int main() {
    try {
        Json j;std::cin>>j;const unsigned w=j.at("width"),h=j.at("height"),depth=j.at("depth");
        if(w<64 || h<64 || w>4096 || h>2160 || w%64 || h%64 || (depth!=8 && depth!=10))throw std::runtime_error("invalid layout");
        std::array<std::vector<uint16_t>,3> data;std::array<fgsmodel::FilmGrainNativePlane,3> planes{};
        for(unsigned c=0;c<3;++c) {
            const auto path=std::filesystem::u8path(j.at("planes").at(c).get<std::string>());const unsigned width=c?w/2:w,height=c?h/2:h;const size_t count=size_t(width)*height;
            if(std::filesystem::file_size(path)!=count*2)throw std::runtime_error("native plane byte count differs");
            data[c].resize(count);std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(data[c].data()),count*2);if(!file)throw std::runtime_error("plane read failed");planes[c]={data[c].data(),count,width};
        }
        const auto start=std::chrono::steady_clock::now();const auto m=fgsmodel::film_grain_native_moments(planes,w,h,depth);
        auto report=fgsdiagnostic::moments(m);report["seconds"]=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::cout<<report.dump()<<'\n';return m.valid?0:1;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
