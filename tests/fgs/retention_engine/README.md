# Finite native retention engine

This development-only CPU engine fits a frozen shape from the first eight native
source/reconstructed-base pairs, calibrates bounded strengths/seeds using pinned
AOM synthesis, and checks every picture and sliding eight-picture window. It
accepts 8–16 progressive 4:2:0 pictures with complete even dimensions up to
4096×2160 and both spatial folds populated. Disjoint even rectangles include
every native pixel in the means; moments use actual support counts. Aligned
64-pixel dimensions preserve their earlier geometry. It does not choose pre-encode
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

`copied_chroma_mask` is an explicit finite diagnostic extension: 2 copies Cb,
4 copies Cr, and 6 copies both. The default is zero. Y remains modeled. Each
copied component must be exactly constant across every native pixel of every
original/reconstructed pair, at the same code throughout a modeled segment,
within the inclusive restricted colour range (16–240 scaled to native depth).
Its model has a present, zero-strength curve and neutral AR coefficients. It
does not undergo a singular colour regression or strength search. Synthesis
must preserve every copied sample exactly; active components retain all their
previous diagnostics. Constant moment rows and cross terms must be exactly
zero, with exact global/fold means; zero variance alone cannot approve a copy.

Live experiments also require matching `pre_encode_copied_chroma` in the
explicit fraction plan. Copied fractions must be exactly one, other fractions
below one. An extra GPU capture verifies the actual pre-encode copied pixels
against the original before submission. The immutable source frame carries
this proof to reconstruction, and the library must explicitly acknowledge the
mask. Missing proof, an ordinary fallback override, a changed constant, a clamp
or an unsupported library rejects the finite trial. Ordinary mode performs none
of these extra transfers. This mechanism does not qualify textured copied
colour, real-source admission or automatic selection; those remain separate.


The standalone reference additionally supports `preserved_chroma_mask` (2/4/6,
default 0) for nonconstant colour. It cannot be combined with constant mode.
All source/reconstructed copied samples must be in the restricted native range;
synthesis must preserve the reconstructed samples exactly with zero strength.
Every ordinary full spatial/joint comparison still applies, including colour
variance, Y/colour and colour/colour correlation and native means. Degenerate
colour moments reject. This option alone proves neither pre-encode source copy
nor source population eligibility. The experimental live path requires matching `pre_encode_preserved_chroma`,
actual pre-encode sample proof and explicit library acknowledgement. D72
finite Linux qualification passes; this remains an experimental diagnostic. See
[the qualification record](../FINDINGS-2026-09-27-PRESERVED-CHROMA.md).

Explicit `pre_encode_source_segments` can interleave whole-source grain-off
rows with separately fitted modeled intervals. Copying the input is not proof
that NVENC preserves its grain. `NativeModelSegments` therefore measures every
source row against its actual reconstruction before publishing a grain-off
model. Both spatial halves must pass native/averaged luma and colour energy
checks (8% relative variance) and complete native means (0.125 in eight-bit
units); zero source energy must remain zero. Failure is terminal and the
rejected row remains unpublished. D78 additionally requires exact reconstructed
samples for each truly constant original component: opposite constant tile
offsets can otherwise disappear under detrending and cancel in the half means.
The report names `native_variance_means_constant_v2`, records the constant-source
and sample-match flags, and marks it as a necessary check only. It is not full local-detail, covariance
or temporal qualification. Read [D75/D76](../FINDINGS-2026-09-28-SOURCE-ENERGY.md)
and [D78](../FINDINGS-2026-09-28-CONSTANT-SOURCE.md) for implementation and current qualification status. Ordinary encoding does
not instantiate this diagnostic path.
