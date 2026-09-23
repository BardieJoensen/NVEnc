// Finite manual whole-component counter comparison; no encoder or installation.
#include "NVEncFilmGrainSourcePreservation.cuh"
#include "json.hpp"
#include <array>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
#include <filesystem>
using namespace fgsmodel;
using nlohmann::json;
namespace fs = std::filesystem;
static void checked(cudaError_t error) {
    if (error != cudaSuccess) throw std::runtime_error(cudaGetErrorString(error));
}
struct Allocation { uint8_t* pointer; size_t bytes; std::vector<uint8_t> original; };
struct Storage {
    std::vector<Allocation> allocations;
    ~Storage() { for (auto& a : allocations) cudaFree(a.pointer); }
    uint8_t* allocate(size_t bytes, std::vector<uint8_t> original = {}) {
        uint8_t* pointer = nullptr; checked(cudaMalloc(&pointer, bytes));
        if (original.empty()) checked(cudaMemset(pointer, 0xa5, bytes));
        else checked(cudaMemcpy(pointer, original.data(), bytes, cudaMemcpyHostToDevice));
        allocations.push_back({pointer, bytes, std::move(original)}); return pointer;
    }
    void unchanged() const {
        for (const auto& a : allocations) if (!a.original.empty()) {
            std::vector<uint8_t> now(a.bytes);
            checked(cudaMemcpy(now.data(), a.pointer, a.bytes, cudaMemcpyDeviceToHost));
            if (now != a.original) throw std::runtime_error("input buffer overwritten");
        }
    }
};
static FilmGrainCollectFrame readFrame(const json& record, Storage& storage) {
    FilmGrainCollectFrame f;
    f.width = record.at("width"); f.height = record.at("height");
    f.bitDepth = record.at("depth"); f.storageShift = record.at("shift");
    f.frameId = record.at("frame_id"); f.timestamp = record.at("pts"); f.epoch = record.at("epoch");
    f.complete = record.at("complete");
    for (unsigned p = 0; p < 3; ++p) {
        const auto& plane = record.at("planes").at(p);
        std::ifstream input(plane.at("path").get<std::string>(), std::ios::binary | std::ios::ate);
        if (!input) throw std::runtime_error("cannot read native plane");
        const size_t bytes = size_t(input.tellg()); input.seekg(0);
        const size_t pitch = plane.at("pitch"), offset = plane.at("offset");
        const unsigned rows = f.height / (p ? 2 : 1), columns = f.width / (p ? 2 : 1);
        const unsigned stride = plane.at("stride"), sampleBytes = f.bitDepth == 8 ? 1 : 2;
        if (bytes != pitch * rows || offset + size_t(columns - 1) * stride * sampleBytes + sampleBytes > pitch)
            throw std::runtime_error("invalid native plane size");
        std::vector<uint8_t> data(bytes); input.read(reinterpret_cast<char*>(data.data()), bytes);
        if (!input) throw std::runtime_error("short native plane");
        f.plane[p] = {storage.allocate(bytes, std::move(data)) + offset, pitch, stride};
    }
    if (!film_grain_collect_layout_valid(f)) throw std::runtime_error("invalid native frame");
    return f;
}

int main(int argc, char** argv) {
    json report={{"complete",false},{"cases",json::array()}};
    try {
        if(argc!=3)throw std::runtime_error("usage: source-preservation MANIFEST REPORT");
        json manifest;std::ifstream(argv[1])>>manifest;
        for(const auto& item:manifest.at("cases")) {
            Storage inputs,results;
            const auto source=readFrame(item.at("source"),inputs),base=readFrame(item.at("base"),inputs);
            auto device=reinterpret_cast<FilmGrainNativeComponentCounts*>(results.allocate(3*sizeof(FilmGrainNativeComponentCounts)));
            cudaStream_t stream;checked(cudaStreamCreate(&stream));unsigned rejected=0;
            const auto reject=[&](const FilmGrainCollectFrame& s,const FilmGrainCollectFrame& b,FilmGrainNativeComponentCounts* out,size_t capacity) {
                if(film_grain_source_preservation_async(s,b,out,capacity,stream)!=cudaErrorInvalidValue)
                    throw std::runtime_error("invalid source-preservation call accepted");
                ++rejected;
            };
            auto wrong=base;wrong.complete=false;reject(source,wrong,device,3);
            wrong=base;wrong.frameId++;reject(source,wrong,device,3);
            wrong=base;wrong.timestamp++;reject(source,wrong,device,3);
            wrong=base;wrong.epoch++;reject(source,wrong,device,3);
            wrong=base;wrong.width+=2;reject(source,wrong,device,3);
            wrong=base;wrong.plane[1].pitchBytes=1;reject(source,wrong,device,3);
            wrong=base;wrong.plane[2].data=nullptr;reject(source,wrong,device,3);
            wrong=base;wrong.plane[0].pitchBytes=std::numeric_limits<size_t>::max()-1;reject(source,wrong,device,3);
            reject(source,base,nullptr,3);reject(source,base,device,2);reject(source,base,device,4);
            reject(source,base,reinterpret_cast<FilmGrainNativeComponentCounts*>(reinterpret_cast<uint8_t*>(device)+1),3);
            reject(source,base,reinterpret_cast<FilmGrainNativeComponentCounts*>(const_cast<void*>(source.plane[0].data)),3);
            reject(source,base,reinterpret_cast<FilmGrainNativeComponentCounts*>(const_cast<void*>(base.plane[1].data)),3);
            std::vector<uint8_t> sentinel(3*sizeof(FilmGrainNativeComponentCounts));
            checked(cudaMemcpy(sentinel.data(),device,sentinel.size(),cudaMemcpyDeviceToHost));
            for(auto b:sentinel)if(b!=0xa5)throw std::runtime_error("invalid call touched counters");
            std::array<FilmGrainNativeComponentCounts,3> counts{},alias{};
            checked(film_grain_source_preservation_async(source,base,device,3,stream));
            checked(cudaMemcpyAsync(counts.data(),device,sizeof(counts),cudaMemcpyDeviceToHost,stream));
            checked(cudaStreamSynchronize(stream));
            // An exact alias is legal and must report zero changed samples.
            checked(film_grain_source_preservation_async(source,source,device,3,stream));
            checked(cudaMemcpyAsync(alias.data(),device,sizeof(alias),cudaMemcpyDeviceToHost,stream));
            checked(cudaStreamSynchronize(stream));checked(cudaStreamDestroy(stream));inputs.unchanged();
            json row={{"id",item.at("id")},{"negative_calls_rejected",rejected},{"invalid_calls_preserve_output",true},{"inputs_unchanged",true},{"counts",json::array()},{"alias_counts",json::array()}};
            for(const auto* values:{&counts,&alias})for(const auto& c:*values)
                row[values==&counts?"counts":"alias_counts"].push_back({{"samples",c.samples},{"changed_samples",c.changedSamples},{"invalid_samples",c.invalidSamples},{"minimum",c.minimum},{"maximum",c.maximum}});
            report["cases"].push_back(row);
        }
        report["complete"]=true;
    }catch(const std::exception& e){report["error"]=e.what();}
    if(argc>=3){std::ofstream out(argv[2]);out<<report.dump(2)<<'\n';if(!out)return 2;}
    std::cout<<json({{"complete",report["complete"]},{"cases",report["cases"].size()},{"error",report.value("error",std::string())}}).dump()<<'\n';
    return report["complete"].get<bool>()?0:1;
}
