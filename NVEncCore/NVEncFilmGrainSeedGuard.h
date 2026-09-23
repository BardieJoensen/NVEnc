// Optional encoded-packet guard. The private parser exposes only a stable C ABI.
// No parsing, library loading or packet copying occurs unless explicitly enabled.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include "rgy_tchar.h"
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

class NVEncFilmGrainSeedGuard {
public:
    NVEncFilmGrainSeedGuard() = default;
    NVEncFilmGrainSeedGuard(const NVEncFilmGrainSeedGuard&) = delete;
    NVEncFilmGrainSeedGuard& operator=(const NVEncFilmGrainSeedGuard&) = delete;
    ~NVEncFilmGrainSeedGuard() { close(); }

    bool open(const tstring& path) {
        close(); m_error.clear(); m_corrected = 0;
#ifdef _WIN32
        m_library = LoadLibrary(path.c_str());
#else
        m_library = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
#endif
        if (!m_library) { m_error = "Cannot load the requested seed parser library"; return false; }
        const auto version = symbol<unsigned (*)()>("fgs_av1_seed_abi_version");
        const auto create = symbol<void* (*)(const uint8_t*, size_t)>("fgs_av1_seed_open");
        m_process = symbol<int (*)(void*, uint8_t*, size_t)>("fgs_av1_seed_process");
        m_getError = symbol<const char* (*)(void*)>("fgs_av1_seed_error");
        m_close = symbol<void (*)(void*)>("fgs_av1_seed_close");
        if (!version || !create || !m_process || !m_getError || !m_close || version() != 1) {
            m_error = "Unsupported seed parser ABI (version 1 required)"; close(); return false;
        }
        m_context = create(nullptr, 0);
        if (!m_context) { m_error = "Cannot initialize the AV1 seed parser"; close(); return false; }
        return true;
    }

    // Only owned writable packet storage may be supplied, never a driver buffer.
    // The parser leaves all caller bytes unchanged on error and stops that stream.
    int process(uint8_t* data, size_t bytes) {
        if (!m_context || !m_process) { m_error = "Seed parser is not initialized"; return -1; }
        const int result = m_process(m_context, data, bytes);
        if (result < 0) {
            const char* error = m_getError(m_context);
            m_error = error && *error ? error : "AV1 seed parser failed";
        } else if (result) ++m_corrected;
        return result;
    }
    const std::string& error() const { return m_error; }
    uint64_t correctedPackets() const { return m_corrected; }

private:
    template<class T> T symbol(const char* name) {
#ifdef _WIN32
        return reinterpret_cast<T>(GetProcAddress(m_library, name));
#else
        return reinterpret_cast<T>(dlsym(m_library, name));
#endif
    }
    void close() {
        if (m_context && m_close) m_close(m_context);
        m_context = nullptr;
        if (m_library) {
#ifdef _WIN32
            FreeLibrary(m_library);
#else
            dlclose(m_library);
#endif
        }
        m_library = nullptr; m_process = nullptr; m_getError = nullptr; m_close = nullptr;
    }
#ifdef _WIN32
    HMODULE m_library = nullptr;
#else
    void* m_library = nullptr;
#endif
    void* m_context = nullptr;
    int (*m_process)(void*, uint8_t*, size_t) = nullptr;
    const char* (*m_getError)(void*) = nullptr;
    void (*m_close)(void*) = nullptr;
    uint64_t m_corrected = 0;
    std::string m_error;
};
