# Source-bound copied chroma in finite retention plans

September 27, 2026 — D69 finite-schedule mechanism qualification is complete.
R3–R8 remain open. A separate encoder failure-cleanup defect found by D68 is
being fixed in D70 before encoder release. Production stays ordinary
`cb903a17`, retention and FEL off.

The bounded selector can already choose to copy an unsupported colour component,
but its finite schedule previously preserved the entire frame for every such
mixture. The schedule now supports the exact constant-colour case implemented
in [D68](FINDINGS-2026-09-27-CONSTANT-CHROMA.md), through an explicit fixed mask.
Y remains partial. The mask enables a supported case; it never forces a different
selector choice or supplies missing source, candidate or joint evidence.

The reference adapter measures constant colour directly from the complete,
digest-bound native original. Missing, changed, out-of-range or wrong-layout
proof preserves the row before encoding. If a constant code changes inside a
contiguous modeled interval, that whole interval becomes source-preserved.
Source intervals permit independent constants on either side. The existing
eight-frame minimum, epoch boundary and bounded search remain unchanged.

This is a source-only planning proof. The actual pre-encode pixels,
reconstruction and synthesized output still have to pass D68's independent
checks. A successful schedule is not authority to install a media file.

Completed CPU evidence:

- 36 measured native schedule controls, 66 preservation controls, both source
  interval directions and invalid-mask cases; both depths and all three masks.
  The earlier exhaustive 65,536 binary plans and bounded-search controls pass.
- All 25 earlier complete adapter responses are byte-identical, including
  expected failures and the four measured-development plans.
- Nine source-bound constructed mechanism plans select the intended fractions.
  Twenty-eight adapter controls reject invalid inputs or preserve the source;
  changed pixels include the final colour sample and a late-frame boundary.
- The real SDR/HDR missing-evidence examples still preserve the entire source.
  No source admission follows from the labelled mechanism fixtures.
- Replaying all nine plans through the qualified finite fitter preserves every
  one of the earlier 144 models, readiness decisions and complete IVF bytes.
- Full CPU suite: 259 Python tests in 36 suites and 52 C++ programs pass.

The full encoder requires no code change for the generated plan schema. Nine
fresh encodes with the isolated D68 build pass both independent decoders in
both grain modes (576 decoded observations). All 113,246,208 original samples,
actual candidate samples and reconstructed samples agree with their respective
references. Independent synthesis agrees on 94,371,840 samples, 120 modeled
frames and 57 sliding windows; 24 explicit source frames remain grain-off.
The new bound plans preserve the previous models and complete packet bytes.
Tdarr was restored to its previous pause state and current worker limits.
These successful output comparisons do not resolve D70’s separate failure path.

Local evidence is in `roadmap-r3-copied-chroma-schedule-20260927/` under the
evidence root linked by [the current handoff](WORK-TO-PRODUCTION.md). Read
`plan.json`, `plan-report.json`, `preflight-report.json`, `phase2-comparison.json`,
`full-cpu.json` and `report.json`.
Broader real-source classification, nonconstant copied colour and bounded
runtime selection remain open. The reserved qualification corpus is unopened.
