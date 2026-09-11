# Exact strength-curve comparison for temporal model reuse

Status: a CPU comparator defect is reproduced and fixed in the work branch.
The full CPU suite passes. GPU qualification, decoded-picture comparisons and
production activation remain deferred while the repair has priority.

## The demonstrated defect

`film_grain_params_close` decides whether a fresh model is close enough to reuse
the previous model. It also checks coherence between pending model candidates.
The old implementation compared strength curves at brightness 0, 15, 30, ...,
255. A valid narrow curve change between those samples could therefore be
classified as unchanged.

The CPU reproduction uses two curves that are identical on that grid, while
one changes grain sigma from 4 to 10 at brightness 7. The old comparator accepts
the pair. The same pattern is tested independently on Y, Cb and Cr. This proves
a comparison error; it does not establish a newly damaged movie or episode.
Other temporal and source-fidelity checks still participate in actual output.

## Implementation

The replacement checks both endpoints and the merged, distinct knots of both
curves. Between consecutive knots each curve and their difference are linear,
so their maxima and maximum absolute difference occur at those boundaries.
This gives an exact comparison of the represented curves, including fractional
brightness between knots, without scanning every brightness or allocating a
temporary container.

The amplitude tolerances, absolute floor, coefficient comparison and model
update cadence are unchanged. Both maximum amplitude and maximum difference
are now exact. Consequently a boundary decision can change in either direction;
this implements the existing relative-tolerance definition rather than a new
tolerance. Equivalent curves with different knot layouts or scaling shifts
remain equivalent, and small permitted jitter still passes.

Simple curves require fewer sample evaluations than the old grid; dense curves
can require more. No overall encoder speedup or runtime cost is established.
There is no additional validation pass in Tdarr.

## Qualification completed without GPU work

- The new regression fails against pre-change source at `1fce3f31`.
- Luma/chroma narrow changes, permitted jitter and equivalent curves pass after
  the fix.
- 6,000 generated curve pairs, tested in both directions, agree with an
  independent exhaustive-brightness sampling oracle: 2,348 close pairs and
  3,652 changed pairs. The cases include all supported scaling shifts, sparse
  and dense curves, endpoint clamping and independent chroma curves.
- The full CPU suite passes in 25.0 seconds under a one-core quota, low CPU/I/O
  priority and a 2 GB memory limit. The model source and test hashes were
  unchanged during that run. No media was decoded or encoded.

Core source BOM and CRLF formatting are preserved. The CUDA filter and the
colour-restoration thresholds were not edited in this step.

## Existing campaign data provided a real curve example

Nine historical grain tables provide 357 adjacent pairs of emitted models.
A separate text-only analysis checked both 5% and 10% comparison tolerances.
All 357 decisions agree at 5%. At 10%, one Ju-on pair changes from close to
different when evaluated exactly; the remaining 356 agree.

For that pair, the old grid measures a maximum sigma difference of 0.410714,
while the exact difference is 0.53125. Peak sigma is 4.34375, so the 10% limit
is 0.434375. The old grid misses the excess. Compiling and running the actual
before/after C++ functions with those table entries confirms the decision
change. The encoder uses a 10% tolerance for pending-candidate coherence and
for the motion denoiser's model-hold comparison.

These tables contain emitted historical models, not every fresh candidate or
the surrounding temporal state. This is evidence that the sampling issue also
occurs in recorded curve shapes, not proof of visible damage or an estimate
of how often today's encoder output will change. The uncorrected Planet Earth
timing experiment was excluded.

## Remaining qualification and current work boundary

The original colour-recovery investigation still needs fresh detailed trace
records. The archived campaign summaries inspected here contain aggregate
picture/grain statistics, not the complete current normal equations and
independent local covariance observations needed to replay those decisions.
They cannot retrospectively identify the missing per-condition rejection
reasons in the recent full-source logs. No colour threshold was relaxed to
increase synthesis coverage.

After repair, build the combined branch and check model-update stability,
source-detail/gradient/jacket controls and quality per byte against the pinned
production and optional reference builds. Intentional temporal model changes
must be assessed separately from the covariance-skip optimization's
output-preservation checks. The current comparison manifest still pins its
previously qualified binaries; this source edit is not a qualified replacement.

Private evidence is under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/model-hold-audit-20260911/`:
`cpu-suite.json`, `cpu-suite.log`, `archive-curves.json`, and
`archive-cpp-check.json`. The reproduction and before/after probes are under
`/tmp/downloads/fgs-retention-prep-20260910/model-hold-20260911/`.
