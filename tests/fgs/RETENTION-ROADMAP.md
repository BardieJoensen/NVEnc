# Automatic retention: remaining work and completion criteria

**September 28 current:** [D73 source-bound preserved colour](FINDINGS-2026-09-28-PRESERVED-SCHEDULE.md) passes four modeled/twelve clean-negative GPU encodes and 256 independent decoded observations. [D74 native component evidence](FINDINGS-2026-09-28-COMPONENT-EVIDENCE.md) improves structured luma estimates, but every occupied brightness code still includes unsupported pixels in the two HDR frames; no new whole-picture source rule is admitted. Full CPU: 267 Python / 37 suites plus 53 C++ programs. Next qualify copied-colour full-resolution and source/model transitions, then continue bounded source/runtime work and R3–R8. Tdarr is unpaused; production `cb903a17`, retention/FEL off, reserved footage unopened. Nothing starts automatically. Continue through checkpoints.

**September 27 current:** [D71 textured-colour fitting](FINDINGS-2026-09-27-PRESERVED-CHROMA.md) and [D72 actual source-copy integration](FINDINGS-2026-09-27-PRESERVED-TRANSPORT.md) are qualified. D72 passes eight positive/ten clean-negative encodes, 416 independent decoded observations and unchanged ordinary SDR/HDR output. Latest GPU-qualified diagnostic: `524a98f6`, SHA `35dcffc13b8100e3961455cdcbea7fa862823971ccd102747382d4e41de7a275`. Next bind source-preserved colour to measured automatic selector plans; real source eligibility, bounded runtime and R3–R8 remain open. All owned pauses are released. Production `cb903a17`, retention/FEL off, reserved footage unopened; no automatic experiment. Earlier dated entries are historical.

**September 27 current:** [D67 aligned source-history estimates](FINDINGS-2026-09-27-ALIGNED-POPULATIONS.md) and [D66 moving-detail vetoes](FINDINGS-2026-09-27-MOTION-DETAIL.md) are complete. The new hypothesis improves known controls but admits no real HDR region; the original R1 rules remain unchanged. Full CPU: 259 Python / 36 suites plus 51 C++ programs. Next implement copied chroma in the finite fitter, starting with exact constant colour and explicit compatibility/range proofs. This removes a separate all-partial-only implementation limit; broader source classification and R3–R8 remain open. The dated entries below are historical.

**September 27 checkpoint:** [usage-limit recovery and exact next steps](FINDINGS-2026-09-27-RETENTION-RESUME.md). R1/R2 remain complete; R3–R8 are open. D64's measured evidence pipeline completed four conservative source-preserving replays. Detail/quiet and regional eligibility are still missing, and the numerical fix is local and not deployed. Finish the fitter/library comparison and commit before continuing actual admission/runtime work. Older dated stage entries remain historical.

Updated September 23, 2026: R1/R2 complete; encoder integration `da9ce557`,
independent comparison tool `128796ea`. R3 host selection/coverage and colour
checks and native GPU blending are qualified. Grain-scale units and exact
native brightness lookup now pass independent decoder comparisons; ordinary
output remains identical on SDR/HDR controls. Full R3 integration remains open.
This is the current task list for optional automatic retention. Start at the
[project handoff](WORK-TO-PRODUCTION.md) for deployed builds and operational
constraints; older experiment plans describe their recorded stages.

The [source-preservation and frame-wide follow-up](FINDINGS-2026-09-23-SOURCE-PRESERVATION.md)
qualifies final-model capture and complete native source/base counters after the
host reboot. Diagnostic build `696a7b40` preserves ordinary SDR/HDR outputs;
CUDA header dependencies are now enforced. Exact-source coverage also requires
proof against the decoder range clamp, including active zero-strength curves.
Whole-picture curves remain rejected: individual seed failures and large
unqualified populations are unresolved. A separate ordinary-NVENC seed-cycle
fixture confirms rare one-frame component dropouts; a seed-only IVF experiment
corrects them without changing coded pictures, but is not a production fix.
No experiment is scheduled. R3–R8 remain open; retention and FEL stay off.

The [isolated seed parser and Linux integration](FINDINGS-2026-09-23-SEED-INTEGRATION.md)
now pass the complete seed cycle, SDR/HDR, Matroska/MP4 and failure controls.
`b2a6daeb` is the latest built trial encoder; the new option remains off and is
not deployed. The [native population envelope](FINDINGS-2026-09-23-POPULATION-ENVELOPE.md)
adds a bounded feasibility preflight: all occupied native lookups in the 36
recorded real censuses conflict with unsupported populations. Alternative
lookup/population evidence or explicit source fallback is required before
another partial-patch model can become a whole-picture selection.

The goal is fast, space-efficient AV1 that preserves source detail and the
appearance of grain on both 1080p SDR and UHD HDR. Retention should keep enough
of the removed source residual when synthesis alone cannot reproduce it well.
It must earn its storage and processing cost through measured picture benefit.
Source preservation here describes the input to lossy NVENC compression; it
does not promise a pixel-identical decoded copy of the original.

## Starting point

- [x] Ordinary ripple, temporal-grain and excess-amplitude corrections have
  completed their recorded qualification and rollout. Ordinary `cb903a17` is
  the comparison baseline; its qualification does not qualify new retention.
- [x] Earlier automatic-retention encodes, matched-size comparisons and
  historical full-title cost measurements exist. Reuse valid evidence with
  its exact build and settings; those costs do not predict the new prototype.
- [x] Offline joint colour modelling, exact finite-template controls,
  brightness-aware fitting and independent synthesis-fidelity checks exist.
- [x] A prototype retaining 25% of the removed Cb residual amplitude passes
  eight development source-patch groups using the actual rounded base.
  Independent AOM/dav1d carrier checks cover its serialization and grain state.
- [ ] The new colour prototype has encoder call sites, whole-picture coverage,
  both colour components, an automatic selection policy and moving NVENC output.
- [ ] Its quality, full-title storage cost and speed justify a deployment policy.

The last two boxes remain open. The patch work reused inspected holdouts and
does not constitute blind qualification. The 25% value is an experimental
residual-amplitude fraction, not a file-size allowance or chosen default.
See the [latest findings](FINDINGS-2026-09-22-BRIGHTNESS-FIT.md).

## Ordered backlog

R1 is complete: the [decision and measurement contract](RETENTION-CONTRACT.md)
defines the finite candidate policy and coverage rules. Six reserved excerpts
from three additional titles are packet-identical to their original sources
(1,487,984,476 bytes); their grain results have not been inspected. The local
`roadmap-r1-r2-20260922/r1-completion.json` and `corpus-report.json` contain the
completion and source proofs. R2's [GPU measurement module](FINDINGS-2026-09-22-JOINT-COLLECTION.md)
passes independent synthetic, real-frame and actual encoder lifecycle comparisons.
Sixteen encodes preserve the controls across all 2,432 output frames in both
grain modes; 393 source/history plane comparisons are exact. The explicit
diagnostic remains off by default. R3–R8 remain open. A package closes
only when its deliverable and completion evidence are linked here.

| ID | Work package | Depends on | Completion evidence |
| --- | --- | --- | --- |
| R1 — complete | Define whole-picture eligibility, fallback and a separate qualification corpus | Existing prototype | [Contract](RETENTION-CONTRACT.md), source manifest and reserved packet-copy proofs |
| R2 — complete | Implement trustworthy, bounded GPU source/base measurements | R1 | [Collector and pipeline evidence](FINDINGS-2026-09-22-JOINT-COLLECTION.md), `roadmap-r1-r2-20260922/report.json` |
| R3 | Integrate automatic partial retention and the grain model | R2 | Actual rounded-base model, legal AV1 parameters and explainable bounded decisions |
| R4 | Make frame-to-frame changes stable | R3 | Moving-sequence transition and reference-state regressions pass |
| R5 | Qualify actual NVENC picture quality and file correctness | R3, R4 | Independent unseen-source evaluation, known-bad controls and existing release checks pass |
| R6 | Measure quality against bytes on clips and full titles | R5 | Matched-size comparisons and a complete quality/space/time table |
| R7 | Optimize measured costs without losing qualified behaviour | Useful candidate and timing baseline from R5/R6 | Controlled timing improvement plus output/quality equivalence for the change |
| R8 | Resolve installation policy and qualify a Tdarr canary | R5, R6; R7 if needed to meet the agreed speed budget | Concrete settings, size/failure behaviour, rollback and actual worker acceptance |

### R1 — Whole-picture rules and independent references

- Define how supported brightness ranges in Y, Cb and Cr determine eligibility
  for a legal frame-wide AV1 grain model. Supported flat patches cannot certify
  an entire image. Account for quiet areas, texture, edges, saturated colour,
  near-black regions and brightness ranges with little source evidence.
- Define source-preserving behaviour when the model cannot represent a region
  or component. AV1 grain parameters are not an arbitrary spatial mask. A local
  retention design must also prevent decoder grain from being added again to
  fully retained content. Keep whole-component/frame fallback available where
  a safe local result cannot be represented.
- Specify the automatic selector's objective and bounded search: try eligible
  retention levels, retain enough source residual to satisfy the quality checks,
  and fall back if none qualifies. A smaller retained amplitude is not yet proof
  of fewer bytes; R6 measures the actual cost.
- Separate development footage from qualification footage before more tuning.
  Inventory the retained corpus and earlier campaign first, verify provenance,
  and add missing coverage. Include SDR, HDR, animation, weak/strong grain,
  both colour components and real luma/colour coupling. Reserve unseen titles
  or scenes and temporal context; new seeds on familiar patches are insufficient.
- Pin comparisons, metrics, exploratory model bounds and failure rules in a
  finite manifest. The current 8% variance/0.08 normalized-covariance bounds
  measure a specific model property; they are not universal visibility limits.
  Keep source-detail, artifact, temporal and decoded-output checks independent.

**Done when:** a reviewed decision table accounts for supported, unsupported,
quiet and textured input, and a pinned corpus separates development from
qualification. Missing real coverage is recorded as a scope restriction.

### R2 — Reliable measurements in the encoder

- Collect joint source/base statistics efficiently for both colour components,
  brightness ranges and their relationship to luma. Carry valid previous colour
  with an explicit initialization/reset/lifetime contract. The current cached
  previous-source chroma is not valid evidence: that cache copies luma only.
- Measure the actual native-depth rounded retained base, or qualify an equivalent
  method. Do not use the unrounded linear-blend covariance as a substitute for
  weak grain, and do not apply the retention fraction twice.
- Match GPU layout, subsampling, coordinates, rounding and current/previous
  source identity against independent decoding and a CPU reference. Exercise
  source-support rejection as well as accepted cases.
- Bound memory, host transfers, candidate evaluations and worst-case analysis
  work. Keep expensive reference synthesis offline. Record baseline timings
  during implementation, before attempting speed tuning.
- Keep ordinary mode unchanged and exclude unused optional analysis from its
  hot path. Compare decoded pictures and grain decisions to the pinned baseline.

**Done when:** collected moments and source identities match the independent
reference within predeclared arithmetic bounds, invalid history fails safely,
and the optional-off control preserves ordinary behaviour.

### R3 — Automatic selection and complete model integration

The [source-bound selector plan](FINDINGS-2026-09-24-SELECTOR-PLAN.md) completes
D63. The bounded R1 selector now drives a finite pre-encode schedule with exact
original-source hashes and explicit mixture/epoch/short-interval preservation.
Actual SDR/HDR missing-evidence fallbacks and independent output comparisons
pass. Accepted mechanism fixtures do not establish measured real-source
eligibility. Next derive and bind source/base/model candidate proofs, then
complete R4–R8. Production is unchanged and reserved footage remains unopened.

The [explicit source/model intervals](FINDINGS-2026-09-23-SOURCE-SEGMENTS.md)
complete D62. Both transition directions and all-source outputs pass on native
8/10-bit controls, with separate fitters, explicit grain-off models and strict
identity checks. Ordinary controls and older models remain exact. D63 next binds
bounded selector decisions to actual pre-encode plans, conservatively preserving
unsupported mixtures and short intervals. Automatic source/fraction evidence,
complete temporal/quality/bytes/speed qualification and R3–R8 remain open.

The [complete native geometry](FINDINGS-2026-09-23-NATIVE-GEOMETRY.md) completes
D61. Full 1080p/UHD fitting and independent source/reconstruction/decoder checks
pass without cropping. Actual sample counts replace tile-count weighting for
ragged dimensions. Ordinary output and aligned model controls remain exact.
D62 next implements explicit source segments alongside modeled output, followed
by automatic bounded source/fraction decisions. R1 population rules and R3–R8
status are unchanged; this does not admit previously unsupported regions.

The [per-picture candidate path](FINDINGS-2026-09-23-FRAME-FRACTIONS.md)
completes D60. Changing fractions, immutable source/model association and source
transitions pass on both native depths; ordinary SDR/HDR outputs are exact.
Complete non-tile-aligned geometry and 1080p/2160p tests are now qualified in
D61; actual automatic source/fraction evidence remains open. R3–R8
remain open; explicit schedules do not grant source admission.

The [independent temporal selector](FINDINGS-2026-09-23-INDEPENDENT-WINDOW.md)
completes D59: both constructed depths pass, four earlier partial candidates
reject late on their independent mean, and all actual GPU/decoder outcomes
match. This removes selection leakage without hiding full-spatial failures.
Next: ordinal-bound changing fractions, then bounded automatic source/fraction
evidence and R4–R8. The reference fitter remains a finite diagnostic.

The [independent-mean and fraction follow-up](FINDINGS-2026-09-23-INDEPENDENT-MEANS.md)
completes D57/D58. Native means and all attempted decisions agree independently;
actual strict 8-bit output passes. Constructed 10-bit remains rejected across
four additional fractions, with exact source fallback. Apply separate means to
the calibrated frame/window policy, then continue automatic source/fraction
integration. This is a diagnostic gate improvement, not R3 completion.

The [strict full-picture policy](FINDINGS-2026-09-23-STRICT-POLICY.md) completes
D56. Original spatial bounds now independently veto each picture, with unchanged
legacy output. Known 8-bit actual NVENC output passes; the 10-bit counterpart
rejects a Cr mean shift. Continue independent training/check mean evidence and
bounded fraction/source integration. No real-source admission or R3 completion
follows from the constructed controls.

The [actual pre-encode/model connection](FINDINGS-2026-09-23-PREENCODE-MODELS.md)
completes D55. Native source, rounding, reconstruction, complete model output and
source-preservation vetoes qualify together in `e4b96c4b`. Eleven positive/six
negative GPU encodes pass, with 64 exact model outputs and independent oracle
pictures. Original full-spatial per-picture failures remain explicit; bounded
automatic fractions, source/detail eligibility and R3–R8 are still open.

The [pre-encode candidate path](FINDINGS-2026-09-23-PREENCODE-RETENTION.md)
completes D54. Eighteen positive/nine negative GPU encodes and independent
native rounding/source/reconstruction checks pass; ordinary SDR/HDR is unchanged.
`5adc0f3e` is qualified for finite bilateral candidate measurements. D55 connects
those actual bases to complete model output, with source-preservation vetoes;
bounded automatic fractions, source eligibility and R3–R8 remain open.

The [direct-source connection](FINDINGS-2026-09-23-SOURCE-TRANSPORT.md)
completes D53: originals are carried through the pipeline into live model fitting.
Native 8/10-bit output, source identity/lifetime, complete decoder/oracle checks
and explicit rejection controls pass. Ordinary SDR/HDR output is unchanged.
The declared frame/window policy passes independently; original per-picture
full-spatial failures remain recorded. Next: automatic pre-encode fractions,
eligibility and source-preserving fallback. Full CPU: 214 Python / 45 C++.

The [live native fitting connection](FINDINGS-2026-09-23-LIVE-FITTING.md)
completes D52: actual NVENC reconstructions produce all 32 reference models
and identical AV1 packets. Ten positive/six negative GPU runs, 2,432 fresh
independent decoded observations and 101 exact captures pass. Full CPU:
214 Python / 44 C++. Original source planes and retained fractions remain
explicit. Continue direct original-source transport and automatic pre-encode
selection/fallback; source eligibility and R3–R8 remain open.

The [direct fitting and finite engine](FINDINGS-2026-09-23-NATIVE-ENGINE.md)
complete D50/D51: original native source and reconstructed base now produce
the frozen shape, strengths, selected seed and actual AV1 output in one process.
Both 16-picture outputs match the independently qualified reference bytes.
The engine remains a diagnostic with supplied source eligibility and pre-encode
fractions. Next is its finite live reconstruction connection, followed by the
remaining automatic source/fraction policy. Full CPU: 214 Python / 43 C++.

The [native measurement and selection implementation](FINDINGS-2026-09-23-NATIVE-SELECTION.md)
completes D48/D49. Complete spatial/cross-component moments match independent
NumPy; bounded in-process seed selection preserves all 32 choices and 42
candidate pictures. All 18 sliding windows and 128 known-negative comparisons
match the recorded policy. Independent-fold selection, isolated dropout,
invalid/quiet evidence and sequence/tail rejection have explicit regressions.
Source/base shape fitting and actual automatic selection/integration are next.
This diagnostic policy does not grant new source/population admission.

The [in-process calibration](FINDINGS-2026-09-23-INPROCESS-SELECTION.md)
completes D47. Batched strength search preserves all 126 recorded component
decisions and 42 independently synthesized final pictures, with a lower measured
calibration cost. Full spatial/cross-component checks, bounded seed selection
and live model fitting still need to join the runtime path. The current adapter
does not approve a source or complete R3. Full CPU: 214 Python / 40 C++.

The [continuous output and bounded integration](FINDINGS-2026-09-23-CONTINUOUS-OUTPUT.md)
completes D42's changing-picture trial and D45's CPU FIFO work. All32 selected
pictures match actual AV1 output in independent decoders. Recorded NVENC receive
order now validates the reconstruction association; the FIFO also waits for
model readiness. D46 qualifies the finite precomputed-model encoder hook on11
positive and7negative runs:2,496 fresh decoded observations and117 exact native
captures. Automatic selection and new real population admission remain open. Continue bounded in-process model selection and then
R3–R8; the diagnostic pause is released and nothing restarts automatically.

The [10-bit and metric calibration follow-up](FINDINGS-2026-09-23-GRAIN-METRICS.md)
completes D39–D41. Three constructive proposals now pass the original checks and
serialize exactly. Independent same-model grain draws also expose a limitation
of the per-picture colour score: all 128 fail the combined exploratory bounds,
while pooled comparisons pass. Isolated dropout/excess negatives show why a
pooled-only guard is unsafe. D42 tests frozen-shape continuous output with bounded
seed choices and separate individual-picture protections. This is an explicit
measurement-policy investigation, not a silent relaxation of R1, approval of
unsupported populations, or completion of automatic integration.

The [compressed-base and reconstruction follow-up](FINDINGS-2026-09-23-RECONSTRUCTION.md) qualifies direct NVENC reconstructed-frame capture on `d0ad6818`: 75,970,560 exact native samples, 1,600 independent decoded observations and six failure controls. D32 refits against the actual compressed base; D34 calibrates total variance per seed. Neither complete colour policy passes both spatial halves on any tested seed. Spatial colour shape/cross-component correlation remain unresolved. Continue bounded finite-template correction and actual selection; this prerequisite does not complete R3. Production retention/FEL remain off and the reserved corpus stays unopened.

The [source-luma policy and actual output trials](FINDINGS-2026-09-23-SOURCE-LUMA.md) now exercise complete colour-only decisions, copied-component range proofs and actual NVENC table output. Two constructive controls pass pre-compression checks; five negative controls preserve the source. Fourteen encodes pass 896 independent decoded observations, but compression removes retained grain that the pre-encode model expected to survive. The later D32/D34 work below measures that missing-energy error using the actual decoded base. Automatic call sites and compressed-output quality remain open. Full CPU: 214 Python tests in 30 suites and 35 C++ programs. Continue the roadmap without treating this checkpoint as completion.

The [complete retained-model constructors](FINDINGS-2026-09-23-RETAINED-MODEL.md) fit native Y and both colour components from actual rounded bases, bind exact finite luma evidence and calibrate integer strength with bounded measured callbacks. Independent solves match 1,992 coefficients. Complete coupled-colour candidates still fail source fidelity; the source-luma policy is a separate explicit revision, not an implicit retry or relaxation of those failures.

The [native persistent-detail work](FINDINGS-2026-09-23-PERSISTENT-DETAIL.md) adds complete development-frame measurements and a candidate-bound veto. Seven-frame GPU and encoder lifecycle qualification now passes on `04bd03aa`: 321 GPU cases, 7,182 history-plane comparisons and 3,040 encoded control frames. Independent AOM/dav1d evidence covers both grain modes. D27 keeps missing temporal anchors distinct from complete independent candidate evidence without granting new check bits or relaxing R1. Full CPU: 214 Python tests in 30 suites plus 32 C++. Whole-picture model/admission and actual output selection remain open.

The [frozen stationarity controls](FINDINGS-2026-09-23-STATIONARITY-CONTROLS.md)
reject short-history consistency plus small-translation matching as a sufficient
population classifier. Fast zero-grain detail and persistent grain evade the
necessary checks; flat independent grain also exposes false motion conflicts.
All 3,960 real tiles retain their R1 classifications. The CPU reference and
counterexamples are reusable, but no new population acceptance is enabled.
The [disjoint-frame-pair revision](FINDINGS-2026-09-23-MOTION-HOLDOUT.md) removes
the flat-grain false motion conflicts in those development controls. It still
cannot approve fast-motion or persistent-grain populations. Full CPU now passes
208 Python tests in 29 suites and 29 C++ programs; output selection remains off.

The [source-only temporal population study](FINDINGS-2026-09-23-TEMPORAL-POPULATIONS.md)
adds independently checked measurements on structured regions. All 3,960 real
tiles preserve the original source classifications; lag-dependent energy and a
zero-grain moving-pattern negative show that stationary temporal estimates alone
cannot approve these regions. Motion/stationarity and temporal correlation need
separate qualification. No new source-population acceptance rule is enabled.

The [runtime copied-colour guard](FINDINGS-2026-09-23-RUNTIME-RANGE.md) now
protects nominal out-of-range chroma from the active-zero-curve decoder clamp
and excludes unsafe frames from synthesis recovery. The finite NV12/P010
transition/border controls and ordinary-output comparisons pass on `53d3ff3f`.
This closes a prerequisite fallback defect; it does not integrate the new
partial-retention selector. The [separate level-signalling investigation](FINDINGS-2026-09-23-AV1-LEVELS.md)
now reproduces outside the fork and adds an optional header-policy regression.
The underlying compatibility issue remains unresolved. Production stays unchanged.

The [first R3 study and hold guard](FINDINGS-2026-09-22-RETENTION-SELECTION.md)
are complete. Eighteen candidate measurements expose insufficient whole-picture
colour coverage; the successful patch fit cannot simply become a frame policy.
Commit `2000f767` prevents model reuse across grain-scale changes and passes the
CPU suite, including an independently measured failing old-model example.
At that first-stage checkpoint, selection and actual new output were still open.

The [second R3 stage](FINDINGS-2026-09-22-RETENTION-SELECTION.md#current-implementation-selector-and-native-base-contract)
now implements the bounded host selector, conservative complete-picture
coverage/fallback gate and common-coordinate colour reconstruction checks.
Seventy-two policy controls, 36 real native coverage replays and the complete
CPU suite pass. The native per-component GPU blend passes its 31-case exact
comparison (141,191,039 valid samples and 434 rejected invalid calls). The
[scale and native-lookup follow-up](FINDINGS-2026-09-22-GRAIN-SCALE.md) corrects
nonzero-scale units, converts finite luma gains explicitly and adds the exact
integer strength lookup. Independent AOM comparisons pass; four SDR/HDR encodes
preserve ordinary decoded pictures, clocks, metadata and grain decisions.
A separate common-colour intersection reducer passes 20 native CPU/GPU controls;
all three real frames still lack a >=16-block brightness/fold/component group.
No job will start automatically. The selection/blend/lookup/common-cohort helpers
still have no encoder output call sites. Remaining complete model/population evidence,
colour gains and actual selection determine whether partial retention is useful.

- Implement the R1 selector behind an explicit experimental option. Cover Y,
  Cb and Cr independently within the permitted shared AV1 model. Define useful
  behaviour for unsupported Cr; do not generalize Cb-only results silently.
- Fit only the missing grain after source retention. Carry integer parameter
  quantization through strength curves, causal/spectral checks and independent
  reconstructed-source checks. Preserve the existing source-support protections.
- Complete grain-scale integration: nominal strength/refit/DC units, native
  blending and exact integer lookup now have independent checks. The prototype
  uses shift one, which requires finite gains for the exact luma/colour model,
  depth and scale plus actual decoded amplitude/mean checks. The linear DC proxy
  and a shift-only rescaling do not supply those checks.
- Match the decoder's chroma strength indexing, native rounding, clipping,
  overlap, quiet-component behaviour and paired chroma syntax. Do not confuse
  the luma samples used for strength lookup with the averaged luma AR driver.
- Log the final selected retention, supported coverage and overlapping fallback
  reasons. Report the final outcome after every guard, not just a successful fit.
  Cap retries and leave diagnostic tracing optional.

**Done when:** real encoder output exercises partial retention and safe fallback,
independent decoding agrees with the signalled model, and deliberately invalid,
unsupported and excessive-grain cases are rejected. This is trial readiness.

### R4 — Temporal behaviour

- Qualify handling of the three degenerate emitted seeds (0, 46372, 18904).
  The manual IVF proof preserves coded pictures across a complete seed cycle;
  private parser/threading, hidden/show-existing cases and finite actual
  encoder/container preservation now pass. A complete SDR animation episode
  adds an ABBA cost comparison: +0.25% mean time within observed run variation,
  identical bytes and 34,626 exact independent decoded observations. HDR/broader
  throughput and release/canary qualification remain open. This requirement is separate
  from the previously repaired apply-grain/reference-state toggles.

- Integrate model reuse, entry to fallback and return to synthesis with the new
  curves and per-component retention. A stale model must not outlive its source
  evidence. A failed safety check takes effect immediately.
- Exercise startup, end of stream, scene cuts, fades, camera/object motion,
  quiet/noisy changes and rapid support changes. Include repeated fallback and
  recovery, asymmetric colour activity and AV1 reference-frame grain reuse.
- Evaluate decoded playback grain, base detail and per-frame decisions together.
  Catch flashes, dropouts, pumping and doubled grain. Account for genuine changes
  already present in the source rather than forcing all grain energy constant.

**Done when:** actual moving NVENC sequences pass the transition controls and
the existing ripple, flicker, texture and amplitude regressions, with their
retained bad examples still failing.

### R5 — Independent compressed-output qualification

- Freeze the candidate before opening the reserved qualification results.
  If those results guide a fix, they become regression/development evidence;
  use another untouched set for the later blind check.
- Decode actual NVENC output with grain on and off. Check whether retained
  source detail survives compression and whether the combined result adds
  excess grain, blur, colour error, ripple, banding or unstable texture.
- Combine source-paired spatial/temporal checks, scene distributions and worst
  examples with playback review. Use VMAF/SSIM-style scores as supporting evidence;
  include appropriate gradient/banding checks and native HDR analysis with
  declared transfer/display assumptions. CAMBI alone cannot certify grain state.
- Complete decode, frame/clock and metadata/nonvideo preservation checks on
  tested outputs. Exercise SDR/HDR and supported input paths; keep FEL excluded.
- Consolidate the new defect checks into reusable offline release tests.
  Extra research analysis is not added to routine Tdarr validation by default.

**Done when:** the frozen candidate meets the predefined picture and file
requirements on the independent corpus, all required controls pass, and any
unsupported content is explicitly excluded or safely preserved.

### R6 — Quality, storage and speed evidence

- Compare ordinary FGS, new automatic retention and plain NVENC at matched
  actual video bytes. Include selected pinned SVT references where they resolve
  a real tradeoff. Reuse earlier verified controls only when settings and
  sources match; old auto measurements do not qualify this new implementation.
- Report both equal-size quality and the bytes needed for comparable quality.
  Show scene-level gains/losses and visible examples, not just mean scores.
- Move to representative complete episodes/films only after short comparisons
  support a useful candidate. Count video bytes, final file bytes, savings versus
  the original, encode/validation time, memory and fallback duration/frequency.
- Predeclare the finite title set and operating points, then expand only to
  resolve a named gap. Timing uses controlled repeats with playback/pause time
  separate. Excerpt behaviour and fallback frequency are not a library estimate.

**Done when:** a comparison table answers what picture benefit retention buys,
its actual GB/percentage cost per tested title, its throughput cost and the
content classes that benefit. No universal storage allowance is assumed.

### R7 — Targeted optimization

Profile the integrated candidate. Prioritize work that dominates measured time:
redundant moments, memory traffic, CPU/GPU synchronization, unnecessary fitting
and safe model reuse. Reuse requires fresh evidence; it must not restore the
previous temporal bugs. Compare output exactly for changes intended to preserve
it; changes to decisions need the affected quality and transition checks again.

**Done when:** the measured overhead meets the chosen throughput budget or a
documented cost makes the feature unsuitable for the intended default. Do not
turn this into an unbounded search for every possible optimization.

### R8 — Predictable Tdarr policy and rollout

- Present a concrete recommendation supported by R6: leave off, enable for
  specific content/settings, or enable more broadly. Agree any additional
  storage allowance using the measured examples. The historical 10% trial cap
  and the 25% residual amplitude are different quantities.
- Define what happens when a file exceeds the chosen allowance or fails quality
  checks. Preserve the original; an oversized trial must not silently install,
  lower quality, or start unlimited alternate encodes. Any ordinary-mode retry
  needs an explicit bounded policy and its own acceptance checks.
- Package the exact qualified build, settings, logging and rollback, then test
  a small explicit Tdarr canary before broader use. Include successful jobs,
  oversized outputs, errors/retries and interrupted work. Recheck ordinary mode.
- Release only redundant study artifacts after dependency review. Preserve the
  required originals, regression witnesses and deployment rollback.

**Done when:** the chosen policy has passed actual worker acceptance, the
deployment recommendation and authorization are recorded, and the installed
scope matches that decision. A decision to leave retention off is a documented
outcome, not a claim that unfinished implementation passed qualification.

## Working method

1. Work through one package at a time, with a small vertical implementation
   covering measurement, selection and decoded output before broad sweeps.
   Keep the next deliverable explicit and continue within existing authorization.
2. Start each experiment with one question, pinned inputs/build/settings, a
   finite job list, acceptance rules and a time/disk budget. Separate tuning
   from validation and preserve failed results. Stop a failed candidate from
   entering the expensive later stages; fix it and rerun affected evidence.
3. Use targeted CPU checks while editing, one complete CPU suite for the coherent
   change, then short GPU tests and the required release checks. Repeat or broaden
   tests when changed code or unresolved evidence warrants it. Long encodes come
   after a useful candidate, not after every edit.
4. Keep heavyweight studies manually started. The user permits pausing/unpausing
   Tdarr when needed: drain active jobs, record the owned pause, preserve Emby's
   separate playback ownership and restore the prior appropriate state. Keep
   large scratch off `/` and clean completed disposable buffers with receipts.
5. After each package, update this checklist with the commit, report, outcome,
   remaining limitation and next action. Use one current roadmap; historical
   reports remain evidence, not competing queues. Commit code and compact public
   findings; keep private media and detailed ledgers outside Git.
6. Routine implementation and testing do not need repeated permission. Bring
   the user concrete quality/space choices when the evidence is ready and any
   unresolved deployment decision actually needs their preference. Continue
   independent work while awaiting that choice.

The immediate deliverable is **R3's bounded automatic selector and complete
model integration**. R2 now passes standalone and actual encoder comparisons,
including ordinary/diagnostic equivalence, complete colour history, startup,
cuts, early fallback, drain and expected failures. Full-title
sweeps, broader encoder research and speculative speed work can wait. This
roadmap creates no scheduled job and changes no Tdarr settings.

## Evidence and resumption

- [Latest model findings](FINDINGS-2026-09-22-BRIGHTNESS-FIT.md): completed
  prototype, failures, independent decoder controls and limitations.
- [Earlier colour/size comparisons](FINDINGS-2026-09-22-COLOUR-RECOVERY.md)
  and [prior campaign inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md):
  reusable measurements and candidate references.
- [Tradeoff tools](../../tools/fgs/RETENTION-TRADEOFFS.md) and
  [test tiers](TIERS.md): existing analysis and release tooling.
- Local evidence root:
  `/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/`.
  `brightness-fit-20260922/report.json` is the completed stage summary;
  `artifact-locations.json` resolves archived paths. Start a new finite ledger
  for new work rather than overwriting completed reports.

**Resume instruction:** Read this roadmap and the project handoff, verify current
repository/runtime state, and continue with the first open ready package. Record
implementation, evidence and next action here. Preserve existing user edits.
