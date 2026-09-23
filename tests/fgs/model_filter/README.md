# Experimental streaming grain-model writer

This private library writes explicitly supplied complete AV1 grain models as
packets arrive. It is a prerequisite for compression-aware retention integration,
with no encoder hook, automatic selection, quality approval or deployment.
It shares model syntax with the [manual IVF writer](../MODEL-OVERRIDE.md).

Each stream has separate original and modified parser/reference states. An
unselected coded picture that copies a changed reference receives its original
model explicitly. A show-existing picture keeps its selected reference's model.
No-op packets retain their bytes. Caller input is read-only, including on error.
This is a header transformer, not a pixel decoder or full AV1 validator.

## Build

Use the verified private FFmpeg n8.0 source/static build described in
[the seed parser](../seed_filter/README.md), not arbitrary system FFmpeg versions.
From the repository root:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -fPIC -shared \
  -I json -I "$FGS_FFMPEG" tests/fgs/model_filter/model-library.cpp \
  "$FGS_FFMPEG/libavcodec/libavcodec.a" \
  "$FGS_FFMPEG/libavutil/libavutil.a" \
  -lpthread -lm -lz -latomic -Wl,--exclude-libs,ALL \
  -Wl,--version-script=tests/fgs/model_filter/exports.map \
  -o /storage/new/libfgsmodel.so
```

Only the eight `fgs_av1_model_*` ABI functions should be exported. Private FFmpeg
symbols stay local; no global log callback is installed. Retain the pinned
FFmpeg source, modifications, build recipe and LGPL license if distributing it.

## ABI version one

[api.h](api.h) specifies ownership and lifecycle. Open a stream with a maximum
packet count (1..1,000,000). At most sixteen model requests may be pending.
Each request is JSON of at most 64 KiB and contains:

- `schema: 1`, `coded_index`, `expected_apply`, `expected_seed`,
  `expected_order_hint`, and the manual writer's complete `model` object.
- `expected_pts`: the exact signed packet PTS in the caller's timebase.
- `packet_sha256`: the lowercase SHA256 of the unmodified packet containing
  the coded picture. Multiple coded pictures can share one packet.

Queue before the requested coded picture is processed. The identity binding
does not prove source quality or association with the correct decoded picture;
the caller still owns that evidence. Process serially within each context.
Independent contexts can run concurrently on the same read-only input allocation.
Input/output packets are bounded to 32 MiB. Copy returned output before the next
process call or close. No FFmpeg object or allocator crosses the ABI.

Any queue/process/finish failure makes the stream terminal. A failed process
returns no output; close/open starts afresh. Finish requires a coded picture and
no pending request. Successful repeated finish is harmless; queue/process after
finish fails. The caller must discard incomplete output after a later failure.
Closing is not successful completion.

Current scope is progressive AV1 4:2:0 at 8/10 bits, lag-three models and the
previously qualified colour lookup. Layered streams and redundant headers reject.
Dynamic selection, encoder frame identity, reconstruction availability under
reordering, bounded output buffering and pipeline error propagation remain open.

## Recorded qualification

D43 compares seven previously decoded controls: a corrected model, reordered
8/10-bit reference isolation, UHD HDR and three promoted-SDR models. Early queues,
just-in-time queues and no-op runs preserve every expected byte. Two grain-free
reference controls preserve no-op bytes too. Sharing model syntax leaves all
seven manual-writer outputs exact.

Sixteen concurrent runs and four contexts sharing one native packet allocation
preserve differing policies without changing input. Tests load unrelated system
FFmpeg globally first. Export/dependency checks verify isolation. Twenty-two
failure controls cover identity/hash/PTS errors, missing/late/duplicate/over-budget
requests, invalid syntax/arguments, truncation, empty/metadata-only streams and
calls after finish. Failed queueing preserves the previous output's lifetime.

The local ledger is `roadmap-r3-model-stream-20260923/` under the evidence root;
read `build-v2.json`, `report.json` and `shared-buffer.json`. Decoder evidence is
reused through complete byte identity; no fresh decoded-picture count is claimed.
This does not qualify automatic retention or change ordinary Tdarr.
