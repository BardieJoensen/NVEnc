# Production cost and grain-fidelity follow-up — 2026-09-08

The bounded study is complete. The guarded fresh-model retry, optional retention
ceiling and validated directional denoising change are committed to the fidelity
work branch. The deployed encoder and Tdarr flow are unchanged. The measurements
support a limited pilot with an explicit size budget, not a library-wide size
or fidelity guarantee.

This follows `FINDINGS-2026-09-08-REPEATABILITY.md`. Earlier auto-versus-auto
comparisons do not describe the cost of enabling auto in this installation:
the actual Tdarr flow uses default `retain=0`. This study compares against that
production default and records costs that remain unresolved.

## Implementation

`retain-max` is an optional ceiling on the residual blend selected by auto.
Its default is 0.5, preserving the previous behavior. A lower limit keeps the
automatic detail guards and strength-fidelity checks active. It is **not a
file-size ceiling** and does not constrain full-source fallback. Fixed numeric
retention and the existing default remain unchanged. Non-finite, malformed and
out-of-range values are rejected.

Before amplitude mismatch triggers source fallback, auto can now try a model
from the current frame's already-collected evidence. This retry goes through
the complete model solver, paired-chroma checks and synthesis-feedback guards,
then a stricter amplitude fit: 10% relative / 0.25 code8 absolute versus the
existing fallback trigger of 25% / 0.5. It is limited to configurations permitting
a one-frame estimate. It does not bypass minimum evidence, add a GPU analysis
pass, or weaken fallback/re-entry requirements. An unsuccessful retry does not
mutate the caller's model. Unsafe or unrepresentable grain still retains the
source picture without synthesis; ordinary AV1 quantization still applies.

The validated directional change replaces the directional part of local
source blending with averaging along coherent structure. Interpolated structure
tensors identify the local normal, and bilateral taps crossing it receive less
weight. The modest repeatability guard remains. Only optional bilateral auto
uses this orientation path; FFT3D, motion and default retention keep their
existing behavior. No historical pixels are blended and no output is delayed.

The motivation is measurable: the preceding local source blend retained extra
random noise on directional detail, while the synthesis model was calibrated
on flatter regions. Reducing the global retention ceiling alone did not fix
that local excess.

## Controlled cost and fidelity

Sixteen deterministic 48-frame sources provide both the noisy input and its
known clean picture. Reference outputs are pinned by hash. Each candidate is
tested at fixed QP 20 with retention ceilings 0.5, 0.1 and 0, followed by a
discrete QP search through 36 at ceiling 0.1. Every output receives a complete
synthesis-texture scan. Fixed-QP and selected-size outputs are decoded with
grain on and off for separate detail and grain measurements.

| Controlled case | Earlier full auto vs production default | Directional auto, ceiling 0.1 vs default |
| --- | ---: | ---: |
| Fine directional detail | +524.4% | +105.8% |
| Coarse-grain directional detail | +62.2% | +11.9% |
| Weak-grain directional detail | +69.5% | +2.0% |
| Static woven detail | +32.0% | +31.8% |
| PQ directional detail | +548.9% | +44.4% |
| Changing grain strength | +129.7% | +13.4% |
| Alternating, unrepresentable strength curve | +110.6% | +110.6% |

These are two-second stress cases, not forecasts for films or the library.
The changing-strength case now needs one fresh-model retry and no source
fallback, versus seven fallback frames before this work. Its post-change grain
amplitude stays within the strict test bounds. The alternating curve still
preserves the source on all 48 frames, and its decoded pixels match the prior
fallback at every retention ceiling.

Fourteen cases meet the production-default byte count within the QP search.
At that bound, measured detail transfer improves on static weave
(0.3460 to 0.4000), moving weave (0.3445 to 0.4028), coarse directional detail
(0.5213 to 0.6456), and PQ detail (0.7761 to 0.8216). Weak detail is essentially
unchanged (0.8601 to 0.8596). These projections are not percentages of overall
visual quality, and increasing QP remains a quality tradeoff.
The matched-size outputs also pass the grain-amplitude bounds: the largest
reduction relative to the production reference is about 0.8 percentage points
of source amplitude. Texture-region residual checks pass at the matched-size
settings as well, not only at fixed QP.

Fine directional detail and the alternating curve do not fit the baseline
through QP 36. At QP 36 their byte costs are still +2.82% and +33.14%. The lower
ceiling also gives up some grain retention: the coarse flat case reconstructs
about 79% of source amplitude versus about 83% at ceiling 0.5 and 77% in the
production default. The experiment does not establish perfect grain recovery.

Measuring those existing QP 36 endpoints clarifies the boundary. Fine detail
still transfers more of the known picture (0.5445 versus 0.4329), with grain
amplitude 0.9200 versus 0.9286 of source and texture-region residual ratio 0.9800.
It remains 2.82% above the exact byte target. The alternating curve reconstructs
about 96% of source grain amplitude at QP 36, but still costs 33.14% more bytes.
These fixed-QP observations do not select a production QVBR value or prove an
unconditional size/quality guarantee.

The additional `texture_residual.py` diagnostic projects known clean texture
out of each grain-on frame in band interiors. Its high-frequency residual
includes quantization error and uses code values, so it is neither a pure grain
score nor an HDR display metric. At ceiling 0.1, fine-detail residual/source
ratio falls from 1.243 in the preceding candidate to 0.992; coarse detail falls
from 1.142 to 0.975. Production references are 0.971 and 0.898. All eight texture
cases pass the new bounds. The preceding noisy candidate fails both directional
controls, demonstrating that the added check detects the measured regression.

## Real footage

The comparison uses explicit copies of production video settings, including
QVBR buckets 29/30/34, lookahead, AQ and color/HDR flags. The baseline is deployed
`e778a88b` at its default retention. The candidate uses bilateral
`retain=auto,retain-max=0.1`. Outputs are video-only scratch artifacts; audio and
subtitle handling are not retested here. The 150-second lossless Gentlemen
fixture uses software decoding; complete retained-source episodes use the
production hardware-decoding and timestamp arguments.

| Clip | Frames | Candidate bytes vs production default |
| --- | ---: | ---: |
| The Gentlemen, 33:00–35:30 | 3,600 | +0.39% |
| Taxi Driver PQ sample | 24 | +4.27% |
| Silo sample | 24 | +1.48% |
| Alien sample | 24 | +4.32% |

Every arm passes a complete synthesis-texture scan, full grain-on/off decoding,
frame-count, timeline and color-property checks. The three short default-mode
outputs remain pixel-identical to production. The Gentlemen candidate has 146
strength-fidelity fallback frames (4.06%) and eight fresh-model retries. The
known jacket passages retain the existing all-plane synthesis-off and source
error bounds. The three one-second clips do not support whole-film predictions.

Complete Gentlemen S01E01 encoding produced 1,008,063,141 bytes versus
992,177,278 in production default, **+1.60%** across 96,671 frames. Additional
strength-fidelity fallback covers 2,718 frames (2.81%), with 235 fresh-model
retries. Encoding took 1,034.56 seconds, versus about 998.80 active seconds for
the earlier baseline. This is an unpaired shared-server timing comparison.
All four complete Gentlemen decodes, synthesis scans, counts, timestamps and
color properties pass. The known jacket timestamps pass in the full episode
too.

South Park S23E01 produces 275,134,375 bytes versus 268,741,386, **+2.38%** across
32,176 frames. Additional strength-fidelity fallback covers 1,811 frames (5.63%),
with 204 fresh-model retries. The candidate takes 315.70 seconds versus 376.24
for the baseline in this sequential pair. All full grain-on/off decodes,
synthesis scans, frame counts, timestamps and color checks pass. Both complete
episodes meet the trial's 5%, 10% and 20% overhead classifications. These two
SDR titles do not establish whole-library costs or full-length HDR coverage.

An exact completed Gentlemen baseline encode from a superseded experiment is
reused to avoid redundant GPU work. Its source identity/hash, binary, arguments,
frame count, bytes and output hash must match. No validation is reused; all
decodes and scans run again. Its original elapsed time includes a recorded
53.63-second pause of our trial unit. Both raw elapsed and pause-adjusted time
are retained. Reused timings are explicitly marked unpaired; shared server
load prevents a reliable isolated speedup claim.

Full-frame checksumming proved expensive when all four episode decodes ran
serially. The harness now offers `--validation-workers 1..4` (default 1) and
`--decode-threads` (default 2). Encoding remains sequential; only independent
CPU decode/checksum passes overlap. This uses more CPU cores to reduce wall
time while preserving every frame, error, grain-on/off and timestamp check.
Six concurrent short-control decodes exactly match their prior serial pixel
and timestamp hashes; all substantive synthesis-scan fields also match.

`--reuse-encodes` extends the same strict artifact reuse to completed candidate
outputs and additionally pins the candidate binary. A changed candidate,
retention setting, source or output is refused. The restarted full comparison
reuses both completed Gentlemen encodes and repeats all validation with four
workers, under a temporary 12-core CPU quota on the 20-logical-CPU host. Partial
serial validation remains recorded as incomplete. This does not alter Tdarr's
production validator or its CPU settings.
The four Gentlemen passes and associated validation finish in 957.07 seconds
with four workers. The complete serial alternative was not timed to completion,
so this is a recorded concurrent duration rather than a measured serial speedup.

## Repeatability

Four raw-stage runs on the first 480 Gentlemen frames produced identical base
pixels and exported tables within each mode: two deployed-default runs and two
earlier-auto runs. Repeated full encodes have varied in both the production
encoder and prior candidate. This does not establish a candidate-only bug or
prove that all analysis is deterministic.

The follow-up feeds one identical retained raw base and table through four
AV1 encodes with film-grain analysis disabled. All 480 decoded frames match
within all four repeats, with grain both on and off, and all synthesis scans
pass. Actual grain application and timestamp identity are checked. The
`carrier_repeat.py` harness separates grain-off base pixels from grain-on
output. This bounded test did not reproduce the earlier full-pipeline variation;
its precise cause remains unresolved. It does not prove universal determinism
or attribute the variation to NVIDIA hardware, the driver or the analyzer.

## Storage policy and deployment

Source fallback protects the picture before AV1 compression; it does not
guarantee a small output. It also is not the only cost: retaining more fine
detail or residual grain makes the base harder to compress. This work reduces
avoidable cost but does not claim an unconditional fidelity/size guarantee.

The existing Tdarr size gates compare the final output to the input, with
retained-audio normalization and 95% / relaxed 120% thresholds. They do not
compare against an output from the old encoder. An output twice the old AV1
size could still pass when the source is much larger. None of the experiments
installs a replacement or adds a new production validation stage.

A production rollout needs an explicit accepted size policy. The trial reports
show 5%, 10% and 20% overhead classifications against measured default outputs.
An output exceeding an agreed budget should keep its input and enter review;
the encoder should not suppress the fidelity guard merely to meet that budget.
Computing the old encoder's exact byte count for every new input would require
another full encode; sampled estimates cannot be a hard relative-size promise.

## Inspiration and evidence

- [libaom noise model](https://aomedia.googlesource.com/aom/+/refs/heads/main/aom_dsp/noise_model.c)
  keeps separate latest and accumulated estimates and can adopt the latest when
  noise changes. This informed the guarded fresh-model retry; our thresholds
  and implementation are independent. Observed source blob:
  `562252b3bb2c0c82df0fc0c908e1304deedd70c6`.
- [SVT-AV1 common questions](https://raw.githubusercontent.com/AOMediaCodec/SVT-AV1/main/Docs/CommonQuestions.md)
  and its [film-grain documentation](https://raw.githubusercontent.com/AOMediaCodec/SVT-AV1/main/Docs/Appendix-Film-Grain-Synthesis.md)
  discuss detail loss and the interaction between retained and synthesized
  grain. Those tradeoffs motivated measuring the base residual separately.
- [grav1synth](https://github.com/rust-av/grav1synth) offers an aligned
  source-minus-denoised comparison workflow for independent grain estimation.
  Existing local estimator comparisons do not establish a universal winner.

NVIDIA hardware still performs AV1 compression. This fork changes analysis,
filtering, model selection and submission; it cannot import a software encoder's
internal coding search into the hardware.

Core recovery commit: `339ea31e`, binary SHA-256
`059a619d709fe8330fbe8520d47a9c9786900f602b4a90b33e72a6fb6757cc05`.
Directional prototype compiled at `ae50ed9d`, binary SHA-256
`12abca76c05f60527fbfe0b66560ed6c7892810e6c9d2e4650953115f4037220`.
The validated CUDA change is integrated as `3ff9255f`. The complete
`NVEncCore`, `NVEncC`, SDK and Meson source trees match the tested build's
source. The final CPU suite, including all nine completed-encode reuse
controls, passes. The directional GPU quick gate passes all four stages.
Production reference SHA-256
`5423d8abda1d2c248f25508c311ed4ca0eda08462e1ebc6bce95fba22e830249`.

Local reports live under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/cost-study-20260908`;
bulky encoded/decoded artifacts live under
`/tmp/downloads/fgs-cost-study-20260908`. `evidence-index.json` in the report
directory pins completed reports, controls and logs by SHA-256. It preserves
the stopped experiments and their incomplete validation status. The final full
episode report is `directional-full-parallel/report.json` under the artifact
directory. The study accepts the optional directional change into the work
branch; it does not install a new production size policy or deploy the encoder.
No downloads or trial-output library replacements are part of this study.
