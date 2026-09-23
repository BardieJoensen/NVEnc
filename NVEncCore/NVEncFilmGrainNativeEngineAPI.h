// ABI 2 for the explicit finite reference-synthesis diagnostic only.
// Adds push_pair; ABI 1 functions retain their file-source semantics.
// No AOM/FFmpeg/C++ object or allocation ownership crosses this boundary.
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct FgsNativePlane {
    const uint16_t* data;
    size_t samples, stride;
} FgsNativePlane;
unsigned fgs_native_engine_abi_version(void);
// Config binds 8..16 original-source plane paths/hashes to input ordinals/PTS.
// Initialization failure returns NULL; error(NULL) is thread-local.
void* fgs_native_engine_open(const char* json, size_t bytes);
// Base is the actual native unpacked NVENC reconstruction; three read-only
// planes, including for 8-bit input. The caller keeps them live for this call.
int fgs_native_engine_push(void*, uint64_t ordinal, int64_t pts, const FgsNativePlane base[3]);
// source_mode:"memory" only. Both pictures use native unpacked samples.
// Read-only spans stay live for this call; no ownership crosses the boundary.
int fgs_native_engine_push_pair(void*, uint64_t ordinal, int64_t pts,
    const FgsNativePlane source[3], const FgsNativePlane base[3]);
// 1=ready model, 0=pending, -1=terminal error. Copy JSON before the next model
// call or close; a failure always returns NULL/zero. No pending-as-original.
int fgs_native_engine_model(void*, uint64_t ordinal, const char** json, size_t* bytes);
int fgs_native_engine_finish(void*);
const char* fgs_native_engine_report(void*);
const char* fgs_native_engine_error(void*);
void fgs_native_engine_close(void*);
#ifdef __cplusplus
}
#endif
