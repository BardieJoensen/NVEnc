# Actual retention candidates with reconstructed model output

D55 qualifies `e4b96c4b`: original source, native pre-encode retention, NVENC
reconstruction and complete fitted model output now operate in the same finite
diagnostic encode. Production remains ordinary `cb903a17`, retention/FEL off.

The extension accepts only all-partial fractions below one, bilateral denoising
and original sources transported in memory. Before fitting, the immutable
per-picture decision must match the requested fractions, with no source guard
reason and no preserved component. A fallback cannot receive a replacement
grain model. Full-source output uses a separate `[1,1,1]` grain-off encode;
partial output rejected after compression is never relabeled as source fallback.
Precomputed model overrides remain incompatible with this candidate path.

## Evidence

- Full CPU suite: 214 Python tests in 30 suites plus 46 C++ programs. Four
  actual 16-picture candidate replays preserve all prior models/output bytes;
  eleven missing/changed/preserved/late-decision and completion controls reject.
  Existing ABI-2 memory-source behaviour also remains byte-identical.
- Eleven positive and six negative GPU encodes. Native 8/10-bit zero and mixed
  fractions produce all 64 reference models, readiness states and AV1 payloads
  exactly. Fresh full-source outputs preserve the original NVENC input and signal
  grain off. Four ordinary SDR/HDR controls preserve packets/clocks/metadata.
- 78,643,200 candidate samples match the independent rounded-base calculation;
  166,017,024 original and reconstruction samples per role match independent
  decoding. Both AOM and dav1d agree across 864 fresh decoded observations,
  including the separate complete-model comparison.
- An independent AOM synthesis oracle reproduces all 50,331,648 final native
  samples. Independent NumPy checks pass the declared 64 per-frame guards and
  36 sliding windows. **The original full-spatial per-picture check passes
  0/64 pictures.** Those failures remain recorded; the declared diagnostic
  frame/window policy is not whole-picture source admission or visual approval.
- GPU negatives exercise a real quiet-source fallback, a forbidden source
  endpoint, file-source mode, packet budget, wrong clocks and early termination.
  Shortening the encode changes lookahead packets and rejects their exact hashes
  first. A separate CPU replay with unchanged packets verifies missing-tail
  completion rejection. The first verification script expected the latter GPU
  error; its assertion and corrected classification are retained.

The reference fitter still uses costly CPU synthesis, and the clips are too
short for production throughput or full-title size claims. Original source
eligibility, automatic fraction selection, temporal quality and R3–R8 remain
unfinished. Reserved qualification footage is unopened.

## Reproduction and continuation

Local evidence: `colour-recovery-20260922/roadmap-r3-preencode-models-20260923/`.
Read `preflight.json`, `cpu-report.json`, `legacy-memory/result.json`, `encodes.json`,
`comparison.json`, `direct-comparison.json` and `drain-pause.json`.
Diagnostic binary `build-e4b96c4b/nvencc`, SHA-256
`1a1b1739a84dd9e3f0c56fe4e1a21401f38d0477963453586a2f8836cb33ab38`.
The [configuration contract](MODEL-OUTPUT-TRIAL.md#finite-pre-encode-candidates)
describes the supported combination and its failure semantics.

All owned Tdarr pauses are released with current worker limits preserved.
Next: connect the bounded fraction policy to these measured candidates and
source/detail eligibility, retaining every rejected outcome and an explicit
whole-source/original-file terminal fallback. No automatic job is scheduled.
