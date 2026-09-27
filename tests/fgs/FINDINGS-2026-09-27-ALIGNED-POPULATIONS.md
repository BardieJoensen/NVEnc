# Aligned independent-history estimates: useful controls, insufficient real support

D67 implements a source-only alignment experiment for structured grain
populations. It removes the known moving-texture bias on controlled sources,
but **does not qualify a new real-source admission rule**. Only 183 of 4,080 HDR
development regions support its registration hypothesis; none survives every
declared consistency/detail check. Keep the existing R1 policy and source
fallbacks. R3–R8 remain unfinished; production is unchanged.

## Implementation

The diagnostic selects native motion from earlier source pairs and validates
the fixed proposal on separate later pairs. Native Y and both colour planes must
agree physically: Y displacement is exactly twice the chroma displacement.
Zero motion requires independent source/history structure anchors. Missing,
ambiguous, fractional or unsupported motion remains unknown.

Initial controls exposed an adjacent-pixel ambiguity in spatially sampled
matching on replicated 2x2 luma blocks. A separately declared refinement searches
only the proposal's integer +/-1 neighborhood using all native training pixels.
It never searches validation frames or uses candidate pixels. The original
failure and source hashes remain recorded.

Eight source pictures are aligned by integer indexing only. Missing historical
overlap and partial current borders are explicit unknowns; no padding, wrapping
or interpolation fills them. The original signed disjoint-three/four-history
estimates, asymmetric source/base cross moments and lag/history/mean diagnostics
then use identical coordinates. Chroma statistics use co-located averaged Y;
native Y detail is checked separately, including alternating-line structure.

An immutable prepared context validates and snapshots the finite native source
history and rounded base once. It prevents caller edits from changing evidence
after validation and avoids rereading all UHD pixels for every small region.
It is an offline CPU representation, not a new streaming encoder allocation.
All 336 existing measurements remain byte-exact after this ownership change.

## Results

The frozen study has 336 cases across 21 families, eight seeds and both depths.

- All 64 static, spatially correlated, moving and coupled-colour independent
  grain cases meet the recorded 8% variance / 0.08 covariance accuracy bounds
  against known native noise. These are estimator diagnostics, not final model
  or output-quality passes.
- All 48 grain-free translation cases and 16 weak native-texture cases estimate
  exactly zero grain after valid alignment. Unaligned moving detail previously
  generated a large false noise estimate.
- Temporal-correlation, exposure changes and strength jumps retain consistency
  conflicts. Cuts, acceleration, reversal and missing overlap remain unknown.
- All 16 persistent-plus-independent-grain cases still require a detail veto:
  the estimate accounts for roughly the independent half, while the candidate
  also removes the persistent half. All 16 removed-native-line cases likewise
  fail detail despite otherwise plausible averaged-luma grain measurements.
- Some clean-detail-preserving noise controls acquire conservative detail or
  consistency conflicts. They remain recorded; no threshold was widened.

The two existing UHD development frames include every canonical region and
border. Registration is supported for 56/127 of their 2,040 regions; most fail
physical component agreement. None passes all three components' consistency
and detail conditions. Separately, 59 Y, six Cb and zero Cr component regions
have no remaining recorded component/detail conflict. They still lack complete
model/population evidence and do not qualify a frame. Original R1 classifications
and every earlier persistent/motion veto remain unchanged.

The full census takes about 67.9 seconds in this offline implementation. The
full CPU suite passes 259 Python tests in 36 suites and 51 C++ programs. This
work adds no routine Tdarr validation, GPU job or media replacement.

## Interpretation and next implementation

Disjoint frame groups are not proof of statistical independence. Motion
selection, temporal noise correlation, changing structure and registration
error can still bias the inference. The controlled result must not be extended
to real footage by filling missing check bits or relaxing the failed gates.

A separate concrete implementation limit remains: the finite fitter supports
all-partial or whole-source pictures, so preserving one colour component forces
the entire frame to source. Address copied chroma first in the narrow case where
that component is exactly constant and its actual reconstruction/range can be
verified. Retain explicit rejection of unsupported mixtures and cross-component
compatibility checks. This does not resolve the broader source classifier;
real-source admission and R3–R8 still need their own evidence.

Records live in `roadmap-r3-aligned-populations-20260927/` under
[the handoff's evidence root](WORK-TO-PRODUCTION.md): frozen plans,
`initial-phase-alias.json`, `synthetic-report.json`, `snapshot-compat-report.json`,
`real-report.json`, `component-census.json`, `full-cpu-final.json` and `report.json`.
The source histories remain available for follow-up. Reserved qualification
footage is unopened; retention/FEL stay off and no trial starts automatically.
