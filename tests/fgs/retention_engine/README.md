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
