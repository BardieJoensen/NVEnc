// Bounded manual reconstruction evidence. Not an output-selection policy.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <cstdint>
#include <array>
#include <cmath>
#include <filesystem>
#include <set>
#include <stdexcept>
#include "../json/json.hpp"
#include "NVEncFilmGrainPreEncodeRetention.h"

struct NVEncFilmGrainReconConfig {
    std::set<uint32_t> frames;
    std::filesystem::path directory;
    uint64_t maxBytes = 0;
    uint64_t maxDeviceBytes = 512ULL*1024*1024;
    bool captureSource = false;
    uint64_t maxSourceBytes = 512ULL*1024*1024;
    fgsdiagnostic::PreEncodeRetentionPlan retention;
    bool preEncodeRetention() const {return retention.enabled();}

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
        // Disk evidence includes both original uint16 planes and reconstruction.
        // Sixteen complete UHD 10-bit pairs need about 760 MiB. This does not
        // enlarge either the source-memory or device allocation budget.
        if (!c.maxBytes || c.maxBytes > 1024ULL*1024*1024)
            throw std::runtime_error("reconstruction probe budget must be 1..1024 MiB");
        if (j.contains("max_device_bytes")) {
            if (!j.at("max_device_bytes").is_number_unsigned())
                throw std::runtime_error("reconstruction device budget must be unsigned");
            c.maxDeviceBytes=j.at("max_device_bytes").get<uint64_t>();
        }
        if (!c.maxDeviceBytes || c.maxDeviceBytes>2ULL*1024*1024*1024)
            throw std::runtime_error("reconstruction device budget must be 1..2048 MiB");
        if(j.contains("capture_source")) {
            if(!j.at("capture_source").is_boolean())throw std::runtime_error("capture_source must be boolean");
            c.captureSource=j.at("capture_source").get<bool>();
        }
        if(j.contains("max_source_bytes")) {
            if(!c.captureSource || !j.at("max_source_bytes").is_number_unsigned())
                throw std::runtime_error("source byte budget requires explicit source capture and unsigned bytes");
            c.maxSourceBytes=j.at("max_source_bytes").get<uint64_t>();
        }
        if(!c.maxSourceBytes || c.maxSourceBytes>512ULL*1024*1024)
            throw std::runtime_error("source byte budget must be 1..512 MiB");
        c.retention=fgsdiagnostic::PreEncodeRetentionPlan::parse(j,c.frames.size());
        if(c.retention.sourceSegments() && !j.contains("native_model_output"))
            throw std::runtime_error("source segments require explicit native model output");
        if(c.preEncodeRetention()) {
            if(!c.captureSource
                || *c.frames.begin()!=0 || *c.frames.rbegin()+1!=c.frames.size())
                throw std::runtime_error("pre-encode retention requires three fractions and consecutive source captures from zero");
            // Ordinary/precomputed models cannot describe an independently
            // changed base. Native fitting must consume the matching original.
            if(j.contains("model_output"))
                throw std::runtime_error("pre-encode candidate cannot be combined with precomputed model output");
            if(j.contains("native_model_output")) {
                if(j.at("native_model_output").at("engine").at("source_mode")!="memory")
                    throw std::runtime_error("pre-encode model fitting requires original memory sources");
                c.retention.modelSegments();
            }
        }
        c.directory = std::filesystem::u8path(j.at("output_directory").get<std::string>());
        if (!c.directory.is_absolute()) throw std::runtime_error("reconstruction directory must be absolute");
        return c;
    }
    uint64_t requireLayout(unsigned width, unsigned height, unsigned depth) const {
        if (width < 64 || height < 64 || width > 4096 || height > 2160
            || (width & 1) || (height & 1) || (depth != 8 && depth != 10))
            throw std::runtime_error("reconstruction probe requires progressive 8/10-bit 4:2:0, at most 4096x2160");
        const uint64_t bytes = uint64_t(width)*height*3/2*(depth == 10 ? 2 : 1);
        const uint64_t sourceBytes=captureSource?uint64_t(width)*height*3:0;
        if (frames.empty() || frames.size() > 16 || (bytes+sourceBytes)*frames.size()+65536 > maxBytes
            || (captureSource && sourceBytes>maxSourceBytes))
            throw std::runtime_error("reconstruction byte budget does not cover all requested frames");
        return bytes;
    }
};
