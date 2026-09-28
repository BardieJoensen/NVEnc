# Source-bound selection of preserved textured colour

D73 extends the finite selector adapter to the source-copy mechanism qualified
in D72. CPU checks pass; fresh encoder and decoder qualification is pending.
This is not real-source admission, R3 completion or deployment.

The explicit `pre_encode_preserved_chroma` option enables Cb, Cr or both. The
bounded selector must independently choose exactly those components for source
preservation. It cannot use the option to skip a candidate/joint veto or supply
missing evidence. Constant and textured-copy modes remain mutually exclusive.

After checking the original source digest, clock and geometry, the adapter
measures every visible requested colour sample. It records native minimum,
maximum and count, including borders and excluding padding. The schedule
requires complete matching geometry/depth, counts and AV1-safe colour range.
Missing or invalid source proof preserves the row with reason 64. Legal colour
changes over time are permitted. Existing epoch, eight-frame minimum, whole-source
fallback, candidate limits and source/detail rules remain unchanged.

This measurement proves only source range. Actual pre-encode source equality,
reconstructed range, complete spatial/joint fidelity and independent temporal
checks remain mandatory downstream. Forging a proof object in the adapter input
does not replace reading and measuring the bound original pixels.

CPU qualification passes 90 native schedule controls, all 65,536 prior binary
schedules and the existing constant-copy suite. Native range/equality checks
cover both depths, padded/ragged layouts, 1080p/UHD and 1,328 invalid cases.
The full suite passes 259 Python tests in 36 suites plus 53 C++ programs.
Sixty-four previous complete adapter responses remain byte-identical. Eight
textured plans, 42 rejection/preservation controls, eight transition controls
and two real missing-evidence fallbacks pass. Independent NumPy reads verify
204,578,816 source range samples. Accepted selection fixtures are explicitly
labelled unit evidence; measured range does not make their luma eligibility real.

Local evidence: `roadmap-r3-preserved-schedule-20260927/` under the handoff's
root, including `plan.json`, `adapter-build.json`, `full-cpu.json`,
`plan-report.json` and `preflight-report.json`. The stage spans September 27–28.
The live encoder is reused at qualified `524a98f6`: the new descriptor has no
live call site, and the old range/equality function bodies are unchanged.
No new GPU build, production configuration or reserved footage is implied.
