# Reconstructed source energy before grain-off fallback

D75 found an untested distinction in the experimental source/model intervals:
copying original pixels into NVENC does not preserve those pixels through lossy
compression. The old D62 mechanism checks proved the requested input, headers,
model association and decoder agreement. They did not qualify the grain energy
of source-preserved output. They must not be read as temporal quality approval.

Independent decoding of six historical 8/10-bit controls finds 64 source rows
with severe grain loss, alongside 32 modeled rows with approximately preserved
energy. The source-to-synthesis boundary can therefore create a large energy
jump despite correct grain headers. D75's comparison against the latest
GPU-qualified diagnostic is still running. This is not evidence of new damage
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
checkpoint. Full encoder build, current reproduction, clean-source positive
controls, ordinary equivalence and GPU rejection checks remain pending.
Production, library files, source protections and reserved footage are unchanged.
