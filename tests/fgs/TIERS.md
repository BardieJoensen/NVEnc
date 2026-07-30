# Which tier catches which class of defect

Two tiers, split by what they need rather than by how long they take. The split
is not a convenience: **the GPU tier is not hosted and cannot be hosted**, and
the reason matters more than the arrangement.

## The short version

| | tier 1 | tier 2 | nightly cron |
|---|---|---|---|
| where | GitHub Actions, every push | this box, manually and pre-push | this box, 08:45 and 20:15 |
| needs | g++, python, numpy | GPU, real film, libaom, Docker | GPU, real film, Docker, Tdarr DB |
| catches | logic and arithmetic errors in the model solver, the table parser, and the descriptor mathematics | analyzer regressions visible only on real film; texture substitution; metric-gaming | grain destruction and grain substitution in shipped library output |
| blind to | anything requiring a real encode | anything not in the four covered titles | anything the deployed binary does not do on the sampled files |
| runtime | ~30 s | ~3.5 min quick, tens of minutes full | ~10 min |

## Why the GPU tier cannot be hosted

This is the whole point of the split, so it is worth being blunt about.

Both defects that reached production on 2026-07-29 and 2026-07-30 — the fixed
8x8 analyzer sampling lattice, and the correlation-driven kernel widening —
were invisible to every conventional signal at once:

- file sizes got **smaller**, which every size guard reads as success;
- VMAF and SSIMULACRA2 got **better**, because they are full-reference and
  score synthesised grain as error, so destroying grain improves them;
- CAMBI stayed clean, because less grain is not banding;
- **all 18 GPU known-answer fixtures passed**, because synthetic fine grain
  does not alias against the lattice. Only real film did.

They were found by comparing against libaom as an external oracle, on real
film, with a grain-applying decoder. A GitHub-hosted runner has no GPU, no
libaom build, no film, and no labelled negatives. A hosted copy of the tier-2
gate would therefore report success for both of the only two regressions this
project has ever had. **A green tick that checks nothing is worse than no
check**, because it is evidence in the wrong direction.

For the same reason `local_gate.sh` refuses to run (exit 2) when a
prerequisite is missing, rather than skipping the stage. A skipped stage inside
an otherwise-green run is the same failure in a different costume.

## Tier 1 — hosted CI, every push

`.github/workflows/fgs_cpu_tests.yml` runs `tests/fgs/run_cpu_tests.sh`:

| check | subject |
|---|---|
| `solver_test.cpp` | `NVEncFilmGrainModel.cpp` — AR normal equations, scaling-curve fitting, chroma correlation clamping, strength LUT, stratified sample coverage |
| `parser_test.cpp` | `NVEncFilmGrain.cpp` — `filmgrn1` table parsing, entry inheritance, interval and ordering validation |
| `test_filmgrn.py` | table comparison in normalised synthesis units |
| `test_quality_metrics.py` | radial spectrum, high-pass, spatial autocorrelation |
| `test_texture_metrics.py` | flat-block selection, luma banding, amplitude independence, the labelled-negative gate logic |
| `test_model_gate.py` | AR synthesis, held-out descriptors, and the accept/reject asymmetry |

`docker-apps/.github/workflows/pipeline_cpu_tests.yml` runs the monitor alert
logic: percentile handling, reference-hash pinning, and
`classify_canary`'s requirement that **both** independent metrics move before
an alert.

Note what tier 1 covers there: the *alert logic* of the monitors, not the
monitors. The monitors themselves need a GPU and real film.

### The meta-check

Both workflows end with a mutation self-test (`selftest_can_fail.sh`). It
injects known defects into a scratch copy and requires the suite to reject each
one. Mutation 1 in the NVEnc suite is the real 2026-07-29 defect: the sampling
lattice with the stagger removed.

This exists because a suite that has never been observed failing is
indistinguishable from one that cannot fail — and that is not hypothetical
here. Writing this automation found exactly that: the documented invocation
`bash tests/fgs/run_cpu_tests.sh` discarded the shebang's `-e`, so the script
exited with the status of its *last* command and a failing solver test still
reported success. `set -e` now lives in the body of the script.

A mutation whose pattern no longer matches the source is a hard error, never a
silent skip. If you move the code, move the mutation.

## Tier 2 — local GPU gate

`tests/fgs/local_gate.sh`. Stages, in order:

| stage | what it establishes |
|---|---|
| `tools` | pins libaom by revision and both NVEncC references by SHA-256, into a persistent cache |
| `kat` | 18 bilateral GPU fixtures. Bounds synthetic behaviour. **Passed throughout both production regressions** |
| `synthetic_oracle` | `reference_compare.py` — model fitting against libaom on generated fixtures |
| `model_negative` | the texture model gate against the adversarial specimen (offline; no GPU needed, but needs the raw Taxi pair) |
| `real_oracle` | `reference_compare_real.py --texture` — occupancy-weighted libaom comparison on real film. **This is the stage that caught the sampling defect** |
| `texture_negative` | the r4047-versus-r4050 texture pair must separate |
| `canary_negative` | the base-fidelity canary must alert on r4047 and stay clean on r4050; the widened Casino encode must read as base-degraded |

`--quick` runs `tools kat model_negative` (~3.5 min) and is what the pre-push
hook uses. It is honestly labelled in the hook's own output: **the quick gate
would not have caught either production regression.** Only `--full` runs the
stages that did.

### Persistent tool paths

`/tmp/aomref` and `/tmp/nvenc-pin4` do not survive a reboot, and the pinned
libaom revision and pinned encoder are the two things that make any of these
numbers comparable across runs. The gate therefore caches under
`${FGS_GATE_CACHE:-~/.cache/fgs-gate}`:

- `aom-<rev>/build/noise_model` — rebuilt from the pinned revision
  `18c52422b835ba6cdde1b2342d760c6037a7fd86` if absent. Pinned by **revision**,
  not by binary hash: a rebuild of the same source is not bit-identical, and a
  distro package would silently compare against a different analyzer.
- `bin/nvencc-r4050` and `bin/nvencc-r4047` — extracted from the pinned Docker
  images and verified against the SHA-256 values in
  `FINDINGS-2026-07-30-TEXTURE.md`. Extracting beats rebuilding: the reference
  binaries are exactly the ones the findings were measured with.
- `builds/pin-<commit>-<timestamp>` — candidate builds from a pinned clone.

### Building a candidate

`--candidate-commit <sha>` clones **with tags** (meson runs
`git describe --tags` and exits 128 without them), copies the submodules from
the live tree (`dtl`, `cppcodec`, `build_pkg` — a plain clone has them empty
and the build dies ~78 files in on `dtl/dtl.hpp`), and uses a fresh timestamped
path every time because the container writes the build directory as root and a
failed attempt cannot be removed afterwards. Never builds from the live
worktree: two builds were discarded on 2026-07-29 when HEAD moved mid-compile,
and the result of that is not a failed build — it is a plausible-looking binary
whose measurements are attributed to the wrong commit.

## The three labelled negatives, and where each is asserted

A monitor validated only against good inputs cannot be distinguished from one
that cannot fail. Each negative is asserted in code, not documented and hoped
for, and each has a positive control beside it so that "rejects everything" is
not mistaken for "works".

| negative | asserted in | expected |
|---|---|---|
| r4047 `-grainfix` image (contains the rejected widening) | `local_gate.sh` stage `canary_negative` | base-fidelity canary **ALERT**, exit 1. Positive control: r4050 exits 0 |
| `casino_widened_r4047.mkv` (retention 1.035/0.979/1.034 — perfect — on a degraded base) | `local_gate.sh` stage `canary_negative` | SSIMULACRA2 mean delta **negative** against the original download. Retention passes this file; base fidelity must not |
| `taxi_ceiling_q.json` (deliberate metric-gamer) | `local_gate.sh` stage `model_negative`, logic in `test_model_gate.py` | model gate **REJECT**. Positive control: the shipping model is accepted |

Measured on 2026-07-30 by this gate, reproducing the published numbers:

```
r4047 canary   SSIMULACRA2 mean -0.872   p5 -0.798   Butteraugli +0.030   ALERT
r4050 canary   all deltas 0.000                                             ok
```

### The third negative needed a gate that did not exist

The first two negatives had detectors already. The third did not, and this is
worth recording because it is a genuine gap that the automation had to close
rather than merely schedule.

`texture_media_report.py --labelled-negative` answers "can the detector see a
known texture change between two encoded arms?". That is a sensitivity check.
It cannot express "should this model be accepted?", and its subject is encoded
media, not a set of AR coefficients. Pointing it at `taxi_ceiling_q.json` is
not a matter of configuration — it is the wrong question.

So `model_gate.py` was added. Its rule follows directly from
`fgs-open-questions.md` item 3a:

- **gated** descriptors — radial spectrum total variation, H/V autocorrelation
  over lags 1-8 — may only ever *help* a candidate;
- **held-out** descriptors — gradient anisotropy, diagonal lag-1
  autocorrelation — may only ever *veto* one.

A candidate that moves any held-out descriptor materially further from the
source than the incumbent is rejected no matter how much it improves the gated
ones. Measured on the specimen with the real Taxi source residual (11,886 flat
patches, 6 frames, four RNG seeds):

```
                       candidate   incumbent
spectrum_tv    gated      0.0229      0.0812   better
acf_rmse       gated      0.0107      0.0370   better
anisotropy     held out   0.0300      0.0140   REGRESSED
diagonal ACF   held out   0.0114      0.0052   REGRESSED
verdict: REJECT
```

3.5x better on what it was fitted against, ~2x worse on what it was not. If
that model had ever passed, the gate would have been measuring the wrong thing.

The held-out set is not a permanent secret; the point is only that it is not
what a candidate was fitted against. If a future analyzer is tuned on
anisotropy and diagonal ACF, this gate needs a new held-out direction and the
specimen should be regenerated against the new loss.

## Nightly cron

| job | schedule | what it answers |
|---|---|---|
| `grain-watch.py` | `45 8 * * *` | did shipped library output lose grain? (destruction) — runs the base canary as its pre-step |
| `grain-base-canary.sh` | `15 20 * * *` | is the deployed binary substituting synthesis for real detail? (substitution) |

The canary is scheduled twice on purpose. `grain-watch.py` runs it as a
pre-step, but grain-watch exits early when no verified source pairs are
available, and a 12-hour offset halves the time a substitution regression can
sit undetected. The second run costs one 24-frame encode pair.

Both exit 1 on alert so cron mails the summary, matching `cambi-watch.py`.

## What each axis is blind to

Never collapse these into one score. Casino is the worked example: retention
1.035 / 0.979 / 1.034 across three scenes — as good as anything in the library
— on a file whose base had been smoothed and its texture substituted.

| axis | detects | blind to |
|---|---|---|
| grain energy (`grain-watch.py`) | destruction | substitution at equal energy |
| base fidelity (`grain-base-canary.sh`) | real detail replaced by synthesis | wrong-scale grain |
| grain texture (`texture_media_report.py`, `model_gate.py`) | wrong scale or correlation | amplitude |

## What is still not automated

- **No absolute real-film texture threshold.** The texture gate only requires a
  *known* change to be detectable. Tightening needs several scenes per title so
  natural film variability is known first; large core/expanded movement stays
  labelled selector-sensitive rather than pass/fail.
- **The gate uses the differential arm, not the absolute one.** Source-distance
  numbers are recorded and are explicitly not gateable: they move ~2x with the
  flat-patch mask while the NVEnc-versus-libaom differential barely moves.
- **Coarse grain at 1080p is uncovered.** Ju-on is fine grain, Taxi is coarse
  4K; neither covers coarse 1080p.
- **Only four titles.** Taxi Driver, Silo, Casino, The Shining.
