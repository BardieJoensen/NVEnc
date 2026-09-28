# Reconstructed source energy before grain-off fallback

D75 found an untested distinction in the experimental source/model intervals:
copying original pixels into NVENC does not preserve those pixels through lossy
compression. The old D62 mechanism checks proved the requested input, headers,
model association and decoder agreement. They did not qualify the grain energy
of source-preserved output. They must not be read as temporal quality approval.

Independent decoding of six historical 8/10-bit controls finds 64 source rows
with severe grain loss, alongside 32 modeled rows with approximately preserved
energy. The source-to-synthesis boundary can therefore create a large energy
jump despite correct grain headers. [D75's current comparison](FINDINGS-2026-09-28-PRESERVED-TRANSITIONS.md)
reproduces the loss on the latest GPU-qualified diagnostic at both depths and
full 1080p/UHD geometry. This is not evidence of new damage
in deployed ordinary `cb903a17`, which has automatic retention disabled.

D76 adds a mandatory necessary veto to the finite native source-segment path.
Every explicit whole-source row compares the original against the actual
post-NVENC reconstruction before its grain-off model can become ready. Native
luma, averaged luma and both colour variances must stay within the existing 8%
bound in both disjoint spatial halves. Whole-frame and half means must stay
within 0.125 in eight-bit units. Numerically zero source energy must remain
zero; there is no invented denominator or noise floor. All visible mean samples
include borders and exclude padding. Native integer differences are summed
before normalization to avoid cancellation at the acceptance boundary.

A failure is terminal, reports the original/actual measurements and leaves the
rejected model unpublished. The helper has no ordinary-mode call site. It does
not lower QVBR, fabricate grain or retry with a larger file. Complete-file
installation/fallback policy remains R8; a failed trial cannot replace a source.

This is an energy/mean veto, not source classification or complete detail,
covariance, local-artifact, perceptual or temporal qualification. Structured
texture can conceal a local loss in aggregate moments. R3–R8 remain open.

CPU qualification passes 14 native positives and 116 loss/mean/quiet/layout
negatives, including padded/ragged, 1080p/UHD and both depths. Six sequence
failures at ordinals 0, 8 and 15 verify terminal state and unpublished models.
The full suite passes 267 Python tests in 37 suites plus 54 C++ programs.
Independent NumPy measurements agree across 150,994,944 source/output samples:
all 64 historical source rows reject and all 32 modeled rows pass. Six complete
native API replays reject before accepting output; four model-only responses,
64 models and complete IVF bytes remain exact. The initial test's rounded-mean
subtraction error and correction are retained in the evidence.

Local evidence: `roadmap-r3-preserved-transitions-20260928/` and
`roadmap-r3-source-energy-20260928/` under the handoff root. D76's `plan.json`,
`full-cpu.json`, `independent-report.json` and `replay-report.json` pin this CPU
checkpoint. The full Linux encoder is built at `296068e8`, SHA
`4005998b910b5713150c34b7d67922b845e87a403138518c3c0a8ad35cf13b0c`.
Current reproduction is complete; actual GPU rejection/positive controls and
ordinary equivalence are pending.

Actual captured-base preflight adds two exactly preserved full-resolution quiet
sources and one 10-bit modeled-to-quiet transition as positives. An 8-bit quiet
transition rejects because 20 of 524,288 luma pixels differ by one native code;
this is a strictness limitation of exact-zero acceptance, not established visible
damage. Both quiet-to-modeled controls encounter the existing ordinary recovery
hold, which the explicit native candidate must respect. These three failed
positive expectations are retained and separately explained. Bounds, model
search and the encoder are unchanged; they are not disguised as grain-loss
defects or replaced with easier successful transitions. All eight D75 source
plans now reject, and four earlier model-only responses remain exact.
Production, library files, source protections and reserved footage are unchanged.
