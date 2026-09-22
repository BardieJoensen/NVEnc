# Brightness-aware colour recovery and partial source retention

The offline prototype now preserves a quarter of the removed Cb residual and
fits the missing grain against the **rounded retained base**. All eight tested
source-patch groups pass the total-source variance and covariance bounds.
This is a development result, not a qualified encoder or a new Tdarr setting.
Production remains ordinary `cb903a17`; automatic retention and FEL remain off.

The evidence is in
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/brightness-fit-20260922/`.
Start with `report.json`, then the stage reports below. The main evidence root's
`handoff.json` and `evidence-index.json` identify the current state and artifacts.

## Implementation and evidence

`NVEncFilmGrainBalancedModel.h` fits one normalized chroma AR shape against the
worst supported brightness group's relative prediction error. The bounded
simplex-dual optimization reports its lower bound and convergence gap; failure
to converge rejects the fit. Training alone determines normalization, weights
and coefficients. Mathematical validity is separate from source eligibility,
quantization, causal stability and actual decoder fidelity.

Analytic one- and two-dimensional controls, an independent dense scalar search,
amplitude changes, duplicated/reordered groups, irrelevant groups and bounded
nonconvergence cover the implementation. The previous worst dark-group
prediction excess falls from about 19.99% to **7.61% after quantization**, below
the unchanged 8% exploratory limit. Five older strength inconsistencies still
reject; one older Bridge fit also fails the unchanged synthesis-stability bound.
Neither threshold was weakened. See `fit-evaluation.json` and
`development-minimax-v2.json`.

Two fresh 360-picture Bridge/Shining captures use later source windows.
Independent software decoding exactly matches all planes of eight captured
current pictures and all eight cached previous luma pictures. Previous colour
comes from independent decoding; the encoder's existing reference cache contains
valid luma only. The source selector and disjoint training/holdout tile split
are unchanged. Bridge remains an unsupported negative; eight Shining Cb
brightness groups initially pass the regression and strength bounds. See
`capture-report.json`, `fresh-report.json` and `fresh/`.

Actual AOM synthesis exposed an additional gap: a good regression score did not
preserve the dark groups' covariance. Only the four brighter groups pass the
separate synthesis check in both overlap modes. More precise grain scaling and
simple block-boundary compensation do not solve it. Training against actual
synthesis covariance improves a trial, but its holdout still fails. These
rejected alternatives remain in `synthesis-report.json`,
`refine-synthesis-report.json` and `covariance-balance-report.json`.

`NVEncFilmGrainJointFidelity.h` therefore compares measured synthesis or
reconstructed-source moments with their independent target. It checks every
diagonal variance, normalized off-diagonal covariance and colour-coupling sign.
The regression test includes a wrong white-noise model whose prediction error
passes 8% but whose actual correlation error is 0.2. A separate control rejects
opposite colour coupling despite identical marginal energy. Passing this helper
does not establish source support or whole-picture coverage.

## Partial-retention prototype

The next prototype tests all five predeclared Cb retention fractions:
0, 0.1, 0.25, 0.5 and 0.75. Y retention is 0.1 and the experimental grain scale
shift is 1. Each fit and integer strength choice uses training only. The grid
uses the already inspected development holdouts; it is **not new blind
validation**, and no automatic selection policy has been qualified.

A linear blend's covariance is insufficient for weak grain. Native 10-bit
rounding can leave a nominally retained pixel unchanged. The prototype therefore
measures each prospective rounded base directly, then fits source-minus-base
with zero further retention. The joint-target API documents this contract and
has an analytic rounding regression: a quarter residual blend predicts missing
variance 2.4375 before rounding, versus the actual 3.0 afterward.

The 0.25 Cb prototype passes all eight groups' original missing-noise support
and predictor bounds, as well as the separate total-source moment bounds.
The missing-noise term itself can still fail its stricter normalized covariance
diagnostic; the new experiment explicitly measures the final source-plus-grain
result and retains the earlier rejected results. This is not a retrospective
clearance of the original full-synthesis candidate.

Actual native-depth source/base patches plus independent AOM grain confirm the
result across **513 held-out source blocks**, each with 48 synthesis seeds:

| Check | Worst measured error | Exploratory bound |
|---|---:|---:|
| Any joint diagonal variance | 4.99% | 8% |
| Normalized joint covariance | 0.07344 | 0.08 |
| Picture clipping in these patches | 0 samples | Recorded separately |

See `rounded-retention-moments-report.json`, `rounded-retention-report.json` and
`retained-source-pixels-report.json`. This includes the actual rounded base and
finite source/grain cross terms. It does not include NVENC compression,
unsupported picture regions, Cr recovery or complete moving sequences.
`0.25` means a fraction of the removed colour residual's amplitude, not a
percentage of file size or a production configuration recommendation.

## Independent decoder and regression checks

Four constructed strong-coupling controls have measured correlations from
about -0.466 to +0.453. Both overlap settings pass, and deliberately removing
the colour driver fails. These are synthetic controls, not varied real-film
coverage (`strong-coupling-report.json`).

Lossless AV1 carriers exercise 20 parameter sets across **140 pictures**:
100 planned grain-on pictures and 40 planned grain-off pictures. AOM and dav1d
match exactly on **110,100,480 compared samples** across grain-on/off decoding.
The zero-strength Cr plane remains unchanged, including the legal paired Cb/Cr
point counts. The later 56-picture carrier includes the partial-retention
models and grain scale shift 1. These tests check serialization and decoder
state; they do not qualify an NVENC implementation or real scene transitions.
See `roundtrip-report.json` and `roundtrip-retained-report.json`.

The complete CPU suite passes 185 Python tests in 26 suites plus the C++ checks.
The additional native-rounding counterexample also passes. The new helpers have
**no encoder call sites** and add no work to routine Tdarr validation.

## Work required before an encoder trial or deployment

1. Define whole-picture brightness support and source-preserving handling of
   unsupported/quiet areas. Eight supported Cb groups are not frame eligibility.
2. Integrate source/base collection and fitting against the actual rounded base,
   with valid previous colour, both chroma components and independent source
   gates. Keep ordinary mode identical. The current luma-only cache must not be
   read as colour evidence.
3. Account for grain scale shift in all gains, amplitude/DC checks and curves.
   Existing runtime recovery assumes shift zero in some paths; setting it to one
   without those changes is not valid integration.
4. Qualify actual NVENC-compressed moving SDR/HDR/animation output, model changes,
   source fallback and recovery. Preserve source clocks, metadata, existing
   ripple/flicker/texture/amplitude guards and no-synthesis source detail.
5. Measure matched-size quality, full-title cost and speed for a useful qualified
   candidate. Keeping residual detail does not guarantee that NVENC retains it
   after compression, and no file-size savings are established here.

The user-authorized capture pause drained active jobs and was released. Tdarr
continues with the qualified ordinary encoder, existing worker limits and its
independent Emby watchdog. FEL originals and source holds remain protected.
No additional library damage, repair or download was established. All study
entry points remain manual; nothing is scheduled to start automatically.
