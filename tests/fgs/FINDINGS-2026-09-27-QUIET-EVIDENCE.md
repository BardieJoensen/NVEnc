# Native quiet-region and decoder-range evidence

D65 completes the measured quiet/range part of the finite retention candidate
checks. The helper examines small smooth regions independently of whole-picture
grain statistics, so a noisy area cannot hide added grain or source changes in a
quiet area. This does not establish detail preservation or admit new source
populations. R3–R8 remain open; production `cb903a17` is unchanged.

## Implementation and limits

`NVEncFilmGrainQuietEvidence.h` measures complete native Y/Cb/Cr pictures at
8/10-bit, including every partial border. It checks both 8x8 raw-variance regions
and detrended Y64/C32 regions. Fine quiet sigma is at most 0.3 eight-bit code
units; coarse quiet variance is below 0.04. These source-only criteria are fixed
across candidate fractions and reuse existing guard/R1 thresholds. They are
code-domain development criteria, not perceptual HDR thresholds.

Every detected quiet region requires unchanged source in the rounded pre-encode
base, zero synthesis strength, and grain-on decoded pixels identical to the
grain-off reconstruction. Luma is never averaged down to chroma resolution.
Fine variance uses exact integer moments; coarse variance measures squared
residuals directly instead of subtracting nearly equal covariance estimates.

The finite model scope is explicit: constant two-endpoint strength curves,
BT.709/BT.2020 matrix and native 4:2:0. Separate full-model validation remains
required. For nonzero grain, output strictly inside the decoder clamp interval
establishes that final clamping did not occur. Endpoint pixels remain unknown.
An active zero curve additionally requires exact grain-on/off equality and an
in-range reconstruction: zero strength alone does not disable clamping.

The evidence join binds the quiet measurement to the exact source, pristine
base, rounded base, reconstruction, decoded picture, model, fractions, clocks,
pixel-evidence file and native geometry. It can supply only the quiet check;
it cannot grant the separate detail check. Range evidence is attached separately
to the corresponding population cells.

## Validation

- 64 constructed controls agree exactly between scalar C++ and independent
  NumPy. They include quiet islands, gradients, native alternating luma rows,
  weak 10-bit noise, partial borders, zero curves, endpoint ambiguity and clamps.
- One valid adapter baseline passes; all 16 invalid scope/layout/code controls
  reject. The complete CPU suite passes 240 Python tests in 34 suites and
  50 C++ programs.
- 64 fresh dav1d observations of existing finite test outputs match the prior
  source/base/decoded hashes. All 192 component quiet checks and all 192 range
  checks pass, with exact C++/NumPy agreement.
- Four measured 16-frame selector replays still preserve the whole source.
  Detail remains unknown, regional source/reconstruction proofs remain missing,
  and the original strict 10-bit per-frame fidelity failures remain failures.

The measured examples are constructed grain sources. Their quiet checks do not
demonstrate useful partial retention on real footage. No new GPU trial, decoder
policy, production setting or library file changed. Disposable raw measurements
were removed with hash receipts; source and regression evidence remain available.

The private evidence root in [the handoff](WORK-TO-PRODUCTION.md) contains
`roadmap-r3-quiet-range-20260927/plan.json`, `control-report.json`,
`invalid-control-report.json`, `measured-report.json`, `plan-report.json`,
`full-cpu-final.json` and `report.json`. Continue independent detail/regional
source evidence and bounded runtime integration before R4–R8 qualification.
