// Manual finite native-pixel test. Does not encode or install media.
#include "NVEncFilmGrainRetentionBlend.cuh"
#include "json.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
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
static FilmGrainCollectFrame destination(const FilmGrainCollectFrame& source, bool semi, Storage& storage) {
    auto out = source; out.complete = false;
    const unsigned bytes = source.bitDepth == 8 ? 1 : 2;
    for (unsigned p = 0; p < 3; ++p) {
        const size_t width = source.width / (p ? 2 : 1), rows = source.height / (p ? 2 : 1);
        const unsigned stride = semi && p ? 2 : 1;
        const size_t pitch = (width * stride + 26 + (p == 0 ? 8 : 0)) * bytes;
        if (semi && p == 2)
            out.plane[p] = {static_cast<const uint8_t*>(out.plane[1].data) + bytes, out.plane[1].pitchBytes, 2};
        else out.plane[p] = {storage.allocate(pitch * rows), pitch, stride};
    }
    return out;
}
static json dump(const fs::path& directory, const FilmGrainCollectFrame& frame, const Storage& storage,
    bool valid) {
    // Account for both interleaved components before testing untouched padding.
    for (const auto& a : storage.allocations) {
        std::vector<uint8_t> occupied(a.bytes, 0), data(a.bytes);
        checked(cudaMemcpy(data.data(), a.pointer, a.bytes, cudaMemcpyDeviceToHost));
        for (unsigned p = 0; p < 3; ++p) {
            const auto& plane = frame.plane[p]; const auto ptr = static_cast<const uint8_t*>(plane.data);
            const uintptr_t start = reinterpret_cast<uintptr_t>(a.pointer), current = reinterpret_cast<uintptr_t>(ptr);
            if (current < start || current >= start + a.bytes) continue;
            const unsigned bytes = frame.bitDepth == 8 ? 1 : 2;
            for (unsigned y = 0; y < frame.height / (p ? 2 : 1); ++y)
                for (unsigned x = 0; x < frame.width / (p ? 2 : 1); ++x)
                    for (unsigned b = 0; b < bytes; ++b)
                        occupied.at(current - start + y * plane.pitchBytes + x * plane.pixelStride * bytes + b) = 1;
        }
        for (size_t i = 0; i < data.size(); ++i)
            if (!occupied[i] && data[i] != 0xa5) throw std::runtime_error("padding overwritten");
    }
    json result = {{"width", frame.width}, {"height", frame.height}, {"depth", frame.bitDepth},
        {"shift", frame.storageShift}, {"frame_id", frame.frameId}, {"pts", frame.timestamp},
        {"epoch", frame.epoch}, {"complete", valid}, {"planes", json::array()}};
    for (unsigned p = 0; p < 3; ++p) {
        const auto& plane = frame.plane[p]; const unsigned bytes = frame.bitDepth == 8 ? 1 : 2;
        const size_t offset = p == 2 && plane.pixelStride == 2 ? bytes : 0;
        const size_t size = plane.pitchBytes * (frame.height / (p ? 2 : 1));
        std::vector<uint8_t> data(size);
        checked(cudaMemcpy(data.data(), static_cast<const uint8_t*>(plane.data) - offset, size, cudaMemcpyDeviceToHost));
        const auto path = directory / ("plane-" + std::to_string(p) + ".raw");
        std::ofstream output(path, std::ios::binary); output.write(reinterpret_cast<const char*>(data.data()), data.size());
        if (!output) throw std::runtime_error("native output write failed");
        result["planes"].push_back({{"path", path.string()}, {"pitch", plane.pitchBytes},
            {"offset", offset}, {"stride", plane.pixelStride}});
    }
    return result;
}
int main(int argc, char** argv) {
    json report = {{"complete", false}, {"cases", json::array()}};
    try {
        if (argc != 3) throw std::runtime_error("usage: retention-blend MANIFEST REPORT");
        json manifest; std::ifstream(argv[1]) >> manifest;
        const fs::path root = manifest.at("output_directory").get<std::string>();
        if (fs::exists(root) || !fs::create_directory(root)) throw std::runtime_error("output directory must be new");
        for (const auto& c : manifest.at("cases")) {
            Storage inputs, outputs, counters;
            const auto source = readFrame(c.at("source"), inputs), base = readFrame(c.at("base"), inputs);
            auto out = destination(source, c.at("output_semiplanar"), outputs);
            auto counter = reinterpret_cast<unsigned long long*>(counters.allocate(sizeof(unsigned long long)));
            FilmGrainCollectRetention fraction{c.at("retain").at(0), c.at("retain").at(1), c.at("retain").at(2)};
            cudaStream_t stream; checked(cudaStreamCreate(&stream));
            unsigned rejected = 0;
            const auto reject = [&](const FilmGrainCollectFrame& s, const FilmGrainCollectFrame& b,
                const FilmGrainCollectFrame& o, FilmGrainCollectRetention r, unsigned long long* count) {
                if (film_grain_retention_blend_async(s, b, o, r, count, stream) != cudaErrorInvalidValue)
                    throw std::runtime_error("invalid blend accepted");
                ++rejected;
            };
            auto alias = source; alias.complete = false; reject(source, base, alias, fraction, counter);
            alias = base; alias.complete = false; reject(source, base, alias, fraction, counter);
            auto wrong = base; wrong.timestamp++; reject(source, wrong, out, fraction, counter);
            wrong = out; wrong.frameId++; reject(source, base, wrong, fraction, counter);
            wrong = out; wrong.complete = true; reject(source, base, wrong, fraction, counter);
            wrong = out; wrong.plane[2] = wrong.plane[1]; reject(source, base, wrong, fraction, counter);
            wrong = out; wrong.plane[0].pitchBytes = 1; reject(source, base, wrong, fraction, counter);
            reject(source, base, out, {std::numeric_limits<float>::quiet_NaN(), 0, 0}, counter);
            reject(source, base, out, {0, std::numeric_limits<float>::infinity(), 0}, counter);
            reject(source, base, out, {0, 0, -.1f}, counter);
            reject(source, base, out, {0, 1.01f, 0}, counter);
            reject(source, base, out, fraction, nullptr);
            reject(source, base, out, fraction, reinterpret_cast<unsigned long long*>(const_cast<void*>(source.plane[0].data)));
            reject(source, base, out, fraction, reinterpret_cast<unsigned long long*>(const_cast<void*>(out.plane[0].data)));
            checked(film_grain_retention_blend_async(source, base, out, fraction, counter, stream));
            checked(cudaStreamSynchronize(stream));
            unsigned long long invalid = 0; checked(cudaMemcpy(&invalid, counter, sizeof(invalid), cudaMemcpyDeviceToHost));
            inputs.unchanged();
            const std::string id = c.at("id");
            const auto directory = root / id;
            if (!fs::create_directory(directory)) throw std::runtime_error("duplicate case directory");
            report["cases"].push_back({{"id", id}, {"invalid_samples", invalid}, {"negative_calls_rejected", rejected},
                {"inputs_unchanged", true}, {"padding_unchanged", true}, {"output", dump(directory, out, outputs, !invalid)}});
            checked(cudaStreamDestroy(stream));
        }
        report["complete"] = true;
    } catch (const std::exception& error) {
        report["error"] = error.what(); std::cerr << error.what() << '\n';
    }
    if (argc == 3) { std::ofstream output(argv[2]); output << report.dump(2) << '\n'; }
    return report["complete"].get<bool>() ? 0 : 1;
}
