# Preserving textured colour while modelling luma grain

September 27, 2026 — D71 reference and actual NVENC candidate/carrier checks pass. This is not real
source admission, R3 completion or a production change.

The finite reference now accepts explicit `preserved_chroma_mask` (2, 4 or 6)
for nonconstant colour. It fits no regression and adds zero grain in those
channels. Every source and reconstructed colour sample must lie in the native
restricted decoder range; every synthesized copied sample must equal the
reconstructed sample exactly. The original spatial, joint correlation and
mean comparisons still include all colour rows and retain their existing
bounds. Compression changes are not relabelled as lossless source preservation.

The earlier `copied_chroma_mask` constant-colour mode remains separate and
unchanged. The modes cannot be combined. Nonconstant colour with singular
within-tile moments still rejects; a zero variance does not invent evidence.
At the D71 checkpoint, live entry points reject this reference-only option.
[D72](FINDINGS-2026-09-27-PRESERVED-TRANSPORT.md) subsequently integrates and
qualifies actual pre-encode proof and explicit library acknowledgement.

CPU evidence:

- 48 complete native range/equality controls, including padded, ragged,
  1080p and UHD planes; 896 border, layout, native-code and mask vetoes.
- Eighteen sixteen-frame synthesis controls: ten positive static/moving/
  changing/shared-seed correlated colour cases and eight expected failures.
  Independent NumPy comparisons cover 231 attempted models and 122 windows;
  52,035,584 copied synthesis samples match exactly. Inputs remain unchanged.
- Correlated colour with independent replacement luma grain rejects at both
  depths. Late invalid source/reconstructed border codes and singular colour
  also reject. No held-out seed retry or numerical-bound change was made.
- Eighteen earlier library replays preserve all 288 models, decisions,
  readiness and complete encoded bytes, including ordinary partial models,
  source transitions, constant-colour modes and 1080p/UHD.
- Full CPU: 259 Python tests in 36 suites plus 53 C++ programs. Additional
  configuration guards reject the reference-only flag before opening a library;
  nine native-library controls reject it before initialization.

One fixture initially expected a correlation failure but reused the original
luma synthesis seed schedule. Independent comparisons correctly showed that
its correlation survived. The original script, plan and result are retained;
that case is a correlated positive. A separate source-luma seed permutation
then creates an actual lost-correlation control, which rejects at both depths.
This correction did not change any encoder/model rule or qualify real footage.

The constructed sources isolate this mechanism; their known luma grain and
artificial colour do not establish natural-image eligibility. Actual NVENC
capture comparisons use the already-qualified `c7a4b827` encoder and no new
live model option. Eight fresh captures yield four accepted reference carriers, one retained
correlation rejection and three 10-bit whole-source overrides (ordinary fallback
and limited support). The latter do not qualify as modeled outputs. All 768
AOM/dav1d observations agree. Native source, candidate and reconstruction each
match 100,663,296 samples; 25,165,824 copied candidate samples are exact.
Independent synthesis verifies 50,331,648 samples and 36 windows.

Local evidence: `roadmap-r3-preserved-chroma-20260927/` under the root linked
by [the project handoff](WORK-TO-PRODUCTION.md). Read `plan.json`,
`study-report.json`, `fixture-correction.json`, `library-v10-report.json`,
`full-cpu.json` and the current `phase1-pause.json`. R3–R8 remain open;
production `cb903a17`, retention and FEL off; reserved footage unopened.
