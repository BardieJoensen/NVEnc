# Automatic retention: remaining work and completion criteria

Updated September 28, 2026. R1/R2 are complete; R3–R8 remain open. Start at the
[current handoff](WORK-TO-PRODUCTION.md) for deployment, live state and constraints.
The [archived roadmap](RETENTION-ROADMAP-HISTORY-THROUGH-2026-09-28.md) preserves
all historical stage updates. This document keeps the ordered requirements.

The goal is fast, space-efficient AV1 that preserves source detail and the
appearance of grain on both 1080p SDR and UHD HDR. Retention should keep enough
of the removed source residual when synthesis alone cannot reproduce it well.
It must earn its storage and processing cost through measured picture benefit.
Source preservation here describes the input to lossy NVENC compression; it
does not promise a pixel-identical decoded copy of the original.

## Current implementation and first open deliverable

The bounded selector, source-bound pre-encode schedules, actual rounded bases,
complete native model fitting, whole-source/copied-colour mechanisms and strict
post-NVENC source vetoes have passed their finite development controls. Latest
[D81 qualification](FINDINGS-2026-09-28-LOCAL-SOURCE.md) covers actual 8/10-bit
source/model transitions and unchanged ordinary SDR/HDR output.
[D80](FINDINGS-2026-09-28-CONSTANT-ENDPOINTS.md) records the separately reviewed
periodic reference. These results do not qualify real source eligibility.

The remaining R3 deliverable is a bounded automatic source/retention decision
with useful real whole-picture behaviour. [D82 source-only model selection](FINDINGS-2026-09-28-COMPONENT-SELECTION.md)
fixes unnecessary stationary rejections and a measured slow-motion overestimate.
Its 1,344 known-source controls, complete HDR census and 287 Python / 55 C++
checks pass. Necessary evidence now covers 8–10% of those pictures, but every
occupied lookup still overlaps unsupported pixels. [D83's optimistic union](FINDINGS-2026-09-28-POPULATION-UNION.md)
with the complementary flat/noise hypothesis separates just four pixels in
16.6 million; another fit of those supported patches cannot resolve coverage.
[D84 compression-only recovery](FINDINGS-2026-09-28-COMPRESSION-RECOVERY.md)
passes two constructed 8-bit windows and retains both 10-bit colour rejections.
D85's guarded full-source diagnostic passes CPU, GPU copy-proof and fresh
encoder qualification for its declared eight-picture development mechanism.
The complete 16-picture control rejects frozen-model reuse at picture eight.
Next test bounded shape refresh with continuous global seed phase and all
cross-boundary windows before another longer encoder trial.
This does not permit synthesis on ordinary fallback or admit unsupported sources.
Missing evidence must preserve or reject, not admit. Keep the reserved corpus
unopened until the candidate is useful and frozen.

The full-movie amplitude regression lacks its exact Play Dirty original and
three rebuildable generated artifacts; recovery of that prerequisite is pending.
Independent R3 work continues. Production remains ordinary `cb903a17`,
retention/FEL off. Completed trials have released all owned pauses.

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

The [selector plan](FINDINGS-2026-09-24-SELECTOR-PLAN.md),
[preserved-colour schedule](FINDINGS-2026-09-28-PRESERVED-SCHEDULE.md) and
[local source veto](FINDINGS-2026-09-28-LOCAL-SOURCE.md) are qualified mechanisms.
Their labelled controls cannot supply missing real source/detail evidence.

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

- [Current handoff](WORK-TO-PRODUCTION.md): exact deployed/trial identities,
  completed reports, active evidence root and operational constraints.
- [Decision contract](RETENTION-CONTRACT.md): source eligibility, finite
  candidates, numerical bounds, source reconstruction and failure rules.
- [Earlier fitting prototype](FINDINGS-2026-09-22-BRIGHTNESS-FIT.md),
  [colour/size comparisons](FINDINGS-2026-09-22-COLOUR-RECOVERY.md) and
  [campaign inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md): historical
  measurements; reuse only when sources, build and settings match.
- [Tradeoff tools](../../tools/fgs/RETENTION-TRADEOFFS.md) and [test tiers](TIERS.md).

**Resume instruction:** Verify repository/runtime state and continue with the
first open ready package. Record implementation, evidence, remaining limitation
and next action in one current status, without appending competing dated queues.
Preserve existing user edits and continue through checkpoints.
