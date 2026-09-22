# Automatic retention: remaining work and completion criteria

Updated September 22, 2026: R1/R2 complete; encoder integration `da9ce557`,
independent comparison tool `128796ea`. R3 host selection/coverage and colour
checks are implemented and CPU-qualified; its native GPU blend is compiled but
awaits the explicit playback-free trial. Full R3 integration remains open.
This is the current task list for optional automatic retention. Start at the
[project handoff](WORK-TO-PRODUCTION.md) for deployed builds and operational
constraints; older experiment plans describe their recorded stages.

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
CPU suite pass. The native per-component GPU blend compiles; its 31-case exact
comparison is prepared but unrun while Emby playback owns the pause. No job
will start automatically. These helpers have no encoder output call sites.
The remaining model/population evidence, consistent gains and actual encoder
selection still determine whether partial retention can be useful.

- Implement the R1 selector behind an explicit experimental option. Cover Y,
  Cb and Cr independently within the permitted shared AV1 model. Define useful
  behaviour for unsupported Cr; do not generalize Cb-only results silently.
- Fit only the missing grain after source retention. Carry integer parameter
  quantization through strength curves, causal/spectral checks and independent
  reconstructed-source checks. Preserve the existing source-support protections.
- Make grain scale shift consistent in all gains, amplitude/DC limits, curves
  and residual blending. The prototype uses shift one while some current runtime
  helpers assume zero; changing the signalled field alone is insufficient.
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
