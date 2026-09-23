// Bounded manual reconstruction evidence. Not an output-selection policy.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <cstdint>
#include <filesystem>
#include <set>
#include <stdexcept>
#include "../json/json.hpp"

struct NVEncFilmGrainReconConfig {
    std::set<uint32_t> frames;
    std::filesystem::path directory;
    uint64_t maxBytes = 0;
    uint64_t maxDeviceBytes = 512ULL*1024*1024;

    static NVEncFilmGrainReconConfig parse(const nlohmann::json& j) {
        NVEncFilmGrainReconConfig c;
        if (!j.is_object() || j.at("schema") != 1 || !j.at("frames").is_array()
            || j.at("frames").empty() || j.at("frames").size() > 16)
            throw std::runtime_error("reconstruction probe requires schema 1 and 1..16 frame IDs");
        for (const auto& value : j.at("frames")) {
            if (!value.is_number_integer() || value < 0 || value > 10000000
                || !c.frames.insert(value.get<uint32_t>()).second)
                throw std::runtime_error("invalid or duplicate reconstruction frame ID");
        }
        if (!j.at("max_output_bytes").is_number_unsigned())
            throw std::runtime_error("reconstruction probe requires an unsigned byte budget");
        c.maxBytes = j.at("max_output_bytes").get<uint64_t>();
        if (!c.maxBytes || c.maxBytes > 512ULL*1024*1024)
            throw std::runtime_error("reconstruction probe budget must be 1..512 MiB");
        if (j.contains("max_device_bytes")) {
            if (!j.at("max_device_bytes").is_number_unsigned())
                throw std::runtime_error("reconstruction device budget must be unsigned");
            c.maxDeviceBytes=j.at("max_device_bytes").get<uint64_t>();
        }
        if (!c.maxDeviceBytes || c.maxDeviceBytes>2ULL*1024*1024*1024)
            throw std::runtime_error("reconstruction device budget must be 1..2048 MiB");
        c.directory = std::filesystem::u8path(j.at("output_directory").get<std::string>());
        if (!c.directory.is_absolute()) throw std::runtime_error("reconstruction directory must be absolute");
        return c;
    }
    uint64_t requireLayout(unsigned width, unsigned height, unsigned depth) const {
        if (width < 64 || height < 64 || width > 4096 || height > 2160
            || (width & 1) || (height & 1) || (depth != 8 && depth != 10))
            throw std::runtime_error("reconstruction probe requires progressive 8/10-bit 4:2:0, at most 4096x2160");
        const uint64_t bytes = uint64_t(width)*height*3/2*(depth == 10 ? 2 : 1);
        if (frames.empty() || frames.size() > 16 || bytes*frames.size()+65536 > maxBytes)
            throw std::runtime_error("reconstruction byte budget does not cover all requested frames");
        return bytes;
    }
};
