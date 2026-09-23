// Versioned C boundary. No FFmpeg types or allocation ownership cross this API.
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
unsigned fgs_av1_model_abi_version(void);
void* fgs_av1_model_open(uint64_t max_packets);
// Queue one explicit, packet-hash/PTS/coded-identity-bound model request.
// At most16 requests may be pending. This is not automatic model admission.
int fgs_av1_model_queue(void*, const char* json, size_t bytes);
// The input is read-only. Output storage belongs to this context until its next
// process call or close. Copy it before processing another packet. On failure
// the output is null/zero and the stream is terminal; close/open starts afresh.
int fgs_av1_model_process(void*, const uint8_t* input, size_t bytes, int64_t pts,
                          const uint8_t** output, size_t* output_bytes);
// Finish rejects an empty stream or any unapplied request. No more queue/process
// calls are allowed after finish. A repeated successful finish is harmless.
int fgs_av1_model_finish(void*);
const char* fgs_av1_model_error(void*);
// A completed packet report includes original packet SHA-256/PTS and all coded
// and show-existing identities. Read only when last_packet_complete is true.
const char* fgs_av1_model_report(void*);
void fgs_av1_model_close(void*);
#ifdef __cplusplus
}
#endif
