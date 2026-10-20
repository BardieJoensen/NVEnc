# R18 observation correction and control reuse

The initial cap-disabled control reproduced R16's IVF and all336 reconstruction
frames exactly. Fresh first-pass statistics also matched. The cap policy then
completed as immutable `cap-1`; its observation replay failed after4.199s with
`r18ed->coded_area_sb >= r18off` (exit86). This failed partial trace admits no
quantizer or quality result.

The hook is in `svt_aom_encdec_update`, which resets the coefficient cursor and
advances it only when its conditional coefficient/CDF update loop runs. That
cursor is not an unconditional position in the already encoded coefficient
layout. Subtracting current block area from it can underflow before any selected
SB record is emitted. The older R11 committed-layout cursor is target216-only
state and cannot be reused as an all-picture cursor without changing its scope.

Correction: in a fresh source/build, derive the selected block's offset from the
areas of its already committed predecessors in the current SB's final block
array. Keep actual TU offsets independently captured on the encoding path and
require exact correspondence during admission. Apply no policy/search/quantizer
change. Preserve source1, build1, all completed runs and the failed trace.

This changes the observation control procedure, **not the quality, rate or
intervention acceptance criteria**. After independently verifying that the
source diff affects only the observer, replay with the corrected observer and
the exact frozen first-pass statistics. Require exact IVF bytes, all336
reconstruction bytes and statistics against `cap-1`. This proves neutrality of
the active corrected observer directly; repeating baseline, first pass and the
unobserved cap is unnecessary if equality holds.

Provenance must explicitly distinguish the original policy build and its
baseline/pass1/cap chain from the corrected observation build and replay.
Quality, packet rate and two-pass encoding cost belong to `cap-1`; observation
runtime is diagnostic overhead. If exact equality fails, run one new-build cap
without observers to distinguish build drift from observer effects before
interpreting any trace. Full trace, native decoder, all-frame decoder, GPU
quality and control gates remain required.

Independent control review:
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020/reviewer/round18-observer-rebuild-control.md`,
SHA256 `f89fe17a3c299bc9dc6861a951d4fd5fe0a1a297867bcc377230a91d0de2a88b`.
Parent decision: accept this explicit two-build control because the decisive
neutrality comparison is stronger than repeating an inactive-observer run.
