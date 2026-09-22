# Experimental joint colour-grain recovery

The helpers added in `78857051` are **offline mathematics, not an encoder
behaviour change**. They have no production call sites. Neither a successful
fit nor a finite spectrum qualifies a source region as grain. Current fallback,
texture, amplitude, temporal-recovery and stability protections still apply.

## Why this model is different

The existing component-only recovery admits nearly independent colour grain.
Removing its spatial-correlation rejection would also admit picture texture.
The experiment instead represents the chroma neighbours, the 2x2 averaged
luma driver and current chroma together. It requires source, filtered-base and
source/base cross-moments from the same source-selected observations.

Let `S` be source covariance, `B` base covariance and
`X[i,j] = Cov(source[i], base[j])`. If the encoded base retains fraction `r[i]`
of the source residual in each component, independently added synthesis needs
the following covariance:

```
G[i,j] = (1 - r[i]*r[j]) * S[i,j]
       - (1 - r[i])*(1 - r[j]) * B[i,j]
       - r[i]*(1 - r[j]) * X[i,j]
       - (1 - r[i])*r[j] * X[j,i]
```

`X` is generally asymmetric. Symmetrizing it loses information when luma and
chroma retention differ. `NVEncFilmGrainJointModel.h` validates the combined
source/base evidence and the target as positive semidefinite before fitting
all 25 chroma predictors together. An impossible missing-noise target is
rejected; a ridge does not conceal it. A mathematically possible target still
needs representable quantized coefficients, causal stability, intensity-bin
support and decoded/source verification.

`NVEncFilmGrainJointSpectrum.h` evaluates actual quantized 4:2:0 coefficients.
The chroma recursion filters both its independent innovation and its luma
driver. The luma driver includes all four aliases from 2x2 averaging and
decimation; white unit-variance luma therefore contributes variance 1/4.
Adding the luma contribution after the chroma recursion misses their
interaction. The stationary calculation excludes finite template borders,
rounding, clipping and overlap. Its `valid` flag establishes finite arithmetic,
not stability or visual correctness.

## Evidence and limits

The normal CPU suite includes analytic/asymmetric-retention controls,
inconsistent and unrepresentable covariance negatives, bit-depth scaling,
coupled fits, alias/pole controls and an independent spatial-noise simulation.
All 180 Python tests in 25 suites and the C++ tests pass.

The September 22 private study additionally uses pinned AOM revision
`18c52422b835ba6cdde1b2342d760c6037a7fd86` and its actual
`av1_add_film_grain` implementation. Four controls, each with 48 seeds and
3,145,728 measured chroma samples, reproduce the predicted powers within about
2.2%. Finite template/block effects remain visible; this is not exact pixel
equivalence or a replacement for actual decoding. The relevant primary
implementation is [AOM grain synthesis](https://aomedia.googlesource.com/aom/+/18c52422b835ba6cdde1b2342d760c6037a7fd86/av1/decoder/grain_synthesis.c).

Six private 720-picture captures retain exact host fit inputs. Their 4,320
model decisions match the uninstrumented reference. Separate source/base/
adjacent-pixel captures cover four pictures each in animation, live-action SDR
and native PQ HDR. One independently software-decoded source picture per case
matches every captured Y/Cb/Cr pixel exactly. Decision equality is not a claim
of complete decoded equality for the diagnostic builds.

An exploratory source-only selector uses disjoint training/holdout tiles,
plane detrending and temporal/directional checks. Its first forward-gradient
implementation incorrectly assigned directional coherence to isotropic noise;
that failed version remains recorded. Central gradients recover 128 training
and 128 holdout tiles of independently generated, coupled colour noise while
rejecting persistent texture and axial stripes. Independent training/holdout
fits agree within the predeclared 8% bound and recover the constructed spatial
and luma coupling. This calibrates the diagnostic, not an encoder classifier.

**None of the 24 captured real frame/component groups supplies enough eligible
independent colour-noise tiles.** In the HDR example, the temporally supported
luma regions largely have very quiet chroma. Elsewhere temporal picture
structure is the main rejection. Thus the captured residual's spatial
correlation is not sufficient evidence for replacing that residual with new
colour noise. These clips do not qualify integration of the joint model.

The existing `chroma=off` option supplies a separate luma-only control with
source chroma retained. It recovers synthesis on 394/720 SDR and 131/720 HDR
pictures, with no one- or two-picture grain-on bursts in these windows. The
animation stays entirely source-preserved. This is not a new automatic policy:
coupled source grain could make a blanket luma-only choice inappropriate, and
equal-size source-fidelity comparisons must decide whether the control helps.

## Reproduction and integration gate

Run `sh tests/fgs/run_cpu_tests.sh` for the public GPU-free controls.
The private evidence root is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/`.
Read `work-plan.json`, `trace/counterfactual*` case records,
`trace/aom-spectrum.cpp`, `trace/aom-spectrum.jsonl`,
`pixels/selector-calibration.json`, `pixels/joint-fit-calibration.json`,
`pixels/moment-report.json` and `selective-control/analysis.json`.
Exact commands, source/patch/build hashes and failed attempts remain there.
`build-archive.json` resolves the retired private build paths to archived
binaries; original fixtures and dependent pixel evidence remain protected.

Before integration, obtain source-supported real colour-noise positives as
well as coupled-noise and persistent-texture negatives, then qualify the
quantized model and its transitions in actual encodes. Keep the source when
support is missing. Demonstrate better fidelity per byte before spending
full-title trials on this candidate or optimizing its fit cost. Do not treat
the completed mathematics as permission to relax existing eligibility.
