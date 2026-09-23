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

`library.cpp` exposes the nine ABI-2 functions in
`NVEncFilmGrainNativeEngineAPI.h`. It privately links pinned AOM and the SHA256
utility from the existing pinned FFmpeg static build; a version script hides
their symbols. No decoder or allocator object crosses the ABI. Source plane
paths/hashes and ordinal/PTS are explicit. Actual reconstructed planes arrive
as read-only native uint16 spans. Separate model queries return pending or ready;
errors are terminal and never return a replacement model. Copy model/report
strings before the next corresponding query or close. Contexts are serial;
separate contexts own independent state. Finish rejects missing source inputs.
ABI 2 adds `push_pair` for `source_mode: "memory"`; its source records contain
ordinal/PTS and must not specify files. Both original and reconstructed planes
are passed directly as native read-only spans. Mixing file and memory push modes
is a terminal error. The encoder still accepts ABI 1 for file-source diagnostics;
memory-source experiments require ABI 2.

The encoder-side `native_model_output` diagnostic uses this ABI only when
explicitly requested. CPU replay qualifies conversion/identity/readiness before
the live encoder trials; it does not prove live GPU behaviour by itself.

`spatial_policy` explicitly selects `frame_window` (the existing diagnostic
default) or `full_picture`. Full-picture mode keeps the same numerical bounds
but requires colour spatial/cross checks on every picture, as well as the existing
sliding windows. At most four seeds are tried using only training-fold spatial
evidence. The first training pass is final: independent-fold or global-mean
failure rejects instead of trying another seed. Neither policy grants source
eligibility. The engine report names the active policy; the encoder requires
explicit confirmation for `full_picture`, since older ABI-compatible libraries
can otherwise ignore an unknown JSON key.

`full_picture_means` adds complete native-pixel means measured separately on the
fixed checkerboard training/check halves, before detrending. The training mean
uses the unchanged 0.125 code-unit limit and may reject a seed before selection.
After the first training spatial/mean pass, the independent mean, spatial checks
and global mean are terminal vetoes. At most four seeds are evaluated. Missing
mean evidence cannot pass, and opposite shifts in the two halves cannot cancel.
Older policies preserve their recorded decisions. The consumer requires exact
confirmation of this new policy too; no source eligibility follows from it.

`frame_window_means` applies disjoint native means to the earlier calibrated
frame/window policy. Each training half must pass native Y spatial checks,
all-channel variance bounds and its own mean bound. The first training pass
then faces independent-half shape/variance/mean and global-mean vetoes; none
of those vetoes causes a seed retry. The same complete spatial/cross-component
eight-picture sliding windows remain mandatory before model release. This
removes global-mean selection leakage from the older diagnostic without hiding
its original full-spatial per-picture failures or granting source eligibility.
All older policy names preserve their decisions; this policy also requires
explicit runtime confirmation.
