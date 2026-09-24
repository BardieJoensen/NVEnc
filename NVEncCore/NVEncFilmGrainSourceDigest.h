// Canonical native uint16 little-endian SHA-256, including for 8-bit sources.
// Uses the encoder's existing FFmpeg dependency. Only explicit source-bound
// diagnostics invoke this; ordinary encodes do not hash or copy source planes.
#pragma once
#include <algorithm>
#include <array>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include <cstdint>
extern "C" {
#include <libavutil/mem.h>
#include <libavutil/sha.h>
}
namespace fgsdiagnostic {
inline std::string nativeSourceDigest(const std::vector<uint16_t>& samples,unsigned depth) {
    if((depth!=8 && depth!=10) || samples.empty() || samples.size()>4096u*2160u)
        throw std::runtime_error("source digest native span is invalid");
    std::unique_ptr<AVSHA,decltype(&av_free)> state(av_sha_alloc(),av_free);
    if(!state || av_sha_init(state.get(),256)!=0)throw std::runtime_error("source digest initialization failed");
    std::array<uint8_t,8192> bytes{};
    for(size_t start=0;start<samples.size();) {
        const auto count=std::min(bytes.size()/2,samples.size()-start);
        for(size_t i=0;i<count;++i) {
            const unsigned v=samples[start+i];
            if(v>=(1u<<depth))throw std::runtime_error("source digest native code is invalid");
            bytes[2*i]=uint8_t(v);bytes[2*i+1]=uint8_t(v>>8);
        }
        av_sha_update(state.get(),bytes.data(),count*2);start+=count;
    }
    std::array<uint8_t,32> result{};av_sha_final(state.get(),result.data());
    constexpr char hex[]="0123456789abcdef";std::string text;text.reserve(64);
    for(const auto v:result){text.push_back(hex[v>>4]);text.push_back(hex[v&15]);}
    return text;
}
}
