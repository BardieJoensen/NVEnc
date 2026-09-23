# Native lookup feasibility before retention fitting

The new bounded preflight detects when AV1's shared brightness curve cannot
represent the frozen R1 population rules. It is an offline R3 prerequisite,
with **no encoder output call sites**. It does not qualify a grain model or
change production retention, FEL, source protection or validation settings.

AV1 cannot give different strengths to two pixels with the same native curve
lookup. Under R1 revision 1, any quiet, rejected, border or undersupported
population at a lookup forbids positive synthesis there. A few supported grain
patches cannot override those other pixels. The new helper accumulates a
complete component census and computes the necessary per-lookup constraint.
It also reports otherwise eligible samples that share a forbidden lookup.

`NVEncFilmGrainPopulationEnvelope.h` rejects incomplete or invalid censuses,
requires source-only populations with at least 16 training and 16 check blocks,
and uses the exact integer AV1 LUT to detect forbidden synthesis. This includes
high-depth interpolation: a nonzero strength can occur between a zero node and
its nonzero neighbor. Invalid requests cannot reuse an earlier result.

A possible lookup is only an optimistic upper bound. It does not prove that a
legal 10/14-point curve exists, that the rounded base is safe, that source
detail survives, or that decoder range/model/temporal checks pass. The census
must describe the **actual candidate lookup equation and rounded luma base**;
changing either requires a fresh census. The source-only populations remain
fixed across retention fractions.

## Independent controls and real replay

The unit controls exercise a single rejected pixel sharing a lookup with 600
eligible pixels, reordered/split cells, interpolation into a forbidden code,
undersupported populations, invalid sizes/depths and malformed results. An
independent per-pixel oracle checks 204,800 synthetic samples across 200 8/10-bit
censuses. A zero curve still fails the separate coverage gate without native
decoder-range evidence.

All 36 existing real native component/fraction censuses reproduce their
independent counts and source population identities. They cover three UHD
Shining development frames, both colour components and six retention levels.
Each component has 2,073,600 pixels. For the recorded rounded-Y base and chroma
lookup equation, **every occupied code is forbidden** under R1 revision 1.
Even the 72,704 / 229,376 / 288,768 otherwise eligible Cb pixels share their
lookups with an unsupported population. Cr has no sufficiently supported grain
population. No positive frame-wide curve can satisfy this particular census.

This is not proof of damaged media or of an inherently impossible AV1 model.
It identifies a precise missing piece: a separately qualified population rule,
a differently measured lookup/model, or source-preserving fallback. Repeating
the same partial-patch strength fit cannot resolve this lookup conflict.

The replay also exposed an outdated comparison assertion: its old reference
treated unchanged base plus zero strength as enough, despite the later decoder
range guard. The historical census supplies no range evidence. The corrected
reference therefore leaves all such cases unqualified. The old-reference failure
is retained; no fabricated range-pass bits or relaxed limits were introduced.

The complete CPU suite passes 185 Python tests in 26 suites and 28 C++ programs.
The evidence root from [the handoff](WORK-TO-PRODUCTION.md) contains
`roadmap-r3-population-envelope-20260923/manifest.json`, `summary.json`,
`comparison.json`, the retained old-reference negative and `cpu.log`.

Next, compare explicitly declared alternative lookup equations and establish
population-specific acceptance before fitting or selecting another whole-picture
candidate. Actual automatic output selection and R3–R8 remain unfinished.
