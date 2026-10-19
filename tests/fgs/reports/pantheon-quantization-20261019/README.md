# Pantheon effective-quantization follow-up — in progress

This is an isolated mechanism study, continuing the completed causal report at
58a113db. No production or library changes are authorized or made. Final findings
will replace this progress note when all bounded checks are complete.

Verified foundation: new final-luma-TU instrumentation leaves complete E04 and
E05-1440 baseline IVF streams byte-identical to the preserved SVT 4.2 baseline.
Each visible diagnostic-frame pixel is captured exactly once; actual input and
pre-loop-filter reconstruction equal the archived stages. Private forward
coefficients equal actual forward coefficients where coding runs; private inverse
reconstruction of final dequantized coefficients equals actual reconstruction.
All captured input-minus-predictor residuals agree exactly.

The `svt-quantization.patch` applies after the preceding causal report's patch to
upstream SVT 4.2 source 9292ec8e32bce26f781f277ec8739b53426c4300. It is opt-in via
`PANTHEON_DETAIL_DIR` and `PANTHEON_DETAIL_POC` (`,230,` for E04 or `,216,` for E05).
It exports final coding decisions, not transient mode-search candidates. Buffers
are isolated and SIMD aligned. `instrument.py` reproducibly constructs the patch.
The initial unaligned diagnostic attempt crashed; it is not quality evidence.

`study.py` prepares fresh intermediates using archived command arrays and checks
new reference hashes against the previously independently verified original.
`encode.py CASE TAG baseline|QP` reproduces baseline or forces CQP/AQ-off while
keeping other settings fixed. `stages.py CASE TAG` verifies and analyzes native
records. `score.py` uses campaign.py and the mandated GPU metrics, texture checks,
and independent decoder comparison. `representability.py` screens old held-out
controls using newly decoded originals/base; `grain_probe.py` tests same-frame,
constant-input neighborhoods over 32 legal seeds without fitting a new model.

Scratch: `/tmp/downloads/codex-work/pantheon-quantization-20261019/`.
Previous evidence archives are immutable. Commands, builds and results are being
retained in scratch for final reconciliation, archival and cleanup.
