# Pantheon coefficient-retention investigation

Starting state: clean `master` at `031569ae`; coord `pantheon-fix` revision 7.
The quantization report supersedes the supplied `58a113db` starting pointer.
Prior archives are immutable. All new implementation is diagnostic scratch;
production, library, torrent and Tdarr changes remain unauthorized.

## Hypothesis ledger

| Hypothesis | Supporting evidence | Contrary evidence / limits | Unknown | Cheapest discriminator |
|---|---|---|---|---|
| Quantization destroys useful residual texture | Fixed-decision unquantized inverse nearly matches source; lower actual FP q restores amplitude/ACF | Bypassed blocks and earlier64x64 support loss remain separate; no isolated global search optimum | Minimum whole-picture preservation cost | Current independent conventional HEVC2x control |
| Coefficient pruning alone explains loss | Same initial FP retention improves both fixtures; validated local coder deltas measure added cost | E05 q32 retention still fails amplitude and ACF; regular-B at sameq is worse | Whether a different RD objective preserves efficiently | Do not repeat pruning-only q32; real q20 retention already tested |
| Local precision allocation can repair at source budget | Real q20/q24 target blocks are realized; selected textures pass within1% source rate | E04/E05 outside detail, face and metric tails regress; E05 unselected background fails | Automatic objective/classifier with better whole-picture tradeoff | New allocation needs a specific objective, not another manual ROI sweep |
| More thorough native analysis improves preservation | x264 subme11 improves broad controls/background at2x | Shirt amplitude fails; QP-RD changes quantizers and first-pass analysis | Rate-by-analysis interaction | Matched3x subme8 is missing factorial cell if mechanism isolation is needed |
| Conventional grain-oriented coding can preserve affordably | x2643x passes shirt amplitude/background and improves line/detail/banding | Shirt ACF0.05736 fails; x264 AQ2 harms face/edges | Independent x26510bit grain policy feasibility at2x | R10: exact-source two-pass x265 slow/grain, fixed controls and packet target |
| Legal grain synthesis can replace lost texture safely | Prior reconstruction-aware model restores some E05 amplitude | Established same-input quiet/textured conflict and E04 structure loss on tested base | Other bases/legal parameter sets | No repeated estimator fitting on unchanged failed base |

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

Round7 primary question: does a stronger *realized* flat-region allocation close
the E05 preservation gap without displaced harm at the same2x budget? Increase
only AQ strength1→2. The measured0.5→1 response lowered shirt QP by1.88; a linear
planning extrapolation predicts~16.6 at2 (not a promised intervention). This is
one bounded dose-response extension, motivated by insufficient actual precision,
not an unrestricted settings sweep. Verify actual QP and framewise relative
allocation again. Keep the original10%HF/.05ACF screens and all quiet, edge,
banding, tail and temporal checks. A stronger allocation that damages other
regions is a valid failure, not a reason to weaken the gate.

Round7 result:19.340294Mbps(−0.066%2xtarget) closes the shirt amplitude gap
(HF0.5820 versus0.6194) but ACF error0.07887 fails; background narrowly passes
both. Picture-wide cost grows:VMAF90.78/NEG88.64/SSIMU63.49 versus AQ1
94.94/93.07/67.34. More amplitude is not equivalent to recovered texture. Do not
increase AQ again after this displaced-damage and structure failure.

Round8 primary question: can more thorough analysis improve this frontier
without increasing AQ strength? Keep x264slow/grain/AQ1 at
2x actual packet rate and change only subme8→11 (pass2 log must confirm11 and
requiredtrellis2/AQ1 prerequisites). Compare with AQ1/subme8 at the samepacket
budget, frozen controls and decoder/geometry gates. This is a native search-
refinement contrast, not a fixed-predictor quantization ablation. Its runtime
cost is part of the result; no other preset/psy/qcomp/deblocking parameter changes.

Round8 result:19.368337Mbps(+0.079%2xtarget,+0.0475% versusAQ1/subme8),
58.649s two-pass versus32.856s. Background now passes both screens; shirt HF
0.5212 versus0.6194 is still15.84%low, ACF error0.04788 passes. Full scores improve
modestly, not enough for a repair. Independent source review clarifies subme11
adds QP-RD/deblock-aware RDO/mode refinement and disables early termination;
explicitsubme also changes fast-first-pass analysis. This is a two-pass analysis-
depth contrast, not pure prediction precision or fixed quantization. Independent
review corrected the original "without further spatial reallocation" wording:
QP-RD can change MB quantizers even with AQ strength held fixed. The exported
R8 QP map exists, but no regional fixed-allocation claim is made.

Round9 primary question: does relaxing total rate, while keeping the balanced
AQ1/subme11 configuration fixed, close the remaining fidelity gap without the
severe AQ2 edge displacement? One3x-source rate bracket is justified by R8's
background preservation and insufficient shirt amplitude. It tests preservation
cost, not matched-rate superiority or accepted practicality. All screens stay
fixed; actual3xpackets must matchwithin1%. A passing3x sample would still require
held-out checks, human playback and an explicit practicality judgment;3x is not
silently accepted as a practical production budget. Do not re-escalate AQ.

Round9 result: calibrated29.013766Mbps(−0.0544%3xtarget),74.287s two-pass.
Shirt HF0.58686 versus0.61935 (−5.25%) now passes, but ACF−0.17039 versus−0.22775
(error0.05736) fails. Background jointly passes (HF+0.22%, ACFerror0.02097).
Shirt source correlation improves0.267→0.434; amplitude and covariance do not
improve monotonically together. Whole-tile MSE4.531→2.626, face5.366→3.161,
VMAF95.16→96.85 and SSIMU67.63→76.70 improve. Quiet HF error improves slightly,
quiet ACF error0.07825→0.08253 worsens. Accept the failed unchanged screen rather
than rounding0.05736 to0.05. All336 CPU/NVDEC planes and QP export grids validate.
Native shirt/background stills inspected; no motion playback claim.

Round10 primary question: can an independent conventional encoder decision stack
preserve the E05 whole picture at2x source rate? No HEVC/x265 arm appears in the
prior Pantheon evidence inventory. Test one x2653.5 slow/grain native10bit
two-pass configuration, request19353kbps then packet calibration if necessary.
Use exact lifted original samples, same336 input/240 scored positions, bounded
pool4/frame-threads2 and CPU affinity0-7. Require logged effective tune/options,
both passes and stats reuse, exact all336 CPU/NVDEC Main10 planes, packetwithin1%,
and unchanged texture/controls/full GPU/tails/banding/temporal screens. No GPU
concurrency. This changes codec, coding precision, filters, RC and search together;
it is a feasibility test, not an isolated codec-superiority or bit-depth claim.
Originals are8bit and the x2648bit input also lifts exactly to the10bit fixture:
there was no input-sample loss to "repair" by changing input conversion.

Round10 result: calibrated19.258751Mbps(−0.4872%2xtarget),219.569s two-pass.
Background passes (HF+0.0048%, ACFerror0.02701), but shirt HF−39.66% and ACF
error0.19511 both fail. VMAF96.30/NEG94.38 coexist with SSIMU62.82/p555.08 and
Butter1.502; no single score establishes fidelity. All336 CPU/NVDEC Main10
frames/planes agree exactly. Accept this configuration's failure, not a HEVC
limit. The grain tune disabled AQ/cutree; no HEVC block-QP allocation claim is made.

Round11 primary question: is the x264 shirt ACF failure at3x attributable to a
rate-by-analysis interaction rather than rate alone? Fill the missing AQ1/subme8
at3x cell, same slow/grain/input/twopass/actualpacket criteria. Initial request
28322kbps uses the R9 calibration, then independently audit actualpackets. Compare
all four2x/3x andsubme8/11 cells. Both analysis passes can change, and no fixed-QP
or fixed-predictor mechanism is claimed. No further HEVC settings are selected.
