# Finite native retention engine

This development-only CPU engine fits a frozen shape from the first eight native
source/reconstructed-base pairs, calibrates bounded strengths/seeds using pinned
AOM synthesis, and checks every picture and sliding eight-picture window. It
accepts 8–16 tile-aligned progressive 4:2:0 pictures. It does not choose pre-encode
retention fractions or grant source-population/perceptual approval.

`reference.cpp` is a manual JSON adapter. Its optional IVF path also exercises
the existing independent complete-model packet library. It writes an output
only after the entire trial completes. Original source/base planes use unpacked
native uint16 samples at both bit depths. Model readiness is separate from
reconstruction availability, including delayed hidden/reference pictures.

Build against pinned AOM `18c52422b835`, with repository `NVEncCore`, `json`, AOM
source/build includes, static `libaom.a`, `-lm -lpthread -ldl`. No new dependency
or analysis runs in ordinary NVEnc. The latest exact local build command,
library hashes and finite inputs are in `roadmap-r3-native-engine-20260923`.

Read the [implementation and qualification](../FINDINGS-2026-09-23-NATIVE-ENGINE.md)
before interpreting its outputs. A passing diagnostic is not deployment approval.

`library.cpp` exposes the eight ABI-1 functions in
`NVEncFilmGrainNativeEngineAPI.h`. It privately links pinned AOM and the SHA256
utility from the existing pinned FFmpeg static build; a version script hides
their symbols. No decoder or allocator object crosses the ABI. Source plane
paths/hashes and ordinal/PTS are explicit. Actual reconstructed planes arrive
as read-only native uint16 spans. Separate model queries return pending or ready;
errors are terminal and never return a replacement model. Copy model/report
strings before the next corresponding query or close. Contexts are serial;
separate contexts own independent state. Finish rejects missing source inputs.

The encoder-side `native_model_output` diagnostic uses this ABI only when
explicitly requested. CPU replay qualifies conversion/identity/readiness before
the live encoder trials; it does not prove live GPU behaviour by itself.
