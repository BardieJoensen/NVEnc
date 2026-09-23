# Finite native retention before NVENC

D54 qualifies the explicit finite candidate path in `5adc0f3e`. Production
ordinary `cb903a17`, retention/FEL off, is unchanged. This is a candidate-base
measurement facility, not automatic retention or new source eligibility.

Each candidate uses the original source and one untouched denoised base,
captured before existing retention/recovery/source-cap/compensation operations.
The qualified GPU blend applies each native component fraction exactly once,
with separate float32 multiply/add and nearest-even rounding. Existing source
fallbacks and limited support/recovery preserve the whole source; inactive
components remain copied. Requested/effective fractions and preservation reasons
travel with the immutable source identity. Candidate-only pictures explicitly
disable grain, including inherited models. Full-source means exact NVENC input,
not lossless decoded output.

The experiment requires bilateral denoising, 1–16 consecutive original/source
captures from ordinal zero, and exact completion. At this stage model-output
combinations and ordinary grain-table export reject. The following integration
stage may admit only separately qualified combinations. Ordinary mode allocates
none of the candidate buffers. The [contract](MODEL-OUTPUT-TRIAL.md#finite-pre-encode-candidates)
describes the current supported configuration.

## Qualification

- Full CPU suite: 214 Python tests in 30 suites, plus 46 C++ programs. The new
  decision controls cover every component mask and combination of source guards,
  invalid fractions and exact source endpoints.
- 18 successful GPU encodes and nine intended failures on the final pinned
  binary. Native 8/10-bit zero, mixed, source-luma and whole-source candidates;
  quiet full-depth chroma and a brightness cut; ordinary SDR and HDR controls.
- 169,162,752 actual candidate samples exactly match independent NumPy rounding.
  All candidates share byte-identical pristine bases. The 96 partial and 72
  whole-source picture decisions agree with the captured pixels and reasons.
- 256,536,576 original samples match independent software decoding; the same
  count of reconstruction samples matches fresh AV1 base decoding. Both AOM
  and dav1d agree across 864 fresh grain-on/off picture observations. Every
  candidate signals grain off. Four ordinary controls preserve packets, clocks
  and colour/HDR metadata exactly.
- Nine failures verify missing source, sparse capture, out-of-range/boolean
  fractions, incompatible model/table output, extra/missing pictures and an
  unsupported motion-denoiser configuration. All fail for the intended reason.

The real SDR/HDR controls are four pictures each and establish mechanics and
ordinary equivalence, not perceptual or temporal qualification. The SDR library
derivative is an input-provenance control, not an original-quality reference.
Reserved qualification excerpts remain unopened.

The first quiet fixture was below NVENC's minimum dimensions; a second setup
attempt requested the bilateral-only joint probe with motion denoising. Both
initialization failures and completed intermediate runs remain documented.
The final positive set was repeated after adding the explicit bilateral guard.
No failed result was counted as a successful candidate.

## Evidence and next work

Local evidence: `colour-recovery-20260922/roadmap-r3-preencode-retention-20260923/`,
particularly `build.json`, `cpu-suite.json`, `encodes.json`, `comparison.json`,
`attempt-1/`, `attempt-2/` and `final-pause.json`.
Binary `build-5adc0f3e/nvencc`, SHA-256
`30d33cb363c37dbd21c90ba3003eb0fecc331142f4eb02fd8f8d8dd9a212776b`.

All trial-owned Tdarr pauses are released with current worker limits preserved.
Continue binding actual candidates to complete reconstructed models, bounded
fraction selection and explicit source fallback. Source/detail eligibility,
perceptual/temporal quality and R3–R8 remain unfinished; nothing runs automatically.
