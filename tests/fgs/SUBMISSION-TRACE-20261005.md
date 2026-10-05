# Diagnostic submission trace, 2026-10-05

This adds a small receipt for each actual frame handed to NVENC, including its grain parameters from the same encode. It is intended to distinguish changed encoder inputs from changed encoder results. No speed or output-identity result is claimed until the pinned trace build has been compared with production.

The branch starts at production head `6cfb28a5`, whose runtime code is `aeb14263`. The helper and pipeline hook apply unchanged to the `6e8fa1fb` filter-kernel candidate (`0a5b5594` documentation head). No filter, grain model, buffer initialization, grain-pointer lifetime, or encoder setting is changed.

Set `NVENC_TRACE_SUBMISSION=/absolute/new/submission.jsonl` for a bounded diagnostic encode. The parent directory must exist; the file is opened exclusively and an existing path fails the encode. Unset or empty disables tracing. There is one environment lookup during encoder construction and one disabled pointer branch per picture. That is not literally zero instructions, but adds no per-picture allocation, hashing, readback, CUDA operation, synchronization, or file I/O while disabled. No CLI option or production flow change is added.

The enabled hook runs after `NV_ENC_PIC_PARAMS` has its final `frameIdx`, input handle, timestamp, flags and film-grain pointer, immediately before `NVEncoder::NvEncEncodePicture`. That wrapper forwards the same structure to the SDK without modifying it. The resource has already been mapped, and producer-event waits have already been placed on the encoder input stream. The trace copies the registered CUDA allocation through that stream and synchronizes it, retaining the completed host snapshot. It copies the exact per-picture grain object into an owned byte array (156 bytes with this SDK), without retaining or changing the original pointer or its lifetime. Picture metadata and the initial grain object are copied too.

MD5 calculation, JSON serialization and flushing now happen only after successful encoder drain. The pre-submit path performs no hashing or JSON writes. The exclusive output file is opened on the first capture and remains empty until successful drain; an empty or partial file is never a passing receipt. `sendFrame` propagates finalization, flush and close errors. The destructor does not finalize traces because it cannot propagate an error. A successful repeated finish call is harmless.

Retained surface bytes plus reserved snapshot-record storage have a hard 2 GiB limit, with at most 4,096 records. Allocation failure or either limit stops the diagnostic explicitly; it never spills, truncates, samples frames or starts hashing mid-encode. The current 240-frame 1080p captures need about 1.484 GiB including records; the 24-frame 4K capture needs about 0.557 GiB. Allocator bookkeeping, the small trace object and existing encoder memory are outside that data-storage cap. The completed snapshots own their allocations until finalization, so recycling an encoder surface cannot change the later hashes. Readback and synchronization still perturb timing; this revision is not a claim of timing neutrality.

Only progressive AV1 CUDA-device NV12 and P010 are supported. Host surfaces, alpha, other formats/codecs and inconsistent allocation/picture geometry fail closed while tracing is enabled. CUDA copy/synchronization and trace-file errors also fail the encode. No trace file is accepted merely because it exists: require successful process exit, one header, exactly the expected number of ordered `submit` records with `frameIdx` 0 through N−1, and successful IVF/decode frame-count checks. A pre-submit record alone does not prove that submission succeeded.

## Schema 1

Each line is JSON. The first has `type=header`, `schema=1`, `hash=md5`, the capture/padding/visible-byte policy, `enableFilmGrainParams`, and `initial_grain` from the configured AV1 parameters. Every following line has `type=submit` and:

- `frameIdx`, `inputFrameId`, `timestamp`, `duration`, `pic_version`, `encodePicFlags`, `pictureStruct`, `bufferFmt`;
- `width`, `height`, `pitch`, `visible_row_bytes`, `rows`;
- `surface_md5`, `visible_md5`, `y_md5`, `uv_md5`, `padding_md5`;
- `filmGrainParamsUpdate` and `grain`.

`surface_md5` covers every pitch byte in the allocated Y and UV rows, with no padding initialization or normalization. `visible_md5` concatenates visible Y rows followed by visible interleaved UV rows. The plane hashes cover each of those portions separately. `padding_md5` concatenates only each row's trailing bytes, including both planes; it is the empty-byte MD5 when pitch equals visible row length. P010 captures the actual stored 16-bit values, including their low six bits. No pixel or padding byte is changed by the trace.

`grain` and `initial_grain` are null for null SDK pointers. Otherwise they contain `object_bytes`, `object_md5`, the exact `object_hex`, every SDK scalar field, and full byte arrays under their field names with `_hex` appended. The object hash includes reserved bits/bytes and any ABI padding. Named fields distinguish that exact-byte evidence from a semantic comparison; do not mistake a reserved or unused-array difference for a changed active model. With no per-picture update, compare the initial parameters and preceding update sequence as well as the current null/update flags. The trace does not infer NVENC's internal coding-order grain state.

## Interpretation and historical changes

The enabled readback and wait perturb timing and may change the frequency or appearance of existing output states. Qualify production+trace against production alone before treating traces as localization evidence. Compare meaningful pixels and exact grain inputs across arms and repeats, and report pitch padding separately. Equal traced inputs with different IVF or reconstructed pixels localize the difference downstream of the observed submission boundary for that instrumented run; they do not independently explain an uninstrumented run.

The old `f1ff639b` experiment captured pixels earlier in `sendFrame`, before mapping and before per-picture grain construction. `0d38724d` changed padding initialization and added completion-time captures. `1c2d333a` changed grain-pointer lifetimes. Those extra mutations are deliberately absent here. Completion-time captures, surface dumps and pointer-lifetime experiments are not needed for this initial bounded test.

## Ownership and parameter consumption audit

The normal successful path holds encoder surfaces until completion. `PipelineTaskCUDAVpp` takes each destination from `m_qEncodeBufferFree` (`NVEncPipeline.h:4109`), records the last producer event (`:4221`), hands the surface onward and releases its local free-queue guard (`:4272`). `sendFrame` queues producer-event waits, maps that resource, calls `encodeFrame`, and then places the surface in `qEncodeBufferUsed` (`:3530`). It is not returned to the free queue at submission. `getOutputBitstream` uses blocking `NvEncLockBitstream` (`:3080`) and copies/unlocks the completed output. Only afterward does `outputThreadFunc` unmap the input (`:3136`) and reset its guard (`:3164`) to return it to the free queue. Failed completion/unmapping removes device surfaces from reuse (`:3140`, `:3147`). This source audit found no ordinary early-reuse path; it cannot independently rule out an unrelated bad write after the snapshot.

Per-picture generated grain data is copied into the local `filmGrainParamsPicture` before the API call and stays alive throughout that call; table parameters instead point into the long-lived table (`NVEncPipeline.h:3372`). `NVEncoder::NvEncEncodePicture` immediately forwards the pointer (`NVEncDevice.cpp:503`). The SDK header describes copying input surfaces during `nvEncEncodePicture` and synchronizing those internal copies (`nvEncodeAPI.h:3676`), but its film-grain pointer comments only require a valid structure (`:2547`); they do not explicitly document when that pointed-to host object is copied. This diagnostic leaves that production lifetime unchanged. Equal traces therefore establish identical observed submissions and support downstream localization alongside the ownership audit, while an alleged post-return host-pointer access remains outside what a pre-submit hash alone can prove. The older persistent-parameter experiment is historical evidence, not a new lifetime test.

## Decision log

- auto: Create a separate branch from production head 6cfb28a5 and keep the same trace patch applicable to the existing filter-kernel candidate.
- auto: Capture at the final per-picture API boundary; keep the actual grain pointer and object lifetime unchanged.
- auto: Observe existing full-pitch bytes and report padding separately; never initialize or normalize them for the diagnostic.
- auto: Cache the environment toggle once; document the one-branch disabled overhead instead of claiming literally zero instructions.
- auto: Use exclusive JSONL output and require successful encode/decode plus exact ordered record counts rather than adding a second result-event branch.
- auto: Leave builds, GPU trials and output-neutrality qualification to the parent measurement workflow; source review is not a passing runtime result.
- auto: After six Lost Tapes production trace-on runs yielded only state B while trace-off runs retained A/B, keep the exact capture boundary and defer MD5/JSON until drain; preserve the original failed-neutrality evidence and requalify the revised instrumentation.
- auto: Bound retained diagnostic surfaces and snapshot records to 2 GiB/4,096 frames; propagate finalization failures on the normal drain path and never emit a successful receipt from destruction.
