# Pantheon coefficient-retention investigation

Starting state: clean `master` at `031569ae`; coord `pantheon-fix` revision 7.
The quantization report supersedes the supplied `58a113db` starting pointer.
Prior archives are immutable. All new implementation is diagnostic scratch;
production, library, torrent and Tdarr changes remain unauthorized.

## Hypothesis ledger

| Hypothesis | Supporting evidence | Contrary evidence / limits | Unknown | Cheapest discriminator |
|---|---|---|---|---|
| Effective quantization destroys meaningful residual texture | Exact final-TU traces; lower realized qindex recovers both fixtures | Quantization alone does not repair E05 selected 64x64 transforms; q16 preservation is very expensive | Minimum preservation cost with better coefficient decisions | Intermediate-qindex coefficient-retention experiment with exercised <=32 transforms |
| Full optimize_b discards perceptually useful coefficients more aggressively than their coded cost warrants | Initial-to-final reconstruction loses texture at identical predictors/TUs | Initial HF alone need not be source-correlated; more coefficients can be expensive or noisy | Fidelity gain and entropy cost of retaining those exact coefficients | Same initial FP quantization and fixed coding decisions; compare retained and pruned coefficients with cloned entropy state |
| Transform/search choices limit preservation separately from quantization | E05 actual 64x64 support truncation; supported TX32 improves q16 result | A TX32 cap changes search/partitions; no isolated search optimum shown | Whether intermediate qindex plus TX32 has a useful retention frontier | Hold exercised <=32 TUs fixed for diagnostic, label skipped/hypothetical TUs separately |
| Source-budget texture allocation can preserve the full picture | E05 target patch passes at +0.175% video rate | E05 face/tails/outside regress; E04 +5.68% still severely damages outside | A feasible automatic allocation or distortion objective | Only after a preservation benefit, real unconstrained encode, then measured within-1% budget test with full-window controls |
| A legal frame-wide grain model can replace all missing texture safely | Prior reconstruction-aware model improves E05 shirt amplitude | Same-frame equal-input quiet/textured neighborhoods have conflicting expected amplitudes; E04 structure remains lost | Feasibility on other bases, intervals and legal parameter sets | Do not repeat estimator fitting on the same failed base; retain established local bounds |

## Round 1 contract and acceptance

Primary question: at intermediate realized qindex near 32 and exercised transforms
no larger than 32, does retaining coefficients removed by full optimize_b improve
texture at a measured, plausibly useful entropy cost?

The worker owns fresh `pantheon-rd-20261019/worker` scratch. The parent owns this
report and Git index. The independent reviewer is read-only. No recursion.
CPU build limit six jobs, encoder LP1 and CPUs 0–7; GPU metrics serialized.
Initial storage budget 50 GB, with over 550 GB free and the 120 GB disk floor intact.

Required controls: unchanged initial quantizer algorithm, predictor, exercised
partition/transform and effective qindex; explicit skip/bypass coverage; texture,
quiet and edge controls; same entropy state for alternatives; tracing-disabled
baseline byte identity; source/input and private/final inverse agreement.
Entropy state or terminated-byte deltas must be distinguished from packet bytes,
whole-stream cost, coefficient proxies and RD estimates. Counterfactual pictures
are diagnostics, not independently decodable repair candidates.

Preservation screens remain amplitude within 10% of original and ACF1 absolute
error <=0.05, paired with source correlation, structure and control errors. They
are provisional numerical screens. A real candidate additionally requires GPU
campaign scores/tails, line/detail and banding checks, full-window temporal
evidence, actual packet rates, bounded runtime evidence, independent review and
human playback. No new numerical gate or practical bitrate ceiling is invented.

## Decisions

- auto: Reuse the completed quantization/representability investigation; the new question is coefficient retention efficiency, not whether lower actual quantization helps.
- auto: Keep the same FP initial quantizer for the retention contrast; the earlier regular-B diagnostic changed two variables and cannot isolate optimize_b.
- auto: Measure local entropy cost before spending on a new rate-control strategy; a local gain is insufficient to claim a practical stream.
- auto: Do not fit another grain estimator to the unchanged base after the documented quiet-region failure.
- auto: Freeze complete source-only control grids before viewing new encoded results. Neither diagnostic frame has a quiet tile under the existing definition; add the earliest previously sampled qualifying frame (E04 88, 23 quiet tiles; E05 24, 20 quiet tiles), without changing thresholds.
- auto: Exclude whole-block skip revival from TU-only entropy accounting. Preserve pre-reset exercised transform type for any zero-EOB TU revival inside a coded block.

## Round 1 observation and next discriminator

On the E05 frame120 CQP8/TX32 control, effective qindex is exactly32. The private
initial-FP reconstruction raises shirt HF0.2587→0.5031 against0.6063 source, but
ACF1 changes +0.1761→−0.0940 against−0.2224 source. Both unchanged screens fail.
These are single-frame, fixed-predictor diagnostics; entropy evidence is still
under independent review. This falsifies pruning-only sufficiency at this qindex.

Round2 primary question: does the initial FP quantizer itself, rather than just
its subsequent pruning, account for the remaining E05 loss? The existing exports
already contain regular-B quantization at the SAME effective qindex and
unquantized inverse under the SAME exercised transform. Compare those private
reconstructions on quantizer-run neighborhoods, keep bypassed pixels unchanged,
and retain both amplitude and ACF/source-correlation tests. Changing FP to B is
explicitly an algorithm contrast, not another pruning-only intervention. No real
encode is authorized by a single-frame diagnostic improvement alone.

Round2 result: regular-B q32 is worse for the E05 shirt (quantizer-run HF0.3306,
ACF+0.0038 versus source0.6178/−0.2268). The unquantized inverse of those same
exercised <=32 transforms is close (HF0.6215, ACF−0.2294, source correlation0.9936).
Thus this is quantizer loss, not a remaining transform-support floor in these TUs.

Round3 primary question: can an intermediate FP quantizer at q24 preserve the
same actual residual more cheaply than the established q16 preservation arm?
Export private FP at current q32 (identity control), q24, and q16 with the same
predictor, partition, transform, qmatrix and no pruning. q16 is the prior supported
preservation endpoint, not a settings sweep. Keep bypassed pixels unchanged and
test the same target/control screens. A passing q24 diagnostic would justify a
real q24+FP-retention arm before any new source-budget redistribution.


Round3 result: same-predictor FP q24 passes E04 but misses E05 ACF by0.0058
(HF0.5816/ACF−0.1666 versus0.6063/−0.2224). The single midpoint bisection q20
passes E05 (0.6117/−0.2014); q16 is the previously supported endpoint. Current-q
private FP exactly equals the exported initial FP coefficients, dequantized
coefficients, EOB and reconstruction. Both complete streams/reconstructions stay
byte-identical to their q32 controls. These remain counterfactual diagnostics.

Round4 primary question: does that local preservation survive a real legal
stream, and what happens when its packet budget is reduced? The combined strategy
uses absolute selected-SB q24(E04)/q20(E05), global TX32 and final-encode FP
retention. Mode decisions remain normal; no isolated pruning-only causal claim.
The first requests are2x original rates. Every selected final block over240frames
must realize its q, and retained coefficient/dequant hashes plus EOB must match.

Round4 first result: E04 actual23.81770Mbps (2.375x original) and E05 actual
18.15288Mbps (1.876x) both pass the five-frame primary-ROI screens. E04 HF1.9042/
ACF−0.1860 versus1.8585/−0.1842; E05 shirt0.6077/−0.1812 versus0.6194/−0.2278.
E05 background still fails (HF0.8984 versus1.7785; ACF−0.0036 versus−0.1924).
These are target-preservation results, not whole-picture repairs. All240 decoded
planes equal application reconstruction exactly. Full GPU scores, tails, CAMBI,
source-defined whole-window controls and temporal traces are retained.

- auto: Test the new local strategy once at the original window budget, because
  lower-cost q20/q24 retention could reduce prior q16 collateral damage. This does
  not assume that unchanged background loss will be repaired. Initial requests
 10316/8447kbps derive from measured high-rate response; actual packets decide match.
- auto: Correct entropy unit wording to bits(tell_frac/8;1/8-bit precision), and
  replace unknown-record fseek with checked reads after independent review found
  an accepted truncation class. The new negative test rejects that class; complete
  measured TU exports were independently validated, so previous numeric results
  are unchanged. Parser-only hardening is not represented as an encode intervention.
