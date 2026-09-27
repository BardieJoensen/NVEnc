# Native moving-detail vetoes

D66 adds a bounded motion/detail guard for experimental retention. It detects
the retained fast-translation counterexample and a separate alternating-line
blind spot without granting source or detail admission. R3–R8 remain open;
production `cb903a17`, retention/FEL settings and routine Tdarr validation are
unchanged.

## What changed

The source-only search uses pairs 0/1 and 2/3 to choose a translation, then
checks that fixed proposal on separate pairs 4/5 and 6/7. Candidate pixels
cannot affect the proposal; validation never searches for a better match.
The complete-picture study uses native Y64/C32 tiles and search radii 32/16.
Insufficient search support and partial borders remain explicit unknowns.

On supported motion, the guard measures actual source-minus-rounded-base change
along the aligned previous source direction over the valid native tile pixels.
It retains the existing 0.5 correlation, 2% projected contrast and 0.125 eight-bit
code RMS/mean limits. These are necessary development checks, not perceptual HDR
guarantees or proof that an arbitrary residual is grain.

The first search smooths its matching reference. A deliberate control showed
that this filter cancels pure alternating lines; it also missed weak native
ten-bit texture. A separately frozen complement matches native pixels directly.
`film_grain_motion_detail_veto` retains conflicts from **either** search. Both
measure detail at full native resolution. The native complement cannot replace
or remove an earlier smoothed/persistent-detail veto.

The candidate-evidence join accepts source/model/geometry-bound detail failures
only. It rejects a claimed positive detail pass from these necessary vetoes.
No-conflict and unmeasured detail remain distinct.

## Evidence

- Each matching mode detects all 192 retained seven-pixel translation controls
  and rejects all 960 deliberately erased moving-detail controls. Across both
  modes, 8,064 component/candidate measurements match independent NumPy.
- Another 96 complete-picture controls cover 31-pixel motion, native rows and
  columns, weak ten-bit texture, acceleration, reversal, rotation, scene changes
  and borders. Exact source copies never acquire a detail conflict. The native
  complement catches the alternating-line and weak ten-bit negatives.
- Both complete HDR development frames cover 12,240 unique native tiles and
  24,883,200 source samples. Each mode has 384 predetermined independent NumPy
  oracle tiles, including the raster endpoints. All agree.
- Smoothed/native searches flag 278/269 tile candidates; their union is 340.
  This adds 333 conflicts beyond the earlier persistent-detail check, for
  909 combined conflicts at the declared Y=0.1/C=0.25 fractions. These are
  pre-compression development candidates, not newly diagnosed library damage.
- The final rebuilt adapter preserves all nine input-plane hashes and complete
  JSON output bytes on 8,076 earlier control/HDR comparisons. Full CPU passes
  250 Python tests in 35 suites and 51 C++ programs.

Independent flat-grain controls produce no detail vetoes. The native complement
does add seven conservative conflicts in negatively correlated-noise controls
and one in an exposure-drift control whose constructed clean detail is retained.
Those results remain recorded; thresholds were not loosened to remove them.
They are potential retention/storage costs, not evidence of visible damage.
Acceleration, rotation, ambiguous motion and unmeasured borders still cannot
receive positive admission from this tool. Persistent grain still needs the
existing persistent-detail guard.

This is an offline CPU diagnostic, with no encoder output call site. The two
complete-frame C++ censuses took about 8.51 seconds for smoothed matching and
4.35 seconds for native matching, including their adapter execution. These
measurements do not establish production throughput or justify adding the
search to routine validation. Source-only work should be reused across fractions
if a later useful runtime policy is qualified.

## Next work and records

The new checks improve rejection of damaging candidates; they do not resolve
whole-picture source classification. Next test whether aligned, independent
source histories can provide useful noise estimates in structured regions,
retaining the known temporal-correlation and motion counterexamples. Freeze any
population-policy revision separately; do not fill missing R1 admission bits
from these vetoes or from whole-frame grain statistics.

The evidence root in [the handoff](WORK-TO-PRODUCTION.md) contains
`roadmap-r3-motion-detail-20260927/`: frozen plans, `legacy-report.json`,
`extended-report.json`, `real-report.json`, their `native-complement/` counterparts,
`union-report.json`, `final-compat-report.json`, `full-cpu-final.json` and
`report.json`. Generated raw copies were retired with hashes; required source
history and regression evidence remain. No GPU work, pause or automatic job
was needed. Reserved qualification footage remains unopened.
