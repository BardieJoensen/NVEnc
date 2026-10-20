# R9 analyzer final integration and admission fault-probe review

Reviewed 2026-10-20, read-only:

- `analyze_psyex_boundary.py` SHA-256 `1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3`
- `check_psyex_boundary_admission.py` SHA-256 `c0215bce6d100effbf801ca274a4f66fd328cf18b5f1ed68b3648e6e91576abf`
- `analyzer-smoke-v2.jsonl` SHA-256 `4aae701fdd4a2fea026a2281a26c89f87c295c9de60d17656bb5e0800b16be9a`

## Analyzer disposition

Accepted for the admitted single-frame analysis. The final integration resolves the prior review findings:

- `stats()` emits both total and evaluable populations and leaves empty/null-only aggregates as `null` rather than inventing a value (lines 72–75).
- `group_semantics` explicitly states that `outside=false` is the complete population and `outside=true` is the legacy outside-only subset (lines 142–143).
- Raw 10-bit samples are divided by four once in `load_frame`; `luma8()` only rounds and clips the already converted values (lines 36–38, 76–78, 114–131). The full-frame panels retain native pixel geometry; the four fixed-ROI strips have explicit stage labels. The README correctly limits them to grayscale inspection rather than RGB, exact-10-bit, motion, or playback evidence.
- The report records actual argv, Python executable identity/version, analyzer identity, validator identity, and the three metric-helper identities.
- The preserved functional smoke covers complete versus outside-only counts, an empty kind, nullable ACF, source self-MSE, the one-conversion mapping, and `-O` rejection. Its target script and helper hashes agree with the reviewed files.

The smoke receipt is adequate for this helper-level check. Its final JSON row does not identify the smoke script itself, but the script is preserved adjacent to the receipt; this is a minor provenance improvement, not an analysis blocker.

## Fault-probe disposition

Accepted to run after the nominal on trace is complete. It uses the validator's actual `parse_trace`, starts from the real admitted-format trace, preserves updated record lengths on re-encoding, and exercises the important independent failure classes: truncated/trailing framing, sequence and generation mismatch, duplicate/missing SB ownership, an out-of-range 10-bit sample, removal of the accepted generation, terminal attempt-count mismatch, and plausible post-loop sample alteration.

One wording correction is recommended before treating its receipt as literal executed evidence: the plausible post-loop mutation is parsed successfully and compared locally against the expected R8 frame; the full validator is not invoked. Therefore `exact_postloop_binding_rejected: true` at lines 98–99 overstates what this harness executed. Rename it to `would_fail_exact_postloop_binding: true` or directly assert/catch the same equality used by validator line 277. This does not block the nominal admission or analyzer; it only affects the fault-probe receipt's claim precision.

The selected probes are sufficient for this targeted parser/admission check. Additional synthetic permutations would mostly duplicate source inspection and are not prerequisites for analysis.
