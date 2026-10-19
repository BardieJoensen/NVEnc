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


- auto: Record independent-review nuance: E05q20 transformed-only neighborhoods
  overshoot HF by10.71%; the established whole-ROI screen passes. Quiet-frame
  minus12 meansq15, notq20. Real absolute q acts before mode decision and changes
  search; only private reconstructions hold decisions fixed.

Round5 primary question: can a conventional same-codec re-encode preserve both
E05 shirt and unselected background at about2x original packet rate, without the
manual spatial map? The prior x264 evidence is E04-only, single-pass ABR at1x
(selected10.041Mbps); its unscored overshoot was only1.25x. Use one two-pass
x264slow/tunegrain8bit configuration, E05 first, with original-derived input,
240scored+96preroll, actual-packet calibration, frozen source controls, all ROI
texture/ACF/correlation, GPU metrics/tails/CAMBI and independent decoder equality.
This tests repair feasibility across encoder families, not AV1 causality or a
fundamental codec bound. Short-window two-pass statistics cannot establish
full-episode rate/quality/runtime. No production format change is authorized.


Round4 matched result: actual E04 10.009985Mbps(−0.193%) and E05
9.617045Mbps(−0.615%) meet the original-packet window budgets. Both primary ROIs
still pass. E04 VMAF85.42/SSIMU44.18 versus baseline90.59/61.02; outside MSE
5.926→9.501. E05 VMAF92.88/SSIMU47.75 versus93.57/52.87; outside MSE9.329→10.847,
face MSE6.840→9.537 and gradient error4.067→4.242. Tail regressions are substantial.
Accept this negative result: this manually localized strategy does not preserve
the whole picture at source rate. It does not prove all allocation objectives fail.

- auto: Raise the task's planning estimate from50 to75GB after retained raw real
  reconstructions and score decodes reached59GB; live free space remains~500GB,
  well above120GB floor. This is a scratch estimate, not a user resource limit.
- auto: Independent review required cross-codec packet accounting by sorted
  presentation positions96:336, with timestamp-cadence checks, rather than absolute
  PTS rounding; record the actual2x target and requirewithin1% before decisive
  scoring. This guards container start offsets without changing decoded samples.

Round5 E05 result: at19.252835Mbps(1.990xsource,−0.518%2xtarget), x264 improves
background HF to1.6363 against1.7785, but ACF error0.05154 narrowly fails. Shirt HF
0.4301 against0.6194 fails by30.56%, despite ACF error0.0013. Its source-residual
correlation is only0.189 and temporal HF correlation0.234 versus0.119 source.
Clean/control/face errors improve broadly; quiet HF absolute error0.01835 versus
SVT baseline0.08861, face MSE4.511 versus6.840. This is complementary regional
behavior, not a qualified repair. All336 CPU/NVDEC decoded planes agree exactly.

Round6 conditional discriminator: test x264's variance-based AQ strength1.0
against the grain tune's0.5 at the same2x original packet budget. This is one
allocation intervention, aimed at the still-damaged low-variance shirt and
background, with unchanged preset/tune/two-pass/coding depth. Export actual
H264 luma QP_Y+block deltas from decoder side data for both arms before claiming
allocation happened. Skipped-block QP state is not proof that quantization ran;
this remains a combined allocation/search encode, not a fixed-predictor ablation.
Require all current gates and inspect displaced damage/quiet regions. Do not
change qcomp, psy or deblocking, and do not call the result an AV1 limit.

Round5 E04 result:20.163398Mbps(2.010xsource,+0.522%2xtarget) passes amplitude
(HF1.8366 versus1.8585), but ACF error0.06229 fails. Source-residual correlation
0.6623; VMAF94.56/NEG92.96/SSIMU72.56; CAMBImean1.486/max16.31 needs explicit
artifact inspection. This is another full-window improvement without texture
qualification. No AV1-specific impossibility follows.

Round6 result: actual19.359144Mbps is+0.032% of2xtarget and+0.552% versusAQ0.5.
Both arms have identical keyframes and picture types. All336 decoded planes agree
between CPU/NVDEC. Fully validated QP-state maps cover336x8160unique16x16MBs;
visible-area weighting clips the padded bottom8rows. Shirt midpoint QP state
22.250→20.370; same-frame shirt-minus-outside contrast decreases0.999QP. Face
QP24.028→24.421 while background23.274→23.033; redistribution really occurs.
Shirt HF0.4301→0.5020 but remains18.95%low; ACF error0.04811 passes narrowly.
Background HF1.6458 passes, ACF error0.05067 fails narrowly. Reject qualification
without relaxing0.05. Quiet HF error improves0.01835→0.01508. This supplies an
allocation-response measurement, not proof that all MBs executed quantization.
