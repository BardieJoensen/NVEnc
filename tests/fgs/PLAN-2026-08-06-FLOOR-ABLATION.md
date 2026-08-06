# Separate the two low-signal floors — plan, 2026-08-06

Pre-registered before any number is measured, following
`PLAN-2026-08-05-NEGATIVE-SPECIMEN.md`. Written because this touches
`NVEncCore/` and so gets a plan before it gets a commit.

## Context

`FINDINGS-2026-08-06-ONE-DEFECT.md` reduced four separately-tracked problems to
one relationship: where the source's true grain signal is weak the analyser
over-delivers (`1.47`--`5.18x` below signal `1.0`), where it is strong delivery
is close to correct (`0.83`--`1.24x` above `3.0`). Log-log corr `-0.802`,
`t = -5.54`, `n = 19`, slope `-0.414`.

`FINDINGS-2026-08-06-FLOOR-LOCATION.md` located two candidate causes in
`NVEncFilterFilmGrain.cu`, both derived from `minNoiseLevel = 0.5f` (8-bit), so
both at sigma `2.0` on 10-bit content:

- **selection floor** (`:2391`) — blocks below `minSigma` never enter the flat
  mask, so the strength curve is fit on a sample censored from below;
- **denoise floor** (`:2449`) — `clamp(metrics[i].sigma, minSigma, maxSigma)`
  sets per-block denoise strength, over-smoothing quiet blocks so the curve is
  fit on an inflated `V_source - V_base`.

The denoise path was measured and largely exonerated: sweeping `denoise` upward
raises the emitted curve monotonically on 3/3 titles but only `~1.1x` per
fourfold change in sigma, which cannot produce `5x`. The selection floor is the
leading candidate. Confirming that requires probing **below** sigma `2.0`, and
no interface allows it — `minNoiseLevel` has no parser anywhere, and
`NVEncCmd.cpp:1181` rejects explicit `denoise` under `1.0`.

Both floors are on master, in `2e164d0e`, the first FGS commit. This is not
branch work and the fix — if there is one — is a production question.

## The change

One test-only hook, following the established `NVENC_FGS_TEST_*` pattern
(env-only, unreachable from any CLI parser, validated in the config block at
`:1957`--`:2130`, logging `ignoring ...` on a bad value):

```
NVENC_FGS_TEST_MIN_NOISE=<select>[,<denoise>]
```

Two independent values so the floors can be moved separately — that separation
is the entire point, and a single override would not answer the question. When
unset, both take `prm->filmGrain.minNoiseLevel` and the code path is unchanged.
Values are clamped to the range the code already validates for itself
(`config.minNoiseLevel = std::max(0.05f, ...)` at `:1945`), so no new range has
to be justified: `0.05` is the encoder's own stated minimum.

`:2391` reads the select value, `:2449` the denoise value. Nothing else in the
file changes.

## Arms

A 2x2, because the two floors are not known to be independent and an
interaction is the interesting case:

| arm | select | denoise | isolates |
| --- | --- | --- | --- |
| A | 0.5 | 0.5 | control — current and production behaviour |
| B | 0.05 | 0.5 | selection floor only |
| C | 0.5 | 0.05 | denoise floor only |
| D | 0.05 | 0.05 | both |

C is expected to reproduce the `~1.1x` already measured through the CLI route
and so doubles as a cross-check that the hook does what the plan says.

## The decisive measurement

**The prediction is a change in slope, not in level.** Any change that lowers
delivered amplitude everywhere would "improve" the low-signal cells while
breaking the high-signal ones, and a level test cannot tell that from a fix.
The floor model predicts something much more specific: low-signal cells move
toward `1.0` and **high-signal cells do not move at all**.

Corpus, drawn from the 19 cells so results are directly comparable to the
relationship they are meant to explain — four spanning each end:

| low signal | true | ratio | | high signal | true | ratio |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| Long Halloween luma | 0.377 | 2.460 | | Interstellar sat. chroma | 3.023 | 1.235 |
| Interstellar V darkest | 0.480 | 2.763 | | Taxi skin chroma | 4.715 | 1.099 |
| Scarface neutral chroma | 0.530 | 5.183 | | Scarface sat. chroma | 5.582 | 0.947 |
| Shining V band 0.25--0.375 | 0.810 | 1.472 | | Deer skin chroma | 8.406 | 0.830 |

Delivered amplitude against source throughout, via
`temporal_grain_report.py --flat-selector production` — never the emitted curve,
which overstates delivered strength roughly twofold
(`FINDINGS-2026-08-04-ADMISSION-GATE.md`). The emitted curve may be logged as a
secondary trace but no conclusion rests on it.

Pass conditions, frozen here:

1. **A floor is confirmed as the cause** if, in its arm, the low-signal group's
   mean ratio falls by at least half its excess over `1.0`, **and** no
   high-signal cell moves by more than `±0.10`, **and** the refitted log-log
   slope over all eight cells moves from `-0.414` to `|slope| <= 0.20`.
2. **Attribution** goes to whichever of B or C satisfies (1); to D only if
   neither does alone, which would mean the floors interact.
3. **The floor model is wrong** if no arm satisfies (1) — in particular if D
   moves the low-signal cells no more than the `~1.1x` C is expected to. Record
   that and stop. It is a real result: it would mean the defect lives in the
   estimator itself, not in a floor, and six estimator rejections would need
   re-reading in that light.

## The counter-test that has to run alongside

**The floor may be a deliberate guard, and this plan must not assume it is a
bug.** Its effect is to stop the analyser fitting a model to blocks with almost
no signal — which is exactly the situation where what little signal exists is
codec ringing or sensor noise rather than film grain. Lowering it could
reintroduce precisely the harm the negative-specimen work went looking for and
failed to find.

So every arm is also scored for harm, not only accuracy, reusing
`covariance_artifact.py`'s axis: is the synthesized texture closer to the
source's grain texture or to the recompression's codec-noise texture? Run on
the x264 and HEVC artifact cells already built, plus the three grain-free
animation titles where there is no true grain for a lowered floor to find.

An arm that satisfies pass condition (1) **and** starts tracking codec noise is
not a fix. That outcome — accuracy and safety trading against each other across
`minNoiseLevel` — is the most useful thing this experiment can produce, and it
is the reason the corpus includes content with no grain in it at all.

## Verification

- **Bit-identity when unset.** With no `NVENC_FGS_TEST_MIN_NOISE` in the
  environment, decoded pixel hashes must match the current pinned candidate
  (`pin-40b987ff-20260804-response-margin`) on at least three titles. This is
  the guard that matters: `9c37ab62` exists because a KAT silently tested the
  wrong arm.
- **Assert the hook took effect** in every arm, and treat any `ignoring` line
  in encoder output as a hard failure, as `negative_specimen.py` already does.
- `tests/fgs/test_floor_ablation.py` plus the existing Python suite.
- `tests/fgs/fgs_kat.py` unchanged and passing — the KAT pins default
  behaviour, which this must not alter.
- Every stream decodes completely under `libdav1d -xerror`; frame counts and
  relative PTS validated per pair.
- Every measurement records which arm and which reference produced it.

## Files

**Modified:** `NVEncCore/NVEncFilterFilmGrain.cu` — the hook, its validation,
and the two read sites. No other file; in particular no CLI parser, so the
override stays unreachable from a command line.

**New:** `tests/fgs/floor_ablation.py`, `tests/fgs/test_floor_ablation.py`.
Findings to `tests/fgs/FINDINGS-2026-08-07-FLOOR-ABLATION.md`.

**Reuse, do not reimplement:** `temporal_grain_report.py` (delivered amplitude),
`covariance_artifact.py` (the codec-noise-vs-grain axis), `filmgrn.py` (table
parsing), `floor_separation.py` (the denoise-sweep cross-check).

**Build:** `nvenc-fgs-build:cuda13.3` with the repo mounted at `/work`, per the
project's build note. Pin the resulting binary under `~/.cache/fgs-gate/builds/`
with its commit in the directory name, as every previous arm has been.

## Discard criteria

Abandon rather than iterate if: no arm satisfies pass condition (1); or the hook
cannot be made bit-identical when unset; or the effect is present but so
content-dependent that no single `minNoiseLevel` separates the low-signal cells
without moving the high-signal ones.

**Do not tune `minNoiseLevel` to a value that looks good on this corpus.** The
question here is *which floor causes the defect and at what cost*, not what the
constant should be. Choosing a production value is a separate decision needing
its own held-out corpus and a quality gate, and picking it here would be the
fixture-threshold mistake this repo has already named once.

## Scope

Diagnosis. `modelsrc` stays default-off, no default changes, Tdarr untouched,
and the hook ships disabled and unreachable. Even a clean confirmation does not
authorise changing `minNoiseLevel` in production — that floor has been in every
encode this project has ever produced, and the counter-test above is the reason
to find out what it was holding back before removing it.
