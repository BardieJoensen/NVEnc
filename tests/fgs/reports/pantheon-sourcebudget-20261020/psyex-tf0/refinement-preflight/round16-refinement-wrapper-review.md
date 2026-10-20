# R16 refinement generated-wrapper review

Reviewed 2026-10-20 before the first real 10042 refinement encode.

The generated files in `parent/psyex-tf0-r16-refine` are narrow adaptations of
the previously accepted R16 observation/scoring pipeline. The substantive
changes are limited to the fresh worker root, `encode_refine.py` and
`replay_refine.py` names, the accepted runner/replay/binder hashes, new addendum
hash, and hashes of the regenerated wrappers. Python compilation passes for all
parent scripts, and `derived-pins.json` agrees with the live file hashes.

The sequencer `observe_selected.py` SHA-256
`97d3d02749e6ccf5eb1a6d96e42056ab85cd00f130e200795807a83e1921753f`
retains the admitted R16 order and persistent outer receipts: all-336 decoder
validation, independent syntax binding, explicit target-identity guard, neutral
encoder off/on, neutral decoder off/on, aggregate admission, then stage
diagnostics. It invokes the accepted refinement replay and binder hashes. The
fixed `(event=314,coded=210,show=0,hint=88,refresh=16)` check is only a reuse
guard: a changed bitstream lifecycle fails before the old native observers are
used, rather than being assumed.

`validate_decoders.py`, `replay_decoder.py`, `admit.py`,
`stage_diagnostic.py`, and `score_r16.py` contain only the expected root and
pin substitutions. Admission loads the new runner and calls its complete
public refinement validator. Scoring still requires the admitted matched,
under-cap selected receipt and unchanged full campaign. `compare_controls.py`
is byte-identical because its evidence paths are supplied by CLI.

**Disposition:** accepted for use after a completed matched refinement encode.
These wrappers do not relax rate, decoder, native-stage, quality or playback
requirements.
