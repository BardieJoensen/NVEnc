# Actual source-copy proof for textured colour

September 27, 2026 — D72 implementation in progress; full GPU/encoder and
failure qualification are pending. Production remains `cb903a17`, retention
and FEL off. This extends the finite diagnostic, not automatic admission.

`pre_encode_preserved_chroma` in the input plan must match
`preserved_chroma_mask` in the native model engine. Both accept only Cb, Cr or
both (2/4/6). Y stays partial and each declared preserved colour fraction is
exactly one. Constant-colour mode remains separate; the modes cannot be mixed.

Before NVENC submission, an additional bounded transfer compares every native
candidate colour sample against the immutable original, including borders.
The transfer validates frame identity, timestamp, geometry, native layout and
decoder range. Its proof travels with the original's existing bounded lifetime.
Model fitting checks the same decision and proof again. The CPU replay adapter
derives proof from actual supplied candidate planes; a success flag in JSON
cannot replace those samples.

The model library must acknowledge the exact requested feature before a model
is accepted. Older ABI-compatible libraries cannot silently ignore the new
mode. D71's reference-only rejection is replaced by these paired controls;
zero colour synthesis and the original complete joint/mean quality checks
remain mandatory. Failed partial output cannot become source fallback without
a separate source encode. Ordinary mode adds no captures/transfers.

Validation is frozen in `roadmap-r3-preserved-transport-20260927/plan.json`
under the root linked by [the current handoff](WORK-TO-PRODUCTION.md). CUDA
controls share the prior native plane-layout fixture and separately exercise
both unchanged constant copying and textured copying, including missing/changed
proof, late border samples, invalid identity and lifetime cleanup. Actual
modeled GPU jobs must first pass D71's actual reconstructed-base reference.
R3–R8 remain open; no reserved footage or production policy is changed.
