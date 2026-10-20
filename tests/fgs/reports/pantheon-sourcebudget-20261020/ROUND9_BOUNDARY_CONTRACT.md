# Round9: localize the fixed PSYEX loss across reconstruction boundaries

R8 delivered its aggregate search policy and failed at the original rate. The
next primary question is whether the prescribed E05 frame loses texture before
coding, during coding, or across the in-loop filter boundary.

This is an observation of the exact R8 stream, not a new settings arm. Capture
input picture216/scored frame120 only. Compare independently bound original
YUV, actual packed coding input, complete pre-loop reconstruction, and actual
post-loop reconstruction. Coding input may differ from original because of
upstream processing; retain and measure that difference.

The independent design review accepts a narrower boundary-first experiment
than the initially discussed final-TU trace. Per-TU realized quantization,
MD coefficient reuse, skips and final spatial/HBD route survival are deferred.
They are not needed to answer the boundary question and cannot be inferred from
stored block fields or aggregate counters. No preservation criterion changes.

Use a fresh private copy of pinned PSYEX59d1a025 and its audited cpuinfo
dependency. Parent owns implementation, runners, analysis and Git index.
Worker owns the source-hook audit and any explicitly assigned fresh build
directory; reviewer owns independent design/implementation/outcome reviews.
No recursive delegation or production changes.

Capture each packed 16-bit source SB immediately after prepare_input_picture.
Retain its frame, generation, SB coordinates, clipped visible dimensions,
strides and all Y/U/V samples. Require exactly one owner for every visible
sample in each attempt. Capture the whole pre-loop frame at the last-SB barrier
after do_recode is computed and before either branch posts more work.

The fixed P4/non-RTC/fast_decode0 source selects DLF level2 with SB-based DLF
disabled. Assert this at runtime before the first target SB; do not change the
setting. Otherwise the whole-frame barrier would be too late and admission must
fail. Frame-based DLF begins only after the EncDec result is posted.

Retain every completed attempt with do_recode and increment the diagnostic
generation only on recode. Exactly one complete accepted generation must join
the actual recon-output snapshot and input/display identity. Assert film grain,
resize and superres are disabled. Both observation-off and observation-on must
reproduce the original complete336-frame IVF and application reconstruction.
The target post-loop YUV must equal admitted R8 frame216 in every sample.

Use a versioned, length-framed trace with sequence numbers, bounded dimensions,
an end marker, fatal write/overflow/coverage errors and a fresh inherited output
descriptor. Record actual commands, source/build/binary hashes and timing.
These replay times are diagnostic overhead, not a replacement for R8 runtime.

Analyze unchanged shirt/background rectangles and all858 frozen frame120 tiles,
with original source descriptors and group definitions. Report contiguous
HF amplitude, ACF, source correlation, pixel errors, controls and tails. No
new pass threshold. This one-frame stage observation cannot qualify a repair,
attribute a component-specific cause, establish packet cost, or imply playback.

A source→coding-input difference implicates upstream sample processing for
this frame. Coding-input→pre-loop loss implicates the coding decisions together.
Pre-loop→post-loop change measures the net filter stack. If a boundary is
nearly unchanged, do not repeat that path's settings without new evidence.
