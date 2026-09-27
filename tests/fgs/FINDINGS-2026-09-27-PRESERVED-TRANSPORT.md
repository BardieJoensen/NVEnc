# Actual source-copy proof for textured colour

September 27, 2026 — D72 Linux qualification complete in `524a98f6`. Production remains `cb903a17`, retention
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


The full encoder SHA is
`35dcffc13b8100e3961455cdcbea7fa862823971ccd102747382d4e41de7a275`.
Both CUDA transfer suites pass: 72 unchanged constant-colour cases/864 vetoes
and 72 textured-colour cases/1,368 vetoes, with 393,120 exact copied samples
per suite. All 16 CPU missing/changed-source proof cases reject without an
accepted output; original files remain unchanged. Four actual reconstruction
replays preserve all 64 models/readiness and complete AV1 bytes. Eighteen older
replays preserve all 288 prior models and bytes, including UHD.

Eight positive fresh encodes and ten deliberate clean rejections pass. Four
new textured-colour models match the reference through independent decoding;
ordinary SDR/HDR and two constant-colour controls retain their earlier output.
AOM/dav1d agree across 416 decoded observations. Complete original, candidate
and reconstruction checks each cover 75,497,472 samples, with 18,874,368 exact
copied candidate samples and 75,497,472 synthesis-oracle samples. All 96 modeled
frames and 54 windows pass. Each failure exits 1, publishes no completed model,
and retains the original quality/source veto. The full CPU suite passes 259
Python tests in 36 suites plus 53 C++ programs.

The new actual textured fixtures are 1024x512; this is not new UHD textured
source, unseen natural-source, full-title speed or transition qualification.
Tdarr's owned pause is released with current limits preserved. Next bind the
bounded selector to measured source ranges, then continue real eligibility,
bounded runtime and R3–R8. No experiment restarts automatically. Read
`report.json`, `phase2-comparison.json`, `legacy-comparison.json`,
`gpu-layout-report.json`, `library-v11-report.json` and
`source-negatives-report.json` in this stage's evidence directory.
